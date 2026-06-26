from typing import Protocol, Any

class ChoiceGroupCreator(Protocol):
    async def create_choice_group(
        self,
        project_id: int,
        generation_type: str,
        target: dict | None = None,
        candidate_count: int | None = None,
        user_feedback: str | None = None,
        session: Any = None,
        progress_callback: Any = None,
        issue_code: str | None = None,
        issue_id: str | None = None,
        stage: str | None = None,
        source_type: str | None = None,
        source_id: str | None = None,
        context_hash: str | None = None,
    ) -> dict:
        ...

class ChoiceGroupSettings(Protocol):
    def is_generation_type_enabled(self, generation_type: str) -> bool:
        ...

class GenerationDraftCreatorPort(Protocol):
    async def create_scenario_draft(
        self,
        project_id: int,
        feature_id: int,
        actor_id: int,
        session: Any,
    ) -> dict:
        ...

    async def create_ac_draft(
        self,
        project_id: int,
        scenario_id: int,
        session: Any,
    ) -> dict:
        ...

    async def create_scope_draft(
        self,
        project_id: int,
        session: Any,
    ) -> dict:
        ...

# Global registry for DIP
_choice_group_creator: ChoiceGroupCreator | None = None
_choice_group_settings: ChoiceGroupSettings | None = None
_generation_draft_creator: GenerationDraftCreatorPort | None = None

def get_choice_group_creator() -> ChoiceGroupCreator | None:
    return _choice_group_creator

def set_choice_group_creator(creator: ChoiceGroupCreator):
    global _choice_group_creator
    _choice_group_creator = creator

def get_choice_group_settings() -> ChoiceGroupSettings | None:
    return _choice_group_settings

def set_choice_group_settings(settings: ChoiceGroupSettings):
    global _choice_group_settings
    _choice_group_settings = settings

def get_generation_draft_creator() -> GenerationDraftCreatorPort | None:
    return _generation_draft_creator

def set_generation_draft_creator(creator: GenerationDraftCreatorPort):
    global _generation_draft_creator
    _generation_draft_creator = creator
