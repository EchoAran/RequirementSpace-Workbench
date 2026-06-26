import logging
from sqlalchemy import select
from backend.database.model import AIAddSessionModel, ProjectModel

logger = logging.getLogger(__name__)


class AIAddSessionCreator:
    def __init__(self, strategy_registry):
        self._strategy_registry = strategy_registry

    @staticmethod
    async def _load_project_actors(project_id: int, session) -> list[dict]:
        from backend.database.model import ActorModel
        result = await session.execute(
            select(ActorModel).where(ActorModel.project_id == project_id)
        )
        actors = result.scalars().all()
        return [{"id": a.id, "name": a.name, "description": a.description} for a in actors]

    @staticmethod
    async def _load_project_feature_tree(project_id: int, session) -> list[dict]:
        from backend.database.model import FeatureModel
        from sqlalchemy.orm import selectinload
        result = await session.execute(
            select(FeatureModel)
            .where(FeatureModel.project_id == project_id)
            .options(selectinload(FeatureModel.parent_relation))
        )
        features = result.scalars().all()
        return [{
            "id": f.id,
            "name": f.name,
            "parent_id": f.parent_relation.parent_feature_id if f.parent_relation else None,
        } for f in features]

    @staticmethod
    async def _load_project_flows(project_id: int, session) -> list[dict]:
        from backend.database.model import FlowModel
        result = await session.execute(
            select(FlowModel).where(FlowModel.project_id == project_id)
        )
        flows = result.scalars().all()
        return [{"id": f.id, "name": f.name} for f in flows]

    @staticmethod
    async def _load_project_business_objects(project_id: int, session) -> list[dict]:
        from backend.database.model import BusinessObjectModel
        result = await session.execute(
            select(BusinessObjectModel).where(BusinessObjectModel.project_id == project_id)
        )
        bos = result.scalars().all()
        return [{"id": b.id, "name": b.name} for b in bos]

    _CONTEXT_LOADERS = {
        "actors": _load_project_actors,
        "features": _load_project_feature_tree,
        "flows": _load_project_flows,
        "business_objects": _load_project_business_objects,
    }

    async def create_session(
        self,
        project_id: str,
        target_type: str,
        anchor: dict,
        session,
        owner_user_id: int,
    ) -> dict:
        """Create a new AI add session. Validates target_type and anchor references."""
        # Validate target_type
        if not self._strategy_registry.has_type(target_type):
            raise ValueError(f"unsupported_target_type: {target_type}")

        # Validate project exists and is owned by the user
        project_result = await session.execute(
            select(ProjectModel).where(
                ProjectModel.public_id == project_id,
                ProjectModel.owner_user_id == owner_user_id,
            )
        )
        project = project_result.scalar_one_or_none()
        if project is None:
            raise ValueError("project_not_found")

        # Validate anchor references exist
        await self._validate_anchor_references(project.id, target_type, anchor, session)

        # Create session
        db_session = AIAddSessionModel(
            project_id=project.id,
            target_type=target_type,
            anchor_payload=anchor,
            status="active",
            ready_to_generate=False,
        )
        session.add(db_session)
        await session.flush()

        logger.info(
            "AI add session created  session_id=%s  project_id=%s  target_type=%s",
            db_session.id, project.public_id, target_type,
        )

        return {
            "session_id": db_session.id,
            "project_id": project.public_id,
            "target_type": db_session.target_type,
            "anchor_payload": db_session.anchor_payload,
            "status": db_session.status,
            "ready_to_generate": db_session.ready_to_generate,
            "created_at": db_session.created_at.isoformat() if db_session.created_at else None,
        }

    async def _validate_anchor_references(
        self,
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
