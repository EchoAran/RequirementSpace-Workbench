from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.shadow_preview.shadow_patch_validator import ShadowPatchValidator
from backend.core.stage_gates.stage_gate_evaluator import StageGateEvaluator


class PreviewShadowValidator:
    def __init__(self) -> None:
        self.gate_evaluator = StageGateEvaluator()

    async def evaluate_gates(self, project_id: int, session: AsyncSession) -> dict:
        """
        Evaluate stage gates for the project.
        """
        return await self.gate_evaluator.evaluate_gates(project_id, session)

    def validate_patch(self, patch: dict, base_snapshot: dict, project_id: str) -> bool:
        return ShadowPatchValidator.validate_patch(
            patch,
            base_snapshot,
            project_id,
            allow_missing_project_id=True,
        )
