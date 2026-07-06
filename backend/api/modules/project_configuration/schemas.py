from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List

class GenerationStrategyItemSchema(BaseModel):
    id: str = Field(..., description="策略的对内唯一标识，例如 balanced, custom_xxx")
    label: str = Field(..., min_length=2, max_length=20, description="策略展现给用户的名称")
    description: Optional[str] = Field(None, max_length=120, description="对策略生成偏好的简短描述")
    instruction: str = Field(..., min_length=20, max_length=800, description="策略对 AI 具体的生成指导提示词")
    generation_types: List[str] = Field(default_factory=list, description="适用此策略的生成类型列表")
    enabled: bool = Field(True, description="策略是否开启")
    order: int = Field(0, description="策略在列表中的排序")

class GenerationStrategyConfigResponse(BaseModel):
    enabled: bool = Field(True, description="是否启用生成策略自定义")
    candidate_count: int = Field(2, description="每次生成的候选方案数量")
    source: str = Field("default", description="策略配置来源：default 或 project")
    strategies: List[GenerationStrategyItemSchema] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)

class GenerationStrategyConfigUpdate(BaseModel):
    enabled: bool = Field(True, description="是否启用生成策略自定义")
    candidate_count: int = Field(2, ge=1, le=5, description="每次生成的候选方案数量")
    strategies: List[GenerationStrategyItemSchema] = Field(..., description="完整的策略列表")

class ProjectKnowledgeSummary(BaseModel):
    enabled: bool = Field(True)
    document_count: int = Field(0)
    ready_count: int = Field(0)
    failed_count: int = Field(0)
    processing_count: int = Field(0)
    ai_enabled_count: int = Field(0)

class ProjectKnowledgeConfigUpdate(BaseModel):
    enabled: bool = Field(True, description="是否启用项目知识库参考")

class ProjectLLMSummary(BaseModel):
    configured: bool = Field(False)
    source: str = Field("system", description="当前生效的 LLM 连接来源: project, personal, system")
    model_name: Optional[str] = Field(None)
    api_key_last4: Optional[str] = Field(None)

class ProjectConfigurationResponse(BaseModel):
    project_id: str = Field(..., description="项目的 UUID / public_id")
    generation_strategy: GenerationStrategyConfigResponse
    knowledge: ProjectKnowledgeSummary
    llm: ProjectLLMSummary
