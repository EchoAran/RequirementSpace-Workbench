from __future__ import annotations

import pytest
import asyncio
import os
from datetime import datetime
from unittest.mock import MagicMock, patch

from backend.api.modules.project_lifecycle.schemas.project import (
    ProjectDetailResponse,
    ActorDetail,
    FeatureDetail,
    BusinessObjectDetail,
    BusinessObjectAttributeDetail,
    FlowDetail,
    FlowStepDetail,
    ScopeDetail
)
from backend.integration.skill_backed_services.spl_syntax_export_service import SplSyntaxExportService
from backend.integration.skill_backed_services.spl_semantic_export_service import SplSemanticExportService


@pytest.mark.asyncio
async def test_spl_syntax_export_service_success():
    service = SplSyntaxExportService()
    now = datetime.now()
    
    # Verify success on empty project
    detail = ProjectDetailResponse(
        project_id="test-proj-uuid",
        project_name="Empty System",
        project_description="Desc",
        user_requirements="Reqs",
        actors=[],
        features=[],
        business_objects=[],
        flows=[],
        unresolved_gates=[]
    )
    
    spl_text = await service.export(detail)
    assert "[DEFINE_AGENT: Agent_testproj" in spl_text
    assert "Empty System" in spl_text
    assert "[END_AGENT]" in spl_text


@pytest.mark.asyncio
async def test_spl_syntax_export_uses_effective_content_locale():
    service = SplSyntaxExportService()
    captured = {}

    def export(payload):
        captured.update(payload)
        return {
            "spl_text": "SPL-en-US",
            "quality": "syntax_shell",
            "warnings": [],
            "trace_links": [],
        }

    service._skill.export = export
    detail = ProjectDetailResponse(
        project_id="english-project",
        project_name="English Project",
        project_description="Description",
        user_requirements="Requirements",
    )

    result = await service.export(detail, content_locale="en-US")

    assert result == "SPL-en-US"
    assert captured["export_options"]["language"] == "en-US"


@pytest.mark.asyncio
async def test_spl_syntax_export_skill_unavailable():
    service = SplSyntaxExportService()
    service._available = False
    
    detail = ProjectDetailResponse(
        project_id="test-proj-uuid",
        project_name="System",
        project_description="Desc",
        user_requirements="Reqs",
        actors=[],
        features=[],
        business_objects=[],
        flows=[],
        unresolved_gates=[]
    )
    
    with pytest.raises(ValueError) as exc_info:
        await service.export(detail)
    assert "spl_export_skill_unavailable" in str(exc_info.value)


@pytest.mark.asyncio
async def test_spl_syntax_export_invalid_output():
    service = SplSyntaxExportService()
    # Mock skill.export to return empty dict
    service._skill.export = MagicMock(return_value={})
    
    detail = ProjectDetailResponse(
        project_id="test-proj-uuid",
        project_name="System",
        project_description="Desc",
        user_requirements="Reqs",
        actors=[],
        features=[],
        business_objects=[],
        flows=[],
        unresolved_gates=[]
    )
    
    with pytest.raises(ValueError) as exc_info:
        await service.export(detail)
    assert "spl_export_invalid_skill_output" in str(exc_info.value)


@pytest.mark.asyncio
async def test_spl_semantic_export_llm_error_transparent():
    service = SplSemanticExportService()
    
    with patch.object(service._core.SplSemanticExportSkill, "export", side_effect=ValueError("invalid_skill_payload")):
        detail = ProjectDetailResponse(
            project_id="transparent-proj-uuid",
            project_name="System",
            project_description="Desc",
            user_requirements="Reqs",
            actors=[],
            features=[],
            business_objects=[],
            flows=[],
            unresolved_gates=[]
        )
        with pytest.raises(ValueError) as exc_info:
            await service.export(detail)
        assert "spl_export_invalid_skill_output" in str(exc_info.value)


@pytest.mark.asyncio
async def test_spl_semantic_export_timeout():
    service = SplSemanticExportService()
    
    with patch.object(service._core.SplSemanticExportSkill, "export", side_effect=asyncio.TimeoutError()):
        detail = ProjectDetailResponse(
            project_id="timeout-proj-uuid",
            project_name="System",
            project_description="Desc",
            user_requirements="Reqs",
            actors=[],
            features=[],
            business_objects=[],
            flows=[],
            unresolved_gates=[]
        )
        with pytest.raises(ValueError) as exc_info:
            await service.export(detail)
        assert "spl_export_timeout" in str(exc_info.value)


