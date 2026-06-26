"""
Draft handler for managing AI-powered generative drafts.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import select

from backend.api.modules.requirements_core.public import (
    ActorUpdateRequest,
    FeatureUpdateRequest,
    FlowUpdateRequest,
    BOUpdateRequest,
)

logger = logging.getLogger(__name__)

BEIJING_TZ = ZoneInfo("Asia/Shanghai")


def _beijing_now() -> datetime:
    return datetime.now(BEIJING_TZ)


class AIAddDraftHandler:
    """Handles the lifecycle of generative drafts generated during AI sessions."""

    def __init__(self, service):
        self._service = service

    async def generate_draft(self, session_id: int, db_session, owner_user_id: int) -> dict:
        """Generate a draft — dispatches to add or edit path based on target_type."""
        from backend.database.model import ProjectModel

        ai_session = await self._get_session_or_raise(session_id, db_session)

        if ai_session.status not in ("ready", "active"):
            raise ValueError(f"session_invalid_status: {ai_session.status}")
        if not ai_session.ready_to_generate:
            raise ValueError("session_not_ready")
        if not ai_session.summary_payload:
            raise ValueError("empty_summary_payload")

        await self._validate_anchor_references(
            ai_session.project_id, ai_session.target_type,
            ai_session.anchor_payload, db_session,
        )

        project_result = await db_session.execute(
            select(ProjectModel).where(ProjectModel.id == ai_session.project_id)
        )
        project = project_result.scalar_one_or_none()
        if project is None:
            raise ValueError("project_not_found")

        if ai_session.target_type.startswith("edit_"):
            return await self._generate_edit_draft(
                ai_session, project, owner_user_id, db_session,
            )
        return await self._generate_add_draft(
            ai_session, project, owner_user_id, db_session,
        )

    async def _generate_add_draft(self, ai_session, project, owner_user_id: int, db_session) -> dict:
        """Generate an add-mode draft (original Phase 2 logic)."""
        from backend.api.modules.decision_workflow.public import GenerativeDraftStore

        generator_ctx_keys = self._generator_ctx_keys(ai_session.target_type)
        project_context = await self._service._load_context(
            ai_session.project_id, generator_ctx_keys, db_session,
        )

        from backend.core.generators.single_object import SingleObjectGeneratorInput
        gen_input = SingleObjectGeneratorInput(
            user_requirements=project.user_requirements,
            project_context=project_context,
            conversation_summary=ai_session.summary_payload or {},
        )

        generator = self._service._get_generator(ai_session.target_type)
        try:
            raw_result = await generator.generate(gen_input)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            logger.error("AI add generator LLM parse failed  session_id=%s  error=%s", ai_session.id, exc)
            raise ValueError("generator_output_parse_failed") from exc

        validated = self._validate_generated_object(ai_session.target_type, raw_result, project_context)
        preview = self._build_preview(ai_session.target_type, validated)

        draft_id = uuid4().hex
        await GenerativeDraftStore.save_draft(
            project_id=ai_session.project_id, draft_id=draft_id,
            draft_type=f"single_{ai_session.target_type}",
            payload={
                "project_id": ai_session.project_id,
                "session_id": ai_session.id,
                "target_type": ai_session.target_type,
                "summary": ai_session.summary_payload or {},
                "generated_object": validated,
                "preview": preview,
                "rationale": raw_result.get("rationale", ""),
            },
            owner_user_id=owner_user_id,
            session=db_session,
        )

        ai_session.status = "draft_created"
        await db_session.flush()

        return {
            "draft_id": draft_id, "project_id": project.public_id,
            "target_type": ai_session.target_type, "preview": preview,
            "message": "draft_created",
        }

    async def _generate_edit_draft(self, ai_session, project, owner_user_id: int, db_session) -> dict:
        """Generate an edit-mode draft: load original object, call EditGenerator, validate diff."""
        from backend.api.modules.decision_workflow.public import GenerativeDraftStore
        from backend.core.generators.single_object.base_edit_generator import EditGeneratorInput
        from backend.api.modules.ai_interaction.ai_add.application.permissions import EDITABLE_FIELDS

        # Extract base target_type (strip "edit_" prefix)
        base_type = ai_session.target_type.replace("edit_", "", 1)

        # Load the original object from DB
        original_obj = await self._load_original_object(
            base_type, ai_session.anchor_payload, ai_session.project_id, db_session,
        )

        generator_ctx_keys = self._generator_ctx_keys(ai_session.target_type)
        project_context = await self._service._load_context(
            ai_session.project_id, generator_ctx_keys, db_session,
        )

        editable = EDITABLE_FIELDS.get(base_type, [])

        gen_input = EditGeneratorInput(
            user_requirements=project.user_requirements,
            project_context=project_context,
            conversation_summary=ai_session.summary_payload or {},
            target_type=base_type,
            original_object=original_obj,
            editable_fields=editable,
        )

        generator = self._service._get_generator(ai_session.target_type)
        try:
            raw_result = await generator.generate(gen_input)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            logger.error("AI edit generator LLM parse failed  session_id=%s  error=%s", ai_session.id, exc)
            raise ValueError("generator_output_parse_failed") from exc

        # Validate edit diff
        self._validate_edit_diff(base_type, raw_result.get("diff", {}))

        diff = raw_result.get("diff", {})
        rationale = raw_result.get("rationale", "")

        # Build preview showing old → new
        preview = {}
        for field, change in diff.items():
            preview[field] = {"old": change.get("old", ""), "new": change.get("new", "")}

        draft_id = uuid4().hex
        await GenerativeDraftStore.save_draft(
            project_id=ai_session.project_id, draft_id=draft_id,
            draft_type=f"single_{ai_session.target_type}",
            payload={
                "project_id": ai_session.project_id,
                "session_id": ai_session.id,
                "target_type": ai_session.target_type,
                "summary": ai_session.summary_payload or {},
                "original_object": original_obj,
                "diff": diff,
                "preview": preview,
                "rationale": rationale,
            },
            owner_user_id=owner_user_id,
            session=db_session,
        )

        ai_session.status = "draft_created"
        await db_session.flush()

        return {
            "draft_id": draft_id, "project_id": project.public_id,
            "target_type": ai_session.target_type, "preview": preview,
            "message": "draft_created",
        }

    async def confirm_draft(self, draft_id: str, db_session, owner_user_id: int) -> dict:
        """Confirm a draft — dispatches to add or edit path based on target_type."""
        from backend.api.modules.decision_workflow.public import GenerativeDraftStore

        draft = await GenerativeDraftStore.get_draft(draft_id, owner_user_id, db_session)
        target_type = draft.get("target_type", "")
        project_id = draft.get("project_id")
        session_id = draft.get("session_id")

        if not project_id:
            raise ValueError("invalid_draft_payload")

        if target_type.startswith("edit_"):
            created_id = await self._confirm_edit_draft(draft, db_session)
        else:
            generated = draft.get("generated_object", {})
            await self._pre_confirm_validation(target_type, generated, project_id, db_session)
            created_id = await self._persist_generated_object(
                target_type, generated, project_id, db_session,
            )

        # Update session status
        if session_id:
            ai_session = await self._get_session_or_raise(session_id, db_session)
            ai_session.status = "confirmed"
            ai_session.closed_at = _beijing_now()
            await db_session.flush()

        await GenerativeDraftStore.delete_draft(draft_id, owner_user_id, db_session)

        logger.info(
            "AI draft confirmed  draft_id=%s  target_type=%s  project_id=%s  created_id=%s",
            draft_id, target_type, project_id, created_id,
        )

        return {
            "draft_id": draft_id,
            "message": "confirmed",
            "created_object_id": created_id,
        }

    async def discard_draft(self, draft_id: str, db_session, owner_user_id: int) -> dict:
        """Discard a draft without persisting."""
        from backend.api.modules.decision_workflow.public import GenerativeDraftStore

        try:
            draft = await GenerativeDraftStore.get_draft(draft_id, owner_user_id, db_session)
            session_id = draft.get("session_id")
            if session_id:
                ai_session = await self._get_session_or_raise(session_id, db_session)
                if ai_session.status == "draft_created":
                    ai_session.status = "discarded"
                    ai_session.closed_at = _beijing_now()
                await db_session.flush()
        except ValueError:
            pass

        await GenerativeDraftStore.delete_draft(draft_id, owner_user_id, db_session)

        logger.info("AI add draft discarded  draft_id=%s", draft_id)

        return {
            "draft_id": draft_id,
            "message": "draft_discarded",
        }

    @staticmethod
    def _generator_ctx_keys(target_type: str) -> list[str]:
        """Return the project context keys needed by the generator for a target_type."""
        lookup = target_type.replace("edit_", "", 1)
        _map = {
            "actor": ["actors"],
            "feature_leaf": ["features", "actors"],
            "feature_branch": ["features", "actors"],
            "feature": ["features", "actors"],
            "flow": ["features", "flows"],
            "business_object": ["business_objects", "flows"],
        }
        return _map.get(lookup, [])

    @staticmethod
    def _validate_generated_object(
        target_type: str, raw: dict, project_context: dict,
    ) -> dict:
        """Validate the generator output and return a cleaned/normalized dict."""
        if target_type == "actor":
            actor = raw.get("actor", {})
            name = (actor.get("name") or "").strip()
            if not name:
                raise ValueError("empty_actor_name")
            existing = {a.get("name", "").strip() for a in project_context.get("actors", [])}
            if name in existing:
                raise ValueError("duplicate_actor_name")
            return {
                "name": name,
                "description": (actor.get("description") or "").strip(),
            }

        elif target_type in ("feature_leaf", "feature_branch"):
            feature = raw.get("feature", {})
            name = (feature.get("name") or "").strip()
            if not name:
                raise ValueError("empty_feature_name")
            feature_kind = (feature.get("feature_kind") or "").strip()
            if feature_kind not in ("leaf", "branch"):
                raise ValueError("invalid_feature_kind")
            actor_ids = feature.get("actor_ids", []) or []
            valid_ids = {a.get("id") for a in project_context.get("actors", [])}
            for aid in actor_ids:
                if aid not in valid_ids:
                    raise ValueError(f"invalid_actor_reference: {aid}")
            return {
                "name": name,
                "description": (feature.get("description") or "").strip(),
                "parent_id": feature.get("parent_id"),
                "actor_ids": actor_ids,
                "feature_kind": feature_kind,
            }

        elif target_type == "flow":
            flow = raw.get("flow", {})
            name = (flow.get("name") or "").strip()
            if not name:
                raise ValueError("empty_flow_name")
            feature_ids = flow.get("feature_ids", []) or []
            if not feature_ids:
                raise ValueError("empty_flow_feature_ids")
            valid_ids = {f.get("id") for f in project_context.get("features", [])}
            for fid in feature_ids:
                if fid not in valid_ids:
                    raise ValueError(f"invalid_feature_reference: {fid}")
            return {
                "name": name,
                "description": (flow.get("description") or "").strip(),
                "feature_ids": feature_ids,
            }

        elif target_type == "business_object":
            bo = raw.get("business_object", {})
            name = (bo.get("name") or "").strip()
            if not name:
                raise ValueError("empty_business_object_name")
            existing = {b.get("name", "").strip() for b in project_context.get("business_objects", [])}
            if name in existing:
                raise ValueError("duplicate_business_object_name")
            attrs = bo.get("attributes", []) or []
            cleaned_attrs = []
            seen_attr_names = set()
            for attr in attrs:
                aname = (attr.get("name") or "").strip()
                if not aname:
                    continue
                if aname in seen_attr_names:
                    continue
                seen_attr_names.add(aname)
                cleaned_attrs.append({
                    "name": aname,
                    "description": (attr.get("description") or "").strip(),
                    "data_type": (attr.get("data_type") or "").strip(),
                    "example": (attr.get("example") or "").strip(),
                })
            return {
                "name": name,
                "description": (bo.get("description") or "").strip(),
                "attributes": cleaned_attrs,
            }

        else:
            raise ValueError(f"unsupported_target_type: {target_type}")

    @staticmethod
    def _build_preview(target_type: str, validated: dict) -> dict:
        """Build a human-readable preview dict (no raw LLM JSON)."""
        if target_type == "actor":
            return {
                "name": validated["name"],
                "description": validated["description"],
            }
        elif target_type in ("feature_leaf", "feature_branch"):
            return {
                "name": validated["name"],
                "description": validated["description"],
                "parent_id": validated.get("parent_id"),
                "actor_ids": validated.get("actor_ids", []),
                "feature_kind": validated["feature_kind"],
            }
        elif target_type == "flow":
            return {
                "name": validated["name"],
                "description": validated["description"],
                "feature_ids": validated.get("feature_ids", []),
            }
        elif target_type == "business_object":
            return {
                "name": validated["name"],
                "description": validated["description"],
                "attribute_count": len(validated.get("attributes", [])),
            }
        return validated

    @staticmethod
    async def _pre_confirm_validation(
        target_type: str, generated: dict, project_id: int, db_session,
    ) -> None:
        """Re-validate that the generated object can still be persisted."""
        from backend.database.model import (
            ActorModel, FeatureModel, FlowModel, BusinessObjectModel,
        )

        if target_type == "actor":
            name = generated.get("name", "").strip()
            if not name:
                raise ValueError("empty_actor_name")
            result = await db_session.execute(
                select(ActorModel).where(
                    ActorModel.project_id == project_id,
                    ActorModel.name == name,
                )
            )
            if result.scalar_one_or_none() is not None:
                raise ValueError("duplicate_actor_name")

        elif target_type in ("feature_leaf", "feature_branch"):
            name = generated.get("name", "").strip()
            if not name:
                raise ValueError("empty_feature_name")
            parent_id = generated.get("parent_id")
            feature_result = await db_session.execute(
                select(FeatureModel).where(
                    FeatureModel.project_id == project_id,
                    FeatureModel.name == name,
                )
            )
            for existing in feature_result.scalars().all():
                from backend.database.model import FeatureRelationModel
                rel_result = await db_session.execute(
                    select(FeatureRelationModel).where(
                        FeatureRelationModel.child_feature_id == existing.id,
                    )
                )
                rel = rel_result.scalar_one_or_none()
                existing_parent_id = rel.parent_feature_id if rel else None
                if existing_parent_id == parent_id:
                    raise ValueError("duplicate_feature_name_under_same_parent")

        elif target_type == "flow":
            name = generated.get("name", "").strip()
            if not name:
                raise ValueError("empty_flow_name")
            result = await db_session.execute(
                select(FlowModel).where(
                    FlowModel.project_id == project_id,
                    FlowModel.name == name,
                )
            )
            if result.scalar_one_or_none() is not None:
                raise ValueError("duplicate_flow_name")

        elif target_type == "business_object":
            name = generated.get("name", "").strip()
            if not name:
                raise ValueError("empty_business_object_name")
            result = await db_session.execute(
                select(BusinessObjectModel).where(
                    BusinessObjectModel.project_id == project_id,
                    BusinessObjectModel.name == name,
                )
            )
            if result.scalar_one_or_none() is not None:
                raise ValueError("duplicate_business_object_name")

    @staticmethod
    async def _load_original_object(
        base_type: str, anchor: dict, project_id: int, db_session,
    ) -> dict:
        """Load the current state of the object being edited from the database."""
        target_id = anchor.get("target_id")
        if not target_id:
            raise ValueError("invalid_edit_anchor")

        from backend.database.model import (
            ActorModel, FeatureModel, FlowModel, BusinessObjectModel,
        )

        if base_type == "actor":
            obj = await db_session.get(ActorModel, target_id)
            if obj is None:
                raise ValueError("target_not_found")
            return {"id": obj.id, "name": obj.name, "description": obj.description}

        elif base_type == "feature":
            obj = await db_session.get(FeatureModel, target_id)
            if obj is None:
                raise ValueError("target_not_found")
            from backend.database.model import feature_actor_table
            actor_result = await db_session.execute(
                select(feature_actor_table.c.actor_id).where(
                    feature_actor_table.c.feature_id == target_id
                )
            )
            actor_ids = [row[0] for row in actor_result.all()]
            return {
                "id": obj.id, "name": obj.name, "description": obj.description,
                "actor_ids": actor_ids,
            }

        elif base_type == "flow":
            obj = await db_session.get(FlowModel, target_id)
            if obj is None:
                raise ValueError("target_not_found")
            from backend.database.model import flow_feature_table
            feat_result = await db_session.execute(
                select(flow_feature_table.c.feature_id).where(
                    flow_feature_table.c.flow_id == target_id
                )
            )
            feature_ids = [row[0] for row in feat_result.all()]
            return {
                "id": obj.id, "name": obj.name, "description": obj.description,
                "feature_ids": feature_ids,
            }

        elif base_type == "business_object":
            obj = await db_session.get(BusinessObjectModel, target_id)
            if obj is None:
                raise ValueError("target_not_found")
            return {"id": obj.id, "name": obj.name, "description": obj.description}

        raise ValueError(f"unsupported_target_type: {base_type}")

    @staticmethod
    def _validate_edit_diff(base_type: str, diff: dict) -> None:
        """Validate that all diff fields are within EDITABLE_FIELDS."""
        from backend.api.modules.ai_interaction.ai_add.application.permissions import EDITABLE_FIELDS

        if not diff:
            raise ValueError("edit_diff_empty")

        editable = set(EDITABLE_FIELDS.get(base_type, []))
        for field in diff:
            if field not in editable:
                raise ValueError(f"field_not_editable: {field}")
            change = diff[field]
            if "old" not in change or "new" not in change:
                raise ValueError(f"edit_diff_validation_failed: {field} missing old/new")

    async def _confirm_edit_draft(self, draft: dict, db_session) -> int | None:
        """Confirm an edit draft: re-validate, apply diff via update CRUD."""
        from backend.api.modules.ai_interaction.ai_add.application.permissions import EDITABLE_FIELDS

        target_type = draft.get("target_type", "")
        base_type = target_type.replace("edit_", "", 1)
        diff = draft.get("diff", {})
        project_id = draft.get("project_id")

        if not diff:
            raise ValueError("edit_diff_empty")

        self._validate_edit_diff(base_type, diff)
        await self._validate_edit_references(base_type, diff, project_id, db_session)

        anchor = {"target_id": draft.get("original_object", {}).get("id")}
        if not anchor["target_id"]:
            session_id = draft.get("session_id")
            if session_id:
                ai_session = await self._get_session_or_raise(session_id, db_session)
                anchor = ai_session.anchor_payload

        original = await self._load_original_object(base_type, anchor, project_id, db_session)

        update_payload = {}
        for field, change in diff.items():
            update_payload[field] = change["new"]

        created_id = original.get("id")

        if base_type == "actor":
            from backend.api.modules.requirements_core.public import ActorService
            req = ActorUpdateRequest(**{k: v for k, v in update_payload.items() if k in EDITABLE_FIELDS["actor"]})
            await ActorService().update_actor(project_id, created_id, req, db_session)

        elif base_type == "feature":
            from backend.api.modules.requirements_core.public import FeatureService
            req = FeatureUpdateRequest(**{k: v for k, v in update_payload.items() if k in EDITABLE_FIELDS["feature"]})
            await FeatureService().update_feature(project_id, created_id, req, db_session)

        elif base_type == "flow":
            from backend.api.modules.requirements_core.public import FlowService
            req = FlowUpdateRequest(**{k: v for k, v in update_payload.items() if k in EDITABLE_FIELDS["flow"]})
            await FlowService().update_flow(project_id, created_id, req, db_session)

        elif base_type == "business_object":
            from backend.api.modules.requirements_core.public import BusinessObjectService
            req = BOUpdateRequest(**{k: v for k, v in update_payload.items() if k in EDITABLE_FIELDS["business_object"]})
            await BusinessObjectService().update_bo(project_id, created_id, req, db_session)

        return created_id

    @staticmethod
    async def _validate_edit_references(
        base_type: str, diff: dict, project_id: int, db_session,
    ) -> None:
        """Validate that reference IDs in edit diff still exist."""
        from backend.database.model import ActorModel, FeatureModel

        if base_type == "feature" and "actor_ids" in diff:
            new_ids = diff["actor_ids"].get("new", [])
            if new_ids:
                result = await db_session.execute(
                    select(ActorModel.id).where(
                        ActorModel.project_id == project_id,
                        ActorModel.id.in_(new_ids),
                    )
                )
                existing = {row[0] for row in result.all()}
                missing = [aid for aid in new_ids if aid not in existing]
                if missing:
                    raise ValueError(f"invalid_actor_reference: {missing}")

        if base_type == "flow" and "feature_ids" in diff:
            new_ids = diff["feature_ids"].get("new", [])
            if new_ids:
                result = await db_session.execute(
                    select(FeatureModel.id).where(
                        FeatureModel.project_id == project_id,
                        FeatureModel.id.in_(new_ids),
                    )
                )
                existing = {row[0] for row in result.all()}
                missing = [fid for fid in new_ids if fid not in existing]
                if missing:
                    raise ValueError(f"invalid_feature_reference: {missing}")

    async def _persist_generated_object(
        self, target_type: str, generated: dict, project_id: int, db_session,
    ) -> int | None:
        """Persist the generated object via the appropriate CRUD service."""
        from backend.api.modules.requirements_core.public import (
            ActorCreateRequest,
            FeatureCreateRequest,
            FeatureUpdateRequest,
            FlowCreateRequest,
            BOCreateRequest,
            BOAttributeCreateRequest,
        )

        if target_type == "actor":
            from backend.api.modules.requirements_core.public import ActorService
            svc = ActorService()
            req = ActorCreateRequest(name=generated["name"], description=generated.get("description", ""))
            result = await svc.create_actor(project_id, req, db_session, confirmation_status='ai_assumption')
            return result.actor_id

        elif target_type in ("feature_leaf", "feature_branch"):
            from backend.api.modules.requirements_core.public import FeatureService
            svc = FeatureService()
            req = FeatureCreateRequest(
                name=generated["name"],
                description=generated.get("description", ""),
                parent_id=generated.get("parent_id"),
            )
            result = await svc.create_feature(project_id, req, db_session, confirmation_status='ai_assumption')
            actor_ids = generated.get("actor_ids", [])
            if actor_ids:
                update_req = FeatureUpdateRequest(actor_ids=actor_ids)
                await svc.update_feature(project_id, result.feature_id, update_req, db_session)
            return result.feature_id

        elif target_type == "flow":
            from backend.api.modules.requirements_core.public import FlowService
            svc = FlowService()
            req = FlowCreateRequest(
                name=generated["name"],
                description=generated.get("description", ""),
                feature_ids=generated.get("feature_ids", []),
            )
            result = await svc.create_flow(project_id, req, db_session, confirmation_status='ai_assumption')
            return result.flow_id

        elif target_type == "business_object":
            from backend.api.modules.requirements_core.public import BusinessObjectService
            svc = BusinessObjectService()
            req = BOCreateRequest(name=generated["name"], description=generated.get("description", ""))
            bo_result = await svc.create_bo(project_id, req, db_session, confirmation_status='ai_assumption')
            for attr in generated.get("attributes", []):
                attr_req = BOAttributeCreateRequest(
                    name=attr["name"],
                    description=attr.get("description", ""),
                    data_type=attr.get("data_type", "string"),
                    example=attr.get("example", ""),
                )
                await svc.create_bo_attribute(project_id, bo_result.business_object_id, attr_req, db_session)
            return bo_result.business_object_id

        return None

    @staticmethod
    async def _get_session_or_raise(session_id: int, session):
        """Load AIAddSessionModel by id, raise ValueError if not found."""
        from backend.database.model import AIAddSessionModel
        result = await session.execute(
            select(AIAddSessionModel).where(AIAddSessionModel.id == session_id)
        )
        db_session = result.scalar_one_or_none()
        if db_session is None:
            raise ValueError("session_not_found")
        return db_session

    @staticmethod
    async def _validate_anchor_references(
        project_id: int,
        target_type: str,
        anchor: dict,
        session,
    ) -> None:
        """Check that objects referenced in anchor still exist."""
        from backend.database.model import FeatureModel, FlowModel

        parent_feature_id = anchor.get("parent_feature_id")
        related_flow_id = anchor.get("related_flow_id")
        feature_ids = anchor.get("feature_ids", [])

        if parent_feature_id is not None:
            result = await session.execute(
                select(FeatureModel).where(
                    FeatureModel.id == parent_feature_id,
                    FeatureModel.project_id == project_id,
                )
            )
            if result.scalar_one_or_none() is None:
                raise ValueError("anchor_reference_not_found: parent_feature_id")

        if related_flow_id is not None:
            result = await session.execute(
                select(FlowModel).where(
                    FlowModel.id == related_flow_id,
                    FlowModel.project_id == project_id,
                )
            )
            if result.scalar_one_or_none() is None:
                raise ValueError("anchor_reference_not_found: related_flow_id")

        if feature_ids:
            result = await session.execute(
                select(FeatureModel).where(
                    FeatureModel.id.in_(feature_ids),
                    FeatureModel.project_id == project_id,
                )
            )
            existing = {r.id for r in result.scalars().all()}
            missing = [fid for fid in feature_ids if fid not in existing]
            if missing:
                raise ValueError(f"anchor_reference_not_found: feature_ids={missing}")
