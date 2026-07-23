from unittest.mock import AsyncMock

import pytest
from fastapi import BackgroundTasks

from backend.api.dependencies import llm as llm_dependency
from backend.api.dependencies.llm import llm_context_manager
from backend.api.modules.diagnosis_quality.perception.application.job_executor import (
    PerceptionJobExecutor,
)
from backend.core.llm_context import LLMRequestContext, current_llm_context


class _QueryResult:
    def __init__(self, content_locale: str | None):
        self._content_locale = content_locale

    def scalar_one_or_none(self) -> str | None:
        return self._content_locale


class _Session:
    def __init__(self, project_locale: str | None = None):
        self._project_locale = project_locale

    async def execute(self, _statement):
        return _QueryResult(self._project_locale)


class _User:
    def __init__(self, preferred_locale: str | None):
        self.id = 1
        self.preferred_locale = preferred_locale


@pytest.fixture
def resolved_llm_config(monkeypatch):
    monkeypatch.setattr(
        llm_dependency.llm_config_service,
        "resolve_for_user",
        AsyncMock(return_value={"api_url": "https://llm.example.com", "api_key": "sk-test", "model_name": "test-model"}),
    )


@pytest.mark.anyio
async def test_llm_context_uses_project_content_locale_before_user_preference(resolved_llm_config):
    async with llm_context_manager(_User("zh-CN"), _Session("en-US"), project_id=1) as context:
        assert context.content_locale == "en-US"
        assert context.content_locale_source == "project"


@pytest.mark.anyio
async def test_llm_context_falls_back_to_user_preference_when_project_locale_is_empty(resolved_llm_config):
    async with llm_context_manager(_User("en-US"), _Session(None), project_id=1) as context:
        assert context.content_locale == "en-US"
        assert context.content_locale_source == "user"


@pytest.mark.anyio
async def test_llm_context_falls_back_to_chinese_when_user_preference_is_empty(resolved_llm_config):
    async with llm_context_manager(_User(None), _Session()) as context:
        assert context.content_locale == "zh-CN"
        assert context.content_locale_source == "default"


@pytest.mark.anyio
async def test_perception_background_job_restores_captured_llm_context(monkeypatch):
    executor = PerceptionJobExecutor()
    context = LLMRequestContext(
        api_url="https://llm.example.com",
        api_key="sk-test",
        model_name="test-model",
        content_locale="en-US",
        content_locale_source="project",
    )
    observed = []

    async def capture(_job_id):
        observed.append(current_llm_context.get())

    monkeypatch.setattr(executor, "_run_perception_job", capture)
    await executor.run_perception_job(1, context)

    assert observed == [context]
    assert current_llm_context.get() is None


@pytest.mark.anyio
async def test_perception_scheduler_passes_current_llm_context():
    executor = PerceptionJobExecutor()
    background_tasks = BackgroundTasks()
    session = AsyncMock()
    context = LLMRequestContext(
        api_url="https://llm.example.com",
        api_key="sk-test",
        model_name="test-model",
        content_locale="en-US",
        content_locale_source="user",
    )
    token = current_llm_context.set(context)
    try:
        await executor._schedule_perception_job(background_tasks, session, 7)
    finally:
        current_llm_context.reset(token)

    assert background_tasks.tasks[0].args == (7, context)
