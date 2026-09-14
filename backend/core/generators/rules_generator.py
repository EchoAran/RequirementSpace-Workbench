import json
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from backend.core.generators.base_generator import BaseGenerator, GenerateInput
from backend.core.generators.prompts import rules_generate_prompt
from backend.core.model_invariants.rule_source_links import (
    canonicalize_rule_source_links,
)
from backend.schemas import ActorNode, FeatureNode


class RuleSourceLinkSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_kind: Literal["scenario", "acceptance_criterion", "knowledge"]
    target_logical_uuid: str = Field(min_length=1)
    context_text: str | None = None


class RuleSourceReferenceSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_kind: Literal["scenario", "acceptance_criterion", "knowledge"]
    target_ref: str = Field(min_length=1)
    context_text: str | None = None


class GeneratedRuleItemSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    temp_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    parent_rule_ref: str | None = None
    confirmation_status: Literal["ai_assumption", "needs_confirmation"] = "ai_assumption"
    source_links: list[RuleSourceLinkSchema] = Field(min_length=1)


class RulesGeneratorOutputSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rules: list[GeneratedRuleItemSchema]


class GeneratedRuleProposalSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    temp_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    parent_rule_ref: str | None = None
    confirmation_status: Literal["ai_assumption", "needs_confirmation"] = "ai_assumption"
    source_links: list[RuleSourceReferenceSchema] = Field(min_length=1)


class RulesGeneratorProposalSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rules: list[GeneratedRuleProposalSchema]


@dataclass(frozen=True)
class RuleSourceCatalog:
    scenarios: list[dict[str, Any]]
    acceptance_criteria: list[dict[str, Any]]
    knowledge_fragments: list[dict[str, Any]]
    target_ids: dict[tuple[str, str], str]


@dataclass
class RulesGeneratorInput(GenerateInput):
    user_requirements: str
    actors: list[ActorNode] = field(default_factory=list)
    features: list[FeatureNode] = field(default_factory=list)
    scenarios: list[dict[str, Any]] = field(default_factory=list)
    acceptance_criteria: list[dict[str, Any]] = field(default_factory=list)
    existing_rules: list[dict[str, Any]] = field(default_factory=list)
    knowledge_fragments: list[dict[str, Any]] = field(default_factory=list)
    user_feedback: str | None = None


