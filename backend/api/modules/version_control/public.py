"""
Version Control Domain Module Public Facade.
对外导出的稳定 API 接口与迁移工具。
"""
from backend.api.modules.version_control.application.branch_service import (
    create_branch,
    delete_branch,
    get_branch_detail,
    list_branches,
    rename_branch,
    resolve_branch_context,
)
from backend.api.modules.version_control.application.clean_initialization import (
    create_initial_workspace,
    finalize_initial_commit,
    initialize_project_version_control,
)
from backend.api.modules.version_control.application.commit_service import (
    create_commit,
    get_commit_detail,
    list_commits,
    resolve_commit_in_project,
)
from backend.api.modules.version_control.application.diff_service import (
    get_diff,
    get_entity_diff,
    resolve_state,
)
from backend.api.modules.version_control.application.merge_execution import (
    get_merge_preview,
    perform_merge,
)
from backend.api.modules.version_control.application.merge_service import (
    add_mr_comment,
    close_mr,
    create_merge_request,
    get_mr_detail,
    list_merge_requests,
    review_mr,
)
from backend.api.modules.version_control.application.workspace_restoration import (
    copy_workspace,
    restore_workspace_from_state,
)
from backend.api.modules.version_control.application.workspace_serializer import (
    build_workspace_state_dict,
    serialize_workspace,
)
from backend.api.modules.version_control.dependencies import (
    map_branch_error,
)
from backend.api.modules.version_control.domain.semantic_diff import (
    compute_semantic_diff,
    find_entity_meta,
)
from backend.api.modules.version_control.domain.semantic_merge import (
    compute_three_way_merge,
)
from backend.api.modules.version_control.domain.serializer import (
    compute_state_hash,
    serialize_requirement_space,
    to_deterministic_json,
)
from backend.api.modules.version_control.domain.uuid_generator import (
    ensure_logical_uuid,
    generate_logical_uuid,
)

__all__ = [
    "add_mr_comment",
    "build_workspace_state_dict",
    "close_mr",
    "compute_semantic_diff",
    "compute_state_hash",
    "compute_three_way_merge",
    "copy_workspace",
    "create_branch",
    "create_commit",
    "create_initial_workspace",
    "create_merge_request",
    "delete_branch",
    "ensure_logical_uuid",
    "finalize_initial_commit",
    "find_entity_meta",
    "generate_logical_uuid",
    "get_branch_detail",
    "get_commit_detail",
    "get_diff",
    "get_entity_diff",
    "get_merge_preview",
    "get_mr_detail",
    "initialize_project_version_control",
    "list_branches",
    "list_commits",
    "list_merge_requests",
    "map_branch_error",
    "perform_merge",
    "rename_branch",
    "resolve_branch_context",
    "resolve_commit_in_project",
    "resolve_state",
    "restore_workspace_from_state",
    "review_mr",
    "serialize_requirement_space",
    "serialize_workspace",
    "to_deterministic_json",
]
