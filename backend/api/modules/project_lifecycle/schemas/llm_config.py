from pydantic import BaseModel, Field
from backend.api.base_schema import CamelModel

class ProjectLLMConfigResponse(CamelModel):
    configured: bool
    api_url: str | None = None
    model_name: str | None = None
    api_key_last4: str | None = None

class ProjectLLMConfigRequest(CamelModel):
    api_url: str = Field(..., min_length=1)
    api_key: str | None = None
    model_name: str = Field(..., min_length=1)

class ProjectLLMConfigTestRequest(CamelModel):
    api_url: str | None = None
    api_key: str | None = None
    model_name: str | None = None

class ProjectLLMConfigTestResponse(CamelModel):
    success: bool
    error_type: str | None = None
    error_detail: str | None = None
