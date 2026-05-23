from pydantic import BaseModel, Field
from datetime import datetime

class ChoiceResponse(BaseModel):
    id: int
    choice_group_id: int
    title: str
    rationale: str
    status: str
    patch: dict
    impact_preview: dict | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ChoiceGroupResponse(BaseModel):
    id: int
    project_id: int
    slot_id: int | None = None
    status: str
    selection_mode: str
    choices: list[ChoiceResponse] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProjectChoiceGroupsResponse(BaseModel):
    project_id: int
    choice_groups: list[ChoiceGroupResponse]


class ChoiceActionResponse(BaseModel):
    message: str
    choice_id: int
    status: str
