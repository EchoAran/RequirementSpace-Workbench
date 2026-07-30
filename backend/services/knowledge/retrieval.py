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

        candidate_chunks = await KnowledgeRetrievalService._load_candidates(
            session,
            project_id,
            workspace_id,
        )
        if not candidate_chunks:
            return []

        query_tokens, query_phrases = (
            KnowledgeRetrievalService._build_search_terms(query)
        )
        scored_chunks = [
            scored
            for chunk in candidate_chunks
            if (
                scored := KnowledgeRetrievalService._score_chunk(
                    chunk,
                    query_tokens,
                    query_phrases,
                )
            ) is not None
        ]
        scored_chunks.sort(key=lambda item: (-item["score"], -item["created_at"]))
        return [item["chunk"] for item in scored_chunks[:top_n]]

    @staticmethod
    async def _load_candidates(session, project_id, workspace_id) -> list:
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
            return []

        result = await session.execute(stmt)
        return result.scalars().all()

    @staticmethod
    def _build_search_terms(query: str) -> tuple[list[str], list[str]]:
        query_tokens = tokenize_for_search(query)
        query_phrases = extract_phrases(query)
        if not query_tokens:
            query_tokens = [query.lower()]
            query_phrases = [query.lower()] if len(query) >= 2 else []
        return query_tokens, query_phrases

    @staticmethod
    def _score_chunk(chunk, query_tokens: list[str], query_phrases: list[str]):
        document = chunk.document
        body_tokens = set(tokenize_for_search(chunk.text))
        title_tokens = set(tokenize_for_search(chunk.heading_path))
        filename_tokens = set(tokenize_for_search(document.original_filename))
        body_keyword_hit = sum(
            1 for token in query_tokens if token in body_tokens
        )
        title_hit = sum(1 for token in query_tokens if token in title_tokens)
        filename_hit = sum(
            1 for token in query_tokens if token in filename_tokens
        )
        text_lower = chunk.text.lower()
        path_lower = chunk.heading_path.lower()
        name_lower = document.original_filename.lower()
        phrase_hit = sum(
            1
            for phrase in query_phrases
            if phrase in text_lower
            or phrase in path_lower
            or phrase in name_lower
        )
        score = title_hit * 3 + filename_hit * 2 + body_keyword_hit + phrase_hit * 2
        if score <= 0:
            return None
        return {
            "chunk": chunk,
            "score": score,
            "created_at": (
                document.created_at.timestamp()
                if document.created_at
                else 0
            ),
        }
