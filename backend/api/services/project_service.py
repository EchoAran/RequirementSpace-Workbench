from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, defaultload

from backend.database.model import ProjectModel, FeatureModel, ScenarioModel, BusinessObjectModel, FlowModel, FlowStepModel, PerceptionJobModel
from backend.api.schemas.project_schema import (
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
    async def list_projects(self, session: AsyncSession) -> list[ProjectListItemResponse]:
        # Eager load relationships to avoid N+1 queries during node count calculation
        stmt = (
            select(ProjectModel)
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
        projects = result.scalars().all()

        response = []
        for p in projects:
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
                    id=str(p.id),
                    project_id=p.id,
                    name=p.name,
                    idea=p.user_requirements,
                    description=p.description,
                    updated_at=p.updated_at,
                    status_code=status_code,
                    status=status,
                    issue_count=issue_count,
                    node_count=node_count,
                )
            )
        return response

    async def _count_visible_open_issues(
        self,
        project: ProjectModel,
        session: AsyncSession,
    ) -> int:
        hidden_issue_ids = await self._load_hidden_issue_ids(
            project.id,
            session,
        )
        issue_count = 0

        for stage in self._get_visible_issue_stages(project.unlocked_stages):
            detector = self._get_issue_detectors().get(stage)
            if detector is None:
                continue

            issues = await detector.detect(
                project_id=project.id,
                session=session,
            )
            issue_count += sum(
                1
                for issue in issues
                if issue.issueId not in hidden_issue_ids
            )

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

    @staticmethod
    async def _load_hidden_issue_ids(
        project_id: int,
        session: AsyncSession,
    ) -> set[str]:
        from backend.database.model import IssueOverrideModel

        result = await session.execute(
            select(IssueOverrideModel.issue_id).where(
                IssueOverrideModel.project_id == project_id,
                IssueOverrideModel.status.in_(("ignored", "resolved")),
            )
        )
        return {issue_id for issue_id in result.scalars().all() if issue_id}

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
                )

            # Map Scenarios
            scenarios = []
            for sc in f.scenarios:
                criteria = [
                    AcceptanceCriterionDetail(
                        criterion_id=ac.id,
                        criterion_content=ac.content,
                        confirmation_status=ac.confirmation_status,
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
                    )
                    for attr in bo.attributes
                ],
                confirmation_status=bo.confirmation_status,
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
                )
            )

        unlocked_list = [s.strip() for s in p.unlocked_stages.split(",") if s.strip()] if p.unlocked_stages else []

        return ProjectDetailResponse(
            project_id=p.id,
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
        )

    async def unlock_stage(self, project_id: int, stage: str, session: AsyncSession) -> dict:
        stmt = select(ProjectModel).where(ProjectModel.id == project_id)
        result = await session.execute(stmt)
        p = result.scalar_one_or_none()
        if p is None:
            raise ValueError("project_not_found")

        unlocked_list = [s.strip() for s in p.unlocked_stages.split(",") if s.strip()] if p.unlocked_stages else []
        stage_clean = stage.strip().lower()
        if stage_clean not in unlocked_list:
            unlocked_list.append(stage_clean)
            p.unlocked_stages = ",".join(unlocked_list)
            await session.commit()

        return {
            "project_id": project_id,
            "stage": stage_clean,
            "message": "stage_unlocked",
            "unlocked_stages": unlocked_list
        }

    async def delete_project(self, project_id: int, session: AsyncSession) -> dict:
        stmt = select(ProjectModel).where(ProjectModel.id == project_id)
        result = await session.execute(stmt)
        p = result.scalar_one_or_none()
        if p is None:
            raise ValueError("project_not_found")

        await session.delete(p)
        await session.commit()
        return {"project_id": project_id, "message": "project_deleted"}

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

        return {"project_id": project_id, "message": "perception_slot_deleted"}

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
            "project_id": p.id,
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

        return "\n".join(md)

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
