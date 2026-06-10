from pydantic import BaseModel, Field

class LLMConfigResponse(BaseModel):
    configured: bool
    source: str | None = None  # "personal" | "server" | None
    api_url: str | None = None
    model_name: str | None = None
    api_key_last4: str | None = None

    class Config:
        from_attributes = True


class LLMConfigRequest(BaseModel):
    api_url: str = Field(..., min_length=1)
    api_key: str = Field(..., min_length=1)
    model_name: str = Field(..., min_length=1)


class LLMConfigTestRequest(BaseModel):
    api_url: str | None = None
    api_key: str | None = None
    model_name: str | None = None


class LLMConfigTestResponse(BaseModel):
    success: bool
    error_type: str | None = None
    error_detail: str | None = None
