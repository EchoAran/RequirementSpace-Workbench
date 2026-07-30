from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.api.modules.diagnosis_quality.perception.application import (
    job_executor as job_executor_module,
)
from backend.api.modules.diagnosis_quality.perception.application.job_executor import (
    PerceptionJobExecutor,
)
from backend.schemas import PerceptionJobStatus


class _SessionContext:
    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, exc_type, exc, traceback):
        return False


def _job():
    return SimpleNamespace(
        id=1,
        project_id=10,
        stage="what",
        target_type="project",
        target_id="",
        perception_kind="ACTOR",
        context_hash="expected",
        status=PerceptionJobStatus.RUNNING.value,
        result_slot_payload={"old": True},
        error_message=None,
    )


def _patch_executor_dependencies(monkeypatch, session, context):
    monkeypatch.setattr(
        job_executor_module,
        "AsyncSessionLocal",
        lambda: _SessionContext(session),
    )
    monkeypatch.setattr(
        job_executor_module,
        "load_issue_project_context",
        AsyncMock(return_value=context),
    )
    monkeypatch.setattr(job_executor_module, "log_event", MagicMock())


@pytest.mark.asyncio
async def test_run_perception_job_marks_changed_context_stale(monkeypatch):
    session = SimpleNamespace(
        commit=AsyncMock(),
        rollback=AsyncMock(),
    )
    context = SimpleNamespace()
    _patch_executor_dependencies(monkeypatch, session, context)
    executor = PerceptionJobExecutor()
    job = _job()
    executor._load_job_with_retry = AsyncMock(return_value=job)
    executor._build_context_hash = MagicMock(return_value="changed")
    executor._run_perceptron = AsyncMock()

    await executor._run_perception_job(job.id)

    assert job.status == PerceptionJobStatus.STALE.value
    session.commit.assert_awaited_once()
    session.rollback.assert_not_awaited()
    executor._run_perceptron.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_perception_job_marks_empty_result_and_deletes_slot(
    monkeypatch,
):
    session = SimpleNamespace(
        commit=AsyncMock(),
        rollback=AsyncMock(),
    )
    context = SimpleNamespace()
    _patch_executor_dependencies(monkeypatch, session, context)
    executor = PerceptionJobExecutor()
    job = _job()
    executor._load_job_with_retry = AsyncMock(return_value=job)
    executor._build_context_hash = MagicMock(return_value="expected")
    executor._run_perceptron = AsyncMock(return_value={})
    executor._normalize_perception_description = MagicMock(
        return_value=None
    )
    executor._delete_slot_for_job = AsyncMock()

    await executor._run_perception_job(job.id)

    assert job.status == PerceptionJobStatus.DONE_EMPTY.value
    assert job.result_slot_payload is None
    executor._delete_slot_for_job.assert_awaited_once_with(
        project_id=job.project_id,
        job_id=job.id,
        session=session,
    )
    session.commit.assert_awaited_once()
    session.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_perception_job_records_failure_after_rollback(monkeypatch):
    session = SimpleNamespace(
        commit=AsyncMock(),
        rollback=AsyncMock(),
    )
    context = SimpleNamespace()
    _patch_executor_dependencies(monkeypatch, session, context)
    executor = PerceptionJobExecutor()
    job = _job()
    executor._load_job_with_retry = AsyncMock(
        side_effect=[job, job]
    )
    executor._build_context_hash = MagicMock(return_value="expected")
    executor._run_perceptron = AsyncMock(
        side_effect=RuntimeError("generation failed")
    )

    await executor._run_perception_job(job.id)

    session.rollback.assert_awaited_once()
    session.commit.assert_awaited_once()
    assert job.status == PerceptionJobStatus.FAILED.value
    assert job.error_message == "RuntimeError: generation failed"
