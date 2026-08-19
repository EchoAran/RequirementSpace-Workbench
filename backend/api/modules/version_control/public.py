"""
Version Control Domain Module Public Facade.
对外导出的稳定 API 接口与迁移工具。
"""
from backend.api.modules.version_control.domain.uuid_generator import (
    generate_logical_uuid,
    ensure_logical_uuid,
)
from backend.api.modules.version_control.domain.serializer import (
    serialize_requirement_space,
    to_deterministic_json,
    compute_state_hash,
)
from backend.api.modules.version_control.application.baseline_migration import (
    migrate_project_to_version_control,
    migrate_all_projects_to_version_control,
)
from backend.api.modules.version_control.application.workspace_restoration import (
    restore_workspace_from_state,
    copy_workspace,
)
from backend.api.modules.version_control.application.workspace_serializer import (
    build_workspace_state_dict,
    serialize_workspace,
)
from backend.api.modules.version_control.application.branch_service import (
    resolve_branch_context,
    list_branches,
    get_branch_detail,
    create_branch,
    rename_branch,
    delete_branch,
)
from backend.api.modules.version_control.application.commit_service import (
    create_commit,
    list_commits,
    get_commit_detail,
    resolve_commit_in_project,
)
from backend.api.modules.version_control.application.diff_service import (
    get_diff,
    get_entity_diff,
    resolve_state,
)
from backend.api.modules.version_control.domain.semantic_diff import (
    compute_semantic_diff,
    find_entity_meta,
)
from backend.api.modules.version_control.application.merge_service import (
    create_merge_request,
    list_merge_requests,
    get_mr_detail,
    add_mr_comment,
    review_mr,
    close_mr,
)
from backend.api.modules.version_control.application.merge_execution import (
    get_merge_preview,
    perform_merge,
)
from backend.api.modules.version_control.domain.semantic_merge import (
    compute_three_way_merge,
)

__all__ = [
    "generate_logical_uuid",
    "ensure_logical_uuid",
    "serialize_requirement_space",
    "to_deterministic_json",
    "compute_state_hash",
    "migrate_project_to_version_control",
    "migrate_all_projects_to_version_control",
    "restore_workspace_from_state",
    "copy_workspace",
    "build_workspace_state_dict",
    "serialize_workspace",
    "resolve_branch_context",
    "list_branches",
    "get_branch_detail",
    "create_branch",
    "rename_branch",
    "delete_branch",
    "create_commit",
    "list_commits",
    "get_commit_detail",
    "resolve_commit_in_project",
    "get_diff",
    "get_entity_diff",
    "resolve_state",
    "compute_semantic_diff",
    "find_entity_meta",
    "create_merge_request",
    "list_merge_requests",
    "get_mr_detail",
    "add_mr_comment",
    "review_mr",
    "close_mr",
    "get_merge_preview",
    "perform_merge",
    "compute_three_way_merge",
]

