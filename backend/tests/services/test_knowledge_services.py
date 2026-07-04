# -*- coding: utf-8 -*-
import os
import pytest
from datetime import datetime, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database.database import Base
from backend.database.model import KnowledgeWorkspaceModel, KnowledgeDocumentModel, KnowledgeChunkModel
from backend.services.knowledge.tokenizer import tokenize_for_search
from backend.services.knowledge.chunking import chunk_markdown, KnowledgeChunkingService
from backend.services.knowledge.retrieval import KnowledgeRetrievalService, extract_phrases
from backend.services.knowledge.context_builder import KnowledgeContextBuilder

DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture
async def knowledge_test_db():
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    yield session_factory
    await engine.dispose()


def test_tokenize_for_search():
    # Test basic tokenization
    tokens = tokenize_for_search("Hello, this is a plain text for knowledge source.")
    assert "hello" in tokens
    assert "plain" in tokens
    assert "text" in tokens
    # Test mixed Chinese/English and punctuation removal
    tokens_mixed = tokenize_for_search("创建项目：订单退款 workflow, 接口名 refund_amount. 包含 100 状态码！")
    assert "创建" in tokens_mixed
    assert "项目" in tokens_mixed
    assert "订单" in tokens_mixed
    assert "退款" in tokens_mixed
    assert "workflow" in tokens_mixed
    assert "refund_amount" in tokens_mixed
    assert "100" in tokens_mixed
    
    # Test stop words filtering
    tokens_stop = tokenize_for_search("这是一个关于所有退款的东西")
    assert "这是一个" not in tokens_stop
    assert "所有" not in tokens_stop
    assert "退款" in tokens_stop


def test_extract_phrases():
    # Chinese phrase extraction (n-grams)
    phrases = extract_phrases("订单退款流程")
    assert "订单" in phrases
    assert "退款" in phrases
    assert "流程" in phrases
    assert "订单退款" in phrases
    assert "退款流程" in phrases
    assert "订单退款流程" in phrases

    # English phrases
    phrases_eng = extract_phrases("refund_amount workflow")
    assert "refund_amount" in phrases_eng
    assert "workflow" in phrases_eng


def test_chunk_markdown_logic():
    content = """# Title 1
## Subtitle 1
This is paragraph one under subtitle 1.

This is paragraph two.

# Title 2
Another section.
"""
    chunks = chunk_markdown(content)
    # The heading Title 1 has no body text immediately (followed by Subtitle 1),
    # so it naturally splits into:
    # 1) heading_path='Title 1', text='# Title 1'
    # 2) heading_path='Title 1 > Subtitle 1', text='## Subtitle 1\n...'
    # 3) heading_path='Title 2', text='# Title 2\nAnother section.'
    assert len(chunks) == 3
    assert chunks[0]["heading_path"] == "Title 1"
    assert chunks[1]["heading_path"] == "Title 1 > Subtitle 1"
    assert "This is paragraph one" in chunks[1]["text"]
    assert "This is paragraph two" in chunks[1]["text"]
    assert chunks[2]["heading_path"] == "Title 2"
    assert "Another section" in chunks[2]["text"]


