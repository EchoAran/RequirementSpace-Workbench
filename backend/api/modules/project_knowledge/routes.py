import os
import uuid
import hashlib
import logging
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request, BackgroundTasks
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.database import get_session
from backend.api.dependencies.auth import get_current_user
from backend.database.model import (
    UserModel,
    ProjectModel,
    KnowledgeWorkspaceModel,
    KnowledgeDocumentModel,
)
from backend.core import config
from backend.api.dependencies.project_access import (
    require_project_member,
    require_project_role,
)
from .dependencies import (
    require_owned_knowledge_workspace,
    require_owned_knowledge_document,
)
import asyncio
from backend.services.knowledge.conversion import KnowledgeConversionService
from .schemas import (
    KnowledgeWorkspaceResponse,
    KnowledgeDocumentResponse,
    KnowledgeDocumentPatchRequest,
)

logger = logging.getLogger(__name__)

def require_knowledge_base_enabled():
    from backend.core.config import KNOWLEDGE_BASE_ENABLED
    if not KNOWLEDGE_BASE_ENABLED:
        raise HTTPException(status_code=403, detail="knowledge_base_disabled")

config_router = APIRouter(tags=["project_knowledge"])

@config_router.get("/api/knowledge/config")
async def get_knowledge_config():
    from backend.core.config import KNOWLEDGE_BASE_ENABLED
    return {"enabled": KNOWLEDGE_BASE_ENABLED}

router = APIRouter(
    tags=["project_knowledge"],
    dependencies=[Depends(require_knowledge_base_enabled)]
)


def _safe_delete_file(file_path: str) -> None:
    if not file_path:
        return
    try:
        abs_storage_dir = os.path.normcase(os.path.abspath(config.KNOWLEDGE_STORAGE_DIR))
        abs_file_path = os.path.normcase(os.path.abspath(file_path))
        if os.path.commonpath([abs_storage_dir, abs_file_path]) == abs_storage_dir:
            if os.path.exists(file_path):
                os.remove(file_path)
        else:
            logger.warning("Prevented deletion of file outside storage directory: %s", file_path)
    except Exception as e:
        logger.error("Failed to delete file safely: %s, error=%s", file_path, e)


@router.post(
    "/api/knowledge_workspaces",
    response_model=KnowledgeWorkspaceResponse,
    status_code=201,
)
async def create_knowledge_workspace(
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Create a new temporary knowledge workspace for onboarding/project creation."""
    workspace = KnowledgeWorkspaceModel(
        owner_user_id=user.id,
        scope="project_creation",
        status="active",
    )
    session.add(workspace)
    await session.commit()
    await session.refresh(workspace)
    return workspace


@router.get(
    "/api/knowledge_workspaces/{workspace_id}/documents",
    response_model=list[KnowledgeDocumentResponse],
)
async def list_workspace_documents(
    workspace: KnowledgeWorkspaceModel = Depends(require_owned_knowledge_workspace),
    session: AsyncSession = Depends(get_session),
):
    """List all non-deleted documents in the workspace."""
    query = (
        select(KnowledgeDocumentModel)
        .where(KnowledgeDocumentModel.workspace_id == workspace.id)
        .where(KnowledgeDocumentModel.status != "deleted")
    )
    res = await session.execute(query)
    return res.scalars().all()


@router.post(
    "/api/knowledge_workspaces/{workspace_id}/documents",
    response_model=KnowledgeDocumentResponse,
    status_code=201,
)
async def upload_workspace_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    workspace: KnowledgeWorkspaceModel = Depends(require_owned_knowledge_workspace),
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Upload a document to the workspace, saving original file and creating metadata."""
    filename = file.filename or "unnamed"
    ext = os.path.splitext(filename)[1].lower()
    if ext not in config.KNOWLEDGE_ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"file_type_not_allowed: allowed extensions are {','.join(config.KNOWLEDGE_ALLOWED_EXTENSIONS)}",
        )

    content = await file.read()
    file_size = len(content)
    max_bytes = config.KNOWLEDGE_MAX_FILE_SIZE_MB * 1024 * 1024

    if file_size == 0:
        raise HTTPException(status_code=400, detail="file_is_empty")
    if file_size > max_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"file_too_large: max allowed size is {config.KNOWLEDGE_MAX_FILE_SIZE_MB}MB",
        )

    sha256_hash = hashlib.sha256(content).hexdigest()

    # Check total storage limit for workspace
    size_query = (
        select(func.sum(KnowledgeDocumentModel.file_size))
        .where(KnowledgeDocumentModel.workspace_id == workspace.id)
        .where(KnowledgeDocumentModel.status != "deleted")
    )
    res_size = await session.execute(size_query)
    total_size = res_size.scalar() or 0
    if total_size + file_size > config.KNOWLEDGE_MAX_PROJECT_STORAGE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail=f"workspace_storage_limit_exceeded: limit is {config.KNOWLEDGE_MAX_PROJECT_STORAGE_MB}MB",
        )

    document_public_id = str(uuid.uuid4())
    workspace_dir = os.path.join(config.KNOWLEDGE_STORAGE_DIR, "workspaces", workspace.public_id)
    os.makedirs(workspace_dir, exist_ok=True)

    # Sanitize original filename
    safe_filename = "".join([c for c in filename if c.isalpha() or c.isdigit() or c in (".", "_", "-")]).rstrip()
    if not safe_filename or safe_filename.startswith("."):
        safe_filename = f"upload{ext}"
    storage_filename = f"{document_public_id}_{safe_filename}"
    storage_path = os.path.join(workspace_dir, storage_filename)

    with open(storage_path, "wb") as f:
        f.write(content)

    doc = KnowledgeDocumentModel(
        public_id=document_public_id,
        workspace_id=workspace.id,
        project_id=None,
        owner_user_id=user.id,
        original_filename=filename,
        content_type=file.content_type or "application/octet-stream",
        file_size=file_size,
        sha256=sha256_hash,
        storage_path=storage_path,
        status="uploaded",
        ai_enabled=True,
    )
    session.add(doc)
    await session.commit()
    await session.refresh(doc)

    # Trigger background document conversion task
    background_tasks.add_task(KnowledgeConversionService.convert_document, doc.id, session.bind)

    return doc


