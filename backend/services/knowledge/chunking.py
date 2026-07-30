import logging
import os
import re

from sqlalchemy import delete

from backend.database.model import KnowledgeChunkModel, KnowledgeDocumentModel

logger = logging.getLogger(__name__)


def estimate_tokens(text: str) -> int:
    """Estimate tokens using Chinese characters and English word count."""
    if not text:
        return 0
    chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
    remaining = re.sub(r"[\u4e00-\u9fff]", " ", text)
    return int(chinese_chars + len(remaining.split()) * 1.3)


def _parse_markdown_blocks(content: str) -> list[tuple[str, str]]:
    blocks: list[tuple[str, str]] = []
    headings = {level: "" for level in range(1, 7)}
    path = ""
    block_lines: list[str] = []
    in_code_block = False

    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith(("```", "~~~")):
            in_code_block = not in_code_block
            block_lines.append(line)
            continue
        if in_code_block:
            block_lines.append(line)
            continue

        heading = re.match(r"^(#{1,6})\s+(.*)$", line)
        if not heading:
            block_lines.append(line)
            continue

        if block_lines:
            blocks.append((path, "\n".join(block_lines)))
            block_lines = []

        level = len(heading.group(1))
        headings[level] = heading.group(2).strip()
        for lower_level in range(level + 1, 7):
            headings[lower_level] = ""
        path = " > ".join(filter(None, headings.values()))
        block_lines.append(line)

    if block_lines:
        blocks.append((path, "\n".join(block_lines)))
    return blocks


def _chunk(path: str, text: str, token_estimate: int) -> dict:
    return {
        "heading_path": path,
        "text": text,
        "token_estimate": token_estimate,
    }


def _split_long_paragraph(
    path: str,
    paragraph: str,
    max_tokens: int,
) -> tuple[list[dict], str, int]:
    chunks: list[dict] = []
    accumulated: list[str] = []
    accumulated_tokens = 0

    for sentence in re.split(r"(?<=[。！？.!?])\s*", paragraph):
        sentence_tokens = estimate_tokens(sentence)
        if accumulated and accumulated_tokens + sentence_tokens > max_tokens:
            chunks.append(_chunk(path, " ".join(accumulated), accumulated_tokens))
            accumulated = []
            accumulated_tokens = 0
        accumulated.append(sentence)
        accumulated_tokens += sentence_tokens

    return chunks, " ".join(accumulated), accumulated_tokens


def _split_large_block(path: str, block_text: str, max_tokens: int) -> list[dict]:
    chunks: list[dict] = []
    accumulated: list[str] = []
    accumulated_tokens = 0

    for paragraph in block_text.split("\n\n"):
        paragraph_tokens = estimate_tokens(paragraph)
        if accumulated_tokens + paragraph_tokens + 2 <= max_tokens:
            accumulated.append(paragraph)
            accumulated_tokens += paragraph_tokens + 2
            continue

        if accumulated:
            chunks.append(_chunk(path, "\n\n".join(accumulated), accumulated_tokens))
            accumulated = []
            accumulated_tokens = 0

        if paragraph_tokens <= max_tokens:
            accumulated.append(paragraph)
            accumulated_tokens = paragraph_tokens + 2
            continue

        sentence_chunks, remainder, remainder_tokens = _split_long_paragraph(
            path,
            paragraph,
            max_tokens,
        )
        chunks.extend(sentence_chunks)
        if remainder:
            accumulated.append(remainder)
            accumulated_tokens = remainder_tokens

    if accumulated:
        chunks.append(_chunk(path, "\n\n".join(accumulated), accumulated_tokens))
    return chunks


def chunk_markdown(content: str, max_tokens: int = 1500) -> list[dict]:
    """Split Markdown along heading, paragraph, then sentence boundaries."""
    chunks: list[dict] = []
    for path, block_text in _parse_markdown_blocks(content):
        block_tokens = estimate_tokens(block_text)
        if block_tokens <= max_tokens:
            chunks.append(_chunk(path, block_text, block_tokens))
        else:
            chunks.extend(_split_large_block(path, block_text, max_tokens))
    return chunks


class KnowledgeChunkingService:
    @staticmethod
    async def chunk_document(document_id: int, session_creator) -> None:
        """
        Chunk a ready Markdown document and write chunks into the database.
        Cleans any existing chunks first to support retry/conversion-update idempotency.
        """
        async with session_creator() as session:
            doc = await session.get(KnowledgeDocumentModel, document_id)
            if not doc:
                logger.error("Document not found for chunking: %s", document_id)
                return
            if doc.status == "deleted":
                logger.warning(
                    "Document status is deleted, skipping chunking: %s",
                    document_id,
                )
                return
            if not doc.markdown_path or not os.path.exists(doc.markdown_path):
                logger.error("Markdown file not found on disk at: %s", doc.markdown_path)
                return

            try:
                with open(doc.markdown_path, "r", encoding="utf-8") as markdown_file:
                    content = markdown_file.read()
            except Exception as error:
                logger.error(
                    "Failed to read markdown file for chunking: %s, error=%s",
                    doc.markdown_path,
                    error,
                )
                return

            await session.execute(
                delete(KnowledgeChunkModel).where(
                    KnowledgeChunkModel.document_id == document_id,
                )
            )

            chunks_data = chunk_markdown(content)
            for index, chunk_data in enumerate(chunks_data):
                session.add(KnowledgeChunkModel(
                    document_id=doc.id,
                    project_id=doc.project_id,
                    workspace_id=doc.workspace_id,
                    chunk_index=index,
                    heading_path=chunk_data["heading_path"],
                    text=chunk_data["text"],
                    token_estimate=chunk_data["token_estimate"],
                ))

            await session.commit()
            logger.info(
                "Successfully generated %s chunks for document: %s",
                len(chunks_data),
                document_id,
            )
