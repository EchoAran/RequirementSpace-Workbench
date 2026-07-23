from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from backend.api.modules.preview_convergence.application import shadow_convergence
from backend.api.modules.preview_convergence.application.shadow_convergence import (
    PreviewShadowConvergenceService,
)
from backend.api.modules.preview_convergence.application.shadow_scope_generator import (
    PreviewShadowScopeGenerator,
)
from backend.api.modules.preview_convergence.routes import shadow_preview
from backend.api.modules.preview_convergence.schemas.shadow_preview import (
    PreviewShadowRegenerateRequest,
)
from backend.core.llm_context import LLMRequestContext, current_llm_context
from backend.database.model import PreviewShadowDraftModel


def _llm_context(source: str) -> LLMRequestContext:
    return LLMRequestContext(
        api_url="https://llm.example.com",
        api_key="sk-test",
        model_name="test-model",
        content_locale="en-US",
        content_locale_source=source,
    )


def _close_background_coroutine(coroutine):
    coroutine.close()
    return MagicMock()


@pytest.mark.asyncio
async def test_shadow_scope_worker_preserves_llm_context_in_thread():
    captured = {}

    class KanoSkill:
        def analyze(self, _requirements, _feature_tree):
            context = current_llm_context.get()
            captured["locale"] = context.content_locale
            captured["source"] = context.content_locale_source
            return {}

    scope_service = SimpleNamespace(
        _kano_skill=KanoSkill(),
        _adapter=SimpleNamespace(
            build_kano_feature_tree=lambda _features: {},
            to_current_scopes=lambda **_kwargs: [],
        ),
        _normalize_generated_scopes=lambda **_kwargs: [],
    )
    token = current_llm_context.set(_llm_context("project"))
    try:
        await PreviewShadowScopeGenerator.generate_scopes_for_features(
            scope_service=scope_service,
            user_requirements="Build an ERP",
            feature_nodes=[],
            leaf_feature_nodes=[],
        )
    finally:
        current_llm_context.reset(token)

    assert captured == {"locale": "en-US", "source": "project"}


@pytest.mark.asyncio
@pytest.mark.parametrize("source", ["project", "user"])
async def test_shadow_worker_restores_en_us_locale_context(monkeypatch, source):
    service = PreviewShadowConvergenceService()
    draft = SimpleNamespace(
        status="generating",
        base_snapshot_json={},
        error_message="",
    )
    result = MagicMock()
    result.scalar_one_or_none.return_value = draft
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)
    session.get = AsyncMock(return_value=SimpleNamespace(public_id="project-public-id"))
    session.commit = AsyncMock()

    class SessionContext:
        async def __aenter__(self):
            return session

        async def __aexit__(self, *_args):
            return False

    captured = {}

    async def capture_context_then_stop(**_kwargs):
        context = current_llm_context.get()
        captured["locale"] = context.content_locale
        captured["source"] = context.content_locale_source
        raise RuntimeError("stop_after_context_capture")

    monkeypatch.setattr(shadow_convergence, "AsyncSessionLocal", SessionContext)
    monkeypatch.setattr(shadow_convergence.asyncio, "sleep", AsyncMock())
    monkeypatch.setattr(service, "_update_progress", AsyncMock())
    monkeypatch.setattr(service, "_generate_shadow_patch", capture_context_then_stop)

    previous_context = current_llm_context.get()
    with patch.object(
        PreviewShadowConvergenceService,
        "_prototype_generation_service",
        new_callable=PropertyMock,
        return_value=MagicMock(),
    ):
        await service.converge_shadow_snapshot_task(
            project_id=1,
            draft_id="draft-locale",
            api_url="https://llm.example.com",
            api_key="sk-test",
            model_name="test-model",
            content_locale="en-US",
            content_locale_source=source,
        )

    assert captured == {"locale": "en-US", "source": source}
    assert current_llm_context.get() is previous_context


@pytest.mark.asyncio
async def test_prepare_shadow_draft_passes_project_locale_context(monkeypatch):
    duplicate_result = MagicMock()
    duplicate_result.scalar_one_or_none.return_value = None
    stale_result = MagicMock()
    stale_result.scalars.return_value.all.return_value = []
    session = MagicMock()
    session.execute = AsyncMock(side_effect=[duplicate_result, stale_result])
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    task = AsyncMock()

    monkeypatch.setattr(
        shadow_preview.convergence_service.gate_evaluator,
        "evaluate_gates",
        AsyncMock(return_value={"what": False, "how": False, "scope": False}),
    )
    monkeypatch.setattr(shadow_preview, "build_project_snapshot", AsyncMock(return_value={}))
    monkeypatch.setattr(shadow_preview, "calculate_stable_snapshot_hash", lambda _snapshot: "hash")
    monkeypatch.setattr(
        shadow_preview.convergence_service,
        "converge_shadow_snapshot_task",
        task,
    )
    monkeypatch.setattr(shadow_preview.asyncio, "create_task", _close_background_coroutine)

    await shadow_preview.prepare_shadow_draft(
        project_id="project-public-id",
        session=session,
        llm_ctx=_llm_context("project"),
        owned_project=SimpleNamespace(id=1),
    )

    assert task.call_args.kwargs["content_locale"] == "en-US"
    assert task.call_args.kwargs["content_locale_source"] == "project"


@pytest.mark.asyncio
async def test_regenerate_shadow_draft_passes_user_locale_context(monkeypatch):
    draft = PreviewShadowDraftModel(
        project_id=1,
        draft_id="draft-locale",
        status="failed",
        source="shadow_project",
        base_snapshot_hash="old-hash",
        base_snapshot_json={},
    )
    result = MagicMock()
    result.scalar_one_or_none.return_value = draft
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)
    session.commit = AsyncMock()
    task = AsyncMock()

    monkeypatch.setattr(
        shadow_preview.convergence_service.gate_evaluator,
        "evaluate_gates",
        AsyncMock(return_value={"what": False, "how": False, "scope": False}),
    )
    monkeypatch.setattr(shadow_preview, "build_project_snapshot", AsyncMock(return_value={}))
    monkeypatch.setattr(shadow_preview, "calculate_stable_snapshot_hash", lambda _snapshot: "new-hash")
    monkeypatch.setattr(
        shadow_preview.convergence_service,
        "converge_shadow_snapshot_task",
        task,
    )
    monkeypatch.setattr(shadow_preview.asyncio, "create_task", _close_background_coroutine)

    await shadow_preview.regenerate_shadow_draft(
        project_id="project-public-id",
        draft_id=draft.draft_id,
        request=PreviewShadowRegenerateRequest(user_feedback="Try again"),
        session=session,
        llm_ctx=_llm_context("user"),
        owned_project=SimpleNamespace(id=1),
    )

    assert task.call_args.kwargs["content_locale"] == "en-US"
    assert task.call_args.kwargs["content_locale_source"] == "user"
