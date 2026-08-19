"""
Version Control Application Errors.
版本控制业务动作的领域异常：受保护分支写入、head 并发覆盖、未找到目标等。
路由层将异常映射为稳定的 HTTP 状态码与错误码，避免把原始异常细节泄露给客户端。
"""


class VersionControlError(Exception):
    """版本控制领域错误的基类，携带稳定的业务错误码。"""

    code: str = "version_control_error"

    def __init__(self, message: str = "") -> None:
        super().__init__(message)
        self.message = message


class ProtectedBranchError(VersionControlError):
    """对受保护分支（如 main）执行直接提交/写入时抛出；变更必须经 Merge Request 合入。"""

    code = "branch_protected"


class HeadChangedError(VersionControlError):
    """提交或合并时预期 head 与当前 head 不一致，用于防止并发提交覆盖。"""

    code = "head_changed"

    def __init__(
        self,
        message: str = "",
        *,
        current_head_commit_id: int | None = None,
        current_head_public_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.current_head_commit_id = current_head_commit_id
        self.current_head_public_id = current_head_public_id


class BranchNotFoundError(VersionControlError):
    """指定的分支在工作区内不存在或无权限访问。"""

    code = "branch_not_found"


class CommitNotFoundError(VersionControlError):
    """指定的提交不存在或不属于当前项目。"""

    code = "commit_not_found"


class InvalidDiffRefError(VersionControlError):
    """Diff 的 ref（commit/branch/workspace）无法解析。"""

    code = "invalid_diff_ref"


class MergeConflictError(VersionControlError):
    """合并时仍有未解决冲突或合并后的结构校验失败；合并被阻止且不产生 merge commit。"""

    code = "merge_conflict"

    def __init__(
        self,
        message: str = "",
        *,
        conflict_ids: list[str] | None = None,
        structure_errors: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.conflict_ids = list(conflict_ids or [])
        self.structure_errors = list(structure_errors or [])


class MergeBlockedError(VersionControlError):
    """合并前置条件未满足（缺审批、目标推进、存在阻塞原因等）；返回阻塞原因供界面提示。"""

    code = "merge_blocked"

    def __init__(self, message: str = "", *, reasons: list[str] | None = None) -> None:
        super().__init__(message)
        self.reasons = list(reasons or [])