@pytest.mark.asyncio
async def test_spl_semantic_export_caching():
    service = SplSemanticExportService()
    now = datetime.now()
    
    # Initialize project detail
    detail1 = ProjectDetailResponse(
        project_id="caching-project-uuid",
        project_name="Caching System",
        project_description="Description",
        user_requirements="Requirements",
        actors=[],
        features=[],
        business_objects=[],
        flows=[],
        unresolved_gates=[]
    )
    
    call_count = 0
    
    def mock_ask_json_counter(prompt: str) -> dict:
        nonlocal call_count
        call_count += 1
        if "translating a database-backed" in prompt:
            return {"type_name": "Device", "fields": []}
        elif "RequirementSpace business flow" in prompt:
            return {"worker_name": "DeviceFlow", "description": "", "actors": [], "inputs": [], "outputs": [], "main_flow_steps": []}
        elif "converting software acceptance" in prompt:
            return {"scenarios": []}
        elif "completeness and correctness" in prompt:
            return {"coverage_passed": True, "semantic_risks": []}
        return {}

    class DummyCtx:
        api_url = "http://mock-api.com"
        api_key = "mock-key"
        model_name = "mock-model"

    ctx = DummyCtx()

    with patch("backend.integration.skill_backed_services.spl_semantic_export_service.SyncSkillBackedLLMJsonClient.ask_json", side_effect=mock_ask_json_counter):
        # 1. First export: triggers LLM calls
        text1 = await service.export(detail1, llm_ctx=ctx)
        assert "[DEFINE_AGENT: Agent_cachingp" in text1
        initial_calls = call_count
        assert initial_calls > 0
        
        # 2. Second export with identical payload: should HIT cache, calling LLM 0 times
        text2 = await service.export(detail1, llm_ctx=ctx)
        assert text2 == text1
        assert call_count == initial_calls  # No additional calls!
        
        # 3. Modify project data (modifies snapshot hash): should MISS cache, triggering LLM calls
        detail2 = ProjectDetailResponse(
            project_id="caching-project-uuid",
            project_name="Caching System",
            project_description="Modified Description",  # Changed!
            user_requirements="Requirements",
            actors=[],
            features=[],
            business_objects=[],
            flows=[],
            unresolved_gates=[]
        )
        
        text3 = await service.export(detail2, llm_ctx=ctx)
        assert call_count > initial_calls  # Additional calls made!


@pytest.mark.asyncio
async def test_spl_semantic_export_cache_separates_llm_context():
    service = SplSemanticExportService()

    detail = ProjectDetailResponse(
        project_id="cache-context-project-uuid",
        project_name="Caching System",
        project_description="Description",
        user_requirements="Requirements",
        actors=[],
        features=[],
        business_objects=[],
        flows=[],
        unresolved_gates=[]
    )

    call_count = 0

    def mock_ask_json_counter(prompt: str) -> dict:
        nonlocal call_count
        call_count += 1
        return {"coverage_passed": True, "semantic_risks": []}

    class CtxA:
        api_url = "http://mock-api.com"
        api_key = "mock-key-a"
        model_name = "mock-model-a"

    class CtxB:
        api_url = "http://mock-api.com"
        api_key = "mock-key-b"
        model_name = "mock-model-b"

    with patch("backend.integration.skill_backed_services.spl_semantic_export_service.SyncSkillBackedLLMJsonClient.ask_json", side_effect=mock_ask_json_counter):
        await service.export(detail, llm_ctx=CtxA())
        calls_after_ctx_a = call_count

        await service.export(detail, llm_ctx=CtxA())
        assert call_count == calls_after_ctx_a

        await service.export(detail, llm_ctx=CtxB())
        assert call_count > calls_after_ctx_a


@pytest.mark.asyncio
async def test_spl_semantic_export_coerces_llm_scalar_field_values():
    service = SplSemanticExportService()
    now = datetime.now()

    detail = ProjectDetailResponse(
        project_id="scalar-field-project-uuid",
        project_name="Scalar Field System",
        project_description="Description",
        user_requirements="Requirements",
        actors=[],
        features=[],
        business_objects=[
            BusinessObjectDetail(
                business_object_id=1,
                business_object_name="Device",
                business_object_description="Desc",
                business_object_attributes=[
                    BusinessObjectAttributeDetail(
                        business_object_attribute_id=10,
                        business_object_attribute_name="device_id",
                        business_object_attribute_description="Identifier",
                        business_object_attribute_type="integer",
                        business_object_attribute_example="123",
                        updated_at=now,
                    )
                ],
                updated_at=now,
            )
        ],
        flows=[],
        unresolved_gates=[],
    )

    def mock_ask_json(prompt: str) -> dict:
        if "translating a database-backed" in prompt:
            return {
                "type_name": "Device",
                "fields": [
                    {
                        "normalized_name": "device_id",
                        "spl_type": "number",
                        "description": 456,
                        "example": 123,
                        "is_enum": True,
                        "enum_candidates": 789,
                    }
                ],
            }
        return {"coverage_passed": True, "semantic_risks": []}

    class DummyCtx:
        api_url = "http://mock-api.com"
        api_key = "mock-key"
        model_name = "scalar-field-model"

    with patch("backend.integration.skill_backed_services.spl_semantic_export_service.SyncSkillBackedLLMJsonClient.ask_json", side_effect=mock_ask_json):
        spl_text = await service.export(detail, llm_ctx=DummyCtx())
        assert "Example: 123" in spl_text
        assert "789" in spl_text


