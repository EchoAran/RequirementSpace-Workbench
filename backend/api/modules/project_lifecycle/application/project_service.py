from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.api.modules.project_lifecycle.schemas.project import (
    FindingsByView,
    ProjectDetailResponse,
    ProjectListItemResponse,
    WorkspaceHydrationResponse,
)
from backend.core.detectors import (
    HowIssueDetector,
    ScopeIssueDetector,
    WhatIssueDetector,
)
from backend.core.locale import SupportedLocale
from backend.core.localized_messages import localized_message
from backend.core.prompt_resolver import get_content_locale
from backend.database.model import (
    BusinessObjectModel,
    FeatureModel,
    FlowModel,
    ProjectMemberModel,
    ProjectMemberStatus,
    ProjectModel,
    ScenarioModel,
)

from .project_detail import (
    build_project_detail_response,
    build_visible_perception_slot,
    load_project_detail_model,
    load_unresolved_export_gates,
)
from .project_markdown_sections import (
    build_feature_markdown_lines,
    build_how_markdown_lines,
)
from .stage_transition_helpers import (
    STAGES_ORDER,
    build_blocked_transition_result,
    build_stage_transition_audit,
    get_source_stage_state,
    get_stage_transition_config,
    parse_unlocked_stages,
)


async def _safe_resolve_branch_context(session, project_id: int, branch_ref: str | None = None, user_id: int | None = None):
    from backend.api.modules.version_control.public import resolve_branch_context
    if hasattr(session, "run_sync") and callable(session.run_sync):
        res = session.run_sync(
            lambda s: resolve_branch_context(s, project_id, branch_ref, user_id)
        )
        if hasattr(res, "__await__"):
            res = await res
        if isinstance(res, (tuple, list)) and len(res) == 3:
            return res[0], res[1], res[2]
    return None, None, {}


