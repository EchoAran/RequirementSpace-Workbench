"""System and user prompt templates for LEAF_FEATURE_WITHOUT_ACTOR AI repair."""

ACTOR_FEATURE_COVERAGE_SYSTEM_PROMPT = """你是一个需求角色-功能匹配助手。

你的任务是根据功能描述和现有角色列表，推荐最合适的执行角色。
只输出 JSON，不要任何额外文本。
"""

ACTOR_FEATURE_COVERAGE_USER_PROMPT_TEMPLATE = """## 需求上下文
{user_requirements}

## 目标叶子功能
名称: {feature_name}
描述: {feature_description}

## 项目已有角色
{actors_json}

## 要求
1. 分析哪个角色最适合执行该功能。
2. 如果只有一个角色明显匹配，输出单个 candidate。
3. 如果有多个角色都可能，输出多个 candidates，每个都有独立 rationale。
4. 如果没有合适角色，设置 fallback。
5. 置信度低于 0.6 时设置 requires_user_decision = true。

输出 JSON 格式:
{{
  "candidates": [
    {{
      "repair_type": "bind_existing_actor",
      "title": "绑定到「角色名称」",
      "rationale": "解释为什么这个角色适合",
      "confidence": 0.85,
      "patch": {{
        "addLinks": [
          {{
            "type": "feature_actor_relation",
            "source_id": {feature_id},
            "target_id": <actor_id>
          }}
        ]
      }},
      "requires_user_decision": false
    }}
  ],
  "fallback": {{
    "kind": "manual_action",
    "reason": "没有找到合适的角色，请手动选择"
  }}
}}
"""
