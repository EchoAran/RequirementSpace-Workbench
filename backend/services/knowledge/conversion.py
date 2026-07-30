import os
import re
import time
import logging
import asyncio
import sys
import types
from backend.database.database import AsyncSessionLocal
from backend.database.model import KnowledgeDocumentModel

logger = logging.getLogger(__name__)

try:
    from markitdown import MarkItDown
except ImportError:
    class MarkItDown:
        def convert(self, file_path: str):
            if os.path.splitext(file_path)[1].lower() not in {".txt", ".md", ".csv", ".json", ".html"}:
                raise ImportError("No module named 'markitdown'")
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                return types.SimpleNamespace(text_content=f.read())

    markitdown_stub = types.ModuleType("markitdown")
    markitdown_stub.MarkItDown = MarkItDown
    sys.modules.setdefault("markitdown", markitdown_stub)


class KnowledgeConversionService:
    @staticmethod
    async def convert_document(document_id: int, bind=None) -> None:
        """Convert document to Markdown asynchronously and update its status."""
        session_creator = KnowledgeConversionService._session_creator(bind)
        document = await KnowledgeConversionService._mark_converting(
            document_id,
            session_creator,
        )
        if document is None:
            return
        storage_path, document_public_id, original_filename = document
        start_time = time.perf_counter()
        try:
            md_path = await KnowledgeConversionService._convert_to_markdown_file(
                storage_path,
                document_public_id,
                original_filename,
            )
            duration = time.perf_counter() - start_time
            logger.info(
                "Knowledge document converted successfully: doc_id=%s, duration=%.2fs",
                document_id, duration
            )
            await KnowledgeConversionService._mark_ready(
                document_id,
                md_path,
                session_creator,
            )
            from backend.services.knowledge.chunking import KnowledgeChunkingService
            await KnowledgeChunkingService.chunk_document(
                document_id=document_id,
                session_creator=session_creator
            )
        except Exception as e:
            duration = time.perf_counter() - start_time
            err_msg = str(e)
            err_msg = err_msg.replace(
                os.path.dirname(os.path.dirname(storage_path)),
                "",
            )
            logger.error(
                "Knowledge document conversion failed: doc_id=%s, duration=%.2fs, error=%s",
                document_id, duration, err_msg
            )
            await KnowledgeConversionService._mark_failed(
                document_id,
                err_msg,
                session_creator,
            )

    @staticmethod
    def _session_creator(bind):
        if bind is None:
            return AsyncSessionLocal
        from sqlalchemy.ext.asyncio import AsyncSession
        return lambda: AsyncSession(bind=bind, expire_on_commit=False)

    @staticmethod
    async def _mark_converting(document_id, session_creator):
        async with session_creator() as session:
            doc = await session.get(KnowledgeDocumentModel, document_id)
            if not doc or doc.status == "deleted":
                return None
            doc.status = "converting"
            await session.commit()
            return doc.storage_path, doc.public_id, doc.original_filename

    @staticmethod
    async def _convert_to_markdown_file(
        storage_path,
        document_public_id,
        original_filename,
    ):
        from backend.core.config import KNOWLEDGE_STORAGE_DIR
        abs_storage_dir = os.path.normcase(os.path.abspath(KNOWLEDGE_STORAGE_DIR))
        abs_file_path = os.path.normcase(os.path.abspath(storage_path))
        if os.path.commonpath([abs_storage_dir, abs_file_path]) != abs_storage_dir:
            raise ValueError("Path injection detected: file is outside storage directory")
        if not os.path.exists(storage_path):
            raise FileNotFoundError("Original document file not found on disk")

        md_content = await asyncio.to_thread(
            KnowledgeConversionService._run_markitdown,
            storage_path,
        )
        cleaned_content = KnowledgeConversionService._clean_markdown(md_content)
        import datetime
        iso_time = datetime.datetime.now(datetime.timezone.utc).isoformat()
        metadata_header = f"---\noriginal_filename: {original_filename}\nconverted_at: {iso_time}\n---\n\n"
        md_path = os.path.join(
            os.path.dirname(storage_path),
            f"{document_public_id}.md",
        )
        await asyncio.to_thread(
            KnowledgeConversionService._write_markdown,
            md_path,
            metadata_header + cleaned_content,
        )
        return md_path

    @staticmethod
    def _write_markdown(md_path, content) -> None:
        with open(md_path, "w", encoding="utf-8") as output:
            output.write(content)

    @staticmethod
    async def _mark_ready(document_id, md_path, session_creator) -> None:
        async with session_creator() as session:
            doc = await session.get(KnowledgeDocumentModel, document_id)
            if doc and doc.status != "deleted":
                doc.status = "ready"
                doc.markdown_path = md_path
                doc.error_message = None
                await session.commit()

    @staticmethod
    async def _mark_failed(document_id, err_msg, session_creator) -> None:
        async with session_creator() as session:
            doc = await session.get(KnowledgeDocumentModel, document_id)
            if doc and doc.status != "deleted":
                doc.status = "failed"
                doc.error_message = err_msg[:500]
                await session.commit()

    @staticmethod
    def _run_markitdown(file_path: str) -> str:
        md = MarkItDown()
        result = md.convert(file_path)
        return result.text_content

    @staticmethod
    def _clean_markdown(content: str) -> str:
        # Collapse multiple empty lines (max 2 consecutive newlines)
        return re.sub(r'\n{3,}', '\n\n', content).strip()
