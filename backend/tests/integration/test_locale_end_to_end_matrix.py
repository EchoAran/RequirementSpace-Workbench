import json
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.api.dependencies import llm as llm_dependency
from backend.api.dependencies.llm import llm_context_manager
from backend.api.modules.project_lifecycle.application.interview_service import (
    ProjectInterviewService,
)
from backend.api.modules.requirements_core.feature.application.feature_generation_service import (
    FeatureGenerationService,
)
from backend.database.model import (
    ActorModel,
    Base,
    GenerativeDraftModel,
    ProjectModel,
    UserModel,
)
from backend.services.llm_handler_service import (
    CONTENT_LANGUAGE_PROTOCOL_MARKER,
    LLMHandler,
)


@pytest.fixture
async def matrix_db():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    yield session_factory
    await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "user_locale",
        "project_locale",
        "expected_locale",
        "expected_source",
    ),
    [
        ("zh-CN", None, "zh-CN", "user"),
        ("en-US", None, "en-US", "user"),
        ("zh-CN", "en-US", "en-US", "project"),
        ("en-US", "zh-CN", "zh-CN", "project"),
    ],
)
async def test_content_locale_end_to_end_matrix(
    matrix_db,
    user_locale,
    project_locale,
    expected_locale,
    expected_source,
):
    expected_english = expected_locale == "en-US"
    interview_response = json.dumps(
        {
            "assistant_message": (
                "Please describe the primary users and their most important goal."
                if expected_english
                else "请继续说明项目的主要使用者和他们最重要的目标。"
            ),
            "is_ready_to_generate": False,
            "summary": (
                "The interview has captured the initial project objective."
                if expected_english
                else "本次访谈已经记录了项目的初始目标。"
            ),
        },
        ensure_ascii=False,
    )
    wrong_feature_response = json.dumps(
        {
            "features": [
                {
                    "feature_number": "F001",
                    "feature_name": "错误语言功能" if expected_english else "Wrong language feature",
                    "feature_description": (
                        "这是一个使用了错误语言的完整功能说明。"
                        if expected_english
                        else "This is a complete feature description in the wrong language."
                    ),
                    "actor_ids": [2],
                }
            ]
        },
        ensure_ascii=False,
    )
    expected_description = (
        "This is the corrected English feature description for the project."
        if expected_english
        else "这是纠正后写入项目草稿的完整中文功能说明。"
    )
    corrected_feature_response = json.dumps(
        {
            "features": [
                {
                    "feature_number": "F001",
                    "feature_name": "Music playback" if expected_english else "音乐播放",
                    "feature_description": expected_description,
                    "actor_ids": [2],
                }
            ]
        },
        ensure_ascii=False,
    )
    responses = [
        interview_response,
        wrong_feature_response,
        corrected_feature_response,
    ]
    captured_requests = []

    async def capture_call(_handler, request_data, **_kwargs):
        captured_requests.append(request_data)
        return responses.pop(0)

    async with matrix_db() as session:
        user = UserModel(
            email=f"matrix-{user_locale}-{project_locale}@example.test",
            password_hash="not-used",
            preferred_locale=user_locale,
        )
        session.add(user)
        await session.flush()
        project = ProjectModel(
            owner_user_id=user.id,
            name="Locale Matrix Project",
            description="",
            user_requirements="Build a local music player",
            content_locale=project_locale,
        )
        session.add(project)
        await session.flush()
        session.add(
            ActorModel(
                id=2,
                project_id=project.id,
                name="Listener",
                description="Listens to local music",
            )
        )
        await session.commit()

        with patch.object(
            llm_dependency.llm_config_service,
            "resolve_for_user",
            AsyncMock(
                return_value={
                    "api_url": "https://llm.example.com",
                    "api_key": "sk-test",
                    "model_name": "test-model",
                }
            ),
        ), patch.object(LLMHandler, "_call_api", capture_call):
            async with llm_context_manager(
                user,
                session,
                project_id=project.id,
            ) as context:
                assert context.content_locale == expected_locale
                assert context.content_locale_source == expected_source

                interview = await ProjectInterviewService().chat(
                    [
                        {"role": "user", "content": "Help refine the project."},
                        {"role": "assistant", "content": "What should it achieve?"},
                        {"role": "user", "content": "It should play local music."},
                    ]
                )
                assert interview["reply"]

                draft = await FeatureGenerationService().create_draft(
                    project_id=project.id,
                    owner_user_id=user.id,
                    session=session,
                )
                draft_id = draft["draft_id"]
        await session.commit()

    assert responses == []
    assert len(captured_requests) == 3
    expected_protocol = (
        "English (en-US)" if expected_english else "中文 (zh-CN)"
    )
    for request in captured_requests:
        outbound = "\n".join(
            message.get("content", "") for message in request["messages"]
        )
        assert outbound.count(CONTENT_LANGUAGE_PROTOCOL_MARKER) == 1
        assert expected_protocol in outbound

    async with matrix_db() as refreshed_session:
        persisted_draft = await refreshed_session.scalar(
            select(GenerativeDraftModel).where(
                GenerativeDraftModel.draft_id == draft_id
            )
        )
        refreshed_project = await refreshed_session.get(ProjectModel, project.id)

    assert persisted_draft is not None
    assert (
        persisted_draft.payload["features"][0]["feature_description"]
        == expected_description
    )
    assert refreshed_project is not None
    assert refreshed_project.content_locale == project_locale
