from pydantic import BaseModel, Field

class UpdatePreferencesRequest(BaseModel):
    preferred_locale: str = Field(..., description="User preferred UI language: zh-CN or en-US")

class PreferencesResponse(BaseModel):
    preferred_locale: str
