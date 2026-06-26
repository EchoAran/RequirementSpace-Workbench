"""Field permissions for AI-powered editing of existing objects.

Each object type defines which fields are allowed to be edited by the AI.
Fields not in this list will be rejected at validation time even if the LLM
outputs them.
"""

from backend.core.rules import EDITABLE_FIELDS

# Human-readable reasons for non-editable fields (for LLM rationale guidance)
NON_EDITABLE_REASONS: dict[str, dict[str, str]] = {
    "actor": {
        "id": "系统内部标识，不可修改",
        "project_id": "项目归属，不可修改",
    },
    "feature": {
        "id": "系统内部标识，不可修改",
        "project_id": "项目归属，不可修改",
        "parent_id": "拓扑位置变更会影响功能树结构，请在右侧面板手动操作",
        "feature_kind": "功能类型变更会影响功能树结构",
    },
    "flow": {
        "id": "系统内部标识，不可修改",
        "project_id": "项目归属，不可修改",
    },
    "business_object": {
        "id": "系统内部标识，不可修改",
        "project_id": "项目归属，不可修改",
    },
}
