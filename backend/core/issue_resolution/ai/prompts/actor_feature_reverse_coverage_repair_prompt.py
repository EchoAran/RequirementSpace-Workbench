"""System and user prompt templates for ACTOR_WITHOUT_FEATURE AI repair."""

ACTOR_FEATURE_REVERSE_COVERAGE_SYSTEM_PROMPT = """你是一个需求角色-功能匹配助手。

你的任务是根据角色描述和项目已有叶子功能列表，推荐最合适关联的功能。
只输出 JSON，不要任何额外文本。
"""

ACTOR_FEATURE_REVERSE_COVERAGE_USER_PROMPT_TEMPLATE = """## 需求上下文
{user_requirements}

## 目标孤立角色
名称: {actor_name}
描述: {actor_description}

## 项目叶子功能列表
{features_json}

## 要求
1. 分析哪些叶子功能最应该与该角色关联。
2. 如果只有一个功能明显匹配，输出单个 candidate。
3. 如果有多个功能都可能，输出多个 candidates，每个都有独立 rationale。
4. 如果没有合适功能，设置 fallback。
5. 置信度低于 0.6 时设置 requires_user_decision = true。

输出 JSON 格式:
{{
  "candidates": [
    {{
      "repair_type": "bind_existing_actor",
      "title": "绑定到功能「功能名称」",
      "rationale": "解释为什么这个功能适合该角色",
      "confidence": 0.85,
      "patch": {{
        "addLinks": [
          {{
            "type": "feature_actor_relation",
            "source_id": <feature_id>,
            "target_id": {actor_id}
          }}
        ]
      }},
      "requires_user_decision": false
    }}
  ],
  "fallback": {{
    "kind": "manual_action",
    "reason": "没有找到合适的功能，请手动关联"
  }}
}}
"""
