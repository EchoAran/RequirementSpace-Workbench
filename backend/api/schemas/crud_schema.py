from pydantic import BaseModel, Field


# ==========================================
# 1. Actor CRUD Schemas
# ==========================================
class ActorCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field(default="")


class ActorUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None)


class ActorResponse(BaseModel):
    actor_id: int
    name: str
    description: str

    class Config:
        from_attributes = True


# ==========================================
# 2. Feature CRUD Schemas
# ==========================================
class FeatureCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field(default="")
    parent_id: int | None = Field(default=None)


class FeatureUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None)
    actor_ids: list[int] | None = Field(default=None)


class FeatureResponse(BaseModel):
    feature_id: int
    name: str
    description: str
    parent_id: int | None = None
    child_ids: list[int] = []
    actor_ids: list[int] = []

    class Config:
        from_attributes = True


# ==========================================
# 3. Acceptance Criterion Schemas
# ==========================================
class ACCreateRequest(BaseModel):
    content: str = Field(..., min_length=1)
    position: int | None = Field(default=None)


class ACUpdateRequest(BaseModel):
    content: str = Field(..., min_length=1)


class ACResponse(BaseModel):
    criterion_id: int
    scenario_id: int
    content: str
    position: int

    class Config:
        from_attributes = True


# ==========================================
# 4. Scenario CRUD Schemas
# ==========================================
class ScenarioCreateRequest(BaseModel):
    feature_id: int
    actor_id: int
    name: str = Field(..., min_length=1, max_length=255)
    content: str = Field(default="")


class ScenarioUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    content: str | None = Field(default=None)


class ScenarioResponse(BaseModel):
    scenario_id: int
    feature_id: int
    actor_id: int
    name: str
    content: str
    acceptance_criteria: list[ACResponse] = []

    class Config:
        from_attributes = True


# ==========================================
# 5. Business Object Attribute Schemas
# ==========================================
class BOAttributeCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field(default="")
    data_type: str = Field(..., min_length=1, max_length=100)
    example: str = Field(default="")


class BOAttributeUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None)
    data_type: str | None = Field(default=None, min_length=1, max_length=100)
    example: str | None = Field(default=None)


class BOAttributeResponse(BaseModel):
    attribute_id: int
    business_object_id: int
    name: str
    description: str
    data_type: str
    example: str

    class Config:
        from_attributes = True


# ==========================================
# 6. Business Object CRUD Schemas
# ==========================================
class BOCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field(default="")


class BOUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None)


class BOResponse(BaseModel):
    business_object_id: int
    name: str
    description: str
    attributes: list[BOAttributeResponse] = []

    class Config:
        from_attributes = True


# ==========================================
# 7. Flow Step CRUD Schemas
# ==========================================
class FlowStepCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field(default="")
    step_type: str = Field(..., pattern="^(actorAction|systemAction|judgment)$")
    actor_ids: list[int] = Field(default_factory=list)
    input_business_object_ids: list[int] = Field(default_factory=list)
    output_business_object_ids: list[int] = Field(default_factory=list)
    next_step_ids: list[int] = Field(default_factory=list)


class FlowStepUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None)
    step_type: str | None = Field(default=None, pattern="^(actorAction|systemAction|judgment)$")
    actor_ids: list[int] | None = Field(default=None)
    input_business_object_ids: list[int] | None = Field(default=None)
    output_business_object_ids: list[int] | None = Field(default=None)
    next_step_ids: list[int] | None = Field(default=None)


class FlowStepResponse(BaseModel):
    step_id: int
    flow_id: int
    position: int
    name: str
    description: str
    step_type: str
    actor_ids: list[int] = []
    input_business_object_ids: list[int] = []
    output_business_object_ids: list[int] = []
    next_step_ids: list[int] = []

    class Config:
        from_attributes = True


# ==========================================
# 8. Flow CRUD Schemas
# ==========================================
class FlowCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field(default="")
    feature_ids: list[int] = Field(default_factory=list)


class FlowUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None)
    feature_ids: list[int] | None = Field(default=None)


class FlowResponse(BaseModel):
    flow_id: int
    name: str
    description: str
    feature_ids: list[int] = []
    steps: list[FlowStepResponse] = []

    class Config:
        from_attributes = True


# ==========================================
# 9. Scope CRUD Schemas
# ==========================================
class ScopeUpdateRequest(BaseModel):
    status: str = Field(..., pattern="^(本期|暂缓|排除)$")
    reason: str = Field(default="")
    positive_summary: str | None = Field(default=None)
    negative_summary: str | None = Field(default=None)


class ScopeResponse(BaseModel):
    scope_id: int
    feature_id: int
    status: str
    reason: str
    positive_summary: str | None = None
    negative_summary: str | None = None

    class Config:
        from_attributes = True