@pytest.mark.asyncio
async def test_spl_export_routes_skill_unavailable():
    from contextlib import asynccontextmanager
    from fastapi.testclient import TestClient
    from backend.main import app
    from backend.api.dependencies.auth import get_current_user
    from backend.api.dependencies.ownership import require_owned_project
    from backend.database.model import ProjectModel, UserModel
    from backend.core.llm_context import LLMRequestContext

    @asynccontextmanager
    async def mock_llm_context_manager(user, session, project_id=None):
        yield LLMRequestContext(
            api_url="http://mock-api.com",
            api_key="mock-key",
            model_name="mock-model"
        )

    # Override dependencies to bypass DB/Auth
    app.dependency_overrides[require_owned_project] = lambda: ProjectModel(id=1, public_id="proj-1", name="TestProj")
    app.dependency_overrides[get_current_user] = lambda: UserModel(id=1, email="test@example.com")

    client = TestClient(app)

    with patch("backend.api.modules.project_lifecycle.routes.project.project_service.export_project_spl_syntax", side_effect=ValueError("spl_export_skill_unavailable")), \
         patch("backend.api.modules.project_lifecycle.routes.project.project_service.export_project_spl_semantic", side_effect=ValueError("spl_export_skill_unavailable")), \
         patch("backend.api.modules.project_lifecycle.routes.project.llm_context_manager", mock_llm_context_manager):

        # 1. Syntax route returns 503
        res_syntax = client.get("/api/projects/proj-1/export/spl/syntax")
        assert res_syntax.status_code == 503

        # 2. Semantic route returns 503
        res_semantic = client.get("/api/projects/proj-1/export/spl/semantic")
        assert res_semantic.status_code == 503

    # Cleanup overrides
    app.dependency_overrides.pop(require_owned_project, None)
    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_spl_syntax_export_route_handles_chinese_filename():
    from fastapi.testclient import TestClient
    from backend.main import app
    from backend.api.dependencies.ownership import require_owned_project
    from backend.api.dependencies.auth import get_current_user
    from backend.database.model import ProjectModel, UserModel

    app.dependency_overrides[require_owned_project] = lambda: ProjectModel(
        id=1,
        public_id="proj-1",
        name="轻量本地音乐播放器",
    )
    app.dependency_overrides[get_current_user] = lambda: UserModel(
        id=1,
        email="test@example.com",
        preferred_locale="en-US",
    )

    client = TestClient(app)

    with patch(
        "backend.api.modules.project_lifecycle.routes.project.project_service.export_project_spl_syntax",
        return_value="[DEFINE_AGENT: Agent_test]\n[END_AGENT]\n",
    ) as export_mock:
        res_syntax = client.get("/api/projects/proj-1/export/spl/syntax")
        assert res_syntax.status_code == 200
        assert export_mock.await_args.kwargs["content_locale"] == "en-US"
        content_disposition = res_syntax.headers["content-disposition"]
        assert "filename*=" in content_disposition
        assert "%E8%BD%BB%E9%87%8F" in content_disposition

    app.dependency_overrides.pop(require_owned_project, None)
    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_spl_semantic_export_overall_timeout_config():
    import os
    service = SplSemanticExportService()
    now = datetime.now()

    detail = ProjectDetailResponse(
        project_id="timeout-config-proj-uuid",
        project_name="System",
        project_description="Desc",
        user_requirements="Reqs",
        actors=[],
        features=[],
        business_objects=[
            BusinessObjectDetail(
                business_object_id=1,
                business_object_name="Device",
                business_object_description="Desc",
                business_object_attributes=[],
                updated_at=now
            )
        ],
        flows=[],
        unresolved_gates=[]
    )

    def slow_ask_json(prompt: str) -> dict:
        import time
        time.sleep(0.05)
        return {"type_name": "Device", "fields": []}

    class DummyCtx:
        api_url = "http://mock-api.com"
        api_key = "mock-key"
        model_name = "mock-model"

    ctx = DummyCtx()

    with patch("backend.integration.skill_backed_services.spl_semantic_export_service.SyncSkillBackedLLMJsonClient.ask_json", side_effect=slow_ask_json):
        # Set short timeout to 0.01
        with patch.dict(os.environ, {"SPL_SEMANTIC_EXPORT_TIMEOUT_SECONDS": "0.01"}):
            with pytest.raises(ValueError) as exc_info:
                await service.export(detail, llm_ctx=ctx)
            assert "spl_export_timeout" in str(exc_info.value)