@router.delete("/api/knowledge_workspaces/{workspace_id}/documents/{document_id}")
async def delete_workspace_document(
    workspace: KnowledgeWorkspaceModel = Depends(require_owned_knowledge_workspace),
    doc: KnowledgeDocumentModel = Depends(require_owned_knowledge_document),
    session: AsyncSession = Depends(get_session),
):
    """Delete a workspace document (soft delete in DB, physical delete of files)."""
    if doc.workspace_id != workspace.id:
        raise HTTPException(status_code=404, detail="document_not_found")

    doc.status = "deleted"

    _safe_delete_file(doc.storage_path)
    _safe_delete_file(doc.markdown_path)

    # Delete related chunks
    from backend.database.model import KnowledgeChunkModel
    from sqlalchemy import delete
    await session.execute(
        delete(KnowledgeChunkModel).where(KnowledgeChunkModel.document_id == doc.id)
    )

    await session.commit()
    return {"message": "document_deleted", "public_id": doc.public_id}


@router.post(
    "/api/knowledge_workspaces/{workspace_id}/documents/{document_id}/retry",
    response_model=KnowledgeDocumentResponse,
)
async def retry_workspace_document(
    workspace_id: str,
    background_tasks: BackgroundTasks,
    workspace: KnowledgeWorkspaceModel = Depends(require_owned_knowledge_workspace),
    doc: KnowledgeDocumentModel = Depends(require_owned_knowledge_document),
    session: AsyncSession = Depends(get_session),
):
    """Retry processing a failed workspace document."""
    if doc.workspace_id != workspace.id:
        raise HTTPException(status_code=404, detail="document_not_found")

    # Reset status to uploaded for retry
    doc.status = "uploaded"
    doc.error_message = None
    await session.commit()
    await session.refresh(doc)

    # Trigger background document conversion task
    background_tasks.add_task(KnowledgeConversionService.convert_document, doc.id, session.bind)

    return doc


