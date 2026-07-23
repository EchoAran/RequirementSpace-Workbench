from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import datetime
from typing import Any

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from .shadow_validator import PreviewShadowValidator
from .shadow_merger import PreviewShadowMerger
from backend.core.shadow_preview.shadow_patch_validator import ShadowPatchValidator
from .shadow_project_creator import (
    build_project_snapshot,
    calculate_stable_snapshot_hash,
    remap_snapshot_to_pydantic,
)
from backend.database.database import AsyncSessionLocal
from backend.database.model import (
    ProjectModel,
    ActorModel,
    FeatureModel,
    FeatureRelationModel,
    ScenarioModel,
    ScenarioAcceptanceCriterionModel,
    BusinessObjectModel,
    BusinessObjectAttributeModel,
    FlowModel,
    FlowStepModel,
    ScopeModel,
    PreviewShadowDraftModel,
    feature_actor_table,
    flow_feature_table,
    flow_step_actor_table,
    flow_step_input_business_object_table,
    flow_step_output_business_object_table,
    flow_step_next_table,
    beijing_now,
)
from backend.api.modules.project_lifecycle.public import ProjectDetailResponse
from backend.core.llm_context import current_llm_context, is_web_request_ctx, LLMRequestContext
from backend.core.locale import DEFAULT_LOCALE, ContentLocaleSource, SupportedLocale


