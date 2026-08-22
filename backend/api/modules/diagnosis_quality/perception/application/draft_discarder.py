class PerceptionDraftDiscarder:
    async def discard_draft(
        self,
        draft_id: str,
        owner_user_id: int,
        session=None,
    ) -> dict:
        from backend.api.modules.decision_workflow.public import GenerativeDraftStore
        if session is not None:
            await GenerativeDraftStore.discard_draft(session, draft_id, owner_user_id)
        else:
            await GenerativeDraftStore.discard_draft_locally(draft_id, owner_user_id)

        return {
            "draft_id": draft_id,
            "message": "draft_discarded",
        }
