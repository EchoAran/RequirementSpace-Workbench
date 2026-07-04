# -*- coding: utf-8 -*-
from sqlalchemy import select, update
from backend.database.model import (
    KnowledgeWorkspaceModel,
    KnowledgeDocumentModel,
    KnowledgeChunkModel
)

class KnowledgeWorkspaceService:
    @staticmethod
    async def bind_workspace_to_project(
        *,
        session,
        workspace_public_id: str,
        project_id: int,
        owner_user_id: int | None = None,
        require_active: bool = True,
    ) -> None:
        """Bind all documents and chunks of a creation-phase workspace to a real project."""
        if not workspace_public_id:
            return

        ws_res = await session.execute(
            select(KnowledgeWorkspaceModel).where(KnowledgeWorkspaceModel.public_id == workspace_public_id)
        )
        ws = ws_res.scalar_one_or_none()
        if not ws:
            raise ValueError("workspace_not_found")
        if owner_user_id is not None and ws.owner_user_id != owner_user_id:
            raise ValueError("forbidden")
        if require_active and ws.status != "active":
            raise ValueError("workspace_inactive")

        # 1. Update workspace status and link to project
        ws.status = "attached"
        ws.project_id = project_id

        # 2. Bind active documents to the project
        await session.execute(
            update(KnowledgeDocumentModel)
            .where(
                KnowledgeDocumentModel.workspace_id == ws.id,
                KnowledgeDocumentModel.status != "deleted"
            )
            .values(project_id=project_id)
        )

        # 3. Bind chunks to the project
        active_document_ids = (
            select(KnowledgeDocumentModel.id)
            .where(
                KnowledgeDocumentModel.workspace_id == ws.id,
                KnowledgeDocumentModel.status != "deleted"
            )
        )
        await session.execute(
            update(KnowledgeChunkModel)
            .where(
                KnowledgeChunkModel.workspace_id == ws.id,
                KnowledgeChunkModel.document_id.in_(active_document_ids)
            )
            .values(project_id=project_id)
        )
