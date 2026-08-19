"""
Version Control Audit Helpers.
在路由层接入现有审计系统：成功事件随请求事务写入，失败事件（如 Diff 计算失败）
用独立会话持久化，避免随出错请求的 rollback 一并丢失。
"""
from backend.services.audit_service import AuditService

audit_service = AuditService()


async def record_vc_event(
    session,
    *,
    project_id: int,
    action_type: str,
    summary: str,
    target_type: str,
    target_id: str | int,
    payload: dict | None = None,
) -> None:
    """在当前请求事务内记录版本控制审计事件；不提交，由调用方控制事务边界。"""
    await audit_service.record(
        session=session,
        project_id=project_id,
        action_type=action_type,
        summary=summary,
        target_type=target_type,
        target_id=target_id,
        payload=payload,
    )


async def record_vc_failure_event(
    *,
    project_id: int,
    action_type: str,
    summary: str,
    target_type: str,
    target_id: str | int,
    payload: dict | None = None,
) -> None:
    """用独立会话持久化失败审计；审计自身失败不掩盖原始错误。"""
    from backend.database.database import AsyncSessionLocal

    try:
        async with AsyncSessionLocal() as session:
            await audit_service.record(
                session=session,
                project_id=project_id,
                action_type=action_type,
                summary=summary,
                target_type=target_type,
                target_id=target_id,
                payload=payload,
            )
            await session.commit()
    except Exception:
        pass
