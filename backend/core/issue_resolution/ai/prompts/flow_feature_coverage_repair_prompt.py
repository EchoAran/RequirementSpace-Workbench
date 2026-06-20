"""Prompt templates for LEAF_FEATURE_WITHOUT_FLOW / FLOW_WITHOUT_FEATURE AI repair."""

SYSTEM_PROMPT = """你是一个流程-功能匹配助手。

根据功能描述和现有流程列表，推荐最合适的匹配关系。
只输出 JSON，不要任何额外文本。
"""

USER_PROMPT_TEMPLATE = """## 需求上下文
{user_requirements}

## 目标实体
类型: {target_type}
名称: {target_name}
描述: {target_description}
{feature_context}

## 项目中可匹配的{target_match_label}
{matches_json}

## 要求
1. 分析哪个{target_match_label}与目标最匹配。
2. 如果只有一个明显匹配，输出单个 candidate。
3. 如果有多个都可能，输出多个 candidates。
4. 如果没有合适的匹配，设置 fallback。
5. 置信度低于 0.6 时设置 requires_user_decision = true。

输出 JSON 格式:
{{
  "candidates": [
    {{
      "repair_type": "bind_flow_feature",
      "title": "绑定到「{match_name}」",
      "rationale": "解释为什么匹配",
      "confidence": 0.85,
      "patch": {{
        "addLinks": [
          {{
            "type": "flow_feature_relation",
            "source_id": {match_id},
            "target_id": {target_id}
          }}
        ]
      }},
      "requires_user_decision": false
    }}
  ],
  "fallback": {{
    "kind": "manual_action",
    "reason": "未找到合适的匹配"
  }}
}}
"""
