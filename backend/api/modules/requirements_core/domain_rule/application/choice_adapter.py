import re
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.modules.decision_workflow.ports.ports import (
    BaseGenerationChoiceAdapter,
    CandidateContext,
    GenerationCandidate,
    build_strategy_feedback,
)
from backend.api.modules.requirements_core.domain_rule.application.rule_generation_service import (
    RuleGenerationService,
)
from backend.core.model_invariants.rule_source_links import (
    canonicalize_rule_source_links,
)
from backend.database.model import (
    ChoiceGroupModel,
    ConfirmationStatus,
    DomainRuleModel,
    RuleLinkModel,
    RuleLinkPurpose,
    RuleOrigin,
    ScenarioAcceptanceCriterionModel,
    ScenarioModel,
)


class RuleGenerationChoiceAdapter(BaseGenerationChoiceAdapter):
    """Generates candidate domain rules from requirement and scenario contexts."""

    generation_type = "rule"

    def __init__(self):
        self._service = RuleGenerationService()

    async def generate_candidate(
        self, context: CandidateContext
    ) -> GenerationCandidate:
        strategy_hint = build_strategy_feedback(context, "发现业务规则与领域约束")
        feedback = context.user_feedback or ""
        combined_feedback = f"{strategy_hint}\n{feedback}".strip()

        result, context_hash = await self._service.generate_rules(
            session=context.session,
            project_id=context.project_id,
            workspace_id=context.workspace_id,
            user_feedback=combined_feedback,
        )
        rules = result.get("rules", [])

        strat_lbl = context.strategy_label or context.strategy
        return GenerationCandidate(
            title=f"{strat_lbl} — {len(rules)} 条业务规则",
            rationale=f"按 {strat_lbl} 策略发现的业务规则与领域约束",
            payload={
                "project_id": context.project_id,
                "workspace_id": context.workspace_id,
                "rules": rules,
                "source_context_hash": context_hash,
            },
            preview={
                "rule_count": len(rules),
                "rules": [
                    {
                        "temp_id": r.get("temp_id", ""),
                        "title": r.get("title", ""),
                        "statement": r.get("statement", ""),
                        "parent_rule_ref": r.get("parent_rule_ref"),
                        "confirmation_status": r.get(
                            "confirmation_status", "ai_assumption"
                        ),
                        "source_links": r.get("source_links", []),
                    }
                    for r in rules
                ],
            },
            draft_type="rule",
            apply_mode="draft_payload",
            comparison_summary=self._make_comparison_summary(strat_lbl, rules),
            apply_behavior="merge",
            apply_behavior_description="此方案将把发现的业务规则添加到项目中",
            strategy_id=context.strategy_id,
            strategy_label=context.strategy_label,
        )

    async def apply_candidate(
        self, payload: dict[str, Any], session: AsyncSession, **kwargs
    ) -> dict[str, Any]:
        project_id = payload["project_id"]
        workspace_id = kwargs["workspace_id"]
        rules_data = payload.get("rules", [])

        models_by_temp_id: dict[str, DomainRuleModel] = {}
        for r in rules_data:
            model = DomainRuleModel(
                project_id=project_id,
                workspace_id=workspace_id,
                title=r["title"].strip(),
                statement=r["statement"].strip(),
                origin=RuleOrigin.AI_GENERATED.value,
                confirmation_status=r.get(
                    "confirmation_status", ConfirmationStatus.AI_ASSUMPTION.value
                ),
            )
            session.add(model)
            models_by_temp_id[r["temp_id"]] = model

        await session.flush()

        for r in rules_data:
            model = models_by_temp_id[r["temp_id"]]
            parent_ref = r.get("parent_rule_ref")
            if parent_ref:
                if parent_ref in models_by_temp_id:
                    model.parent_rule_id = models_by_temp_id[parent_ref].id
                else:
                    stmt = sa.select(DomainRuleModel).where(
                        DomainRuleModel.project_id == project_id,
                        DomainRuleModel.logical_uuid == parent_ref,
                    )
                    stmt = stmt.where(DomainRuleModel.workspace_id == workspace_id)
                    res = await session.execute(stmt)
                    existing_parent = res.scalar_one_or_none()
                    if existing_parent:
                        model.parent_rule_id = existing_parent.id
                    else:
                        raise ValueError(
                            f"invalid_parent_rule_ref: parent rule '{parent_ref}' not found"
                        )

            for link in canonicalize_rule_source_links(r.get("source_links", [])):
                session.add(
                    RuleLinkModel(
                        project_id=project_id,
                        workspace_id=workspace_id,
                        rule_id=model.id,
                        target_kind=link["target_kind"],
                        target_logical_uuid=link["target_logical_uuid"],
                        link_purpose=RuleLinkPurpose.SOURCE.value,
                        context_text=link.get("context_text", ""),
                    )
                )

        await session.flush()

        return {
            "project_id": project_id,
            "rule_count": len(rules_data),
            "message": "rules_created",
        }

    def is_duplicate(
        self, candidate: GenerationCandidate, existing: list[GenerationCandidate]
    ) -> bool:
        def _fingerprint_set(c: GenerationCandidate) -> frozenset[str]:
            rules = (c.payload or {}).get("rules", [])
            prints = set()
            for r in rules:
                clean_stmt = re.sub(r"\s+", " ", r.get("statement", "").strip().lower())
                targets = sorted(
                    f"{link.get('target_kind')}:{link.get('target_logical_uuid')}"
                    for link in r.get("source_links", [])
                )
                prints.add(f"{clean_stmt}::{','.join(targets)}")
            return frozenset(prints)

        candidate_fp = _fingerprint_set(candidate)
        return any(_fingerprint_set(e) == candidate_fp for e in existing)

    async def is_context_stale(
        self, choice, session: AsyncSession
    ) -> tuple[bool, str | None]:
        payload = choice.payload or {}
        rules = payload.get("rules", [])
        workspace_id = payload["workspace_id"]
        candidate_hash = payload.get("source_context_hash")
        group = await session.get(ChoiceGroupModel, choice.choice_group_id)
        project_id = group.project_id

        # The stored source hash is authoritative for candidate freshness.
        if candidate_hash and project_id:
            _input, current_hash = await self._service.load_rule_generation_context(
                session=session,
                project_id=project_id,
                workspace_id=workspace_id,
            )
            if current_hash != candidate_hash:
                return (
                    True,
                    "上游需求、场景、验收标准或领域规则已变更，此规则候选已过期",
                )

        # Source references must still resolve within the same workspace.
        for r in rules:
            for link in r.get("source_links", []):
                kind = link.get("target_kind")
                uuid_val = link.get("target_logical_uuid")
                if kind == "scenario":
                    stmt = sa.select(ScenarioModel.id).where(
                        ScenarioModel.logical_uuid == uuid_val
                    )
                    stmt = stmt.where(ScenarioModel.workspace_id == workspace_id)
                    res = await session.execute(stmt)
                    if res.scalar_one_or_none() is None:
                        return True, f"规则来源场景（UUID={uuid_val}）已被修改或删除"
                elif kind == "acceptance_criterion":
                    stmt = sa.select(ScenarioAcceptanceCriterionModel.id).where(
                        ScenarioAcceptanceCriterionModel.logical_uuid == uuid_val
                    )
                    stmt = stmt.where(
                        ScenarioAcceptanceCriterionModel.workspace_id == workspace_id
                    )
                    res = await session.execute(stmt)
                    if res.scalar_one_or_none() is None:
                        return True, f"规则来源验收标准（UUID={uuid_val}）已被修改或删除"

        return False, None

    @staticmethod
    def _make_comparison_summary(strategy: str, rules: list[dict[str, Any]]) -> str:
        descriptions = {
            "balanced": "规则发现均衡",
            "comprehensive": "全面规则覆盖",
            "minimal": "核心规则约束",
            "risk_averse": "风险防范规则",
            "workflow_first": "流程前置规则",
        }
        desc = descriptions.get(strategy, strategy)
        rule_titles = ", ".join(r.get("title", "") for r in rules[:3])
        return f"{desc}：{len(rules)} 条业务规则（{rule_titles}）"
