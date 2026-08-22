"""
Version Control FastAPI Dependencies.
提供写接口的历史提交只读保护依赖。
"""
import json
from typing import Any

from fastapi import HTTPException, Request, status


def _commit_ref_present(value: Any) -> bool:
    """判断一个 commit_id 引用是否非空。"""
    if value is None:
        return False
    return bool(str(value).strip())


def _reject() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="commit_is_read_only: writing to a historical commit is not allowed",
    )


def _find_commit_id(payload: Any) -> bool:
    """在 JSON 载荷中递归查找 commit_id 字段，避免嵌套结构被绕过。"""
    if isinstance(payload, dict):
        if _commit_ref_present(payload.get("commit_id")):
            return True
        return any(_find_commit_id(value) for value in payload.values())
    if isinstance(payload, list):
        return any(_find_commit_id(value) for value in payload)
    return False


async def reject_commit_write(request: Request) -> None:
    """拒绝在需求模型写请求中携带 commit_id（query 或 JSON body）。

    历史提交永远只读。客户端若尝试“写入某个历史提交”（通过 commit_id 指定），
    必须被显式拒绝，而不能被框架静默忽略参数后继续写入当前分支工作区。
    该依赖由所有需求模型写接口统一挂载。

    说明：query 参数通过 request.query_params 读取；JSON body 通过 request.body()
    读取（Starlette 会缓存 body，路由的 Pydantic 解析复用同一缓存，因此不影响后续解析）。
    """
    # 1. query 参数
    if _commit_ref_present(request.query_params.get("commit_id")):
        raise _reject()

    # 2. JSON body：Pydantic 默认会静默忽略额外字段，因此需要显式检查。
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("application/json"):
        body = await request.body()
        if body:
            try:
                payload = json.loads(body)
            except (ValueError, UnicodeDecodeError):
                payload = None
            if payload is not None and _find_commit_id(payload):
                raise _reject()


def map_branch_error(error: Exception) -> HTTPException:
    """统一将分支解析、权限以及未找到等异常映射为对应的 HTTP 状态码。"""
    if isinstance(error, HTTPException):
        return error
    err_str = str(error)
    lower = err_str.lower()
    if "not found" in lower or "not_found" in lower:
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=err_str)
    if "protected" in lower or "cannot_write" in lower or "permission" in lower or isinstance(error, PermissionError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Branch is protected or read-only")
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_str)
