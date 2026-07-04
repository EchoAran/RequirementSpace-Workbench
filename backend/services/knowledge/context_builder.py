import logging
from backend.services.knowledge.chunking import estimate_tokens
from backend.services.knowledge.retrieval import KnowledgeRetrievalService

logger = logging.getLogger(__name__)

# System instructions to append
CONTEXT_TEMPLATE = """# 项目知识库参考

以下内容来自用户上传文件。你可以基于这些内容推断需求，但不得声称文件中存在未出现的信息。

{chunks_content}

# 知识库使用规则

- 优先使用项目知识库中明确出现的信息。
- 如果知识库与用户当前输入冲突，优先遵循用户当前输入，并指出冲突。
- 不要输出大段原文。
- 如果知识库没有覆盖当前问题，可以基于用户输入和通用需求工程经验继续工作。"""

class KnowledgeContextBuilder:
    @staticmethod
    async def build(
        *,
        project_id: int | None = None,
        workspace_id: int | None = None,
        purpose: str,
        query: str,
        token_budget: int = 4000,
        session,
    ) -> str:
        """
        Build the references reference prompt block matching context criteria.
        Returns empty string if no references matches.
        """
        # 1. Retrieve ranked matching chunks
        chunks = await KnowledgeRetrievalService.retrieve_chunks(
            session=session,
            query=query,
            project_id=project_id,
            workspace_id=workspace_id,
            top_n=15
        )

        if not chunks:
            return ""

        # 2. Format and accumulate chunks within token budget
        acc_chunks = []
        current_tokens = 0
        
        # Estimate static wrapper instruction tokens
        wrapper_tokens = estimate_tokens(CONTEXT_TEMPLATE.format(chunks_content=""))
        
        for chunk in chunks:
            doc = chunk.document
            
            # Format source heading
            if chunk.heading_path:
                source_header = f"[Source: {doc.original_filename} > {chunk.heading_path}]"
            else:
                source_header = f"[Source: {doc.original_filename}]"
                
            formatted_chunk = f"{source_header}\n\n{chunk.text}"
            chunk_tokens = estimate_tokens(formatted_chunk)

            # Check token budget (accounting for the wrapper template overhead)
            if wrapper_tokens + current_tokens + chunk_tokens + 2 > token_budget:
                # Stop if budget exceeded
                break
                
            acc_chunks.append(formatted_chunk)
            current_tokens += chunk_tokens + 2

        if not acc_chunks:
            return ""

        # 3. Assemble and return wrapped reference string
        chunks_content = "\n\n---\n\n".join(acc_chunks)
        return CONTEXT_TEMPLATE.format(chunks_content=chunks_content)
