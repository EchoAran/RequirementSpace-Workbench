import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.model import (
    KnowledgeDocumentModel,
    UserModel,
    UserRole,
    UserLLMConfigModel,
)
from backend.api.modules.project_configuration.schemas import (
    ProjectConfigurationResponse,
    ProjectKnowledgeSummary,
    ProjectLLMSummary,
)
from backend.api.modules.project_configuration.application.generation_strategy_config_service import (
    GenerationStrategyConfigService,
)

logger = logging.getLogger(__name__)

class ProjectConfigurationService:
    def __init__(self):
        self.strategy_service = GenerationStrategyConfigService()

    async def get_active_llm_summary(self, user_id: int, project_id: int, session: AsyncSession) -> ProjectLLMSummary:
        # 1. Check Project-level LLM Config
        from backend.database.model import ProjectLLMConfigModel
        stmt = select(ProjectLLMConfigModel).where(ProjectLLMConfigModel.project_id == project_id)
        res = await session.execute(stmt)
        db_proj = res.scalar_one_or_none()
        if db_proj:
            return ProjectLLMSummary(
                configured=True,
                source="project",
                model_name=db_proj.model_name,
                api_key_last4=db_proj.api_key_last4
            )

        effective_source = "system"
        effective_model_name = None

        # Load user to check role
        stmt_user = select(UserModel).where(UserModel.id == user_id)
        res_user = await session.execute(stmt_user)
        user = res_user.scalar_one_or_none()
        if not user:
            return ProjectLLMSummary(configured=False, source="system", model_name=None, api_key_last4=None)

        # 2. Check Personal-level LLM Config (Only applies to non-admin users)
        if user.role != UserRole.ADMIN.value:
            stmt_config = select(UserLLMConfigModel).where(UserLLMConfigModel.user_id == user_id)
            res_config = await session.execute(stmt_config)
            db_config = res_config.scalar_one_or_none()
            if db_config:
                effective_source = "personal"
                effective_model_name = db_config.model_name

        # 3. Check System-level LLM Config (From server-side environment variables)
        if effective_source == "system":
            from backend.services.llm_handler_service import load_llm_config
            server_config = load_llm_config()
            if server_config:
                effective_model_name = server_config.get("model_name")

        return ProjectLLMSummary(
            configured=False,
            source=effective_source,
            model_name=effective_model_name,
            api_key_last4=None
        )

    async def get_configuration(
        self,
        project_id: int,
        project_public_id: str,
        content_locale: str | None,
        user_id: int,
        session: AsyncSession
    ) -> ProjectConfigurationResponse:
        # 1. Generation Strategy
        strategy_config = await self.strategy_service.get_for_project(project_id, session)

        # 2. Knowledge Base Summary
        from backend.core.config import KNOWLEDGE_BASE_ENABLED
        from backend.database.model import ProjectGenerationStrategyConfigModel
        
        stmt = select(ProjectGenerationStrategyConfigModel).where(
            ProjectGenerationStrategyConfigModel.project_id == project_id
        )
        res_config = await session.execute(stmt)
        db_config = res_config.scalar_one_or_none()
        
        proj_knowledge_enabled = KNOWLEDGE_BASE_ENABLED
        if db_config is not None:
            proj_knowledge_enabled = KNOWLEDGE_BASE_ENABLED and db_config.knowledge_enabled

        query = (
            select(KnowledgeDocumentModel)
            .where(KnowledgeDocumentModel.project_id == project_id)
            .where(KnowledgeDocumentModel.status != "deleted")
        )
        res = await session.execute(query)
        docs = res.scalars().all()

        ai_ready_count = sum(1 for d in docs if d.status == "ready" and d.ai_enabled)

        knowledge_summary = ProjectKnowledgeSummary(
            enabled=proj_knowledge_enabled,
            document_count=len(docs),
            ready_count=sum(1 for d in docs if d.status == "ready"),
            failed_count=sum(1 for d in docs if d.status == "failed"),
            processing_count=sum(1 for d in docs if d.status in ("uploaded", "converting")),
            ai_enabled_count=ai_ready_count
        )

        # 3. Team LLM Config
        llm_summary = await self.get_active_llm_summary(user_id, project_id, session)

        return ProjectConfigurationResponse(
            project_id=project_public_id,
            content_locale=content_locale,
            generation_strategy=strategy_config,
            knowledge=knowledge_summary,
            llm=llm_summary
        )

    async def save_knowledge_config(
        self,
        project_id: int,
        user_id: int,
        enabled: bool,
        session: AsyncSession
    ) -> ProjectKnowledgeSummary:
        from backend.database.model import ProjectGenerationStrategyConfigModel
        from backend.core.config import KNOWLEDGE_BASE_ENABLED
        
        stmt = select(ProjectGenerationStrategyConfigModel).where(
            ProjectGenerationStrategyConfigModel.project_id == project_id
        )
        res = await session.execute(stmt)
        db_config = res.scalar_one_or_none()
        
        if db_config:
            db_config.knowledge_enabled = enabled
            db_config.updated_by_user_id = user_id
        else:
            from backend.api.modules.project_configuration.application.generation_strategy_config_service import DEFAULT_STRATEGIES
            db_config = ProjectGenerationStrategyConfigModel(
                project_id=project_id,
                enabled=True,
                candidate_count=2,
                strategies=DEFAULT_STRATEGIES,
                knowledge_enabled=enabled,
                updated_by_user_id=user_id
            )
            session.add(db_config)
            
        await session.commit()
        await session.refresh(db_config)
        
        query = (
            select(KnowledgeDocumentModel)
            .where(KnowledgeDocumentModel.project_id == project_id)
            .where(KnowledgeDocumentModel.status != "deleted")
        )
        res_docs = await session.execute(query)
        docs = res_docs.scalars().all()
        
        ai_ready_count = sum(1 for d in docs if d.status == "ready" and d.ai_enabled)

        return ProjectKnowledgeSummary(
            enabled=KNOWLEDGE_BASE_ENABLED and db_config.knowledge_enabled,
            document_count=len(docs),
            ready_count=sum(1 for d in docs if d.status == "ready"),
            failed_count=sum(1 for d in docs if d.status == "failed"),
            processing_count=sum(1 for d in docs if d.status in ("uploaded", "converting")),
            ai_enabled_count=ai_ready_count
        )
