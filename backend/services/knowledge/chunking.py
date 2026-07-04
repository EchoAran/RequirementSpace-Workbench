import os
import re
import logging
from sqlalchemy import delete
from backend.database.model import KnowledgeDocumentModel, KnowledgeChunkModel

logger = logging.getLogger(__name__)

def estimate_tokens(text: str) -> int:
    """
    Estimate token count for a text snippet.
    Counts Chinese characters as 1 token each.
    Counts English words as 1.3 tokens each.
    """
    if not text:
        return 0
    # Match Chinese characters
    chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
    # Remove Chinese characters to split remaining words/punctuation
    remaining = re.sub(r"[\u4e00-\u9fff]", " ", text)
    words = len(remaining.split())
    return int(chinese_chars + words * 1.3)

def chunk_markdown(content: str, max_tokens: int = 1500, target_tokens: int = 1000) -> list[dict]:
    """
    Markdown-aware chunking algorithm.
    Groups lines by headings and heading paths, then slices large blocks.
    """
    # 1. Parse headings and group lines into blocks with heading paths
    blocks = []
    
    current_headings = {i: "" for i in range(1, 7)}
    current_path = ""
    current_block_lines = []
    
    lines = content.splitlines()
    in_code_block = False
    
    for line in lines:
        stripped = line.strip()
        # Handle code block toggle
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_code_block = not in_code_block
            current_block_lines.append(line)
            continue
            
        if in_code_block:
            current_block_lines.append(line)
            continue
            
        # Check if it is a heading
        heading_match = re.match(r"^(#{1,6})\s+(.*)$", line)
        if heading_match:
            # Save existing block
            if current_block_lines:
                blocks.append((current_path, "\n".join(current_block_lines)))
                current_block_lines = []
                
            level = len(heading_match.group(1))
            title = heading_match.group(2).strip()
            current_headings[level] = title
            # Clear lower levels
            for l in range(level + 1, 7):
                current_headings[l] = ""
                
            # Rebuild heading path
            path_parts = [current_headings[i] for i in range(1, 7) if current_headings[i]]
            current_path = " > ".join(path_parts)
            
            # Heading line itself is part of the new block
            current_block_lines.append(line)
        else:
            current_block_lines.append(line)
            
    if current_block_lines:
        blocks.append((current_path, "\n".join(current_block_lines)))
        
    # 2. Slice/combine blocks into chunks
    chunks = []
    
    for path, block_text in blocks:
        block_tokens = estimate_tokens(block_text)
        if block_tokens <= max_tokens:
            chunks.append({
                "heading_path": path,
                "text": block_text,
                "token_estimate": block_tokens
            })
        else:
            # Block is too large. Split by paragraphs first
            paragraphs = block_text.split("\n\n")
            acc_lines = []
            acc_tokens = 0
            
            for p in paragraphs:
                p_tokens = estimate_tokens(p)
                if acc_tokens + p_tokens + 2 <= max_tokens:
                    acc_lines.append(p)
                    acc_tokens += p_tokens + 2
                else:
                    if acc_lines:
                        chunks.append({
                            "heading_path": path,
                            "text": "\n\n".join(acc_lines),
                            "token_estimate": acc_tokens
                        })
                        acc_lines = []
                        acc_tokens = 0
                    
                    if p_tokens > max_tokens:
                        # Split paragraph by sentence ending
                        sentences = re.split(r"(?<=[。\.])\s*", p)
                        s_acc = []
                        s_tokens = 0
                        for s in sentences:
                            s_tok = estimate_tokens(s)
                            if s_tokens + s_tok <= max_tokens:
                                s_acc.append(s)
                                s_tokens += s_tok
                            else:
                                if s_acc:
                                    chunks.append({
                                        "heading_path": path,
                                        "text": " ".join(s_acc),
                                        "token_estimate": s_tokens
                                    })
                                s_acc = [s]
                                s_tokens = s_tok
                        if s_acc:
                            acc_lines.append(" ".join(s_acc))
                            acc_tokens += s_tokens
                    else:
                        acc_lines.append(p)
                        acc_tokens += p_tokens + 2
                        
            if acc_lines:
                chunks.append({
                    "heading_path": path,
                    "text": "\n\n".join(acc_lines),
                    "token_estimate": acc_tokens
                })
                
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
                logger.warning("Document status is deleted, skipping chunking: %s", document_id)
                return
            if not doc.markdown_path or not os.path.exists(doc.markdown_path):
                logger.error("Markdown file not found on disk at: %s", doc.markdown_path)
                return
                
            try:
                with open(doc.markdown_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception as e:
                logger.error("Failed to read markdown file for chunking: %s, error=%s", doc.markdown_path, e)
                return

            # Clear old chunks first
            await session.execute(
                delete(KnowledgeChunkModel).where(KnowledgeChunkModel.document_id == document_id)
            )

            # Generate chunks
            chunks_data = chunk_markdown(content)
            
            for idx, c in enumerate(chunks_data):
                chunk = KnowledgeChunkModel(
                    document_id=doc.id,
                    project_id=doc.project_id,
                    workspace_id=doc.workspace_id,
                    chunk_index=idx,
                    heading_path=c["heading_path"],
                    text=c["text"],
                    token_estimate=c["token_estimate"]
                )
                session.add(chunk)
                
            await session.commit()
            logger.info("Successfully generated %s chunks for document: %s", len(chunks_data), document_id)
