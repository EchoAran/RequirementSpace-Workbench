"""System and user prompt templates for DUPLICATE_SCENARIO_NAME AI repair."""

DUPLICATE_SCENARIO_NAME_SYSTEM_PROMPT = """你是一个需求场景去重命名助手。

你的任务是为同名场景建议独特、去重且语义保真的新名称。
只输出 JSON，不要任何额外文本。
"""

DUPLICATE_SCENARIO_NAME_USER_PROMPT_TEMPLATE = """## 需求上下文
功能名称: {feature_name}
功能描述: {feature_description}

## 目标冲突场景
重复名称: {scenario_name}
场景内容: {scenario_content}

## 其他同功能的场景名称列表
{other_scenario_names_json}

## 要求
1. 结合重复场景的具体内容（{scenario_content}）与功能的上下文，为该场景生成一个新的、更有语义辨识度且不与同功能场景冲突的名称。
2. 给出新名称的修改方案。
3. 如果只有一个推荐名称，输出单个 candidate。如果是并列方案，可以输出 2 个以上的 candidates（会形成 choice group）。

输出 JSON 格式:
{{
  "candidates": [
    {{
      "repair_type": "rename_scenario",
      "title": "重命名场景为「新场景名称」",
      "rationale": "解释为什么要改这个名字",
      "confidence": 0.9,
      "patch": {{
        "updateNodes": [
          {{
            "kind": "scenario",
            "id": {scenario_id},
            "name": "新场景名称"
          }}
        ]
      }},
      "requires_user_decision": false
    }}
  ],
  "fallback": {{
    "kind": "manual_action",
    "reason": "无法生成更合适的名字，请手动重命名"
  }}
}}
"""
