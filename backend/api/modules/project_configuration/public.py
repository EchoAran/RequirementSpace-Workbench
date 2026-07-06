from dataclasses import dataclass
import os
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from backend.database.model import ProjectGenerationStrategyConfigModel
from backend.api.modules.project_configuration.application.generation_strategy_config_service import (
    DEFAULT_STRATEGIES,
)

@dataclass
class ResolvedGenerationStrategy:
    id: str
    label: str
    description: Optional[str]
    instruction: Optional[str]
    order: int

def _default_strategies_for(generation_type: str) -> List[ResolvedGenerationStrategy]:
    strategies = []
    for s in DEFAULT_STRATEGIES:
        if s.get("enabled", True):
            gen_types = s.get("generation_types") or []
            if not gen_types or generation_type in gen_types:
                strategies.append(
                    ResolvedGenerationStrategy(
                        id=s["id"],
                        label=s["label"],
                        description=s.get("description"),
                        instruction=s.get("instruction"),
                        order=s.get("order", 0)
                    )
                )
    return strategies

async def resolve_generation_strategies(
    *,
    project_id: int,
    generation_type: str,
    requested_count: Optional[int] = None,
    session: AsyncSession,
) -> List[ResolvedGenerationStrategy]:
    """
    Resolve generation strategies for a project and generation type.
    1. Reads project-specific configuration from DB.
    2. Filters strategies applicable to the generation_type.
    3. Limits to candidate_count (or requested_count if specified).
    4. Falls back to defaults if no custom strategies exist or if none match.
    """
    if os.getenv("PROJECT_GENERATION_STRATEGIES_ENABLED", "true").lower() != "true":
        defaults = _default_strategies_for(generation_type)
        defaults.sort(key=lambda x: x.order)
        limit = requested_count if requested_count is not None else 2
        return defaults[:limit]

    # 1. Try project-level config
    stmt = select(ProjectGenerationStrategyConfigModel).where(
        ProjectGenerationStrategyConfigModel.project_id == project_id
    )
    res = await session.execute(stmt)
    db_config = res.scalar_one_or_none()

    resolved_strategies = []
    candidate_count = 2

    if db_config and db_config.enabled:
        candidate_count = db_config.candidate_count
        raw_strategies = db_config.strategies
        if isinstance(raw_strategies, list):
            for s in raw_strategies:
                if isinstance(s, dict) and s.get("enabled", True):
                    # Filter by generation_type
                    gen_types = s.get("generation_types") or []
                    if not gen_types or generation_type in gen_types:
                        resolved_strategies.append(
                            ResolvedGenerationStrategy(
                                id=s["id"],
                                label=s["label"],
                                description=s.get("description"),
                                instruction=s.get("instruction"),
                                order=s.get("order", 0)
                            )
                        )

    # 2. Fallback to default strategies if empty
    if not resolved_strategies:
        candidate_count = 2
        resolved_strategies = _default_strategies_for(generation_type)

    # 3. Sort by order
    resolved_strategies.sort(key=lambda x: x.order)

    # 4. Limit to candidate_count or requested_count
    limit = requested_count if requested_count is not None else candidate_count
    return resolved_strategies[:limit]
