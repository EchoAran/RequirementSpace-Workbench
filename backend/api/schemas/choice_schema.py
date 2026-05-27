from pydantic import BaseModel, Field
from datetime import datetime
from backend.api.schemas.project_schema import CamelModel

class ChoiceResponse(CamelModel):
    id: int
    choice_group_id: int
    title: str
    rationale: str
    status: str
    patch: dict
    impact_preview: dict | None = None
    created_at: datetime
    updated_at: datetime


class ChoiceGroupResponse(CamelModel):
    id: int
    project_id: int
    slot_id: int | None = None
    status: str
    selection_mode: str
    choices: list[ChoiceResponse] = []
    created_at: datetime
    updated_at: datetime


class ProjectChoiceGroupsResponse(CamelModel):
    project_id: int
    choice_groups: list[ChoiceGroupResponse]


class ChoiceActionResponse(CamelModel):
    message: str
    choice_id: int
    status: str
