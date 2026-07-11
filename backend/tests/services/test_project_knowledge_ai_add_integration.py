# -*- coding: utf-8 -*-
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database.database import Base
from backend.database.model import (
    UserModel,
    ProjectModel,
    KnowledgeWorkspaceModel,
    KnowledgeDocumentModel,
    KnowledgeChunkModel,
    AIAddSessionModel,
    UserRole,
)
from backend.api.modules.ai_interaction.ai_add.application.session import AIAddSessionService
from backend.api.modules.ai_interaction.ai_add.application.interview_strategy import (
    InterviewStrategyRegistry,
    BaseInterviewStrategy,
)
from backend.services.knowledge.tokenizer import tokenize_for_search
from backend.services.knowledge.chunking import estimate_tokens

DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture
async def test_db():
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.fixture
def registry():
    reg = InterviewStrategyRegistry()
    
    # Custom strategies supporting knowledge_context
    class MockActorStrategy(BaseInterviewStrategy):
        target_type = "actor"
        required_context = ["actors"]
        
        async def interview(self, project_context, anchor, current_summary, latest_user_message, llm_call_chat, knowledge_context=None):
            system_prompt = "Mock system prompt for actor."
            # Trigger execute slot filling which wraps rules
            return await self._execute_llm_slot_filling(
                system_prompt=system_prompt,
                current_summary=current_summary,
                latest_user_message=latest_user_message,
                llm_call_chat=llm_call_chat,
                knowledge_context=knowledge_context,
            )
            
    class MockLegacyStrategy(BaseInterviewStrategy):
        target_type = "legacy_actor"
        required_context = ["actors"]
        
        async def interview(self, project_context, anchor, current_summary, latest_user_message, llm_call_chat):
            # Stub strategy WITHOUT knowledge_context parameter to test backward compatibility
            return {
                "assistant_message": "Stub reply",
                "is_ready_to_generate": True,
                "summary": {"known_facts": [{"key": "name", "value": "test"}]},
            }

    reg.register(MockActorStrategy())
    reg.register(MockLegacyStrategy())
    return reg


@pytest.fixture
def service(registry):
    return AIAddSessionService(strategy_registry=registry)


