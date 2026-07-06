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
        if bind is not None:
            from sqlalchemy.ext.asyncio import AsyncSession
            session_creator = lambda: AsyncSession(bind=bind, expire_on_commit=False)
        else:
            session_creator = AsyncSessionLocal

        # 1. Update status to converting
        async with session_creator() as session:
            doc = await session.get(KnowledgeDocumentModel, document_id)
            if not doc or doc.status == "deleted":
                return
            doc.status = "converting"
            await session.commit()

            storage_path = doc.storage_path
            document_public_id = doc.public_id
            original_filename = doc.original_filename

        # 2. Perform conversion
        start_time = time.perf_counter()
        try:
            # Check file exists and is in KNOWLEDGE_STORAGE_DIR
            from backend.core.config import KNOWLEDGE_STORAGE_DIR
            abs_storage_dir = os.path.normcase(os.path.abspath(KNOWLEDGE_STORAGE_DIR))
            abs_file_path = os.path.normcase(os.path.abspath(storage_path))
            if os.path.commonpath([abs_storage_dir, abs_file_path]) != abs_storage_dir:
                raise ValueError("Path injection detected: file is outside storage directory")

            if not os.path.exists(storage_path):
                raise FileNotFoundError("Original document file not found on disk")

            # Call MarkItDown in thread pool to avoid blocking async event loop
            md_content = await asyncio.to_thread(
                KnowledgeConversionService._run_markitdown,
                storage_path
            )

            # Clean Markdown content
            cleaned_content = KnowledgeConversionService._clean_markdown(md_content)

            # Prepend metadata header
            import datetime
            iso_time = datetime.datetime.now(datetime.timezone.utc).isoformat()
            metadata_header = f"---\noriginal_filename: {original_filename}\nconverted_at: {iso_time}\n---\n\n"
            final_content = metadata_header + cleaned_content

            # Save Markdown file next to original file
            base_dir = os.path.dirname(storage_path)
            md_filename = f"{document_public_id}.md"
            md_path = os.path.join(base_dir, md_filename)

            with open(md_path, "w", encoding="utf-8") as f:
                f.write(final_content)

            duration = time.perf_counter() - start_time
            logger.info(
                "Knowledge document converted successfully: doc_id=%s, duration=%.2fs",
                document_id, duration
            )

            # 3. Update DB to ready
            async with session_creator() as session:
                doc = await session.get(KnowledgeDocumentModel, document_id)
                if doc and doc.status != "deleted":
                    doc.status = "ready"
                    doc.markdown_path = md_path
                    doc.error_message = None
                    await session.commit()

            # 4. Trigger chunking
            from backend.services.knowledge.chunking import KnowledgeChunkingService
            await KnowledgeChunkingService.chunk_document(
                document_id=document_id,
                session_creator=session_creator
            )

        except Exception as e:
            duration = time.perf_counter() - start_time
            err_msg = str(e)
            
            # Clean absolute path info from error message to prevent leakage
            err_msg = err_msg.replace(os.path.dirname(os.path.dirname(storage_path)), "")
            logger.error(
                "Knowledge document conversion failed: doc_id=%s, duration=%.2fs, error=%s",
                document_id, duration, err_msg
            )

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