@pytest.mark.asyncio
async def test_spl_semantic_concurrency_env_var():
    import os
    service = SplSemanticExportService()

    detail = ProjectDetailResponse(
        project_id="concurrency-proj-uuid",
        project_name="System",
        project_description="Desc",
        user_requirements="Reqs",
        actors=[],
        features=[],
        business_objects=[],
        flows=[],
        unresolved_gates=[]
    )

    class DummyCtx:
        api_url = "http://mock-api.com"
        api_key = "mock-key"
        model_name = "mock-model"

    ctx = DummyCtx()

    def mock_ask_json(prompt: str) -> dict:
        return {"coverage_passed": True, "semantic_risks": []}

    with patch("backend.integration.skill_backed_services.spl_semantic_export_service.SyncSkillBackedLLMJsonClient.ask_json", side_effect=mock_ask_json):
        with patch("asyncio.Semaphore", wraps=asyncio.Semaphore) as mock_sem:
            # Case 1: SPL_SEMANTIC_MAX_CONCURRENCY = 12
            with patch.dict(os.environ, {"SPL_SEMANTIC_MAX_CONCURRENCY": "12"}):
                await service.export(detail, llm_ctx=ctx)
                mock_sem.assert_any_call(12)

            mock_sem.reset_mock()

            # Case 2: SPL_SEMANTIC_TYPE_MAX_CONCURRENCY = 8
            with patch.dict(os.environ, {"SPL_SEMANTIC_TYPE_MAX_CONCURRENCY": "8"}):
                # Modify project data to bypass cache and trigger Semaphore limit
                detail.project_description = "Modified Desc to bypass cache"
                await service.export(detail, llm_ctx=ctx)
                mock_sem.assert_any_call(8)


@pytest.mark.asyncio
async def test_spl_semantic_export_enabled_flag():
    import os
    service = SplSemanticExportService()

    detail = ProjectDetailResponse(
        project_id="flag-proj-uuid",
        project_name="System",
        project_description="Desc",
        user_requirements="Reqs",
        actors=[],
        features=[],
        business_objects=[],
        flows=[],
        unresolved_gates=[]
    )

    with patch.dict(os.environ, {"SPL_SEMANTIC_EXPORT_ENABLED": "false"}):
        with pytest.raises(ValueError) as exc_info:
            await service.export(detail)
        assert "spl_export_semantic_disabled" in str(exc_info.value)


@pytest.mark.asyncio
async def test_spl_export_routes_semantic_disabled():
    from fastapi.testclient import TestClient
    from backend.main import app
    from backend.api.dependencies.auth import get_current_user
    from backend.api.dependencies.ownership import require_owned_project
    from backend.database.model import ProjectModel, UserModel
    from backend.api.dependencies.llm import get_llm_context

    # Override dependencies to bypass DB/Auth
    app.dependency_overrides[require_owned_project] = lambda: ProjectModel(id=1, public_id="proj-1", name="TestProj")
    app.dependency_overrides[get_current_user] = lambda: UserModel(id=1, email="test@example.com")
    app.dependency_overrides[get_llm_context] = lambda: (_ for _ in ()).throw(AssertionError("LLM context should not be resolved when semantic export is disabled"))

    client = TestClient(app)

    with patch.dict(os.environ, {"SPL_SEMANTIC_EXPORT_ENABLED": "false"}), \
         patch("backend.api.modules.project_lifecycle.routes.project.project_service.export_project_spl_semantic") as mock_export:
        res_semantic = client.get("/api/projects/proj-1/export/spl/semantic")
        assert res_semantic.status_code == 400
        assert res_semantic.json()["detail"] == "spl_export_semantic_disabled"
        mock_export.assert_not_called()

    # Cleanup overrides
    app.dependency_overrides.pop(require_owned_project, None)
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_llm_context, None)
