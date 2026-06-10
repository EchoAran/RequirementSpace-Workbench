"""通用节点确认状态变更 API

允许前端通过 node_kind + node_id 任意修改任一节点的 confirmation_status。
支持单节点更新和批量更新，每次变更自动记录审计日志。
"""
from backend.api.dependencies.ownership import require_owned_project

from backend.database.model import ProjectModel


from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database.database import get_session
from backend.database.model import (
    ActorModel,
    FeatureModel,
    ScopeModel,
    ScenarioModel,
    ScenarioAcceptanceCriterionModel,
    BusinessObjectModel,
    FlowModel,
    AuditLogModel,
)
from backend.api.schemas.project_schema import ConfirmationStatusEnum

router = APIRouter(prefix="/api/projects/{project_id}/node-status", tags=["node-status"])

# 确认状态中文映射
_CONFIRMATION_STATUS_LABEL = {
    "ai_assumption": "AI 推测",
    "needs_confirmation": "待确认",
    "confirmed": "已确认",
}


class UpdateNodeStatusRequest(BaseModel):
    node_kind: str
    node_id: int
    confirmation_status: ConfirmationStatusEnum


class BatchUpdateNodeStatusRequest(BaseModel):
    """批量更新：一组 node_kind + node_id 统一设为同一状态"""
    nodes: list[UpdateNodeStatusRequest]
    confirmation_status: ConfirmationStatusEnum


# Model 映射表：所有支持 confirmation_status 的实体
NODE_KIND_MODEL_MAP = {
    "actor": ActorModel,
    "feature": FeatureModel,
    "scope": ScopeModel,
    "scenario": ScenarioModel,
    "acceptance_criterion": ScenarioAcceptanceCriterionModel,
    "business_object": BusinessObjectModel,
    "flow": FlowModel,
}

# 节点类型中文名
_NODE_KIND_LABEL = {
    "actor": "角色",
    "feature": "功能",
    "scope": "范围",
    "scenario": "场景",
    "acceptance_criterion": "验收标准",
    "business_object": "业务对象",
    "flow": "流程",
}


async def _apply_status_update(
    model_class, project_id: int, node_id: int, new_status: str, session,
) -> dict | None:
    """执行单个节点的状态更新，返回审计日志所需信息；节点不存在时返回 None。"""
    if model_class is ScopeModel:
        stmt = (
            select(ScopeModel)
            .join(FeatureModel, ScopeModel.feature_id == FeatureModel.id)
            .where(
                FeatureModel.project_id == project_id,
                ScopeModel.id == node_id,
            )
        )
    elif model_class is ScenarioAcceptanceCriterionModel:
        stmt = (
            select(ScenarioAcceptanceCriterionModel)
            .join(ScenarioModel, ScenarioAcceptanceCriterionModel.scenario_id == ScenarioModel.id)
            .where(
                ScenarioModel.project_id == project_id,
                ScenarioAcceptanceCriterionModel.id == node_id,
            )
        )
    else:
        stmt = select(model_class).where(
            model_class.project_id == project_id,
            model_class.id == node_id,
        )
    result = await session.execute(stmt)
    obj = result.scalar_one_or_none()
    if obj is None:
        return None

    old_status = obj.confirmation_status
    if old_status == new_status:
        return {"skipped": True, "node_kind": model_class.__tablename__, "node_id": node_id}

    obj.confirmation_status = new_status
    return {
        "skipped": False,
        "node_kind": model_class.__tablename__,
        "node_id": node_id,
        "old_status": old_status,
        "new_status": new_status,
    }


async def _write_audit_log(
    project_id: int, node_kind: str, node_id: int,
    old_status: str, new_status: str, session,
):
    """写入状态变更审计日志。"""
    kind_label = _NODE_KIND_LABEL.get(node_kind, node_kind)
    old_label = _CONFIRMATION_STATUS_LABEL.get(old_status, old_status)
    new_label = _CONFIRMATION_STATUS_LABEL.get(new_status, new_status)
    session.add(AuditLogModel(
        project_id=project_id,
        action_type="update_confirmation_status",
        summary=f"节点确认状态变更: {kind_label}(id={node_id}) {old_label} → {new_label}",
        target_type=node_kind,
        target_id=str(node_id),
        payload={
            "old_status": old_status,
            "new_status": new_status,
            "old_label": old_label,
            "new_label": new_label,
        },
    ))


@router.patch("")
async def update_node_status(
    project_id: str,
    req: UpdateNodeStatusRequest,
    session: AsyncSession = Depends(get_session),
    owned_project: ProjectModel = Depends(require_owned_project)
):
    model_class = NODE_KIND_MODEL_MAP.get(req.node_kind)
    if not model_class:
        raise HTTPException(status_code=400, detail=f"Unknown node_kind: {req.node_kind}")

    result = await _apply_status_update(
        model_class, owned_project.id, req.node_id, req.confirmation_status.value, session,
    )
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"{req.node_kind}(id={req.node_id}) not found",
        )

    # 记录审计日志（跳过无变更的情况）
    if not result.get("skipped"):
        await _write_audit_log(
            owned_project.id, req.node_kind, req.node_id,
            result["old_status"], result["new_status"], session,
        )

    await session.commit()
    return {"success": True, "confirmation_status": req.confirmation_status.value}


@router.patch("/batch")
async def batch_update_node_status(
    project_id: str,
    req: BatchUpdateNodeStatusRequest,
    session: AsyncSession = Depends(get_session),
    owned_project: ProjectModel = Depends(require_owned_project)
):
    """批量更新一组节点的确认状态为统一值。"""
    results = []
    errors = []

    for node_req in req.nodes:
        kind = node_req.node_kind
        model_class = NODE_KIND_MODEL_MAP.get(kind)
        if not model_class:
            errors.append({"node_kind": kind, "node_id": node_req.node_id, "error": "unknown_kind"})
            continue

        result = await _apply_status_update(
            model_class, owned_project.id, node_req.node_id,
            req.confirmation_status.value, session,
        )
        if result is None:
            errors.append({"node_kind": kind, "node_id": node_req.node_id, "error": "not_found"})
            continue

        if not result.get("skipped"):
            await _write_audit_log(
                owned_project.id, kind, node_req.node_id,
                result["old_status"], result["new_status"], session,
            )
            results.append({"node_kind": kind, "node_id": node_req.node_id, "status": "updated"})
        else:
            results.append({"node_kind": kind, "node_id": node_req.node_id, "status": "skipped"})

    await session.commit()
    return {"success": True, "updated_count": len(results) - len(errors), "results": results, "errors": errors}
