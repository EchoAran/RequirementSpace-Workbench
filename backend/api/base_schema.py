from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """Base Pydantic model configuration that converts field names to camelCase."""
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True
    )


class DraftRegenerateRequest(CamelModel):
    user_feedback: Optional[str] = Field(None, description="Optional modification suggestions or feedback to steer the regeneration process")
