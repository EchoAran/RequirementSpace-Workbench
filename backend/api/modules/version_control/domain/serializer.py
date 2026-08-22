"""
Deterministic Requirement Space Serializer and SHA-256 State Hasher.
负责将 BranchWorkspace 及其关联的需求实体（Actor, Feature, Scenario, AC, BusinessObject, Attribute, Flow, Step, Scope）
序列化为规范化、只含逻辑 ID 的确定性 JSON 字符串，并计算 SHA-256 内容哈希。
"""
import hashlib
import json
from typing import Any

CURRENT_SCHEMA_VERSION = "1.0"


def serialize_requirement_space(
    workspace_data: dict[str, Any],
    schema_version: str = CURRENT_SCHEMA_VERSION,
) -> dict[str, Any]:
    """
    将原生需求空间字典规范化整理为无噪声、固定排序的格式化字典。

    :param workspace_data: 包含 actors, features, feature_relations, scenarios, business_objects, flows, scopes 等元数据的输入字典
    :param schema_version: 规范版本号
    :return: 经过清洗和确定性排序的完整规范模型字典
    """
    # 提取项目元数据并默认规范化
    project_meta = workspace_data.get("project_metadata", {})
    normalized_meta = {
        "user_requirements": str(project_meta.get("user_requirements", "") or ""),
        "kano_status": str(project_meta.get("kano_status", "missing") or "missing"),
        "unlocked_stages": str(project_meta.get("unlocked_stages", "") or ""),
    }

    # Actors 规范化与排序
    actors_raw: list[dict[str, Any]] = workspace_data.get("actors", [])
    actors = []
    for item in actors_raw:
        actors.append({
            "logical_uuid": str(item["logical_uuid"]),
            "name": str(item.get("name", "") or ""),
            "description": str(item.get("description", "") or ""),
            "confirmation_status": str(item.get("confirmation_status", "ai_assumption") or "ai_assumption"),
        })
    actors.sort(key=lambda x: x["logical_uuid"])

    # Features 规范化与排序
    features_raw: list[dict[str, Any]] = workspace_data.get("features", [])
    features = []
    for item in features_raw:
        actor_uuids = sorted(list(set(str(u) for u in item.get("actor_logical_uuids", []))))
        features.append({
            "logical_uuid": str(item["logical_uuid"]),
            "name": str(item.get("name", "") or ""),
            "description": str(item.get("description", "") or ""),
            "confirmation_status": str(item.get("confirmation_status", "ai_assumption") or "ai_assumption"),
            "actor_logical_uuids": actor_uuids,
        })
    features.sort(key=lambda x: x["logical_uuid"])

    # Feature Relations 规范化与排序
    feature_relations_raw: list[dict[str, Any]] = workspace_data.get("feature_relations", [])
    feature_relations = []
    for item in feature_relations_raw:
        feature_relations.append({
            "logical_uuid": str(item["logical_uuid"]),
            "parent_feature_logical_uuid": str(item["parent_feature_logical_uuid"]),
            "child_feature_logical_uuid": str(item["child_feature_logical_uuid"]),
            "position": int(item.get("position", 0)),
        })
    feature_relations.sort(
        key=lambda x: (x["parent_feature_logical_uuid"], x["position"], x["child_feature_logical_uuid"])
    )

    # Scenarios 规范化与排序
    scenarios_raw: list[dict[str, Any]] = workspace_data.get("scenarios", [])
    scenarios = []
    for item in scenarios_raw:
        ac_raw: list[dict[str, Any]] = item.get("acceptance_criteria", [])
        ac_list = []
        for ac in ac_raw:
            ac_list.append({
                "logical_uuid": str(ac["logical_uuid"]),
                "position": int(ac.get("position", 0)),
                "content": str(ac.get("content", "") or ""),
                "confirmation_status": str(ac.get("confirmation_status", "ai_assumption") or "ai_assumption"),
            })
        ac_list.sort(key=lambda x: (x["position"], x["logical_uuid"]))

        scenarios.append({
            "logical_uuid": str(item["logical_uuid"]),
            "feature_logical_uuid": str(item["feature_logical_uuid"]) if item.get("feature_logical_uuid") else None,
            "actor_logical_uuid": str(item["actor_logical_uuid"]) if item.get("actor_logical_uuid") else None,
            "name": str(item.get("name", "") or ""),
            "content": str(item.get("content", "") or ""),
            "confirmation_status": str(item.get("confirmation_status", "ai_assumption") or "ai_assumption"),
            "acceptance_criteria": ac_list,
        })
    scenarios.sort(key=lambda x: x["logical_uuid"])

    # Business Objects 规范化与排序
    bo_raw: list[dict[str, Any]] = workspace_data.get("business_objects", [])
    business_objects = []
    for item in bo_raw:
        attrs_raw: list[dict[str, Any]] = item.get("attributes", [])
        attrs_list = []
        for attr in attrs_raw:
            attrs_list.append({
                "logical_uuid": str(attr["logical_uuid"]),
                "name": str(attr.get("name", "") or ""),
                "data_type": str(attr.get("data_type", "") or ""),
                "description": str(attr.get("description", "") or ""),
                "example": str(attr.get("example", "") or ""),
                "confirmation_status": str(attr.get("confirmation_status", "ai_assumption") or "ai_assumption"),
            })
        attrs_list.sort(key=lambda x: x["logical_uuid"])

        business_objects.append({
            "logical_uuid": str(item["logical_uuid"]),
            "name": str(item.get("name", "") or ""),
            "description": str(item.get("description", "") or ""),
            "confirmation_status": str(item.get("confirmation_status", "ai_assumption") or "ai_assumption"),
            "attributes": attrs_list,
        })
    business_objects.sort(key=lambda x: x["logical_uuid"])

    # Flows 规范化与排序
    flows_raw: list[dict[str, Any]] = workspace_data.get("flows", [])
    flows = []
    for item in flows_raw:
        f_feat_uuids = sorted(list(set(str(u) for u in item.get("feature_logical_uuids", []))))
        steps_raw: list[dict[str, Any]] = item.get("steps", [])
        steps_list = []
        for step in steps_raw:
            steps_list.append({
                "logical_uuid": str(step["logical_uuid"]),
                "position": int(step.get("position", 0)),
                "name": str(step.get("name", "") or ""),
                "description": str(step.get("description", "") or ""),
                "step_type": str(step.get("step_type", "") or ""),
                "confirmation_status": str(step.get("confirmation_status", "ai_assumption") or "ai_assumption"),
                "actor_logical_uuids": sorted(list(set(str(u) for u in step.get("actor_logical_uuids", [])))),
                "input_business_object_logical_uuids": sorted(list(set(str(u) for u in step.get("input_business_object_logical_uuids", [])))),
                "output_business_object_logical_uuids": sorted(list(set(str(u) for u in step.get("output_business_object_logical_uuids", [])))),
                "next_step_logical_uuids": sorted(list(set(str(u) for u in step.get("next_step_logical_uuids", [])))),
            })
        steps_list.sort(key=lambda x: (x["position"], x["logical_uuid"]))

        flows.append({
            "logical_uuid": str(item["logical_uuid"]),
            "name": str(item.get("name", "") or ""),
            "description": str(item.get("description", "") or ""),
            "confirmation_status": str(item.get("confirmation_status", "ai_assumption") or "ai_assumption"),
            "feature_logical_uuids": f_feat_uuids,
            "steps": steps_list,
        })
    flows.sort(key=lambda x: x["logical_uuid"])

    # Scopes 规范化与排序
    scopes_raw: list[dict[str, Any]] = workspace_data.get("scopes", [])
    scopes = []
    for item in scopes_raw:
        scopes.append({
            "logical_uuid": str(item["logical_uuid"]),
            "feature_logical_uuid": str(item["feature_logical_uuid"]) if item.get("feature_logical_uuid") else None,
            "status": str(item.get("status", "") or ""),
            "positive_summary": str(item.get("positive_summary", "") or "") if item.get("positive_summary") is not None else None,
            "negative_summary": str(item.get("negative_summary", "") or "") if item.get("negative_summary") is not None else None,
            "reason": str(item.get("reason", "") or ""),
            "kano_category": str(item.get("kano_category", "") or "") if item.get("kano_category") is not None else None,
            "kano_category_name": str(item.get("kano_category_name", "") or "") if item.get("kano_category_name") is not None else None,
            "confirmation_status": str(item.get("confirmation_status", "ai_assumption") or "ai_assumption"),
        })
    scopes.sort(key=lambda x: x["logical_uuid"])

    return {
        "schema_version": schema_version,
        "project_metadata": normalized_meta,
        "actors": actors,
        "features": features,
        "feature_relations": feature_relations,
        "scenarios": scenarios,
        "business_objects": business_objects,
        "flows": flows,
        "scopes": scopes,
    }


def to_deterministic_json(normalized_dict: dict[str, Any]) -> str:
    """
    将规范模型字典转换为具有严格确定性的 JSON 字符串。
    统一使用 UTF-8，键名升序，紧凑无多余空格分隔符。
    """
    return json.dumps(
        normalized_dict,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def compute_state_hash(state_json: str) -> str:
    """
    计算确定性 JSON 字符串的 SHA-256 哈希散列值。
    """
    return hashlib.sha256(state_json.encode("utf-8")).hexdigest()
