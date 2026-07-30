from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.api.modules.project_lifecycle.application.project_service import (
    ProjectService,
)


@pytest.mark.asyncio
async def test_stage_progress_keeps_missing_project_error():
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)

    with pytest.raises(ValueError, match="^project_not_found$"):
        await ProjectService().get_stage_progress(
            project_id=999,
            public_project_id="missing",
            session=session,
        )

    session.execute.assert_awaited_once()
