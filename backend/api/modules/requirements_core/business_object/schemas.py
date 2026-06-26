from pydantic import BaseModel, ConfigDict, Field

# Business Object Attribute Schemas
class BusinessObjectAttributeCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field(default="")
    data_type: str = Field(..., min_length=1, max_length=100)
    example: str = Field(default="")


class BusinessObjectAttributeUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None)
    data_type: str | None = Field(default=None, min_length=1, max_length=100)
    example: str | None = Field(default=None)


class BusinessObjectAttributeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    attribute_id: int
    business_object_id: int
    name: str
    description: str
    data_type: str
    example: str
    confirmation_status: str | None = None


# Business Object CRUD Schemas
class BusinessObjectCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field(default="")


class BusinessObjectUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None)


class BusinessObjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    business_object_id: int
    name: str
    description: str
    attributes: list[BusinessObjectAttributeResponse] = []
    confirmation_status: str | None = None


# Legacy compatibility aliases
BOCreateRequest = BusinessObjectCreateRequest
BOUpdateRequest = BusinessObjectUpdateRequest
BOResponse = BusinessObjectResponse
BOAttributeCreateRequest = BusinessObjectAttributeCreateRequest
BOAttributeUpdateRequest = BusinessObjectAttributeUpdateRequest
BOAttributeResponse = BusinessObjectAttributeResponse
