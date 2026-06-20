"""Finding factory — 共享的 Finding 构建器。

各 stage finding policy 通过本工厂构建 Finding 对象，避免重复手写：
  - findingId 拼装
  - blockingScope 设置
  - capability 注入（由 FindingService._attach_capability 统一处理）
  - target/metadata 复制

usage:
    from backend.core.findings.finding_factory import make_finding

    finding = make_finding(
        stage=IssueStage.WHAT,
        code="SCOPE_WITHOUT_REASON",
        severity=IssueSeverity.INFO,
        title="...",
        description="...",
        target=issue.target,
        blocking_scope=BlockingScope.NONE,
        action_code=issue.actionCode,
        metadata=issue.metadata or {},
    )
"""

from backend.schemas import (
    BlockingScope,
    Finding,
    FindingType,
    IssueSeverity,
    IssueStage,
    IssueTarget,
)


def make_finding(
    stage: IssueStage,
    code: str,
    severity: IssueSeverity,
    title: str,
    description: str,
    target: IssueTarget | None = None,
    finding_type: FindingType = FindingType.ISSUE,
    blocking_scope: BlockingScope = BlockingScope.NONE,
    action_code: str | None = None,
    metadata: dict | None = None,
    finding_id_override: str | None = None,
) -> Finding:
    """构建一个 Finding 对象，自动拼装 findingId。

    通常 findingId = stage:code:target_key。
    对于聚合 (aggregate) 或特殊 finding，传入 finding_id_override 覆盖。
    """
    if finding_id_override:
        finding_id = finding_id_override
    else:
        target_key = target.key() if target is not None else "project"
        finding_id = f"{stage.value}:{code}:{target_key}"

    return Finding(
        findingId=finding_id,
        type=finding_type,
        stage=stage,
        code=code,
        severity=severity,
        title=title,
        description=description,
        target=target,
        blockingScope=blocking_scope,
        actionCode=action_code,
        metadata=metadata or {},
    )
