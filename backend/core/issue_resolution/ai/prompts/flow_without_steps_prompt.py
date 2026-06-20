"""System and user prompt templates for FLOW_WITHOUT_STEPS AI recommendation."""

FLOW_WITHOUT_STEPS_SYSTEM_PROMPT = """你是一个业务流程设计助手。

你的任务是分析流程上下文，推荐一组典型的流程步骤（Steps）。
只输出 JSON，不要任何额外文本。
"""

FLOW_WITHOUT_STEPS_USER_PROMPT_TEMPLATE = """## 目标空流程
流程名称: {flow_name}
流程描述: {flow_description}

## 所属功能及需求上下文
功能名称: {feature_name}
功能描述: {feature_description}
用户需求: {user_requirements}

## 项目现有参与角色
{actors_json}

## 项目现有业务对象
{business_objects_json}

## 要求
由于流程缺少步骤，请为此流程设计并推荐 3-6 个核心步骤。
为确保流程模型的精细度，此步骤列表不需要自动写入库，而是应作为结构化 AI 处理建议呈现给用户。

输出 JSON 格式:
{{
  "fallback": {{
    "kind": "manual_action",
    "reason": "建议为此流程添加以下典型步骤：\\n1. [步骤名] 参与者:xxx, 说明:xxx\\n2. [步骤名] ...\\n\\n您可以打开流程面板，根据上述建议手动配置步骤。"
  }}
}}
"""
