from __future__ import annotations

from sqlalchemy import delete, select

from backend.database.database import AsyncSessionLocal
from backend.database.model import GenerativeDraftModel


class GenerativeDraftStore:
    """Manages database storage and persistence for all generative drafts.

    Replaces standard in-memory dicts with a durable SQLite table.
    """

    @staticmethod
    async def save_draft(
        project_id: int | None,
        draft_id: str,
        draft_type: str,
        payload: dict,
        owner_user_id: int,
        session = None,
    ) -> None:
        """Saves or updates a draft in the database."""
        await session.execute(
            delete(GenerativeDraftModel).where(
                GenerativeDraftModel.draft_id == draft_id,
                GenerativeDraftModel.owner_user_id == owner_user_id,
            )
        )
        db_draft = GenerativeDraftModel(
            project_id=project_id,
            draft_id=draft_id,
            draft_type=draft_type,
            payload=payload,
            owner_user_id=owner_user_id,
        )
        session.add(db_draft)
        await session.flush()

    @staticmethod
    async def get_draft(draft_id: str, owner_user_id: int, session = None) -> dict:
        """Retrieves a draft from the database.

        Raises ValueError('draft_not_found') if not found.
        """
        result = await session.execute(
            select(GenerativeDraftModel).where(
                GenerativeDraftModel.draft_id == draft_id,
                GenerativeDraftModel.owner_user_id == owner_user_id,
            )
        )
        db_draft = result.scalar_one_or_none()
        if db_draft is None:
            raise ValueError("draft_not_found")
        return db_draft.payload

    @staticmethod
    async def delete_draft(draft_id: str, owner_user_id: int, session = None) -> None:
        """Deletes a draft from the database using an existing active session."""
        await session.execute(
            delete(GenerativeDraftModel).where(
                GenerativeDraftModel.draft_id == draft_id,
                GenerativeDraftModel.owner_user_id == owner_user_id,
            )
        )

    @staticmethod
    async def discard_draft_locally(draft_id: str, owner_user_id: int) -> None:
        """Deletes a draft asynchronously using a localized database session."""
        async with AsyncSessionLocal() as session:
            await session.execute(
                delete(GenerativeDraftModel).where(
                    GenerativeDraftModel.draft_id == draft_id,
                    GenerativeDraftModel.owner_user_id == owner_user_id,
                )
            )
            await session.commit()
