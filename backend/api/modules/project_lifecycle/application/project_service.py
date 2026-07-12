from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, defaultload

from backend.database.model import ProjectModel, FeatureModel, ScenarioModel, BusinessObjectModel, FlowModel, FlowStepModel, PerceptionJobModel, ProjectMemberModel, ProjectMemberStatus
from backend.api.modules.project_lifecycle.schemas.project import (
    ProjectListItemResponse,
    ProjectDetailResponse,
    PerceptionSlotDetail,
    ActorDetail,
    ScopeDetail,
    AcceptanceCriterionDetail,
    ScenarioDetail,
    FeatureDetail,
    BusinessObjectAttributeDetail,
    BusinessObjectDetail,
    FlowStepDetail,
    FlowDetail,
)
from backend.core.detectors import (
    HowIssueDetector,
    ScopeIssueDetector,
    WhatIssueDetector,
)
from backend.services.binary_conversion_service import BinaryConversionService

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
        stmt = (
            select(ProjectModel)
            .where(ProjectModel.id == project_id)
            .options(
                selectinload(ProjectModel.perception_slot),
                selectinload(ProjectModel.actors),
                selectinload(ProjectModel.features).selectinload(FeatureModel.child_relations),
                defaultload(ProjectModel.features).selectinload(FeatureModel.parent_relation),
                defaultload(ProjectModel.features).selectinload(FeatureModel.actors),
                defaultload(ProjectModel.features).selectinload(FeatureModel.scope),
                defaultload(ProjectModel.features).selectinload(FeatureModel.scenarios).selectinload(ScenarioModel.acceptance_criteria),
                selectinload(ProjectModel.business_objects).selectinload(BusinessObjectModel.attributes),
                selectinload(ProjectModel.flows).selectinload(FlowModel.features),
                defaultload(ProjectModel.flows).selectinload(FlowModel.steps).selectinload(FlowStepModel.actors),
                defaultload(ProjectModel.flows).defaultload(FlowModel.steps).selectinload(FlowStepModel.input_business_objects),
                defaultload(ProjectModel.flows).defaultload(FlowModel.steps).selectinload(FlowStepModel.output_business_objects),
                defaultload(ProjectModel.flows).defaultload(FlowModel.steps).selectinload(FlowStepModel.next_steps),
            )
        )
        result = await session.execute(stmt)
        p = result.scalar_one_or_none()
        if p is None:
            raise ValueError("project_not_found")

        # 1. Map Perception Slot
        perception_slot = None
        if p.perception_slot:
            slot_job = await session.get(
                PerceptionJobModel,
                p.perception_slot.id,
            )
            slot_stage = slot_job.stage if slot_job is not None else None

            if self._is_stage_visible(
                stage=slot_stage,
                unlocked_stages=p.unlocked_stages,
            ):
                perception_slot = PerceptionSlotDetail(
                    perception_slot_id=p.perception_slot.id,
                    perception_kind=p.perception_slot.perception_kind,
                    perception_description=p.perception_slot.description,
                    stage=slot_stage,
                )

        # 2. Map Actors
        actors_list = [
            ActorDetail(
                actor_id=a.id,
                actor_name=a.name,
                actor_description=a.description,
                confirmation_status=a.confirmation_status,
                updated_at=a.updated_at,
            )
            for a in p.actors
        ]

        # 3. Map Features
        features_list = []
        for f in p.features:
            # Map Scope
            scope = None
            if f.scope:
                scope = ScopeDetail(
                    scope_id=f.scope.id,
                    scope_status=f.scope.status,
                    reason=f.scope.reason,
                    positive_summary=f.scope.positive_summary,
                    negative_summary=f.scope.negative_summary,
                    positive_picture_base64=(
                        BinaryConversionService.bytes_to_base64(
                            f.scope.positive_picture
                        )
                        if f.scope.positive_picture is not None
                        else None
                    ),
                    negative_picture_base64=(
                        BinaryConversionService.bytes_to_base64(
                            f.scope.negative_picture
                        )
                        if f.scope.negative_picture is not None
                        else None
                    ),
                    kano_category=f.scope.kano_category,
                    kano_category_name=f.scope.kano_category_name,
                    confirmation_status=f.scope.confirmation_status,
                    updated_at=f.scope.updated_at,
                )

            # Map Scenarios
            scenarios = []
            for sc in f.scenarios:
                criteria = [
                    AcceptanceCriterionDetail(
                        criterion_id=ac.id,
                        criterion_content=ac.content,
                        confirmation_status=ac.confirmation_status,
                        updated_at=ac.updated_at,
                    )
                    for ac in sc.acceptance_criteria
                ]
                scenarios.append(
                    ScenarioDetail(
                        scenario_id=sc.id,
                        scenario_name=sc.name,
                        scenario_content=sc.content,
                        feature_id=sc.feature_id,
                        actor_id=sc.actor_id,
                        acceptance_criteria=criteria,
                        confirmation_status=sc.confirmation_status,
                        updated_at=sc.updated_at,
                    )
                )

            features_list.append(
                FeatureDetail(
                    feature_id=f.id,
                    feature_name=f.name,
                    feature_description=f.description,
                    actor_ids=[a.id for a in f.actors],
                    parent_id=f.parent_relation.parent_feature_id if f.parent_relation else None,
                    children_ids=[rel.child_feature_id for rel in f.child_relations],
                    scenarios=scenarios,
                    scope=scope,
                    confirmation_status=f.confirmation_status,
                    updated_at=f.updated_at,
                )
            )

        # 4. Map Business Objects
        business_objects_list = [
            BusinessObjectDetail(
                business_object_id=bo.id,
                business_object_name=bo.name,
                business_object_description=bo.description,
                business_object_attributes=[
                    BusinessObjectAttributeDetail(
                        business_object_attribute_id=attr.id,
                        business_object_attribute_name=attr.name,
                        business_object_attribute_description=attr.description,
                        business_object_attribute_type=attr.data_type,
                        business_object_attribute_example=attr.example,
                        confirmation_status=attr.confirmation_status,
                        updated_at=attr.updated_at,
                    )
                    for attr in bo.attributes
                ],
                confirmation_status=bo.confirmation_status,
                updated_at=bo.updated_at,
            )
            for bo in p.business_objects
        ]

        # 5. Map Flows
        flows_list = []
        for fl in p.flows:
            steps = [
                FlowStepDetail(
                    step_id=st.id,
                    step_name=st.name,
                    step_description=st.description,
                    step_type=st.step_type,
                    position=st.position,
                    actor_ids=[a.id for a in st.actors],
                    input_business_object_ids=[bo.id for bo in st.input_business_objects],
                    output_business_object_ids=[bo.id for bo in st.output_business_objects],
                    next_step_ids=[ns.id for ns in st.next_steps],
                    confirmation_status=st.confirmation_status,
                    updated_at=st.updated_at,
                )
                for st in fl.steps
            ]
            flows_list.append(
                FlowDetail(
                    flow_id=fl.id,
                    flow_name=fl.name,
                    flow_description=fl.description,
                    feature_ids=[f.id for f in fl.features],
                    flow_steps=steps,
                    confirmation_status=fl.confirmation_status,
                    updated_at=fl.updated_at,
                )
            )

        unlocked_list = [s.strip() for s in p.unlocked_stages.split(",") if s.strip()] if p.unlocked_stages else []

        # Get unresolved gates for export action
        from backend.api.modules.diagnosis_quality.public import FindingService
        from backend.api.modules.project_lifecycle.schemas.project import UnresolvedGateResponse
        finding_service = FindingService()
        gate_findings = await finding_service.list_findings(
            project_id=p.id,
            stage="all",
            view="gate",
            action="export",
            session=session,
        )
        unresolved_gates_list = [
            UnresolvedGateResponse(
                finding_id=gf.findingId,
                title=gf.title,
                description=gf.description,
                stage=gf.stage.value,
                code=gf.code,
            )
            for gf in gate_findings
        ]

        return ProjectDetailResponse(
            project_id=p.public_id,
            project_name=p.name,
            project_description=p.description,
            user_requirements=p.user_requirements,
            perception_slot=perception_slot,
            actors=actors_list,
            features=features_list,
            business_objects=business_objects_list,
            flows=flows_list,
            kano_status=p.kano_status,
            unlocked_stages=unlocked_list,
            unresolved_gates=unresolved_gates_list,
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

        # 1. Core Info
        md = []
        md.append(f"# 需求空间建模 PRD 成果报告 - {detail.project_name}")
        md.append("")
        md.append("## 1. 项目基础信息")
        md.append(f"- **项目名称**: {detail.project_name}")
        md.append(f"- **项目描述**: {detail.project_description}")
        md.append("")
        md.append("---")
        md.append("")

        # 2. Raw User Requirements
        md.append("## 2. 原始用户需求说明")
        md.append(detail.user_requirements or "暂无需求说明。")
        md.append("")
        md.append("---")
        md.append("")

        # 3. Actors
        md.append("## 3. 核心角色与参与者 (Who)")
        if not detail.actors:
            md.append("暂无角色数据。")
        else:
            for a in detail.actors:
                md.append(f"- **{a.actor_name}**: {a.actor_description}")
        md.append("")
        md.append("---")
        md.append("")

        # 4. Features (Tree and details)
        md.append("## 4. 功能架构能力树 (What)")
        if not detail.features:
            md.append("暂无功能数据。")
        else:
            # 4.1 Feature Tree structure
            md.append("### 4.1 功能模块树")
            lines = []
            def build_tree(feat_list, parent_id=None, level=0):
                for f in feat_list:
                    if f.parent_id == parent_id:
                        indent = "  " * level
                        scope_text = ""
                        if f.scope:
                            status_map = {
                                "current": "本期",
                                "postponed": "暂缓",
                                "exclude": "不纳入"
                            }
                            raw_status = f.scope.scope_status or ""
                            status_zh = status_map.get(raw_status.lower(), raw_status)
                            scope_text = f" [范围: {status_zh}]"
                        lines.append(f"{indent}- **{f.feature_name}**: {f.feature_description}{scope_text}")
                        build_tree(feat_list, f.feature_id, level + 1)
            build_tree(detail.features)
            md.extend(lines)
            md.append("")

            # 4.2 Scenarios & ACs
            md.append("### 4.2 典型场景与验收标准 (AC)")
            has_scenarios = False
            for f in detail.features:
                if f.scenarios:
                    has_scenarios = True
                    md.append(f"#### 模块：{f.feature_name}")
                    for sc in f.scenarios:
                        md.append(f"- **场景：{sc.scenario_name}**")
                        md.append(f"  - *用户场景描述*: {sc.scenario_content}")
                        if sc.acceptance_criteria:
                            md.append("  - *验收成功标准 (AC)*:")
                            for ac in sc.acceptance_criteria:
                                md.append(f"    - [ ] {ac.criterion_content}")
                    md.append("")
            if not has_scenarios:
                md.append("暂无典型场景。")
        md.append("")
        md.append("---")
        md.append("")

        # 5. Business Objects & Flows
        md.append("## 5. 运作泳道流与业务对象建模 (How)")
        md.append("")

        # 5.1 Business Objects
        md.append("### 5.1 业务数据对象与属性表")
        if not detail.business_objects:
            md.append("暂无数据对象。")
        else:
            for bo in detail.business_objects:
                md.append(f"#### 数据实体: {bo.business_object_name}")
                md.append(f"- *对象描述*: {bo.business_object_description}")
                if bo.business_object_attributes:
                    md.append("")
                    md.append("| 属性名称 | 属性描述 | 数据类型 | 示例值 |")
                    md.append("| --- | --- | --- | --- |")
                    for attr in bo.business_object_attributes:
                        md.append(f"| {attr.business_object_attribute_name} | {attr.business_object_attribute_description} | {attr.business_object_attribute_type} | {attr.business_object_attribute_example} |")
                else:
                    md.append("- *暂无细粒度属性。*")
                md.append("")
        md.append("")

        # 5.2 Flows
        md.append("### 5.2 流程建模与步骤流水线")
        if not detail.flows:
            md.append("暂无业务泳道流建模。")
        else:
            for fl in detail.flows:
                md.append(f"#### 业务流程: {fl.flow_name}")
                md.append(f"- *流程描述*: {fl.flow_description}")
                if fl.flow_steps:
                    md.append("")
                    md.append("##### 泳道步骤详情:")
                    for st in fl.flow_steps:
                        md.append(f"- **步骤: {st.step_name}** ({st.step_type})")
                        md.append(f"  - *描述*: {st.step_description}")
                        
                        actor_names = []
                        for a_id in st.actor_ids:
                            actor = next((a.actor_name for a in detail.actors if a.actor_id == a_id), None)
                            if actor:
                                actor_names.append(actor)
                        if actor_names:
                            md.append(f"  - *参与角色*: {', '.join(actor_names)}")

                        input_bo_names = []
                        for bo_id in st.input_business_object_ids:
                            bo = next((b.business_object_name for b in detail.business_objects if b.business_object_id == bo_id), None)
                            if bo:
                                input_bo_names.append(bo)
                        if input_bo_names:
                            md.append(f"  - *输入数据*: {', '.join(input_bo_names)}")

                        output_bo_names = []
                        for bo_id in st.output_business_object_ids:
                            bo = next((b.business_object_name for b in detail.business_objects if b.business_object_id == bo_id), None)
                            if bo:
                                output_bo_names.append(bo)
                        if output_bo_names:
                            md.append(f"  - *输出数据*: {', '.join(output_bo_names)}")
                md.append("")
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
            md.append("## 附录：未处理阶段检查项 (Gates)")
            md.append("⚠️ 以下项在导出时仍未通过阶段检查约束：")
            for gf in gate_findings:
                md.append(f"- **[{gf.title}]**: {gf.description}")
            md.append("")

        return "\n".join(md)

    async def export_project_spl_syntax(self, project_id: int, session: AsyncSession) -> str:
        from backend.integration.skill_backed_services.spl_syntax_export_service import SplSyntaxExportService
        detail = await self.get_project_detail(project_id, session)
        service = SplSyntaxExportService()
        return await service.export(detail)

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

        target_feature = all_features[feature_id]

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

        summary = (
            f"变更功能【{target_feature.feature_name}】的交付状态为【{next_status}】，"
            f"将直接或间接影响 {len(affected_scenarios)} 个用户场景、"
            f"{len(affected_flows)} 个业务泳道流程以及 "
            f"{len(affected_business_objects)} 个核心数据实体。"
        )

        return {
            "affected_scenarios": affected_scenarios,
            "affected_flows": affected_flows,
            "affected_business_objects": affected_business_objects,
            "summary": summary,
        }

    async def get_stage_progress(
        self,
        project_id: int,
        public_project_id: str,
        session: AsyncSession,
    ) -> dict:
        """
        Compute unified stage progress for What / How / Scope stages.
        Returns a StageProgressResponse-compatible dict.
        """
        from backend.api.modules.diagnosis_quality.public import FindingService
        from backend.database.model import (
            ActorModel, FeatureModel, FeatureRelationModel,
            ScenarioModel, ScenarioAcceptanceCriterionModel,
            FlowModel, FlowStepModel, ScopeModel,
            PerceptionJobModel,
            BusinessObjectModel,
        )

        # Load project
        stmt = select(ProjectModel).where(ProjectModel.id == project_id)
        p = (await session.execute(stmt)).scalar_one_or_none()
        if p is None:
            raise ValueError("project_not_found")

        unlocked_set: set[str] = {
            s.strip().lower() for s in p.unlocked_stages.split(",") if s.strip()
        } if p.unlocked_stages else set()

        STAGES_ORDER = ["what", "how", "scope"]
        finding_service = FindingService()

        # ── Structural data ──────────────────────────────────────────────

        actors_rows = (await session.execute(
            select(ActorModel.id).where(ActorModel.project_id == project_id)
        )).scalars().all()
        actors_count = len(actors_rows)

        features = (await session.execute(
            select(FeatureModel).where(FeatureModel.project_id == project_id)
        )).scalars().all()

        feature_ids = [f.id for f in features]
        parent_ids: set[int] = set()
        if feature_ids:
            parent_ids = set((await session.execute(
                select(FeatureRelationModel.parent_feature_id).where(
                    FeatureRelationModel.parent_feature_id.in_(feature_ids),
                    FeatureRelationModel.child_feature_id.in_(feature_ids),
                )
            )).scalars().all())
        leaf_features = [f for f in features if f.id not in parent_ids]

        # Feature to Actor mapping
        from backend.database.model import feature_actor_table
        feature_actor_rows = (await session.execute(
            select(feature_actor_table.c.feature_id, feature_actor_table.c.actor_id)
            .join(FeatureModel, FeatureModel.id == feature_actor_table.c.feature_id)
            .where(FeatureModel.project_id == project_id)
        )).all()
        feature_actor_map: dict[int, list[int]] = {}
        for f_id, a_id in feature_actor_rows:
            feature_actor_map.setdefault(f_id, []).append(a_id)

        # Scenarios and ACs
        scenarios_result = await session.execute(
            select(ScenarioModel)
            .join(FeatureModel, FeatureModel.id == ScenarioModel.feature_id)
            .where(FeatureModel.project_id == project_id)
        )
        scenarios_db = scenarios_result.scalars().all()
        scenario_ids = [s.id for s in scenarios_db]
        scenarios_map = {s.id: s for s in scenarios_db}
        feature_scenario_map: dict[int, list[int]] = {}
        for s in scenarios_db:
            feature_scenario_map.setdefault(s.feature_id, []).append(s.id)

        ac_scenario_ids: set[int] = set()
        if scenario_ids:
            ac_rows = (await session.execute(
                select(ScenarioAcceptanceCriterionModel.scenario_id).where(
                    ScenarioAcceptanceCriterionModel.scenario_id.in_(scenario_ids)
                )
            )).scalars().all()
            ac_scenario_ids = set(ac_rows)

        # Flows and Business Objects
        flows_result = await session.execute(
            select(FlowModel).where(FlowModel.project_id == project_id)
        )
        flows_db = flows_result.scalars().all()
        flows = [f.id for f in flows_db]
        flows_map = {f.id: f for f in flows_db}

        flows_with_steps = set()
        steps_db = []
        step_actor_map: dict[int, list[int]] = {}
        step_input_bo_map: dict[int, list[int]] = {}
        step_output_bo_map: dict[int, list[int]] = {}
        if flows:
            steps_result = await session.execute(
                select(FlowStepModel).where(FlowStepModel.flow_id.in_(flows))
            )
            steps_db = steps_result.scalars().all()
            flows_with_steps = {step.flow_id for step in steps_db}
            step_ids = [step.id for step in steps_db]

            if step_ids:
                from backend.database.model import (
                    flow_step_actor_table,
                    flow_step_input_business_object_table,
                    flow_step_output_business_object_table,
                )
                # Query step actors mapping
                step_actors_rows = (await session.execute(
                    select(flow_step_actor_table.c.flow_step_id, flow_step_actor_table.c.actor_id)
                    .where(flow_step_actor_table.c.flow_step_id.in_(step_ids))
                )).all()
                for step_id, actor_id in step_actors_rows:
                    step_actor_map.setdefault(step_id, []).append(actor_id)

                # Query step input BOs mapping
                step_input_bo_rows = (await session.execute(
                    select(flow_step_input_business_object_table.c.flow_step_id, flow_step_input_business_object_table.c.business_object_id)
                    .where(flow_step_input_business_object_table.c.flow_step_id.in_(step_ids))
                )).all()
                for step_id, bo_id in step_input_bo_rows:
                    step_input_bo_map.setdefault(step_id, []).append(bo_id)

                # Query step output BOs mapping
                step_output_bo_rows = (await session.execute(
                    select(flow_step_output_business_object_table.c.flow_step_id, flow_step_output_business_object_table.c.business_object_id)
                    .where(flow_step_output_business_object_table.c.flow_step_id.in_(step_ids))
                )).all()
                for step_id, bo_id in step_output_bo_rows:
                    step_output_bo_map.setdefault(step_id, []).append(bo_id)

        bos_result = await session.execute(
            select(BusinessObjectModel)
            .options(selectinload(BusinessObjectModel.attributes))
            .where(BusinessObjectModel.project_id == project_id)
        )
        bos_db = bos_result.scalars().all()
        bo_set = {bo.id for bo in bos_db}

        scope_rows = (await session.execute(
            select(ScopeModel.feature_id)
            .join(FeatureModel, FeatureModel.id == ScopeModel.feature_id)
            .where(FeatureModel.project_id == project_id, ScopeModel.status != None)
        )).scalars().all()
        scoped_feature_ids = set(scope_rows)

        # Perception job status (latest running or failed job for each stage)
        latest_jobs_result = await session.execute(
            select(PerceptionJobModel)
            .where(PerceptionJobModel.project_id == project_id)
            .order_by(PerceptionJobModel.id.desc())
        )
        latest_jobs_db = latest_jobs_result.scalars().all()
        latest_jobs_map: dict[str, PerceptionJobModel] = {}
        for job in latest_jobs_db:
            if job.stage not in latest_jobs_map:
                latest_jobs_map[job.stage] = job

        # Gate findings
        what_gate_findings = await finding_service.list_findings(
            project_id=project_id, stage="what", view="gate", action="enter_how", session=session,
        )
        how_gate_findings = await finding_service.list_findings(
            project_id=project_id, stage="how", view="gate", action="enter_scope", session=session,
        )
        scope_gate_findings = await finding_service.list_findings(
            project_id=project_id, stage="scope", view="gate", action="generate_preview", session=session,
        )

        stages: list[dict] = []
        for stage in STAGES_ORDER:
            if stage == "what":
                unlocked = True
            elif stage == "how":
                unlocked = "what" in unlocked_set
            elif stage == "scope":
                unlocked = "how" in unlocked_set
            else:
                unlocked = False
            gate_findings = {"what": what_gate_findings, "how": how_gate_findings, "scope": scope_gate_findings}[stage]
            blocked = bool(gate_findings)

            # ── What checks ─────────────────────────────────────────────
            failed_checks: list[dict] = []
            content_complete = False

            if stage == "what":
                if actors_count == 0:
                    failed_checks.append({"code": "missing_actors", "message": "项目尚未有参与者", "targets": []})
                if not leaf_features:
                    failed_checks.append({"code": "missing_leaf_features", "message": "项目尚未有叶子功能", "targets": []})
                # leaf without actor check
                leaf_without_actor = [f for f in leaf_features if not feature_actor_map.get(f.id)] if leaf_features else []
                if leaf_without_actor:
                    failed_checks.append({
                        "code": "leaf_feature_without_actor",
                        "message": f"{len(leaf_without_actor)} 个叶子功能未绑定参与者",
                        "targets": [{"type": "feature", "id": str(f.id), "name": f.name} for f in leaf_without_actor[:5]],
                    })
                # leaf without scenario
                leaf_without_scenario = [f for f in leaf_features if not feature_scenario_map.get(f.id)]
                if leaf_without_scenario:
                    failed_checks.append({
                        "code": "leaf_feature_without_scenario",
                        "message": f"{len(leaf_without_scenario)} 个叶子功能缺少场景",
                        "targets": [{"type": "feature", "id": str(f.id), "name": f.name} for f in leaf_without_scenario[:5]],
                    })
                # scenario without AC
                scenarios_without_ac = [sid for sid in scenario_ids if sid not in ac_scenario_ids]
                if scenarios_without_ac:
                    failed_checks.append({
                        "code": "missing_acceptance_criteria",
                        "message": f"{len(scenarios_without_ac)} 个场景缺少验收标准",
                        "targets": [{"type": "scenario", "id": str(sid), "name": scenarios_map[sid].name} for sid in scenarios_without_ac[:5]],
                    })
                content_complete = len(failed_checks) == 0

            elif stage == "how":
                if not flows:
                    failed_checks.append({"code": "missing_flows", "message": "项目尚未有流程", "targets": []})
                else:
                    flows_without_steps_ids = [fid for fid in flows if fid not in flows_with_steps]
                    if flows_without_steps_ids:
                        failed_checks.append({
                            "code": "flows_without_steps",
                            "message": f"{len(flows_without_steps_ids)} 个流程缺少步骤",
                            "targets": [{"type": "flow", "id": str(fid), "name": flows_map[fid].name} for fid in flows_without_steps_ids[:5]],
                        })
                    
                    # step actor check
                    actors_set = set(actors_rows)
                    invalid_actor_steps = []
                    for step in steps_db:
                        step_actor_ids = step_actor_map.get(step.id, [])
                        if step_actor_ids:
                            if any(aid not in actors_set for aid in step_actor_ids):
                                invalid_actor_steps.append(step)
                    if invalid_actor_steps:
                        failed_checks.append({
                            "code": "invalid_step_actor",
                            "message": f"{len(invalid_actor_steps)} 个流程步骤关联了无效或被删除的角色",
                            "targets": [{"type": "step", "id": str(s.id), "name": s.name} for s in invalid_actor_steps[:5]],
                        })

                    # step business object check
                    invalid_bo_steps = []
                    for step in steps_db:
                        all_step_bos = step_input_bo_map.get(step.id, []) + step_output_bo_map.get(step.id, [])
                        if any(boid not in bo_set for boid in all_step_bos):
                            invalid_bo_steps.append(step)
                    if invalid_bo_steps:
                        failed_checks.append({
                            "code": "invalid_step_business_object",
                            "message": f"{len(invalid_bo_steps)} 个流程步骤关联了无效的业务对象",
                            "targets": [{"type": "step", "id": str(s.id), "name": s.name} for s in invalid_bo_steps[:5]],
                        })

                    # business object attributes definition check
                    if bos_db:
                        total_attributes = sum(len(bo.attributes) for bo in bos_db)
                        if total_attributes == 0:
                            failed_checks.append({
                                "code": "missing_object_attributes",
                                "message": "业务对象尚未定义任何属性字段",
                                "targets": [{"type": "business_object", "id": str(bo.id), "name": bo.name} for bo in bos_db[:5]],
                            })
                content_complete = len(failed_checks) == 0

            elif stage == "scope":
                leaf_not_scoped = [f for f in leaf_features if f.id not in scoped_feature_ids]
                if leaf_not_scoped:
                    failed_checks.append({
                        "code": "missing_scope_decision",
                        "message": f"{len(leaf_not_scoped)} 个叶子功能缺少范围决策",
                        "targets": [{"type": "feature", "id": str(f.id), "name": f.name} for f in leaf_not_scoped[:5]],
                    })
                kano_ready = p.kano_status in ("generated", "skipped")
                if not kano_ready:
                    failed_checks.append({"code": "kano_not_ready", "message": "Kano 分析尚未完成", "targets": []})
                content_complete = len(failed_checks) == 0

            # Determine next_stage_unlocked
            next_stage_unlocked = stage in unlocked_set

            # Stage perception status
            stage_latest_job = latest_jobs_map.get(stage)
            stage_perception_running = stage_latest_job is not None and stage_latest_job.status in ("running", "pending")

            # ── Status code ──────────────────────────────────────────────
            if next_stage_unlocked:
                status_code = "ready"
                status_label = "阶段已完成"
            else:
                if not unlocked:
                    status_code = "locked"
                    status_label = "尚未解锁"
                else:
                    if stage_perception_running:
                        status_code = "analysis_running"
                        status_label = "AI 分析运行中"
                    elif blocked:
                        status_code = "blocked"
                        status_label = "存在阻塞问题，需先解决"
                    elif content_complete:
                        status_code = "ready_to_advance"
                        status_label = "可申请进入下一阶段"
                    else:
                        # Check unlocked but not started
                        is_not_started = False
                        if stage == "what":
                            is_not_started = (actors_count == 0)
                        elif stage == "how":
                            is_not_started = (len(flows_db) == 0 and len(bos_db) == 0)
                        elif stage == "scope":
                            is_not_started = (len(scoped_feature_ids) == 0)

                        if is_not_started:
                            status_code = "unlocked_not_started"
                            status_label = "已解锁，尚未开始"
                        else:
                            status_code = "in_progress"
                            status_label = "阶段进行中"

            # ── Next action ──────────────────────────────────────────────
            transition_action_map = {"what": "enter_how", "how": "enter_scope", "scope": "enter_preview"}
            transition_available = status_code == "ready_to_advance"
            route_map = {
                "what": f"/projects/{public_project_id}/what",
                "how": f"/projects/{public_project_id}/flow",
                "scope": f"/projects/{public_project_id}/scope",
            }

            if status_code == "ready_to_advance":
                next_action = {
                    "kind": "stage_transition",
                    "transition_action": transition_action_map[stage],
                    "route": None,
                    "label": f"申请进入下一阶段",
                }
            elif status_code == "blocked":
                next_action = {"kind": "open_gate_findings", "transition_action": None, "route": None, "label": "查看阻塞问题"}
            elif status_code == "analysis_running":
                next_action = {"kind": "wait", "transition_action": None, "route": None, "label": "查看分析进度"}
            elif status_code == "locked":
                next_action = {"kind": "none", "transition_action": None, "route": None, "label": ""}
            elif status_code == "unlocked_not_started":
                next_action = {"kind": "navigate", "transition_action": None, "route": route_map.get(stage), "label": "开始建模"}
            elif status_code in ("in_progress", "ready"):
                next_action = {"kind": "navigate", "transition_action": None, "route": route_map.get(stage), "label": "前往该阶段"}
            else:
                next_action = {"kind": "navigate", "transition_action": None, "route": route_map.get(stage), "label": "继续完善"}

            # Analysis status
            if stage_latest_job:
                if stage_perception_running:
                    analysis_status = {
                        "status": "running",
                        "job_id": stage_latest_job.id,
                        "started_at": stage_latest_job.created_at.isoformat() if hasattr(stage_latest_job, "created_at") and stage_latest_job.created_at else None,
                        "message": f"AI 正在分析 {stage} 阶段...",
                    }
                elif stage_latest_job.status == "failed":
                    analysis_status = {
                        "status": "failed",
                        "job_id": stage_latest_job.id,
                        "started_at": stage_latest_job.created_at.isoformat() if hasattr(stage_latest_job, "created_at") and stage_latest_job.created_at else None,
                        "message": stage_latest_job.error_message or "分析失败，请重试",
                    }
                else:
                    analysis_status = {"status": "idle", "job_id": None, "started_at": None, "message": None}
            else:
                analysis_status = {"status": "idle", "job_id": None, "started_at": None, "message": None}

            stages.append({
                "stage": stage,
                "status_code": status_code,
                "status_label": status_label,
                "content_complete": content_complete,
                "unlocked": unlocked,
                "transition_available": transition_available,
                "next_action": next_action,
                "failed_checks": failed_checks,
                "blocking_findings": gate_findings,
                "analysis_status": analysis_status,
            })

        return {
            "project_id": public_project_id,
            "stages": stages,
        }

    async def stage_transition(
        self,
        project_id: int,
        action: str,
        force: bool,
        session: AsyncSession,
        operator_id: int | None = None,
    ) -> dict:
        from backend.api.modules.diagnosis_quality.public import FindingService
        from backend.database.model import AuditLogModel
        
        stmt = select(ProjectModel).where(ProjectModel.id == project_id)
        result = await session.execute(stmt)
        p = result.scalar_one_or_none()
        if p is None:
            raise ValueError("project_not_found")

        # 1. Map action
        if action == "enter_how":
            gate_action = "enter_how"
            gate_stage = "what"
            unlock_stage = "what"
            target_route = f"/projects/{p.public_id}/flow"
        elif action == "enter_scope":
            gate_action = "enter_scope"
            gate_stage = "how"
            unlock_stage = "how"
            target_route = f"/projects/{p.public_id}/scope"
        elif action == "enter_preview":
            gate_action = "generate_preview"
            gate_stage = "scope"
            unlock_stage = "scope"
            target_route = f"/projects/{p.public_id}/preview"
        else:
            raise ValueError("invalid_stage_transition")

        STAGES_ORDER = ["what", "how", "scope"]
        unlocked_set = {s.strip().lower() for s in p.unlocked_stages.split(",") if s.strip()} if p.unlocked_stages else set()
        ordered_unlocked = [s for s in STAGES_ORDER if s in unlocked_set]

        # 2. Check unified stage progress before gate findings. A forced transition may
        # skip blocking findings, but it must not bypass incomplete mandatory checks.
        stage_progress = await self.get_stage_progress(project_id, p.public_id, session)
        source_progress = next(
            (s for s in stage_progress["stages"] if s["stage"] == gate_stage),
            None,
        )
        source_status = source_progress.get("status_code") if source_progress else None
        content_complete = bool(source_progress.get("content_complete")) if source_progress else False
        already_unlocked = unlock_stage in unlocked_set

        # 3. Check gate findings
        finding_service = FindingService()
        findings = await finding_service.list_findings(
            project_id=project_id,
            stage=gate_stage,
            view="gate",
            action=gate_action,
            session=session,
        )

        if not already_unlocked:
            if source_status in ("locked", "analysis_running") or not content_complete:
                return {
                    "status": "blocked",
                    "action": action,
                    "unlocked_stage": None,
                    "target_route": None,
                    "unlocked_stages": ordered_unlocked,
                    "blocking_findings": findings,
                }

        # 4. Handle force and findings
        if findings and not force:
            return {
                "status": "blocked",
                "action": action,
                "unlocked_stage": None,
                "target_route": None,
                "unlocked_stages": ordered_unlocked,
                "blocking_findings": findings,
            }

        # 5. Perform stage unlock
        unlocked_set.add(unlock_stage)
        ordered_unlocked = [s for s in STAGES_ORDER if s in unlocked_set]
        p.unlocked_stages = ",".join(ordered_unlocked)
        
        # 6. Add Audit Log
        audit_action = "stage_transition_forced" if (findings and force) else "stage_transition_unlocked"
        audit_summary = (
            f"强制推进阶段: {action} (跳过了 {len(findings)} 个阻塞项)" 
            if (findings and force) 
            else f"解锁阶段: {action} (前置 {unlock_stage} 已满足)"
        )
        
        is_forced_transition = bool(findings and force)
        from_stage = ""
        target_stage = ""
        if action == "enter_how":
            from_stage = "what"
            target_stage = "how"
        elif action == "enter_scope":
            from_stage = "how"
            target_stage = "scope"
        elif action == "enter_preview":
            from_stage = "scope"
            target_stage = "preview"

        blocking_finding_ids = [f.findingId for f in findings] if findings else []

        audit_log = AuditLogModel(
            project_id=project_id,
            action_type=audit_action,
            summary=audit_summary,
            target_type="project",
            target_id=p.public_id,
            actor_user_id=operator_id,
            payload={
                "action": action,
                "unlock_stage": unlock_stage,
                "force": force,
                "is_forced_transition": is_forced_transition,
                "from_stage": from_stage,
                "target_stage": target_stage,
                "blocking_finding_ids": blocking_finding_ids,
                "operator_id": operator_id,
                "bypass_findings_count": len(findings) if findings else 0
            }
        )
        session.add(audit_log)
        await session.commit()

        return {
            "status": "unlocked",
            "action": action,
            "unlocked_stage": unlock_stage,
            "target_route": target_route,
            "unlocked_stages": ordered_unlocked,
            "blocking_findings": [],
        }