@pytest.mark.asyncio
async def test_ai_add_knowledge_retrieval_and_prompts(test_db, service):
    # 1. Setup Project 1 & WS 1 (attached to Project 1)
    p1 = ProjectModel(name="Project 1", description="Proj 1 desc", user_requirements="Proj 1 reqs", owner_user_id=1)
    test_db.add(p1)
    await test_db.flush()

    ws1 = KnowledgeWorkspaceModel(status="attached", project_id=p1.id, owner_user_id=1)
    test_db.add(ws1)
    await test_db.flush()

    # Doc 1: Active and AI Enabled (should be retrieved)
    doc1 = KnowledgeDocumentModel(
        workspace_id=ws1.id,
        project_id=p1.id,
        owner_user_id=1,
        original_filename="refund.md",
        content_type="text/markdown",
        file_size=100,
        sha256="abc",
        storage_path="refund.md",
        status="ready",
        ai_enabled=True,
    )
    test_db.add(doc1)
    await test_db.flush()

    chunk1 = KnowledgeChunkModel(
        document_id=doc1.id,
        project_id=p1.id,
        heading_path="Refund Details",
        text="The refund limit is 500 dollars.",
        token_estimate=10,
        chunk_index=0,
    )
    test_db.add(chunk1)

    # Doc 2: Active but AI Disabled (should NOT be retrieved)
    doc2 = KnowledgeDocumentModel(
        workspace_id=ws1.id,
        project_id=p1.id,
        owner_user_id=1,
        original_filename="secret.md",
        content_type="text/markdown",
        file_size=100,
        sha256="def",
        storage_path="secret.md",
        status="ready",
        ai_enabled=False,
    )
    test_db.add(doc2)
    await test_db.flush()

    chunk2 = KnowledgeChunkModel(
        document_id=doc2.id,
        project_id=p1.id,
        heading_path="Secrets",
        text="This should not be exposed to AI.",
        token_estimate=10,
        chunk_index=0,
    )
    test_db.add(chunk2)

    # 2. Setup Project 2 & WS 2 (Cross-project boundary test, should NOT be retrieved for Project 1)
    p2 = ProjectModel(name="Project 2", description="Proj 2 desc", user_requirements="Proj 2 reqs", owner_user_id=1)
    test_db.add(p2)
    await test_db.flush()

    ws2 = KnowledgeWorkspaceModel(status="attached", project_id=p2.id, owner_user_id=1)
    test_db.add(ws2)
    await test_db.flush()

    doc3 = KnowledgeDocumentModel(
        workspace_id=ws2.id,
        project_id=p2.id,
        owner_user_id=1,
        original_filename="other_refund.md",
        content_type="text/markdown",
        file_size=100,
        sha256="ghi",
        storage_path="other_refund.md",
        status="ready",
        ai_enabled=True,
    )
    test_db.add(doc3)
    await test_db.flush()

    chunk3 = KnowledgeChunkModel(
        document_id=doc3.id,
        project_id=p2.id,
        heading_path="Other Refund Details",
        text="Project two refund limit is 1000 dollars.",
        token_estimate=10,
        chunk_index=0,
    )
    test_db.add(chunk3)
    await test_db.flush()

    # Doc 4: Active, AI Enabled but status is 'failed' (should NOT be retrieved)
    doc4 = KnowledgeDocumentModel(
        workspace_id=ws1.id,
        project_id=p1.id,
        owner_user_id=1,
        original_filename="failed_doc.md",
        content_type="text/markdown",
        file_size=100,
        sha256="abc4",
        storage_path="failed_doc.md",
        status="failed",
        ai_enabled=True,
    )
    test_db.add(doc4)
    await test_db.flush()

    chunk4 = KnowledgeChunkModel(
        document_id=doc4.id,
        project_id=p1.id,
        heading_path="Failed Details",
        text="This failed document should be ignored.",
        token_estimate=10,
        chunk_index=0,
    )
    test_db.add(chunk4)

    # Doc 5: Active, AI Enabled but status is 'converting' (should NOT be retrieved)
    doc5 = KnowledgeDocumentModel(
        workspace_id=ws1.id,
        project_id=p1.id,
        owner_user_id=1,
        original_filename="converting_doc.md",
        content_type="text/markdown",
        file_size=100,
        sha256="abc5",
        storage_path="converting_doc.md",
        status="converting",
        ai_enabled=True,
    )
    test_db.add(doc5)
    await test_db.flush()

    chunk5 = KnowledgeChunkModel(
        document_id=doc5.id,
        project_id=p1.id,
        heading_path="Converting Details",
        text="This converting document should be ignored.",
        token_estimate=10,
        chunk_index=0,
    )
    test_db.add(chunk5)
    await test_db.flush()

    # Create AIAddSession for Project 1
    session_res = await service.create_session(
        project_id=p1.public_id,
        target_type="actor",
        anchor={},
        session=test_db,
        owner_user_id=1,
    )
    session_id = session_res["session_id"]

    # 3. Test interview phase: check if knowledge_context is retrieved and injected into prompt
    from backend.services.llm_handler_service import LLMHandler
    with patch.object(LLMHandler, "call_chat", new_callable=AsyncMock) as mock_call_chat:
        mock_call_chat.return_value = '{"assistant_message": "Ask details?", "is_ready_to_generate": true, "known_facts": [{"key": "name", "value": "Admin"}], "missing_facts": []}'
        
        await service.append_user_message(
            session_id=session_id,
            content="Tell me about refund details limit",
            db_session=test_db,
        )
        
        # Verify call_chat messages argument
        mock_call_chat.assert_called_once()
        messages = mock_call_chat.call_args[1]["messages"]
        system_prompt = messages[0]["content"]
        
        # Check system prompt includes doc1 chunks but NOT doc2 or doc3 or doc4 or doc5
        assert "[Source: refund.md > Refund Details]" in system_prompt
        assert "The refund limit is 500 dollars." in system_prompt
        assert "secret.md" not in system_prompt
        assert "other_refund.md" not in system_prompt
        assert "failed_doc.md" not in system_prompt
        assert "converting_doc.md" not in system_prompt

    # 4. Test legacy strategy signature compatibility (should not crash when strategy doesn't accept knowledge_context)
    legacy_session_res = await service.create_session(
        project_id=p1.public_id,
        target_type="legacy_actor",
        anchor={},
        session=test_db,
        owner_user_id=1,
    )
    legacy_session_id = legacy_session_res["session_id"]
    
    # Should work without TypeError
    legacy_reply = await service.append_user_message(
        session_id=legacy_session_id,
        content="Tell me about refund details limit",
        db_session=test_db,
    )
    assert legacy_reply["is_ready_to_generate"] is True

    # 5. Test generation phase: check if knowledge_context is retrieved and injected into single object generators
    with patch.object(LLMHandler, "call_llm", new_callable=AsyncMock) as mock_call_llm:
        mock_call_llm.return_value = '{"actor": {"name": "Admin", "description": "Refund officer"}, "rationale": "tested"}'
        
        # Generate draft for Project 1
        draft_res = await service.generate_draft(
            session_id=session_id,
            db_session=test_db,
            owner_user_id=1,
        )
        
        assert draft_res is not None
        # Check that mock call_llm prompt contains knowledge context
        prompt_arg = mock_call_llm.call_args[1]["prompt"]
        assert "[Source: refund.md > Refund Details]" in prompt_arg
        assert "The refund limit is 500 dollars." in prompt_arg
        assert "secret.md" not in prompt_arg
        assert "other_refund.md" not in prompt_arg