@router.get(
    "/api/projects/{project_id}/knowledge/documents",
    response_model=list[KnowledgeDocumentResponse],
)
async def list_project_documents(
    project_id: str,
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """List all non-deleted documents in the project."""
    project = await require_project_member(project_id, user, session)
    query = (
        select(KnowledgeDocumentModel)
        .where(KnowledgeDocumentModel.project_id == project.id)
        .where(KnowledgeDocumentModel.status != "deleted")
    )
    res = await session.execute(query)
    return res.scalars().all()


@router.post(
    "/api/projects/{project_id}/knowledge/documents",
    response_model=KnowledgeDocumentResponse,
    status_code=201,
)
async def upload_project_document(
    project_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Upload a document to the project (requires editor role)."""
    project = await require_project_role("editor")(project_id, user, session)

    filename = file.filename or "unnamed"
    ext = os.path.splitext(filename)[1].lower()
    if ext not in config.KNOWLEDGE_ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"file_type_not_allowed: allowed extensions are {','.join(config.KNOWLEDGE_ALLOWED_EXTENSIONS)}",
        )

    content = await file.read()
    file_size = len(content)
    max_bytes = config.KNOWLEDGE_MAX_FILE_SIZE_MB * 1024 * 1024

    if file_size == 0:
        raise HTTPException(status_code=400, detail="file_is_empty")
    if file_size > max_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"file_too_large: max allowed size is {config.KNOWLEDGE_MAX_FILE_SIZE_MB}MB",
        )

    sha256_hash = hashlib.sha256(content).hexdigest()

    # Check total storage limit for project
    size_query = (
        select(func.sum(KnowledgeDocumentModel.file_size))
        .where(KnowledgeDocumentModel.project_id == project.id)
        .where(KnowledgeDocumentModel.status != "deleted")
    )
    res_size = await session.execute(size_query)
    total_size = res_size.scalar() or 0
    if total_size + file_size > config.KNOWLEDGE_MAX_PROJECT_STORAGE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail=f"project_storage_limit_exceeded: limit is {config.KNOWLEDGE_MAX_PROJECT_STORAGE_MB}MB",
        )

    document_public_id = str(uuid.uuid4())
    project_dir = os.path.join(config.KNOWLEDGE_STORAGE_DIR, "projects", project.public_id)
    os.makedirs(project_dir, exist_ok=True)

    safe_filename = "".join([c for c in filename if c.isalpha() or c.isdigit() or c in (".", "_", "-")]).rstrip()
    if not safe_filename or safe_filename.startswith("."):
        safe_filename = f"upload{ext}"
    storage_filename = f"{document_public_id}_{safe_filename}"
    storage_path = os.path.join(project_dir, storage_filename)

    with open(storage_path, "wb") as f:
        f.write(content)

    doc = KnowledgeDocumentModel(
        public_id=document_public_id,
        workspace_id=None,
        project_id=project.id,
        owner_user_id=user.id,
        original_filename=filename,
        content_type=file.content_type or "application/octet-stream",
        file_size=file_size,
        sha256=sha256_hash,
        storage_path=storage_path,
        status="uploaded",
        ai_enabled=True,
    )
    session.add(doc)
    await session.commit()
    await session.refresh(doc)

    # Trigger background document conversion task
    background_tasks.add_task(KnowledgeConversionService.convert_document, doc.id, session.bind)

    return doc


@router.delete("/api/projects/{project_id}/knowledge/documents/{document_id}")
async def delete_project_document(
    project_id: str,
    doc: KnowledgeDocumentModel = Depends(require_owned_knowledge_document),
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Delete a project document (soft delete in DB, physical delete of files)."""
    # Verify project ID matches
    project = await require_project_member(project_id, user, session)
    if doc.project_id != project.id:
        raise HTTPException(status_code=404, detail="document_not_found")

    doc.status = "deleted"

    _safe_delete_file(doc.storage_path)
    _safe_delete_file(doc.markdown_path)

    # Delete related chunks
    from backend.database.model import KnowledgeChunkModel
    from sqlalchemy import delete
    await session.execute(
        delete(KnowledgeChunkModel).where(KnowledgeChunkModel.document_id == doc.id)
    )

    await session.commit()
    return {"message": "document_deleted", "public_id": doc.public_id}


@router.post(
    "/api/projects/{project_id}/knowledge/documents/{document_id}/retry",
    response_model=KnowledgeDocumentResponse,
)
async def retry_project_document(
    project_id: str,
    background_tasks: BackgroundTasks,
    doc: KnowledgeDocumentModel = Depends(require_owned_knowledge_document),
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Retry processing a failed document."""
    # Verify project ID matches
    project = await require_project_member(project_id, user, session)
    if doc.project_id != project.id:
        raise HTTPException(status_code=404, detail="document_not_found")

    # Reset status to uploaded for retry
    doc.status = "uploaded"
    doc.error_message = None
    await session.commit()
    await session.refresh(doc)

    # Trigger background document conversion task
    background_tasks.add_task(KnowledgeConversionService.convert_document, doc.id, session.bind)

    return doc


@router.patch(
    "/api/projects/{project_id}/knowledge/documents/{document_id}",
    response_model=KnowledgeDocumentResponse,
)
async def patch_project_document(
    project_id: str,
    request_data: KnowledgeDocumentPatchRequest,
    doc: KnowledgeDocumentModel = Depends(require_owned_knowledge_document),
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Update settings of a project document, such as ai_enabled."""
    # Verify project ID matches
    project = await require_project_member(project_id, user, session)
    if doc.project_id != project.id:
        raise HTTPException(status_code=404, detail="document_not_found")

    doc.ai_enabled = request_data.ai_enabled
    await session.commit()
    await session.refresh(doc)
    return doc