class ProjectService:
    async def list_projects(self, user_id: int, session: AsyncSession) -> list[ProjectListItemResponse]:
        from sqlalchemy import func

        # Subquery to calculate member count for each project
        member_count_subquery = (
            select(func.count(ProjectMemberModel.id))
            .where(
                ProjectMemberModel.project_id == ProjectModel.id,
                ProjectMemberModel.status == ProjectMemberStatus.ACTIVE.value
            )
            .correlate(ProjectModel)
            .scalar_subquery()
        )

        stmt = (
            select(ProjectModel, ProjectMemberModel.role, member_count_subquery)
            .join(ProjectMemberModel, ProjectModel.id == ProjectMemberModel.project_id)
            .where(
                ProjectMemberModel.user_id == user_id,
                ProjectMemberModel.status == ProjectMemberStatus.ACTIVE.value
            )
            .options(
                selectinload(ProjectModel.perception_slots),
                selectinload(ProjectModel.actors),
                selectinload(ProjectModel.features).selectinload(FeatureModel.child_relations),
                selectinload(ProjectModel.features).selectinload(FeatureModel.scope),
                selectinload(ProjectModel.scenarios).selectinload(ScenarioModel.acceptance_criteria),
                selectinload(ProjectModel.business_objects).selectinload(BusinessObjectModel.attributes),
                selectinload(ProjectModel.flows).selectinload(FlowModel.steps),
            )
            .order_by(ProjectModel.updated_at.desc())
        )
        result = await session.execute(stmt)
        rows = result.all()

        response = []
        for p, role, member_count in rows:
            # 1. Sum up all nodes inside this project space to get node_count
            node_count = (
                len(p.actors)
                + len(p.features)
                + len(p.scenarios)
                + sum(len(s.acceptance_criteria) for s in p.scenarios)
                + len(p.business_objects)
                + sum(len(bo.attributes) for bo in p.business_objects)
                + len(p.flows)
                + sum(len(fl.steps) for fl in p.flows)
            )

            # Compute effective updated_at from project and child entities
            all_timestamps = [p.updated_at]
            for entity in (
                p.actors
                + p.features
                + p.scenarios
                + p.business_objects
                + p.flows
                + (p.perception_slots or [])
            ):
                if getattr(entity, "updated_at", None):
                    all_timestamps.append(entity.updated_at)
            effective_updated_at = max(all_timestamps) if all_timestamps else p.updated_at

            issue_count = await self._count_visible_open_issues(
                project=p,
                session=session,
            )
            status_code, status = self._derive_project_status(
                project=p,
                issue_count=issue_count,
                perception_slot=None,
            )

            response.append(
                ProjectListItemResponse(
                    id=p.public_id,
                    project_id=p.public_id,
                    name=p.name,
                    idea=p.user_requirements,
                    description=p.description,
                    updated_at=effective_updated_at,
                    status_code=status_code,
                    status=status,
                    issue_count=issue_count,
                    node_count=node_count,
                    membership_role=role,
                    owner_user_id=p.owner_user_id,
                    member_count=member_count,
                )
            )
        return response

    async def _count_visible_open_issues(
        self,
        project: ProjectModel,
        session: AsyncSession,
    ) -> int:
        from backend.api.modules.diagnosis_quality.public import FindingService
        finding_service = FindingService()

        visible_stages = self._get_visible_issue_stages(
            project.unlocked_stages
        )
        issue_count = 0
        for stage in visible_stages:
            findings = await finding_service.list_findings(
                project_id=project.id,
                stage=stage,
                view="issues",
                action=None,
                session=session,
            )
            issue_count += len(findings)

        return issue_count

    def _derive_project_status(
        self,
        project: ProjectModel,
        issue_count: int,
        perception_slot=None,
    ) -> tuple[str, str]:
        features = project.features or []
        leaf_features = [
            feature
            for feature in features
            if not (feature.child_relations or [])
        ]
        has_any_content = any(
            (
                project.actors,
                features,
                project.scenarios,
                project.business_objects,
                project.flows,
            )
        )
        has_scope_pending = bool(leaf_features) and any(
            feature.scope is None
            or not (feature.scope.status or "").strip()
            for feature in leaf_features
        )
        is_scope_ready = bool(leaf_features) and all(
            feature.scope is not None and (feature.scope.status or "").strip()
            for feature in leaf_features
        )
        has_modeling_backbone = bool(project.actors) and bool(features) and bool(project.flows)

        if not has_any_content:
            return "not_started", "未开始"

        if perception_slot is not None:
            return "needs_attention", "待处理卡点"

        if issue_count > 0:
            return "has_issues", "存在待处理问题"

        if has_modeling_backbone and has_scope_pending:
            return "scope_pending", "范围待确认"

        if has_modeling_backbone and (is_scope_ready or not leaf_features):
            return "converged", "已基本收敛"

        return "in_progress", "建模中"

    def _get_visible_issue_stages(self, unlocked_stages: str) -> list[str]:
        visible_stages: list[str] = []
        for stage in ("what", "how", "scope"):
            if self._is_stage_visible(stage, unlocked_stages):
                visible_stages.append(stage)
        return visible_stages

    @staticmethod
    def _get_issue_detectors():
        return {
            "what": WhatIssueDetector(),
            "how": HowIssueDetector(),
            "scope": ScopeIssueDetector(),
        }

    async def get_project_detail(
        self,
        project_id: int,
        session: AsyncSession,
        branch_ref: str | None = None,
        user_id: int | None = None,
    ) -> ProjectDetailResponse:
        from .stage_progress.loader import _load_project
        project = await _load_project(project_id, session)

        _branch_obj, ws_obj, _perms = await _safe_resolve_branch_context(
            session, project_id, branch_ref, user_id
        )
        ws_id = ws_obj.id if ws_obj else None
        if ws_id is not None:
            project = await load_project_detail_model(project_id, session, workspace_id=ws_id)
        else:
            project = await load_project_detail_model(project_id, session, workspace_id=None)

        effective_reqs = project.user_requirements
        effective_kano = project.kano_status
        effective_stages = project.unlocked_stages

        if ws_obj is not None:
            effective_reqs = ws_obj.user_requirements if ws_obj.user_requirements is not None else ""
            effective_kano = ws_obj.kano_status or "missing"
            effective_stages = ws_obj.unlocked_stages if ws_obj.unlocked_stages is not None else ""

        perception_slot = await build_visible_perception_slot(
            project,
            session,
            self._is_stage_visible,
            workspace_id=ws_obj.id if ws_obj else None,
            unlocked_stages=effective_stages,
        )
        issue_count = await self._count_visible_open_issues(
            project=project,
            session=session,
        )
        status_code, status = self._derive_project_status(
            project=project,
            issue_count=issue_count,
            perception_slot=perception_slot,
        )
        unresolved_gates = await load_unresolved_export_gates(
            project.id,
            session=session,
        )
        detail_response = build_project_detail_response(
            project=project,
            perception_slot=perception_slot,
            issue_count=issue_count,
            status_code=status_code,
            status=status,
            unresolved_gates=unresolved_gates,
        )
        detail_response.user_requirements = effective_reqs
        detail_response.kano_status = effective_kano
        # ProjectDetailResponse.unlocked_stages 契约是 list[str]，而数据库以逗号分隔字符串存储；
        # 这里在边界统一转换为有序列表，避免旧数据/工作区字符串直接序列化触发 Pydantic 警告。
        if isinstance(effective_stages, list):
            detail_response.unlocked_stages = list(effective_stages)
        else:
            _, ordered_stages = parse_unlocked_stages(effective_stages or "")
            detail_response.unlocked_stages = ordered_stages
        return detail_response

    async def delete_project(self, project_id: int, session: AsyncSession) -> dict:
        stmt = select(ProjectModel).where(ProjectModel.id == project_id)
        result = await session.execute(stmt)
        p = result.scalar_one_or_none()
        if p is None:
            raise ValueError("project_not_found")

        await session.delete(p)
        await session.commit()
        return {"project_id": p.public_id, "message": "project_deleted"}

    async def delete_perception_slot(
        self,
        project_id: int,
        session: AsyncSession,
        workspace_id: int | None = None,
    ) -> dict:
        from backend.database.model import PerceptionSlotModel

        stmt = select(ProjectModel).where(ProjectModel.id == project_id)
        result = await session.execute(stmt)
        p = result.scalar_one_or_none()
        if p is None:
            raise ValueError("project_not_found")

        slot_stmt = select(PerceptionSlotModel).where(PerceptionSlotModel.project_id == project_id)
        if workspace_id is not None:
            slot_stmt = slot_stmt.where(PerceptionSlotModel.workspace_id == workspace_id)
        else:
            slot_stmt = slot_stmt.where(PerceptionSlotModel.workspace_id.is_(None))

        slots = (await session.execute(slot_stmt)).scalars().all()
        for slot in slots:
            await session.delete(slot)
        await session.commit()

        return {"project_id": p.public_id, "message": "perception_slot_deleted"}

    @staticmethod
    def _is_stage_visible(
        stage: str | None,
        unlocked_stages: str,
    ) -> bool:
        if stage is None:
            return True

        unlocked = {
            item.strip()
            for item in (unlocked_stages or "").split(",")
            if item.strip()
        }

        if stage == "what":
            return True
        if stage == "how":
            return "what" in unlocked
        if stage == "scope":
            return "how" in unlocked
        if stage == "preview":
            return "scope" in unlocked

        return False

    async def update_project(self, project_id: int, name: str, description: str, session: AsyncSession) -> dict:
        stmt = select(ProjectModel).where(ProjectModel.id == project_id)
        result = await session.execute(stmt)
        p = result.scalar_one_or_none()
        if p is None:
            raise ValueError("project_not_found")

        p.name = name.strip()
        p.description = description.strip()
        await session.commit()
        return {
            "project_id": p.public_id,
            "name": p.name,
            "description": p.description,
            "message": "project_updated"
        }

    async def export_project_markdown(
        self,
        project_id: int,
        session: AsyncSession,
        branch_ref: str | None = None,
        user_id: int | None = None,
    ) -> str:
        """获取项目完整建模详情并序列化输出高格式的 Markdown 需求文档报告"""
        detail = await self.get_project_detail(
            project_id=project_id,
            session=session,
            branch_ref=branch_ref,
            user_id=user_id,
        )
        tr = localized_message
        locale = get_content_locale()

        # 1. Core Info
        md = []
        md.append(f"# {tr('markdown_title')} - {detail.project_name}")
        md.append("")
        md.append(f"## 1. {tr('markdown_project_info')}")
        md.append(f"- **{tr('markdown_project_name')}**: {detail.project_name}")
        md.append(f"- **{tr('markdown_project_description')}**: {detail.project_description}")
        md.append("")
        md.append("---")
        md.append("")

        # 2. Raw User Requirements
        md.append(f"## 2. {tr('markdown_requirements')}")
        md.append(detail.user_requirements or tr("markdown_no_requirements"))
        md.append("")
        md.append("---")
        md.append("")

        # 3. Actors
        md.append(f"## 3. {tr('markdown_actors')}")
        if not detail.actors:
            md.append(tr("markdown_no_actors"))
        else:
            for a in detail.actors:
                md.append(f"- **{a.actor_name}**: {a.actor_description}")
        md.append("")
        md.append("---")
        md.append("")

        md.extend(build_feature_markdown_lines(detail, tr))

        md.extend(build_how_markdown_lines(detail, tr))
        # Fetch gate findings for export action
        from backend.api.modules.diagnosis_quality.public import FindingService
        finding_service = FindingService()
        gate_findings = await finding_service.list_findings(
            project_id=project_id,
            stage="all",
            view="gate",
            action="export",
            session=session,
        )
        if gate_findings:
            md.append(f"## {tr('markdown_gates')}")
            md.append(tr("markdown_gates_warning"))
            for gf in gate_findings:
                if locale == "en-US":
                    md.append(
                        f"- **[{gf.code}]**: {tr('markdown_unresolved_gate')}"
                    )
                else:
                    md.append(f"- **[{gf.title}]**: {gf.description}")
            md.append("")

        return "\n".join(md)

    async def export_project_spl_syntax(
        self,
        project_id: int,
        session: AsyncSession,
        content_locale: SupportedLocale,
        branch_ref: str | None = None,
        user_id: int | None = None,
    ) -> str:
        from backend.integration.skill_backed_services.spl_syntax_export_service import (
            SplSyntaxExportService,
        )
        detail = await self.get_project_detail(
            project_id=project_id,
            session=session,
            branch_ref=branch_ref,
            user_id=user_id,
        )
        service = SplSyntaxExportService()
        return await service.export(detail, content_locale=content_locale)

    async def export_project_spl_semantic(
        self,
        project_id: int,
        session: AsyncSession,
        llm_ctx,
        branch_ref: str | None = None,
        user_id: int | None = None,
    ) -> str:
        from backend.integration.skill_backed_services.spl_semantic_export_service import (
            SplSemanticExportService,
        )
        detail = await self.get_project_detail(
            project_id=project_id,
            session=session,
            branch_ref=branch_ref,
            user_id=user_id,
        )
        service = SplSemanticExportService()
        return await service.export(detail, llm_ctx)

    async def preview_scope_impact(
        self,
        project_id: int,
        feature_id: int,
        next_status: str,
        session: AsyncSession,
        branch_ref: str | None = None,
        user_id: int | None = None,
    ) -> dict:
        """根据变更的功能节点进行图引用深层依赖分析，评估暂缓或启用对其他建模资产的影响范围"""
        detail = await self.get_project_detail(project_id, session, branch_ref=branch_ref, user_id=user_id)

        # 1. Find all features recursively
        all_features = {f.feature_id: f for f in detail.features}
        if feature_id not in all_features:
            feat_res = await session.execute(
                select(FeatureModel).where(
                    FeatureModel.project_id == project_id,
                    FeatureModel.id == feature_id,
                )
            )
            feat_row = feat_res.scalar_one_or_none()
            if feat_row is None:
                raise ValueError("feature_not_found")
            return {
                "affected_scenarios": [],
                "affected_flows": [],
                "affected_business_objects": [],
                "summary": f"功能点 '{feat_row.name}' 影响范围评估完成（无级联依赖）",
            }

        affected_feature_ids = set()
        def collect_features(f_id):
            affected_feature_ids.add(f_id)
            feat = all_features[f_id]
            for child_id in feat.children_ids:
                if child_id in all_features:
                    collect_features(child_id)

        collect_features(feature_id)

        # 2. Scenarios directly under these features
        affected_scenarios = []
        for f_id in affected_feature_ids:
            feat = all_features[f_id]
            for sc in feat.scenarios:
                affected_scenarios.append(f"场景: {sc.scenario_name} (隶属功能: {feat.feature_name})")

        # 3. Flows that link to these features
        affected_flows = []
        affected_flow_ids = set()
        for fl in detail.flows:
            has_ref = False
            for f_id in fl.feature_ids:
                if f_id in affected_feature_ids:
                    has_ref = True
                    break
            if has_ref:
                affected_flows.append(f"泳道流: {fl.flow_name}")
                affected_flow_ids.add(fl.flow_id)

        # 4. Business Objects referenced in affected flows
        affected_business_objects = []
        affected_bo_ids = set()
        for fl_id in affected_flow_ids:
            fl = next((f for f in detail.flows if f.flow_id == fl_id), None)
            if fl:
                for st in fl.flow_steps:
                    for bo_id in st.input_business_object_ids + st.output_business_object_ids:
                        if bo_id not in affected_bo_ids:
                            affected_bo_ids.add(bo_id)
                            bo = next((b for b in detail.business_objects if b.business_object_id == bo_id), None)
                            if bo:
                                affected_business_objects.append(f"实体: {bo.business_object_name}")

        return {
            "affected_scenarios": [
                scenario.scenario_name
                for feature in detail.features
                if feature.feature_id in affected_feature_ids
                for scenario in feature.scenarios
            ],
            "affected_flows": [
                flow.flow_name for flow in detail.flows if flow.flow_id in affected_flow_ids
            ],
            "affected_business_objects": [
                item.business_object_name
                for item in detail.business_objects
                if item.business_object_id in affected_bo_ids
            ],
            "summary": "scope_impact_summary",
        }

    async def get_stage_progress(
        self,
        project_id: int,
        public_project_id: str,
        session: AsyncSession,
        branch_ref: str | None = None,
        user_id: int | None = None,
    ) -> dict:
        """Compute unified What, How, and Scope stage progress."""
        from .stage_progress import get_stage_progress
        _branch_obj, ws_obj, _perms = await _safe_resolve_branch_context(
            session, project_id, branch_ref, user_id
        )
        ws_id = ws_obj.id if ws_obj else None

        return await get_stage_progress(
            project_id,
            public_project_id,
            session,
            workspace_id=ws_id,
        )

    async def stage_transition(
        self,
        project_id: int,
        action: str,
        force: bool,
        session: AsyncSession,
        operator_id: int | None = None,
        branch_ref: str | None = None,
    ) -> dict:
        from backend.api.modules.diagnosis_quality.public import FindingService

        stmt = select(ProjectModel).where(ProjectModel.id == project_id)
        result = await session.execute(stmt)
        p = result.scalar_one_or_none()
        if p is None:
            raise ValueError("project_not_found")

        _branch_obj, ws_obj, perms = await _safe_resolve_branch_context(
            session, project_id, branch_ref, operator_id
        )
        if perms and not perms.get("can_write", True):
            raise PermissionError("protected_branch_cannot_write")

        config = get_stage_transition_config(action, p.public_id)
        effective_stages_str = ws_obj.unlocked_stages if ws_obj is not None else p.unlocked_stages
        unlocked_set, ordered_unlocked = parse_unlocked_stages(
            effective_stages_str
        )

        # Force may skip findings, but never incomplete mandatory checks.
        stage_progress = await self.get_stage_progress(
            project_id,
            p.public_id,
            session,
            branch_ref=branch_ref,
            user_id=operator_id,
        )
        source_status, content_complete = get_source_stage_state(
            stage_progress,
            config.gate_stage,
        )
        already_unlocked = config.unlock_stage in unlocked_set

        # 3. Check gate findings
        finding_service = FindingService()
        findings = await finding_service.list_findings(
            project_id=project_id,
            stage=config.gate_stage,
            view="gate",
            action=config.gate_action,
            session=session,
            workspace_id=ws_obj.id if ws_obj else None,
        )

        if not already_unlocked:
            if source_status in ("locked", "analysis_running") or not content_complete:
                return build_blocked_transition_result(
                    action,
                    ordered_unlocked,
                    findings,
                )

        # 4. Handle force and findings
        if findings and not force:
            return build_blocked_transition_result(
                action,
                ordered_unlocked,
                findings,
            )

        # 5. Perform stage unlock
        unlocked_set.add(config.unlock_stage)
        ordered_unlocked = [s for s in STAGES_ORDER if s in unlocked_set]
        new_unlocked_str = ",".join(ordered_unlocked)
        if ws_obj:
            ws_obj.unlocked_stages = new_unlocked_str
        else:
            p.unlocked_stages = new_unlocked_str

        audit_log = build_stage_transition_audit(
            project_id=project_id,
            public_project_id=p.public_id,
            action=action,
            config=config,
            force=force,
            findings=findings,
            operator_id=operator_id,
        )
        session.add(audit_log)
        await session.commit()

        return {
            "status": "unlocked",
            "action": action,
            "unlocked_stage": config.unlock_stage,
            "target_route": config.target_route,
            "unlocked_stages": ordered_unlocked,
            "blocking_findings": [],
        }

    async def get_workspace_hydration(
        self,
        project_id: int,
        session: AsyncSession,
        branch_ref: str | None = None,
        user_id: int | None = None,
        background_tasks = None,
    ) -> WorkspaceHydrationResponse:
        """Unified aggregation for workspace entry, reducing 7 waterfall HTTP requests to 1 roundtrip."""
        from backend.api.modules.decision_workflow.public import ChoiceService
        from backend.api.modules.diagnosis_quality.public import FindingResponse, FindingService

        detail = await self.get_project_detail(
            project_id=project_id,
            session=session,
            branch_ref=branch_ref,
            user_id=user_id,
        )

        stage_progress_dict = await self.get_stage_progress(
            project_id=project_id,
            public_project_id=detail.project_id,
            session=session,
            branch_ref=branch_ref,
            user_id=user_id,
        )

        _branch_obj, ws_obj, _perms = await _safe_resolve_branch_context(
            session, project_id, branch_ref, user_id
        )
        ws_id = ws_obj.id if ws_obj else None

        finding_service = FindingService()
        findings_dict = await finding_service.list_all_findings_views(
            project_id=project_id,
            session=session,
            stage="all",
            background_tasks=background_tasks,
            public_project_id=detail.project_id,
            workspace_id=ws_id,
        )

        choice_service = ChoiceService()
        raw_choices = await choice_service.list_choice_groups(
            project_id=project_id,
            session=session,
            status="open",
            workspace_id=ws_id,
        )
        choice_groups = [
            cg.model_dump() if hasattr(cg, "model_dump") else cg
            for cg in raw_choices
        ]

        issues_res = [FindingResponse.model_validate(f) for f in findings_dict.get("issues", [])]
        next_res = [FindingResponse.model_validate(f) for f in findings_dict.get("next_action", [])]
        gate_res = [FindingResponse.model_validate(f) for f in findings_dict.get("gate", [])]
        health_res = [FindingResponse.model_validate(f) for f in findings_dict.get("health", [])]

        all_findings = issues_res + next_res + gate_res + health_res

        return WorkspaceHydrationResponse(
            project_id=detail.project_id,
            project_detail=detail,
            backend_findings=all_findings,
            findings_by_view=FindingsByView(
                issues=issues_res,
                next_action=next_res,
                gate=gate_res,
                health=health_res,
            ),
            choice_groups=choice_groups,
            stage_progress=stage_progress_dict,
        )