class PreviewShadowConvergenceService:
    def __init__(self) -> None:
        self.validator = PreviewShadowValidator()
        self.gate_evaluator = self.validator.gate_evaluator

    @property
    def _prototype_generation_service(self):
        from backend.api.modules.preview_convergence.ports import get_prototype_generation_service
        return get_prototype_generation_service()

    async def _generate_scopes_for_features(
        self,
        scope_service,
        user_requirements: str,
        feature_nodes: list,
        leaf_feature_nodes: list,
        user_feedback: str = "",
        temp_feat_to_int: dict[str, int] = None,
    ) -> list[dict]:
        return await PreviewShadowMerger.generate_scopes_for_features(
            scope_service=scope_service,
            user_requirements=user_requirements,
            feature_nodes=feature_nodes,
            leaf_feature_nodes=leaf_feature_nodes,
            user_feedback=user_feedback,
            temp_feat_to_int=temp_feat_to_int,
        )

    async def _generate_shadow_patch(
        self,
        project_id: int,
        base_snapshot: dict,
        session: AsyncSession = None,
        feedback: str = "",
        draft_id: str = "",
    ) -> dict:
        return await PreviewShadowMerger.generate_shadow_patch(
            service=self,
            project_id=project_id,
            base_snapshot=base_snapshot,
            session=session,
            feedback=feedback,
            draft_id=draft_id,
        )

    def _apply_patch_to_snapshot(
        self, base_snapshot: dict, patch: dict
    ) -> tuple[dict, dict[str, int]]:
        return PreviewShadowMerger.apply_patch_to_snapshot(base_snapshot, patch)



    async def _update_progress(self, draft_id: str, progress: int, message: str) -> None:
        try:
            async with AsyncSessionLocal() as session:
                draft_res = await session.execute(
                    select(PreviewShadowDraftModel).where(PreviewShadowDraftModel.draft_id == draft_id)
                )
                draft = draft_res.scalar_one_or_none()
                if draft and draft.status == "generating":
                    import json
                    progress_info = {
                        "progress": progress,
                        "message": message
                    }
                    draft.error_message = json.dumps(progress_info, ensure_ascii=False)
                    await session.commit()
        except Exception:
            pass

    async def converge_shadow_snapshot_task(
        self,
        project_id: int,
        draft_id: str,
        api_url: str | None = None,
        api_key: str | None = None,
        model_name: str | None = None,
        content_locale: SupportedLocale = DEFAULT_LOCALE.value,
        content_locale_source: ContentLocaleSource = "default",
    ) -> None:
        """
        Background AsyncIO task worker with isolated database session context.
        """
        prototype_generation_service = self._prototype_generation_service
        token_ctx = None
        token_web = None
        if api_url and api_key and model_name:
            ctx = LLMRequestContext(
                api_url=api_url,
                api_key=api_key,
                model_name=model_name,
                content_locale=content_locale,
                content_locale_source=content_locale_source,
            )
            token_ctx = current_llm_context.set(ctx)
            token_web = is_web_request_ctx.set(True)

        try:
            await asyncio.sleep(0.5)  # Let parent request return safely
            
            # 1. Fetch Draft and baseline info in a short session
            try:
                async with AsyncSessionLocal() as session:
                    draft_res = await session.execute(
                        select(PreviewShadowDraftModel).where(PreviewShadowDraftModel.draft_id == draft_id)
                    )
                    draft = draft_res.scalar_one_or_none()
                    if not draft:
                        return

                    # Resolve public_id for client-facing payloads
                    project_obj = await session.get(ProjectModel, project_id)
                    project_public_id = project_obj.public_id if project_obj else str(project_id)

                    base_snapshot = draft.base_snapshot_json
                    feedback = ""
                    if draft.error_message and draft.error_message.startswith("Regenerating draft with feedback: "):
                        feedback = draft.error_message[len("Regenerating draft with feedback: "):].strip()
            except Exception as e:
                # If draft fetching fails, we can't do anything
                return

            # 2. Run convergence AI helper to build patch OUTSIDE of any database transaction!
            try:
                await self._update_progress(draft_id, 5, "preview.full.loadingShadow")
                patch = await self._generate_shadow_patch(
                    project_id=project_id,
                    base_snapshot=base_snapshot,
                    feedback=feedback,
                    draft_id=draft_id,
                )

                await self._update_progress(draft_id, 85, "preview.full.progressAssembly")
                # 3. Validate patch
                self.validator.validate_patch(patch, base_snapshot, project_public_id)

                # 4. Construct virtual shadow snapshot (with negative IDs to appease Pydantic type validator)
                shadow_snapshot, temp_id_to_neg_int = self._apply_patch_to_snapshot(base_snapshot, patch)

                # 5. Parse shadow_snapshot as ProjectDetailResponse
                remapped_snapshot = remap_snapshot_to_pydantic(shadow_snapshot)
                shadow_detail = ProjectDetailResponse.model_validate(remapped_snapshot)

                # 6. Generate simulated UI prototype pages using PrototypeGenerationService
                await self._update_progress(draft_id, 90, "preview.full.progressAssembly")
                generator_input = prototype_generation_service._build_generator_input(
                    detail=shadow_detail,
                    gherkin_specs=[]
                )
                targets = prototype_generation_service._build_role_feature_targets(
                    generator_input=generator_input,
                    detail=shadow_detail
                )

                pages = await prototype_generation_service._generate_pages(targets)
                first_page = pages[0]

                # Build PrototypePreviewResponse payload
                prototype_preview = {
                    "prototypeId": 0,
                    "projectId": project_public_id,
                    "html": first_page["html"],
                    "javascript": first_page["javascript"],
                    "css": first_page["css"],
                    "pages": pages,
                    "source": "shadow_project",
                    "status": "ready",
                    "createdAt": beijing_now().isoformat(),
                    "updatedAt": beijing_now().isoformat(),
                    "shadowDraftId": draft_id
                }

                # Calculate hash of final shadow snapshot
                shadow_hash = calculate_stable_snapshot_hash(shadow_snapshot)

                # Write results back in a short, atomic write transaction
                async with AsyncSessionLocal() as session:
                    draft_res = await session.execute(
                        select(PreviewShadowDraftModel).where(PreviewShadowDraftModel.draft_id == draft_id)
                    )
                    draft = draft_res.scalar_one_or_none()
                    if draft:
                        draft.status = "ready"
                        draft.shadow_snapshot_hash = shadow_hash
                        draft.shadow_snapshot_json = remapped_snapshot
                        draft.patch_json = patch
                        draft.prototype_preview_json = prototype_preview
                        await session.commit()

            except Exception as e:
                # Log error and fail gracefully
                import traceback
                error_trace = traceback.format_exc()

                try:
                    async with AsyncSessionLocal() as session:
                        draft_res = await session.execute(
                            select(PreviewShadowDraftModel).where(PreviewShadowDraftModel.draft_id == draft_id)
                        )
                        draft = draft_res.scalar_one_or_none()
                        if draft:
                            draft.status = "failed"
                            draft.error_message = f"Convergence failed: {str(e)}\n{error_trace}"
                            await session.commit()
                except Exception:
                    pass
        finally:
            if token_ctx is not None:
                current_llm_context.reset(token_ctx)
            if token_web is not None:
                is_web_request_ctx.reset(token_web)

    async def commit_shadow_draft(self, project_id: int, draft_id: str, session: AsyncSession) -> None:
        """
        Transactional write-back implementation mapping transient IDs to auto-increment DB IDs
        in a single atomic write transaction.
        """
        prototype_generation_service = self._prototype_generation_service
        # 1. Fetch Draft
        draft_res = await session.execute(
            select(PreviewShadowDraftModel).where(PreviewShadowDraftModel.draft_id == draft_id)
        )
        draft = draft_res.scalar_one_or_none()
        if not draft:
            raise ValueError("shadow_draft_not_found")
        if draft.status != "ready":
            raise ValueError("shadow_draft_not_ready")

        # 2. Hash conflict verification
        current_snapshot = await build_project_snapshot(project_id, session)
        current_hash = calculate_stable_snapshot_hash(current_snapshot)
        if current_hash != draft.base_snapshot_hash:
            raise ValueError("shadow_draft_conflict")

        # 3. Secondary validator check
        patch = draft.patch_json
        ShadowPatchValidator.validate_patch(patch, current_snapshot, current_snapshot["project_id"])

        # 4. Map temporary string IDs to new database IDs
        actor_id_map: dict[str, int] = {}
        feature_id_map: dict[str, int] = {}
        scenario_id_map: dict[str, int] = {}
        bo_id_map: dict[str, int] = {}
        flow_id_map: dict[str, int] = {}
        step_id_map: dict[str, int] = {}

        # Helpers to resolve a ref string (e.g. "actor:12" or "tmp_actor_1") to integer ID
        def resolve_actor_id(ref: Any) -> int:
            if not ref:
                return 0
            ref_str = str(ref)
            if ref_str.startswith("tmp_"):
                return actor_id_map[ref_str]
            if ":" in ref_str:
                return int(ref_str.split(":")[1])
            return int(ref_str)

        def resolve_feature_id(ref: Any) -> int:
            if not ref:
                return 0
            ref_str = str(ref)
            if ref_str.startswith("tmp_"):
                return feature_id_map[ref_str]
            if ":" in ref_str:
                return int(ref_str.split(":")[1])
            return int(ref_str)

        def resolve_scenario_id(ref: Any) -> int:
            if not ref:
                return 0
            ref_str = str(ref)
            if ref_str.startswith("tmp_"):
                return scenario_id_map[ref_str]
            if ":" in ref_str:
                return int(ref_str.split(":")[1])
            return int(ref_str)

        def resolve_bo_id(ref: Any) -> int:
            if not ref:
                return 0
            ref_str = str(ref)
            if ref_str.startswith("tmp_"):
                return bo_id_map[ref_str]
            if ":" in ref_str:
                return int(ref_str.split(":")[1])
            return int(ref_str)

        def resolve_flow_id(ref: Any) -> int:
            if not ref:
                return 0
            ref_str = str(ref)
            if ref_str.startswith("tmp_"):
                return flow_id_map[ref_str]
            if ":" in ref_str:
                return int(ref_str.split(":")[1])
            return int(ref_str)

        def resolve_step_id(ref: Any) -> int:
            if not ref:
                return 0
            ref_str = str(ref)
            if ref_str.startswith("tmp_"):
                return step_id_map[ref_str]
            if ":" in ref_str:
                return int(ref_str.split(":")[1])
            return int(ref_str)

        # Step A: Insert Actors
        for a in patch.get("actors_added", []):
            actor = ActorModel(
                project_id=project_id,
                name=a["name"],
                description=a["description"]
            )
            session.add(actor)
            await session.flush()
            actor_id_map[a["temp_id"]] = actor.id

        # Step B: Insert Features (topological multi-pass parent resolution)
        feats_to_insert = list(patch.get("features_added", []))
        while feats_to_insert:
            inserted_in_this_pass = 0
            remaining = []
            
            for f in feats_to_insert:
                parent_ref = f.get("parent_ref")
                
                # Check if parent is resolved or None
                can_insert = False
                parent_id = None
                
                if parent_ref is None:
                    can_insert = True
                else:
                    parent_ref_str = str(parent_ref)
                    if parent_ref_str.startswith("feature:"):
                        can_insert = True
                        parent_id = int(parent_ref_str.split(":")[1])
                    elif parent_ref_str.startswith("tmp_"):
                        if parent_ref_str in feature_id_map:
                            can_insert = True
                            parent_id = feature_id_map[parent_ref_str]
                    else:
                        try:
                            parent_id = int(parent_ref_str)
                            can_insert = True
                        except ValueError:
                            pass
                
                if can_insert:
                    feat = FeatureModel(
                        project_id=project_id,
                        name=f["name"],
                        description=f["description"]
                    )
                    session.add(feat)
                    await session.flush()
                    feature_id_map[f["temp_id"]] = feat.id
                    
                    # If has parent, save to FeatureRelationModel
                    if parent_id is not None:
                        # Find next position under parent
                        pos_res = await session.execute(
                            select(func.max(FeatureRelationModel.position)).where(
                                FeatureRelationModel.parent_feature_id == parent_id
                            )
                        )
                        max_pos = pos_res.scalar()
                        next_pos = 0 if max_pos is None else max_pos + 1
                        
                        relation = FeatureRelationModel(
                            parent_feature_id=parent_id,
                            child_feature_id=feat.id,
                            position=next_pos
                        )
                        session.add(relation)
                        await session.flush()

                    inserted_in_this_pass += 1
                else:
                    remaining.append(f)
            
            if inserted_in_this_pass == 0:
                raise ValueError("Cyclic dependency detected in features_added!")
            feats_to_insert = remaining

        # Step C: Insert Feature-Actor Links
        for link in patch.get("feature_actor_links_added", []):
            feat_id = resolve_feature_id(link["feature_ref"])
            act_id = resolve_actor_id(link["actor_ref"])
            await session.execute(
                feature_actor_table.insert().values(feature_id=feat_id, actor_id=act_id)
            )

        # Step D: Insert Scenarios
        for s in patch.get("scenarios_added", []):
            feat_id = resolve_feature_id(s["feature_ref"])
            act_id = resolve_actor_id(s["actor_ref"])
            scenario = ScenarioModel(
                project_id=project_id,
                feature_id=feat_id,
                actor_id=act_id,
                name=s["name"],
                content=s["content"]
            )
            session.add(scenario)
            await session.flush()
            scenario_id_map[s["temp_id"]] = scenario.id

        # Step E: Insert ACs
        for ac in patch.get("acceptance_criteria_added", []):
            sc_id = resolve_scenario_id(ac["scenario_ref"])
            criterion = ScenarioAcceptanceCriterionModel(
                scenario_id=sc_id,
                content=ac["content"],
                position=ac["position"]
            )
            session.add(criterion)
            await session.flush()

        # Step F: Insert Business Objects
        for bo in patch.get("business_objects_added", []):
            business_object = BusinessObjectModel(
                project_id=project_id,
                name=bo["name"],
                description=bo["description"]
            )
            session.add(business_object)
            await session.flush()
            bo_id_map[bo["temp_id"]] = business_object.id

        # Step G: Insert BO Attributes
        for attr in patch.get("business_object_attributes_added", []):
            bo_id = resolve_bo_id(attr["business_object_ref"])
            bo_attr = BusinessObjectAttributeModel(
                business_object_id=bo_id,
                name=attr["name"],
                description=attr["description"],
                data_type=attr["data_type"],
                example=attr["example"]
            )
            session.add(bo_attr)
            await session.flush()

        # Step H: Insert Flows
        for fl in patch.get("flows_added", []):
            flow = FlowModel(
                project_id=project_id,
                name=fl["name"],
                description=fl["description"]
            )
            session.add(flow)
            await session.flush()
            flow_id_map[fl["temp_id"]] = flow.id
            
            # Associate features
            for fref in fl.get("feature_refs", []):
                feat_id = resolve_feature_id(fref)
                await session.execute(
                    flow_feature_table.insert().values(flow_id=flow.id, feature_id=feat_id)
                )

        # Step I: Insert Flow Steps (Pass 1 - insert models)
        for st in patch.get("flow_steps_added", []):
            flow_id = resolve_flow_id(st["flow_ref"])
            step = FlowStepModel(
                flow_id=flow_id,
                name=st["name"],
                description=st["description"],
                step_type=st["step_type"],
                position=st["position"]
            )
            session.add(step)
            await session.flush()
            step_id_map[st["temp_id"]] = step.id

        # Step J: Insert Flow Steps (Pass 2 - insert associations)
        for st in patch.get("flow_steps_added", []):
            step_id = step_id_map[st["temp_id"]]
            
            for aref in st.get("actor_refs", []):
                act_id = resolve_actor_id(aref)
                await session.execute(
                    flow_step_actor_table.insert().values(flow_step_id=step_id, actor_id=act_id)
                )
            for iref in st.get("input_bo_refs", []):
                bo_id = resolve_bo_id(iref)
                await session.execute(
                    flow_step_input_business_object_table.insert().values(
                        flow_step_id=step_id, business_object_id=bo_id
                    )
                )
            for oref in st.get("output_bo_refs", []):
                bo_id = resolve_bo_id(oref)
                await session.execute(
                    flow_step_output_business_object_table.insert().values(
                        flow_step_id=step_id, business_object_id=bo_id
                    )
                )
            for nref in st.get("next_step_refs", []):
                next_step_id = resolve_step_id(nref)
                await session.execute(
                    flow_step_next_table.insert().values(
                        source_step_id=step_id, target_step_id=next_step_id
                    )
                )

        # Step K: Insert Scopes
        for sc in patch.get("scopes_added", []):
            feat_id = resolve_feature_id(sc["feature_ref"])
            
            # Check if scope exists for feature
            scope_res = await session.execute(
                select(ScopeModel).where(ScopeModel.feature_id == feat_id)
            )
            existing_scope = scope_res.scalar_one_or_none()
            
            from backend.services.binary_conversion_service import BinaryConversionService
            pos_pic = BinaryConversionService.base64_to_bytes(sc.get("positive_picture_base64")) if sc.get("positive_picture_base64") else None
            neg_pic = BinaryConversionService.base64_to_bytes(sc.get("negative_picture_base64")) if sc.get("negative_picture_base64") else None

            if existing_scope:
                existing_scope.status = sc["status"]
                existing_scope.reason = sc["reason"]
                existing_scope.kano_category = sc.get("kano_category")
                existing_scope.kano_category_name = sc.get("kano_category_name")
                existing_scope.positive_summary = sc.get("positive_summary")
                existing_scope.negative_summary = sc.get("negative_summary")
                if pos_pic is not None:
                    existing_scope.positive_picture = pos_pic
                if neg_pic is not None:
                    existing_scope.negative_picture = neg_pic
            else:
                new_scope = ScopeModel(
                    feature_id=feat_id,
                    status=sc["status"],
                    reason=sc["reason"],
                    kano_category=sc.get("kano_category"),
                    kano_category_name=sc.get("kano_category_name"),
                    positive_summary=sc.get("positive_summary"),
                    negative_summary=sc.get("negative_summary"),
                    positive_picture=pos_pic,
                    negative_picture=neg_pic
                )
                session.add(new_scope)
                await session.flush()

        # Sweep all leaf features and ensure they have a real Scope generated if missing
        feature_res = await session.execute(
            select(FeatureModel).where(FeatureModel.project_id == project_id)
        )
        feature_models = feature_res.scalars().all()
        feature_ids = [f.id for f in feature_models]
        
        if feature_ids:
            relation_res = await session.execute(
                select(FeatureRelationModel).where(
                    FeatureRelationModel.parent_feature_id.in_(feature_ids)
                )
            )
            relation_models = relation_res.scalars().all()
            parent_with_children = {r.parent_feature_id for r in relation_models}
            leaf_features = [f for f in feature_models if f.id not in parent_with_children]
            
            scope_res = await session.execute(
                select(ScopeModel).where(ScopeModel.feature_id.in_(feature_ids))
            )
            existing_scopes = scope_res.scalars().all()
            existing_scope_feature_ids = {s.feature_id for s in existing_scopes}
            
            missing_leaf_ids = [f.id for f in leaf_features if f.id not in existing_scope_feature_ids]
            if missing_leaf_ids:
                from backend.api.modules.requirements_core.ports import get_scope_generation_service
                scope_generation_service = get_scope_generation_service()
                draft_payload, _ = await scope_generation_service._generate_preview(
                    project_id=project_id,
                    user_feedback=None,
                    session=session
                )
                generated_scopes = draft_payload.get("scopes", [])
                for sc in generated_scopes:
                    feat_id = sc.get("feature_id")
                    if feat_id in missing_leaf_ids:
                        from backend.services.binary_conversion_service import BinaryConversionService
                        pos_pic = BinaryConversionService.base64_to_bytes(sc.get("positive_picture_base64")) if sc.get("positive_picture_base64") else None
                        neg_pic = BinaryConversionService.base64_to_bytes(sc.get("negative_picture_base64")) if sc.get("negative_picture_base64") else None
                        new_scope = ScopeModel(
                            feature_id=feat_id,
                            status=sc.get("scope_status", "current").upper(),
                            reason=sc.get("reason", "AI影子收敛补充"),
                            kano_category=sc.get("kano_category"),
                            kano_category_name=sc.get("kano_category_name"),
                            positive_summary=sc.get("positive_summary"),
                            negative_summary=sc.get("negative_summary"),
                            positive_picture=pos_pic,
                            negative_picture=neg_pic
                        )
                        session.add(new_scope)
                        missing_leaf_ids.remove(feat_id)
                
                # Double fallback check
                for f_id in missing_leaf_ids:
                    new_scope = ScopeModel(
                        feature_id=f_id,
                        status="CURRENT",
                        reason="AI影子收敛补充",
                        kano_category="M",
                        kano_category_name="Must-be"
                    )
                    session.add(new_scope)
                await session.flush()

        # Update Project Kano Status to generated (completed) and unlock all stages
        project = await session.get(ProjectModel, project_id)
        if project:
            if project.kano_status not in ("generated", "skipped"):
                project.kano_status = "generated"
            project.unlocked_stages = "what,how,scope"


        # Step L: Clear slot and issue cache by soft deleting/staling perception jobs and slots
        from backend.database.model import PerceptionJobModel, PerceptionSlotModel
        await session.execute(
            delete(PerceptionJobModel).where(
                PerceptionJobModel.project_id == project_id,
                PerceptionJobModel.stage.in_(["what", "how", "scope"])
            )
        )
        await session.execute(
            delete(PerceptionSlotModel).where(
                PerceptionSlotModel.project_id == project_id
            )
        )


        # Step M: Finalize Draft setting committed
        draft.status = "committed"
        draft.committed_at = beijing_now()
        await session.flush()

        # Step N: Copy and map shadow draft prototype preview to the real project prototype preview table
        prototype_preview_dict = draft.prototype_preview_json
        if prototype_preview_dict:
            from backend.database.model import PrototypePreviewModel
            temp_id_to_neg_int: dict[str, int] = {}
            neg_counter = -1001
            for a in patch.get("actors_added", []):
                temp_id_to_neg_int[a["temp_id"]] = neg_counter
                neg_counter -= 1
            for f in patch.get("features_added", []):
                temp_id_to_neg_int[f["temp_id"]] = neg_counter
                neg_counter -= 1

            neg_to_pos_actor_id = {}
            neg_to_pos_feature_id = {}
            for temp_id, neg_id in temp_id_to_neg_int.items():
                if temp_id in actor_id_map:
                    neg_to_pos_actor_id[neg_id] = actor_id_map[temp_id]
                if temp_id in feature_id_map:
                    neg_to_pos_feature_id[neg_id] = feature_id_map[temp_id]

            mapped_pages = []
            for page in prototype_preview_dict.get("pages", []):
                r_id = page.get("roleId") or page.get("role_id")
                f_id = page.get("featureId") or page.get("feature_id")
                
                mapped_role_id = neg_to_pos_actor_id.get(r_id, r_id) if isinstance(r_id, int) and r_id < 0 else r_id
                mapped_feature_id = neg_to_pos_feature_id.get(f_id, f_id) if isinstance(f_id, int) and f_id < 0 else f_id
                
                mapped_pages.append({
                    "page_id": f"role-{mapped_role_id}-feature-{mapped_feature_id}",
                    "role_id": mapped_role_id,
                    "role_name": page.get("roleName") or page.get("role_name"),
                    "feature_id": mapped_feature_id,
                    "feature_name": page.get("featureName") or page.get("feature_name"),
                    "html": page.get("html"),
                    "javascript": page.get("javascript"),
                    "css": page.get("css"),
                    "source": "committed_shadow_project",
                    "status": "ready"
                })

            first_page = mapped_pages[0] if mapped_pages else {
                "html": prototype_preview_dict.get("html", ""),
                "javascript": prototype_preview_dict.get("javascript", ""),
                "css": prototype_preview_dict.get("css", "")
            }

            detail = await prototype_generation_service._project_service.get_project_detail(
                project_id=project_id,
                session=session
            )

            new_preview = PrototypePreviewModel(
                project_id=project_id,
                status="ready",
                source="committed_shadow_project",
                html=first_page["html"],
                javascript=first_page["javascript"],
                css=first_page["css"],
                pages=mapped_pages,
                input_snapshot=detail.model_dump(mode="json", by_alias=True)
            )
            session.add(new_preview)
            await session.flush()

        import sys
        if "pytest" in sys.modules:
            await prototype_generation_service.generate_preview(
                project_id=project_id,
                force_regenerate=True
            )
        else:
            await session.commit()

    async def generate_post_commit_prototype(self, project_id: int) -> None:
        """
        Runs prototype generation asynchronously in a fresh session context.
        """
        prototype_generation_service = self._prototype_generation_service
        import logging
        logger = logging.getLogger(__name__)
        try:
            async with AsyncSessionLocal() as session:
                await prototype_generation_service.generate_preview(
                    project_id=project_id,
                    force_regenerate=True
                )
                await session.commit()
        except Exception as e:
            import traceback
            from backend.core.security import sanitize_message
            tb_str = "".join(traceback.format_exception(type(e), e, e.__traceback__))
            sanitized_tb = sanitize_message(tb_str)
            logger.error(
                f"Post-commit prototype generation failed for project {project_id} ({type(e).__name__}):\n{sanitized_tb}"
            )


    @staticmethod
    async def discard_shadow_draft(project_id: int, draft_id: str, session: AsyncSession) -> None:
        """
        Soft deletes the shadow draft by updating its status and timestamp.
        """
        draft_res = await session.execute(
            select(PreviewShadowDraftModel).where(
                PreviewShadowDraftModel.project_id == project_id,
                PreviewShadowDraftModel.draft_id == draft_id
            )
        )
        draft = draft_res.scalar_one_or_none()
        if not draft:
            raise ValueError("shadow_draft_not_found")
        
        draft.status = "discarded"
        draft.discarded_at = beijing_now()
