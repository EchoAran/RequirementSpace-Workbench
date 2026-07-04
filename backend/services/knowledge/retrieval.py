import logging
import re
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from backend.database.model import KnowledgeDocumentModel, KnowledgeChunkModel
from backend.services.knowledge.tokenizer import tokenize_for_search

logger = logging.getLogger(__name__)

def extract_phrases(query: str) -> list[str]:
    """
    Extract contiguous substrings of length >= 2 from query for phrase matching.
    Includes Chinese n-grams (length 2-4) and English/numeric tokens of length >= 2.
    """
    if not query:
        return []
    
    phrases = []
    
    # 1. Chinese contiguous n-grams
    chinese_seqs = re.findall(r"[\u4e00-\u9fff]+", query)
    for seq in chinese_seqs:
        s_len = len(seq)
        for l in range(2, min(10, s_len + 1)):
            for i in range(s_len - l + 1):
                phrases.append(seq[i:i+l].lower())
                
    # 2. English / numeric tokens of length >= 2
    tokens = tokenize_for_search(query)
    for t in tokens:
        if len(t) >= 2:
            phrases.append(t)
            
    return list(set(phrases))

class KnowledgeRetrievalService:
    @staticmethod
    async def retrieve_chunks(
        *,
        session,
        query: str,
        project_id: int | None = None,
        workspace_id: int | None = None,
        top_n: int = 10,
    ) -> list[KnowledgeChunkModel]:
        """
        Retrieve chunks matching the keyword query.
        Calculates title, filename, body overlaps, and continuous phrase matches.
        Orders by score descending, then by document creation time descending (recency).
        """
        from backend.core.config import KNOWLEDGE_BASE_ENABLED
        if not KNOWLEDGE_BASE_ENABLED or not query:
            return []

        # 1. Query candidate chunks from active, AI-enabled documents
        stmt = (
            select(KnowledgeChunkModel)
            .join(KnowledgeDocumentModel)
            .options(joinedload(KnowledgeChunkModel.document))
            .where(
                KnowledgeDocumentModel.status == "ready",
                KnowledgeDocumentModel.ai_enabled == True
            )
        )

        if project_id is not None:
            stmt = stmt.where(KnowledgeChunkModel.project_id == project_id)
        elif workspace_id is not None:
            stmt = stmt.where(KnowledgeChunkModel.workspace_id == workspace_id)
        else:
            # Neither project nor workspace id provided: return empty
            return []

        result = await session.execute(stmt)
        candidate_chunks = result.scalars().all()
        if not candidate_chunks:
            return []

        # 2. Extract query tokens and phrases
        query_tokens = tokenize_for_search(query)
        query_phrases = extract_phrases(query)

        if not query_tokens:
            # If tokenization results in nothing, fall back to simple substring match check on candidates
            query_tokens = [query.lower()]
            query_phrases = [query.lower()] if len(query) >= 2 else []

        # 3. Score candidates
        scored_chunks = []
        for chunk in candidate_chunks:
            doc = chunk.document
            
            # Tokenize body, heading path, and filename
            body_tokens = set(tokenize_for_search(chunk.text))
            title_tokens = set(tokenize_for_search(chunk.heading_path))
            filename_tokens = set(tokenize_for_search(doc.original_filename))

            # Compute hit counts
            body_keyword_hit = sum(1 for q_t in query_tokens if q_t in body_tokens)
            title_hit = sum(1 for q_t in query_tokens if q_t in title_tokens)
            filename_hit = sum(1 for q_t in query_tokens if q_t in filename_tokens)

            # Compute phrase matches
            phrase_hit = 0
            text_lower = chunk.text.lower()
            path_lower = chunk.heading_path.lower()
            name_lower = doc.original_filename.lower()

            for phrase in query_phrases:
                if phrase in text_lower or phrase in path_lower or phrase in name_lower:
                    phrase_hit += 1

            # Scoring formula
            score = title_hit * 3 + filename_hit * 2 + body_keyword_hit + phrase_hit * 2

            # Only return chunks with score > 0
            if score > 0:
                scored_chunks.append({
                    "chunk": chunk,
                    "score": score,
                    "created_at": doc.created_at.timestamp() if doc.created_at else 0
                })

        # 4. Sort by score descending, then by created_at descending (recency)
        # Ties are broken by the most recently uploaded documents
        scored_chunks.sort(key=lambda x: (-x["score"], -x["created_at"]))

        # Return the chunk models up to top_n
        return [item["chunk"] for item in scored_chunks[:top_n]]
