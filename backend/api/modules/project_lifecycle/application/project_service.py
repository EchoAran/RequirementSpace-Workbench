from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.database.model import ProjectModel, FeatureModel, ScenarioModel, BusinessObjectModel, FlowModel, ProjectMemberModel, ProjectMemberStatus
from backend.api.modules.project_lifecycle.schemas.project import (
    ProjectListItemResponse,
    ProjectDetailResponse,
)
from backend.core.detectors import (
    HowIssueDetector,
    ScopeIssueDetector,
    WhatIssueDetector,
)
from backend.core.localized_messages import localized_message
from backend.core.locale import SupportedLocale
from backend.core.prompt_resolver import get_content_locale
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
from .stage_progress import (
    business_object_definition_checks as _business_object_definition_checks,
    how_stage_checks as _how_stage_checks,
    scope_stage_checks as _scope_stage_checks,
    stage_analysis_status as _stage_analysis_status,
    stage_next_action as _stage_next_action,
    stage_status as _stage_status,
    what_stage_checks as _what_stage_checks,
)
from .stage_transition_helpers import (
    STAGES_ORDER,
    build_blocked_transition_result,
    build_stage_transition_audit,
    get_stage_transition_config,
    get_source_stage_state,
    parse_unlocked_stages,
)


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
                selectinload(ProjectModel.perception_slot),
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

            issue_count = await self._count_visible_open_issues(
                project=p,
                session=session,
            )
            status_code, status = self._derive_project_status(
                project=p,
                issue_count=issue_count,
            )

            response.append(
                ProjectListItemResponse(
                    id=p.public_id,
                    project_id=p.public_id,
                    name=p.name,
                    idea=p.user_requirements,
                    description=p.description,
                    updated_at=p.updated_at,
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

        issue_count = 0
        for stage in self._get_visible_issue_stages(project.unlocked_stages):
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

        if project.perception_slot is not None:
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



    async def get_project_detail(self, project_id: int, session: AsyncSession) -> ProjectDetailResponse:
        project = await load_project_detail_model(project_id, session)
        perception_slot = await build_visible_perception_slot(
            project,
            session,
            self._is_stage_visible,
        )
        issue_count = await self._count_visible_open_issues(
            project=project,
            session=session,
        )
        status_code, status = self._derive_project_status(
            project=project,
            issue_count=issue_count,
        )
        unresolved_gates = await load_unresolved_export_gates(
            project.id,
            session=session,
        )
        return build_project_detail_response(
            project=project,
            perception_slot=perception_slot,
            issue_count=issue_count,
            status_code=status_code,
            status=status,
            unresolved_gates=unresolved_gates,
        )

    async def delete_project(self, project_id: int, session: AsyncSession) -> dict:
        stmt = select(ProjectModel).where(ProjectModel.id == project_id)
        result = await session.execute(stmt)
        p = result.scalar_one_or_none()
        if p is None:
            raise ValueError("project_not_found")

        await session.delete(p)
        await session.commit()
        return {"project_id": p.public_id, "message": "project_deleted"}

    async def delete_perception_slot(self, project_id: int, session: AsyncSession) -> dict:
        stmt = (
            select(ProjectModel)
            .where(ProjectModel.id == project_id)
            .options(selectinload(ProjectModel.perception_slot))
        )
        result = await session.execute(stmt)
        p = result.scalar_one_or_none()
        if p is None:
            raise ValueError("project_not_found")

        if p.perception_slot is not None:
            await session.delete(p.perception_slot)
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

    async def export_project_markdown(self, project_id: int, session: AsyncSession) -> str:
        """获取项目完整建模详情并序列化输出高格式的 Markdown 需求文档报告"""
        detail = await self.get_project_detail(project_id, session)
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
    ) -> str:
        from backend.integration.skill_backed_services.spl_syntax_export_service import SplSyntaxExportService
        detail = await self.get_project_detail(project_id, session)
        service = SplSyntaxExportService()
        return await service.export(detail, content_locale=content_locale)

    async def export_project_spl_semantic(self, project_id: int, session: AsyncSession, llm_ctx) -> str:
        from backend.integration.skill_backed_services.spl_semantic_export_service import SplSemanticExportService
        detail = await self.get_project_detail(project_id, session)
        service = SplSemanticExportService()
        return await service.export(detail, llm_ctx)

    async def preview_scope_impact(self, project_id: int, feature_id: int, next_status: str, session: AsyncSession) -> dict:
        """根据变更的功能节点进行图引用深层依赖分析，评估暂缓或启用对其他建模资产的影响范围"""
        detail = await self.get_project_detail(project_id, session)

        # 1. Find all features recursively
        all_features = {f.feature_id: f for f in detail.features}
        if feature_id not in all_features:
            raise ValueError("feature_not_found")

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
    ) -> dict:
        """Compute unified What, How, and Scope stage progress."""
        from .stage_progress import get_stage_progress

        return await get_stage_progress(
            project_id,
            public_project_id,
            session,
        )

    async def stage_transition(
        self,
        project_id: int,
        action: str,
        force: bool,
        session: AsyncSession,
        operator_id: int | None = None,
    ) -> dict:
        from backend.api.modules.diagnosis_quality.public import FindingService
        
        stmt = select(ProjectModel).where(ProjectModel.id == project_id)
        result = await session.execute(stmt)
        p = result.scalar_one_or_none()
        if p is None:
            raise ValueError("project_not_found")

        config = get_stage_transition_config(action, p.public_id)
        unlocked_set, ordered_unlocked = parse_unlocked_stages(
            p.unlocked_stages
        )

        # Force may skip findings, but never incomplete mandatory checks.
        stage_progress = await self.get_stage_progress(project_id, p.public_id, session)
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
        p.unlocked_stages = ",".join(ordered_unlocked)
        
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