class RulesGenerator(BaseGenerator[RulesGeneratorInput]):
    """Extracts candidate domain rules from requirement specifications and scenario context."""

    async def generate(self, input_data: RulesGeneratorInput) -> dict[str, Any]:
        source_catalog = self._build_source_catalog(input_data)
        prompt_text = self._build_prompt(input_data, source_catalog)
        try:
            return await self._generate_once(
                input_data,
                source_catalog,
                prompt_text,
                input_data.user_feedback or "",
            )
        except ValueError as error:
            if not str(error).startswith("invalid_source_reference:"):
                raise

            allowed_refs = ", ".join(
                target_ref for _, target_ref in source_catalog.target_ids
            )
            correction = (
                f"The previous response was rejected: {error}. "
                "Return the complete JSON object again. Copy every target_ref "
                f"exactly from this list: {allowed_refs}. Do not output UUIDs, "
                "placeholders, or modified references."
            )
            return await self._generate_once(
                input_data,
                source_catalog,
                prompt_text,
                correction,
            )

    async def _generate_once(
        self,
        input_data: RulesGeneratorInput,
        source_catalog: RuleSourceCatalog,
        prompt_text: str,
        query: str,
    ) -> dict[str, Any]:
        response = await self._llm_handler.call_llm(
            prompt=prompt_text,
            query=query,
            print_log=False,
            raise_on_failure=True,
            protected_inputs=(
                *self._protected_inputs(input_data),
                *(target_ref for _, target_ref in source_catalog.target_ids),
            ),
        )
        result = self._loads_llm_json(response)
        if not isinstance(result, dict):
            raise ValueError("invalid_llm_response: expected root JSON object")

        proposed_rules = result.get("rules")
        if not isinstance(proposed_rules, list):
            raise ValueError("invalid_llm_response: expected 'rules' array")

        rules = self._resolve_source_references(proposed_rules, source_catalog)
        self._validate_rules(rules, input_data)
        return {"rules": rules}

    @staticmethod
    def _loads_llm_json(response: str | None) -> Any:
        if response is None:
            raise ValueError("empty_llm_response")
        return json.loads(response)

    def _build_prompt(
        self,
        input_data: RulesGeneratorInput,
        source_catalog: RuleSourceCatalog | None = None,
    ) -> str:
        source_catalog = source_catalog or self._build_source_catalog(input_data)
        actors_payload = [
            {
                "actor_id": a.actorId,
                "actor_name": a.actorName,
                "actor_description": a.actorDescription,
            }
            for a in input_data.actors
        ]
        leaf_features_payload = [
            {
                "feature_id": f.featureId,
                "feature_name": f.featureName,
                "feature_description": f.featureDescription,
            }
            for f in input_data.features
            if not f.childrenIds
        ]
        existing_rules_payload = [
            {
                "rule_id": r.get("id"),
                "logical_uuid": r.get("logical_uuid"),
                "title": r.get("title"),
                "statement": r.get("statement"),
            }
            for r in input_data.existing_rules
        ]

        return (
            rules_generate_prompt.replace(
                "{{user_requirements}}", input_data.user_requirements or ""
            )
            .replace(
                "{{actors}}",
                json.dumps({"actors": actors_payload}, ensure_ascii=False, indent=2),
            )
            .replace(
                "{{features}}",
                json.dumps(
                    {"features": leaf_features_payload}, ensure_ascii=False, indent=2
                ),
            )
            .replace(
                "{{scenarios}}",
                json.dumps(
                    {"scenarios": source_catalog.scenarios},
                    ensure_ascii=False,
                    indent=2,
                ),
            )
            .replace(
                "{{acceptance_criteria}}",
                json.dumps(
                    {"acceptance_criteria": source_catalog.acceptance_criteria},
                    ensure_ascii=False,
                    indent=2,
                ),
            )
            .replace(
                "{{existing_rules}}",
                json.dumps(
                    {"existing_rules": existing_rules_payload},
                    ensure_ascii=False,
                    indent=2,
                ),
            )
            .replace(
                "{{knowledge_fragments}}",
                json.dumps(
                    {"knowledge_fragments": source_catalog.knowledge_fragments},
                    ensure_ascii=False,
                    indent=2,
                ),
            )
        )

    @staticmethod
    def _build_source_catalog(input_data: RulesGeneratorInput) -> RuleSourceCatalog:
        target_ids: dict[tuple[str, str], str] = {}
        scenario_refs_by_id: dict[Any, str] = {}
        scenarios: list[dict[str, Any]] = []
        for index, scenario in enumerate(input_data.scenarios, start=1):
            target_id = scenario.get("logical_uuid")
            if not target_id:
                continue
            source_ref = f"SCN-{index}"
            target_ids[("scenario", source_ref)] = str(target_id)
            scenario_refs_by_id[scenario.get("id")] = source_ref
            scenarios.append(
                {
                    "source_ref": source_ref,
                    "scenario_name": scenario.get("name"),
                    "scenario_content": scenario.get("content"),
                }
            )

        acceptance_criteria: list[dict[str, Any]] = []
        for index, criterion in enumerate(
            input_data.acceptance_criteria,
            start=1,
        ):
            target_id = criterion.get("logical_uuid")
            if not target_id:
                continue
            source_ref = f"AC-{index}"
            target_ids[("acceptance_criterion", source_ref)] = str(target_id)
            acceptance_criteria.append(
                {
                    "source_ref": source_ref,
                    "scenario_ref": scenario_refs_by_id.get(
                        criterion.get("scenario_id")
                    ),
                    "content": criterion.get("content"),
                }
            )

        knowledge_fragments: list[dict[str, Any]] = []
        for index, fragment in enumerate(input_data.knowledge_fragments, start=1):
            target_id = fragment.get("fragment_id")
            if not target_id:
                continue
            source_ref = f"KNOW-{index}"
            target_ids[("knowledge", source_ref)] = str(target_id)
            knowledge_fragments.append(
                {
                    "source_ref": source_ref,
                    "document_name": fragment.get("document_name"),
                    "content": fragment.get("content"),
                }
            )

        return RuleSourceCatalog(
            scenarios=scenarios,
            acceptance_criteria=acceptance_criteria,
            knowledge_fragments=knowledge_fragments,
            target_ids=target_ids,
        )

    @staticmethod
    def _resolve_source_references(
        rules: list[Any],
        source_catalog: RuleSourceCatalog,
    ) -> list[dict[str, Any]]:
        try:
            validated = RulesGeneratorProposalSchema(rules=rules)
        except ValidationError as exc:
            raise ValueError(f"rule_schema_validation_failed: {exc}") from exc

        resolved_rules: list[dict[str, Any]] = []
        for rule in validated.rules:
            resolved_rule = rule.model_dump(exclude={"source_links"})
            resolved_links: list[dict[str, Any]] = []
            for link in rule.source_links:
                target_id = source_catalog.target_ids.get(
                    (link.target_kind, link.target_ref)
                )
                if target_id is None:
                    raise ValueError(
                        "invalid_source_reference: "
                        f"'{link.target_ref}' not found for {link.target_kind}"
                    )
                resolved_links.append(
                    {
                        "target_kind": link.target_kind,
                        "target_logical_uuid": target_id,
                        "context_text": link.context_text,
                    }
                )
            resolved_rule["source_links"] = canonicalize_rule_source_links(resolved_links)
            resolved_rules.append(resolved_rule)
        return resolved_rules

    def _validate_rules(
        self,
        rules: list[Any],
        input_data: RulesGeneratorInput,
    ) -> None:
        try:
            validated = RulesGeneratorOutputSchema(rules=rules)
        except ValidationError as exc:
            raise ValueError(f"rule_schema_validation_failed: {exc}") from exc

        valid_scenario_uuids = {
            str(s["logical_uuid"])
            for s in input_data.scenarios
            if s.get("logical_uuid")
        }
        valid_ac_uuids = {
            str(ac["logical_uuid"])
            for ac in input_data.acceptance_criteria
            if ac.get("logical_uuid")
        }
        valid_knowledge_ids = {
            str(k["fragment_id"])
            for k in input_data.knowledge_fragments
            if k.get("fragment_id")
        }

        existing_rule_uuids = {
            str(r["logical_uuid"])
            for r in input_data.existing_rules
            if r.get("logical_uuid")
        }
        generated_temp_ids = {r.temp_id for r in validated.rules}

        for rule in validated.rules:
            if not rule.title.strip():
                raise ValueError("empty_rule_title")
            if not rule.statement.strip():
                raise ValueError("empty_rule_statement")

            parent_ref = rule.parent_rule_ref
            if parent_ref is not None:
                if (
                    parent_ref not in generated_temp_ids
                    and parent_ref not in existing_rule_uuids
                ):
                    raise ValueError(
                        f"invalid_parent_rule_ref: referenced parent '{parent_ref}' does not exist"
                    )

            for link in rule.source_links:
                kind = link.target_kind
                uuid_val = link.target_logical_uuid
                if kind == "scenario":
                    if uuid_val not in valid_scenario_uuids:
                        raise ValueError(
                            f"invalid_source_link_target: '{uuid_val}' not found in scenario context"
                        )
                elif kind == "acceptance_criterion":
                    if uuid_val not in valid_ac_uuids:
                        raise ValueError(
                            f"invalid_source_link_target: '{uuid_val}' not found in acceptance criterion context"
                        )
                elif kind == "knowledge":
                    if uuid_val not in valid_knowledge_ids:
                        raise ValueError(
                            f"invalid_source_link_target: '{uuid_val}' not found in knowledge context"
                        )
                else:
                    raise ValueError(f"invalid_source_link_kind: {kind}")
