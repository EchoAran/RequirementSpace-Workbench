"""System and user prompt templates for BUSINESS_OBJECT_WITHOUT_USAGE AI recommendation."""

BUSINESS_OBJECT_WITHOUT_USAGE_SYSTEM_PROMPT = """你是一个业务对象建模与分析助手。

你的任务是分析项目中的孤立业务对象，并推荐它们应该在哪些流程步骤中被使用。
只输出 JSON，不要任何额外文本。
"""

BUSINESS_OBJECT_WITHOUT_USAGE_USER_PROMPT_TEMPLATE = """## 目标业务对象
名称: {bo_name}
描述: {bo_description}
属性列表: {bo_attributes_json}

## 项目现有流程与步骤
{flows_and_steps_json}

## 需求上下文
{user_requirements}

## 要求
该业务对象没有被任何流程步骤使用。请分析项目上下文，推荐其最适合在哪个流程的哪个步骤中作为输入（Input）或输出（Output）对象，并说明理由。
此建议无需自动写库，应作为结构化 AI 处理建议呈现给用户。

输出 JSON 格式:
{{
  "fallback": {{
    "kind": "manual_action",
    "reason": "业务对象「{bo_name}」建议在以下流程步骤中被使用：\\n- 流程「xxx」的步骤「xxx」：建议作为 [输入/输出] 关联，因为 [理由]\\n\\n您可以打开业务对象面板查看并手动配置其使用关系。"
  }}
}}
"""
