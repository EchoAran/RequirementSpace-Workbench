import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Any, Dict, List

from backend.database.model import ProjectGenerationStrategyConfigModel
from backend.api.modules.project_configuration.schemas import (
    GenerationStrategyConfigResponse,
    GenerationStrategyConfigUpdate,
    GenerationStrategyItemSchema,
)

logger = logging.getLogger(__name__)

DEFAULT_STRATEGIES = [
    {
        "id": "balanced",
        "label": "均衡版",
        "description": "在功能完整性与复杂度之间保持均衡，优先生成可落地、边界清晰的方案。",
        "instruction": "在功能完整性与复杂度之间保持均衡，优先生成可落地、边界清晰的方案。覆盖核心业务角色、主流程、关键异常和必要验收条件，避免过度拆分、重复角色和低价值边界场景。",
        "generation_types": ["project_creation", "actor", "feature", "scenario", "flow", "scope", "acceptance_criteria"],
        "enabled": True,
        "order": 0
    },
    {
        "id": "comprehensive",
        "label": "全面版",
        "description": "尽可能完整覆盖主路径、异常路径、边界条件和验收条件。",
        "instruction": "尽可能完整覆盖主路径、异常路径、边界条件、权限约束和验收条件。可以比均衡版更细，但不得编造与需求明显无关的内容。",
        "generation_types": ["project_creation", "actor", "feature", "scenario", "flow", "scope", "acceptance_criteria"],
        "enabled": True,
        "order": 1
    },
    {
        "id": "minimal",
        "label": "精简版",
        "description": "优先生成最小可行、低复杂度、便于快速评审和落地的方案。",
        "instruction": "优先生成最小可行、低复杂度、便于快速评审和落地的方案。只覆盖最核心角色、主流程和必须验收条件，避免引入暂不必要的扩展场景、复杂权限和过细边界。",
        "generation_types": ["project_creation", "actor", "feature", "scenario", "flow", "scope", "acceptance_criteria"],
        "enabled": False,
        "order": 2
    },
    {
        "id": "risk_averse",
        "label": "风控版",
        "description": "重点识别权限、数据一致性、异常处理和合规风险。",
        "instruction": "重点识别权限、数据一致性、异常处理、审计追踪和合规风险。生成方案时应补充关键风险场景、失败兜底、边界校验和验收条件，但不要脱离当前需求编造无关流程。",
        "generation_types": ["project_creation", "actor", "feature", "scenario", "flow", "scope", "acceptance_criteria"],
        "enabled": False,
        "order": 3
    },
    {
        "id": "workflow_first",
        "label": "流程优先版",
        "description": "优先围绕端到端业务流程、状态流转和协作节点组织方案。",
        "instruction": "优先围绕端到端业务流程、状态流转、协作节点和前后置条件组织方案。生成内容应突出流程顺序、触发条件、角色交接和完成标准，避免只罗列静态功能点。",
        "generation_types": ["project_creation", "actor", "feature", "scenario", "flow", "scope", "acceptance_criteria"],
        "enabled": False,
        "order": 4
    }
]

LEGACY_DEFAULT_STRATEGIES = DEFAULT_STRATEGIES[:2]

def _is_default_strategy_config(db_config: ProjectGenerationStrategyConfigModel) -> bool:
    return (
        db_config.enabled is True
        and db_config.candidate_count == 2
        and db_config.strategies in (DEFAULT_STRATEGIES, LEGACY_DEFAULT_STRATEGIES)
    )