@pytest.mark.asyncio
async def test_knowledge_services_e2e(knowledge_test_db, tmp_path):
    session_creator = knowledge_test_db

    # 1. Create Workspace
    async with session_creator() as session:
        ws = KnowledgeWorkspaceModel(owner_user_id=1, scope="project_creation", status="active")
        session.add(ws)
        await session.commit()
        workspace_id = ws.id

    # Create dummy markdown file
    md_content = """# System Requirements
## Refund Feature
The system must support refund requests.

## Database Schema
Table: `refund_log`, fields: `id`, `refund_amount`, `status_code`.
"""
    md_file = tmp_path / "test_doc.md"
    md_file.write_text(md_content, encoding="utf-8")

    # 2. Seed Document
    async with session_creator() as session:
        from backend.database.model import beijing_now
        doc = KnowledgeDocumentModel(
            workspace_id=workspace_id,
            owner_user_id=1,
            original_filename="requirements_v1.md",
            content_type="text/markdown",
            file_size=len(md_content),
            sha256="dummysha256",
            storage_path=str(md_file),
            markdown_path=str(md_file),
            status="ready",
            ai_enabled=True,
            created_at=beijing_now()
        )
        session.add(doc)
        await session.commit()
        doc_id = doc.id

    # 3. Test Chunking
    await KnowledgeChunkingService.chunk_document(doc_id, session_creator)

    # Verify chunks written to database
    async with session_creator() as session:
        chunks = (await session.execute(
            select(KnowledgeChunkModel).where(KnowledgeChunkModel.document_id == doc_id)
        )).scalars().all()
        # Chunks are:
        # 0: '# System Requirements'
        # 1: '## Refund Feature...'
        # 2: '## Database Schema...'
        assert len(chunks) == 3
        assert chunks[1].heading_path == "System Requirements > Refund Feature"
        assert "refund requests" in chunks[1].text
        assert chunks[2].heading_path == "System Requirements > Database Schema"
        assert "refund_amount" in chunks[2].text

    # 4. Test Retrieval
    async with session_creator() as session:
        # Retrieve by keyword match in body
        res = await KnowledgeRetrievalService.retrieve_chunks(
            session=session,
            query="refund requests",
            workspace_id=workspace_id,
        )
        assert len(res) >= 1
        assert res[0].heading_path == "System Requirements > Refund Feature"

        # Retrieve by heading path match
        res_heading = await KnowledgeRetrievalService.retrieve_chunks(
            session=session,
            query="Database Schema",
            workspace_id=workspace_id,
        )
        assert len(res_heading) >= 1
        assert res_heading[0].heading_path == "System Requirements > Database Schema"

        # Retrieve by technical identifier phrase match
        res_phrase = await KnowledgeRetrievalService.retrieve_chunks(
            session=session,
            query="refund_amount field",
            workspace_id=workspace_id,
        )
        assert len(res_phrase) >= 1
        assert res_phrase[0].heading_path == "System Requirements > Database Schema"

    # 5. Test AI Enabled Filtering
    async with session_creator() as session:
        doc_to_disable = await session.get(KnowledgeDocumentModel, doc_id)
        doc_to_disable.ai_enabled = False
        await session.commit()

        # Should retrieve nothing because ai_enabled is False
        res_disabled = await KnowledgeRetrievalService.retrieve_chunks(
            session=session,
            query="refund requests",
            workspace_id=workspace_id,
        )
        assert len(res_disabled) == 0

        # Enable it back
        doc_to_disable.ai_enabled = True
        await session.commit()

    # 6. Test Recency Weighting (Ties broken by created_at desc)
    # Upload a newer document with similar content
    md_content_newer = """# System Requirements
## Refund Feature
The newer system also supports refund requests.
"""
    md_file_newer = tmp_path / "test_doc_newer.md"
    md_file_newer.write_text(md_content_newer, encoding="utf-8")

    async with session_creator() as session:
        # doc_newer created 10 minutes later
        from backend.database.model import beijing_now
        doc_newer = KnowledgeDocumentModel(
            workspace_id=workspace_id,
            owner_user_id=1,
            original_filename="requirements_v2.md",
            content_type="text/markdown",
            file_size=len(md_content_newer),
            sha256="dummysha256_newer",
            storage_path=str(md_file_newer),
            markdown_path=str(md_file_newer),
            status="ready",
            ai_enabled=True,
            created_at=beijing_now() + timedelta(minutes=10)
        )
        session.add(doc_newer)
        await session.commit()
        doc_newer_id = doc_newer.id

    await KnowledgeChunkingService.chunk_document(doc_newer_id, session_creator)

    async with session_creator() as session:
        res_recency = await KnowledgeRetrievalService.retrieve_chunks(
            session=session,
            query="Refund Feature",
            workspace_id=workspace_id,
        )
        # Both documents match "Refund Feature" and "refund requests" with identical keyword/phrase score.
        # But document v2 is newer (created_at is later), so it must be ranked first!
        assert len(res_recency) >= 2
        assert res_recency[0].document.original_filename == "requirements_v2.md"

    # 7. Test Context Builder
    async with session_creator() as session:
        ctx = await KnowledgeContextBuilder.build(
            workspace_id=workspace_id,
            purpose="project_creation",
            query="refund requests",
            token_budget=4000,
            session=session,
        )
        assert "# 项目知识库参考" in ctx
        assert "requirements_v2.md" in ctx
        assert "The newer system also supports refund requests." in ctx

        # Test context builder token budget limit truncation
        ctx_small_budget = await KnowledgeContextBuilder.build(
            workspace_id=workspace_id,
            purpose="project_creation",
            query="Refund Feature",
            token_budget=150,  # Tiny budget
            session=session,
        )
        # Should return empty string or be truncated because 150 tokens is too small for context wrapper
        assert ctx_small_budget == ""

        # Test empty return when no query match or empty query
        ctx_empty = await KnowledgeContextBuilder.build(
            workspace_id=workspace_id,
            purpose="project_creation",
            query="nonexistent term",
            token_budget=4000,
            session=session,
        )
        assert ctx_empty == ""
