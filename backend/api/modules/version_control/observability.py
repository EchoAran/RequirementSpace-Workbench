"""
Version Control Observability Helpers (Phase 7).

封装版本控制领域的结构化日志与失败审计，作为运维信号的统一入口：
  - 领域日志统一走 core/logging 的 log_event（category=domain，可开关），
    覆盖迁移、提交冲突、合并冲突/阻塞/head 变化、diff/合并耗时；
  - 失败审计（record_vc_failure_event）留在路由层，用独立会话持久化，避免随出错请求回滚丢失。

分层约定：
  - service 层（diff/merge/baseline_migration）调用 log_vc_event / monitor_vc_operation / log_vc_duration；
  - 路由层调用 audit_vc_failure（先记日志再落审计），并负责成功事件的 record_vc_event。
"""
from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Iterator

from backend.core.logging.logger import get_logger, log_event
from backend.api.modules.version_control.audit import record_vc_failure_event

# 版本控制领域日志统一使用 domain 类目（默认关闭，运维按需开启 LOG_ENABLED_CATEGORIES=...,domain）。
VC_CATEGORY = "domain"
vc_logger = get_logger("backend.version_control")


def log_vc_event(
    level: int,
    event: str,
    message: str,
    **fields: object,
) -> None:
    """写一条版本控制领域日志；类别固定为 domain，便于按类目开关过滤。"""
    log_event(vc_logger, level, VC_CATEGORY, event, message, **fields)


@contextmanager
def monitor_vc_operation(
    operation: str,
    *,
    failure_event: str,
    project_id: int | None = None,
    **fields: object,
) -> Iterator[None]:
    """为一次 VC 计算计时，并在异常时记录失败事件后重新抛出。

    用于 diff/merge 等同步计算（在 run_sync 内），异常时补 error_type 与 duration_ms。
    """
    started = time.perf_counter()
    try:
        yield
    except Exception as exc:
        log_vc_event(
            logging.WARNING,
            failure_event,
            f"{operation} failed",
            operation=operation,
            project_id=project_id,
            error_type=type(exc).__name__,
            duration_ms=_elapsed_ms(started),
            **fields,
        )
        raise


def log_vc_duration(
    event: str,
    started: float,
    *,
    level: int = logging.INFO,
    **fields: object,
) -> None:
    """按开始时间计算耗时并写一条已完成事件（供 diff/merge 成功侧使用）。"""
    log_vc_event(level, event, "completed", duration_ms=_elapsed_ms(started), **fields)


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


async def audit_vc_failure(
    *,
    project_id: int,
    action_type: str,
    summary: str,
    target_type: str,
    target_id: str | int,
    error_type: str | None = None,
    event: str | None = None,
    **payload: object,
) -> None:
    """路由层失败审计封装：先记 WARNING 日志，再用独立会话持久化失败审计（含 payload）。

    审计自身失败不掩盖原始异常（record_vc_failure_event 内部静默吞掉）。
    payload 落库供监控按审计聚合（冲突 ID、阻塞原因、最新 head 等）。
    event 缺省时由 action_type 派生（vc_<action_type>），与审计 action 保持一致。
    """
    log_vc_event(
        logging.WARNING,
        event or f"vc_{action_type}",
        summary,
        project_id=project_id,
        error_type=error_type,
        **payload,
    )
    await record_vc_failure_event(
        project_id=project_id,
        action_type=action_type,
        summary=summary,
        target_type=target_type,
        target_id=target_id,
        payload={**payload, "error_type": error_type},
    )
