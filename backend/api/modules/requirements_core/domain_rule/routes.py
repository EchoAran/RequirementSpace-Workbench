"""FastAPI router handling domain rule CRUD and link management."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies.auth import get_current_user
from backend.api.dependencies.ownership import require_project_member
from backend.api.modules.requirements_core.domain_rule.ports import (
    get_domain_rule_service,
)
from backend.api.modules.requirements_core.domain_rule.schemas import (
    DomainRuleCreateRequest,
    DomainRuleListResponse,
    DomainRuleResponse,
    DomainRuleUpdateRequest,
    RuleLinkCreateRequest,
    RuleLinkResponse,
    RuleLinkUpdateRequest,
    TargetRuleLinksUpdateRequest,
)
from backend.api.modules.version_control.dependencies import reject_commit_write
from backend.api.modules.version_control.public import map_branch_error, resolve_branch_context
from backend.database.database import get_session
from backend.database.model import (
    DomainRuleModel,
    ProjectModel,
    RuleLinkModel,
    UserModel,
)

router = APIRouter(
    prefix="/api/projects/{project_id}/rules",
    tags=["domain_rules"],
)


def _serialize_link(link: RuleLinkModel) -> RuleLinkResponse:
    """Transform RuleLinkModel to response schema."""
    return RuleLinkResponse(
        id=link.id,
        logical_uuid=link.logical_uuid,
        project_id=link.project_id,
        workspace_id=link.workspace_id,
        rule_id=link.rule_id,
        target_kind=link.target_kind,
        target_logical_uuid=link.target_logical_uuid,
        link_purpose=link.link_purpose,
        context_text=link.context_text,
        created_at=link.created_at,
        updated_at=link.updated_at,
    )


def _serialize_rule(rule: DomainRuleModel) -> DomainRuleResponse:
    """Transform DomainRuleModel to response schema."""
    return DomainRuleResponse(
        id=rule.id,
        logical_uuid=rule.logical_uuid,
        project_id=rule.project_id,
        workspace_id=rule.workspace_id,
        parent_rule_id=rule.parent_rule_id,
        title=rule.title,
        statement=rule.statement,
        origin=rule.origin,
        confirmation_status=rule.confirmation_status,
        links=[_serialize_link(lnk) for lnk in (rule.links or [])],
        child_rule_ids=[child.id for child in (rule.child_rules or [])],
        created_at=rule.created_at,
        updated_at=rule.updated_at,
    )


async def _resolve_ws_and_check_write(
    session: AsyncSession,
    project_id: int,
    branch: str | None,
    user_id: int,
    require_write: bool = False,
) -> int | None:
    """Resolve branch workspace context and check permissions."""
    try:
        _branch_obj, ws_obj, perms = await session.run_sync(
            lambda s: resolve_branch_context(s, project_id, branch, user_id)
        )
    except (ValueError, PermissionError) as error:
        raise map_branch_error(error)

    if require_write and not perms["can_write"]:
        raise HTTPException(status_code=403, detail="Branch is read-only or protected for current user")

    return ws_obj.id


@router.put("/associations", status_code=204)
async def replace_target_rule_links(
    project_id: str,
    request: TargetRuleLinksUpdateRequest,
    branch: str | None = Query(None),
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    owned_project: ProjectModel = Depends(require_project_member),
    commit_guard: None = Depends(reject_commit_write),
):
    ws_id = await _resolve_ws_and_check_write(
        session, owned_project.id, branch, user.id, require_write=True,
    )
    try:
        await get_domain_rule_service().replace_target_rules(
            session, owned_project.id, request.target_kind,
            request.target_logical_uuid, request.rule_ids, ws_id,
        )
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@router.get("", response_model=DomainRuleListResponse)
async def list_domain_rules(
    project_id: str,
    branch: str | None = Query(None),
    confirmation_status: str | None = Query(None),
    origin: str | None = Query(None),
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    owned_project: ProjectModel = Depends(require_project_member),
):
    """List all domain rules within the active project workspace."""
    ws_id = await _resolve_ws_and_check_write(session, owned_project.id, branch, user.id)
    service = get_domain_rule_service()
    rules, total = await service.list_rules(
        session=session,
        project_id=owned_project.id,
        workspace_id=ws_id,
        confirmation_status=confirmation_status,
        origin=origin,
    )
    return DomainRuleListResponse(rules=[_serialize_rule(r) for r in rules], total=total)


@router.post("", response_model=DomainRuleResponse, status_code=201)
async def create_domain_rule(
    project_id: str,
    request: DomainRuleCreateRequest,
    branch: str | None = Query(None),
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    owned_project: ProjectModel = Depends(require_project_member),
    commit_guard: None = Depends(reject_commit_write),
):
    """Create a new domain rule in the active workspace."""
    ws_id = await _resolve_ws_and_check_write(session, owned_project.id, branch, user.id, require_write=True)
    service = get_domain_rule_service()
    try:
        rule = await service.create_rule(
            session=session,
            project_id=owned_project.id,
            request=request,
            workspace_id=ws_id,
        )
        return _serialize_rule(rule)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))


@router.get("/{rule_id}", response_model=DomainRuleResponse)
async def get_domain_rule(
    project_id: str,
    rule_id: int,
    branch: str | None = Query(None),
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    owned_project: ProjectModel = Depends(require_project_member),
):
    """Retrieve details of a specific domain rule."""
    ws_id = await _resolve_ws_and_check_write(session, owned_project.id, branch, user.id)
    service = get_domain_rule_service()
    rule = await service.get_rule(session, owned_project.id, rule_id, ws_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Domain rule not found.")
    return _serialize_rule(rule)


@router.put("/{rule_id}", response_model=DomainRuleResponse)
async def update_domain_rule(
    project_id: str,
    rule_id: int,
    request: DomainRuleUpdateRequest,
    branch: str | None = Query(None),
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    owned_project: ProjectModel = Depends(require_project_member),
    commit_guard: None = Depends(reject_commit_write),
):
    """Update attributes or parent refinement of a domain rule."""
    ws_id = await _resolve_ws_and_check_write(session, owned_project.id, branch, user.id, require_write=True)
    service = get_domain_rule_service()
    try:
        rule = await service.update_rule(
            session=session,
            project_id=owned_project.id,
            rule_id=rule_id,
            request=request,
            workspace_id=ws_id,
        )
        return _serialize_rule(rule)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))


@router.delete("/{rule_id}")
async def delete_domain_rule(
    project_id: str,
    rule_id: int,
    branch: str | None = Query(None),
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    owned_project: ProjectModel = Depends(require_project_member),
    commit_guard: None = Depends(reject_commit_write),
):
    """Delete a domain rule and its cascade links."""
    ws_id = await _resolve_ws_and_check_write(session, owned_project.id, branch, user.id, require_write=True)
    service = get_domain_rule_service()
    deleted = await service.delete_rule(session, owned_project.id, rule_id, ws_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Domain rule not found.")
    return {"message": "Domain rule deleted successfully"}


@router.post("/{rule_id}/links", response_model=RuleLinkResponse, status_code=201)
async def create_rule_link(
    project_id: str,
    rule_id: int,
    request: RuleLinkCreateRequest,
    branch: str | None = Query(None),
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    owned_project: ProjectModel = Depends(require_project_member),
    commit_guard: None = Depends(reject_commit_write),
):
    """Create a link from this rule to a requirement or flow node."""
    ws_id = await _resolve_ws_and_check_write(session, owned_project.id, branch, user.id, require_write=True)
    service = get_domain_rule_service()
    try:
        link = await service.create_link(
            session=session,
            project_id=owned_project.id,
            rule_id=rule_id,
            request=request,
            workspace_id=ws_id,
        )
        return _serialize_link(link)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))


@router.delete("/{rule_id}/links/{link_id}")
async def delete_rule_link(
    project_id: str,
    rule_id: int,
    link_id: int,
    branch: str | None = Query(None),
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    owned_project: ProjectModel = Depends(require_project_member),
    commit_guard: None = Depends(reject_commit_write),
):
    """Delete a specific rule link."""
    ws_id = await _resolve_ws_and_check_write(session, owned_project.id, branch, user.id, require_write=True)
    service = get_domain_rule_service()
    deleted = await service.delete_link(
        session=session,
        project_id=owned_project.id,
        rule_id=rule_id,
        link_id=link_id,
        workspace_id=ws_id,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Rule link not found.")
    return {"message": "Rule link deleted successfully"}


@router.patch("/{rule_id}/links/{link_id}", response_model=RuleLinkResponse)
async def update_rule_link(
    project_id: str,
    rule_id: int,
    link_id: int,
    request: RuleLinkUpdateRequest,
    branch: str | None = Query(None),
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    owned_project: ProjectModel = Depends(require_project_member),
    commit_guard: None = Depends(reject_commit_write),
):
    """Update a rule link in the active workspace."""
    ws_id = await _resolve_ws_and_check_write(
        session,
        owned_project.id,
        branch,
        user.id,
        require_write=True,
    )
    try:
        link = await get_domain_rule_service().update_link(
            session=session,
            project_id=owned_project.id,
            rule_id=rule_id,
            link_id=link_id,
            request=request,
            workspace_id=ws_id,
        )
        return _serialize_link(link)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))