class GenerationStrategyConfigService:
    def get_default_config(self) -> GenerationStrategyConfigResponse:
        return GenerationStrategyConfigResponse(
            enabled=True,
            candidate_count=2,
            source="default",
            strategies=[GenerationStrategyItemSchema(**s) for s in DEFAULT_STRATEGIES]
        )

    async def get_for_project(self, project_id: int, session: AsyncSession) -> GenerationStrategyConfigResponse:
        stmt = select(ProjectGenerationStrategyConfigModel).where(
            ProjectGenerationStrategyConfigModel.project_id == project_id
        )
        res = await session.execute(stmt)
        db_config = res.scalar_one_or_none()

        if db_config:
            if _is_default_strategy_config(db_config):
                return self.get_default_config()
            # Map raw JSON dicts in database to Pydantic objects
            strategies_list = []
            raw_strategies = db_config.strategies
            if isinstance(raw_strategies, list):
                for s in raw_strategies:
                    if isinstance(s, dict):
                        strategies_list.append(GenerationStrategyItemSchema(**s))
            return GenerationStrategyConfigResponse(
                enabled=db_config.enabled,
                candidate_count=db_config.candidate_count,
                source="project",
                strategies=strategies_list
            )
        
        return self.get_default_config()

    async def save_for_project(
        self,
        project_id: int,
        user_id: int,
        req: GenerationStrategyConfigUpdate,
        session: AsyncSession
    ) -> GenerationStrategyConfigResponse:
        # 1. Validation Rules
        if req.candidate_count < 1 or req.candidate_count > 5:
            raise ValueError("candidate_count_out_of_bounds")

        if req.enabled:
            enabled_count = sum(1 for s in req.strategies if s.enabled)
            if enabled_count < req.candidate_count:
                raise ValueError("insufficient_enabled_strategies")
            if enabled_count > 5:
                raise ValueError("too_many_enabled_strategies")

        # Strategy ID uniqueness check
        strategy_ids = [s.id for s in req.strategies]
        if len(strategy_ids) != len(set(strategy_ids)):
            raise ValueError("duplicate_strategy_id")

        # Basic label, instruction, control characters, and injection validation
        import re
        CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
        
        bypass_terms = [
            "ignore previous", "system prompt",
            "忽略以上指令", "覆盖系统指令", "忽略系统指令", "忽略原有指令", "忽略前文", "忽略先前", "覆盖之前",
            "ignore instructions", "override instructions", "bypass constraints", "ignore constraints"
        ]
        format_terms = [
            "忽略格式", "不要遵守格式", "只输出 json", "仅输出 json", "只返回 json",
            "only output json", "only return json", "ignore format", "bypass format",
            "don't follow format", "do not follow format"
        ]

        for s in req.strategies:
            label = s.label.strip()
            instruction = s.instruction.strip()
            if len(label) < 2 or len(label) > 20:
                raise ValueError("invalid_strategy_label_length")
            if len(instruction) < 20 or len(instruction) > 800:
                raise ValueError("invalid_strategy_instruction_length")
            
            if CONTROL_CHAR_RE.search(instruction):
                raise ValueError("control_characters_detected")

            lower_instruction = instruction.lower()
            if any(term in lower_instruction for term in bypass_terms) or any(term in lower_instruction for term in format_terms):
                raise ValueError("strategy_prompt_injection_detected")

        # 2. Convert strategies pydantic model to list of dicts for DB JSON storage
        serialized_strategies = [s.model_dump() for s in req.strategies]

        # 3. DB Persistence
        stmt = select(ProjectGenerationStrategyConfigModel).where(
            ProjectGenerationStrategyConfigModel.project_id == project_id
        )
        res = await session.execute(stmt)
        db_config = res.scalar_one_or_none()

        if db_config:
            db_config.enabled = req.enabled
            db_config.candidate_count = req.candidate_count
            db_config.strategies = serialized_strategies
            db_config.updated_by_user_id = user_id
        else:
            db_config = ProjectGenerationStrategyConfigModel(
                project_id=project_id,
                enabled=req.enabled,
                candidate_count=req.candidate_count,
                strategies=serialized_strategies,
                updated_by_user_id=user_id
            )
            session.add(db_config)
        
        await session.commit()
        await session.refresh(db_config)

        strategies_list = [GenerationStrategyItemSchema(**s) for s in db_config.strategies]
        return GenerationStrategyConfigResponse(
            enabled=db_config.enabled,
            candidate_count=db_config.candidate_count,
            source="project",
            strategies=strategies_list
        )

    async def delete_for_project(self, project_id: int, session: AsyncSession) -> None:
        stmt = select(ProjectGenerationStrategyConfigModel).where(
            ProjectGenerationStrategyConfigModel.project_id == project_id
        )
        res = await session.execute(stmt)
        db_config = res.scalar_one_or_none()
        if db_config:
            db_config.enabled = True
            db_config.candidate_count = 2
            db_config.strategies = DEFAULT_STRATEGIES
        await session.commit()
