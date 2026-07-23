import os
from pathlib import Path

prompts_dir = Path("e:/PycharmProjects/RequirementSpace-Workbench/backend/core/prompts")
zh_dir = prompts_dir / "zh-CN"
zh_dir.mkdir(parents=True, exist_ok=True)

# 1. Perceptrons
from backend.core.perceptrons.prompts.actors_perceive_agent import actors_perceive_prompt
from backend.core.perceptrons.prompts.features_perceive_agent import features_perceive_prompt
from backend.core.perceptrons.prompts.flows_perceive_agent import flows_perceive_prompt
from backend.core.perceptrons.prompts.scenarios_perceive_agent import scenarios_perceive_prompt
from backend.core.perceptrons.prompts.acceptance_criteria_perceive_agent import acceptance_criteria_perceive_prompt

# 2. Slot Fillers
from backend.core.perceptrons.slot_fillers.prompts.actors_fill_agent import actors_fill_prompt
from backend.core.perceptrons.slot_fillers.prompts.features_fill_agent import features_fill_prompt
from backend.core.perceptrons.slot_fillers.prompts.flows_fill_agent import flows_fill_prompt
from backend.core.perceptrons.slot_fillers.prompts.scenarios_fill_agent import scenarios_fill_prompt
from backend.core.perceptrons.slot_fillers.prompts.acceptance_criteria_fill_agent import acceptance_criteria_fill_prompt

# 3. Issue resolution prompts
from backend.core.issue_resolution.ai.prompts.actor_feature_coverage_repair_prompt import actor_feature_coverage_repair_prompt
from backend.core.issue_resolution.ai.prompts.actor_feature_reverse_coverage_repair_prompt import actor_feature_reverse_coverage_repair_prompt
from backend.core.issue_resolution.ai.prompts.business_object_attribute_repair_prompt import business_object_attribute_repair_prompt
from backend.core.issue_resolution.ai.prompts.business_object_without_usage_prompt import business_object_without_usage_prompt
from backend.core.issue_resolution.ai.prompts.duplicate_scenario_name_repair_prompt import duplicate_scenario_name_repair_prompt
from backend.core.issue_resolution.ai.prompts.flow_feature_coverage_repair_prompt import flow_feature_coverage_repair_prompt
from backend.core.issue_resolution.ai.prompts.flow_without_steps_prompt import flow_without_steps_prompt
from backend.core.issue_resolution.ai.prompts.scenario_actor_consistency_repair_prompt import scenario_actor_consistency_repair_prompt
from backend.core.issue_resolution.ai.prompts.scenario_coverage_repair_prompt import scenario_coverage_repair_prompt
from backend.core.issue_resolution.ai.prompts.scope_reason_repair_prompt import scope_reason_repair_prompt

# 4. Single object prompts
from backend.core.generators.single_object.prompts.edit_actor_prompt import edit_actor_prompt
from backend.core.generators.single_object.prompts.edit_business_object_prompt import edit_business_object_prompt
from backend.core.generators.single_object.prompts.edit_feature_prompt import edit_feature_prompt
from backend.core.generators.single_object.prompts.edit_flow_prompt import edit_flow_prompt
from backend.core.generators.single_object.prompts.single_actor_prompt import single_actor_prompt
from backend.core.generators.single_object.prompts.single_business_object_prompt import single_business_object_prompt
from backend.core.generators.single_object.prompts.single_feature_prompt import single_feature_prompt
from backend.core.generators.single_object.prompts.single_flow_prompt import single_flow_prompt

prompts = {
    # Perceptrons
    "actors_perceive": actors_perceive_prompt,
    "features_perceive": features_perceive_prompt,
    "flows_perceive": flows_perceive_prompt,
    "scenarios_perceive": scenarios_perceive_prompt,
    "acceptance_criteria_perceive": acceptance_criteria_perceive_prompt,
    
    # Slot fillers
    "actors_fill": actors_fill_prompt,
    "features_fill": features_fill_prompt,
    "flows_fill": flows_fill_prompt,
    "scenarios_fill": scenarios_fill_prompt,
    "acceptance_criteria_fill": acceptance_criteria_fill_prompt,
    
    # Issue resolution
    "actor_feature_coverage_repair": actor_feature_coverage_repair_prompt,
    "actor_feature_reverse_coverage_repair": actor_feature_reverse_coverage_repair_prompt,
    "business_object_attribute_repair": business_object_attribute_repair_prompt,
    "business_object_without_usage": business_object_without_usage_prompt,
    "duplicate_scenario_name_repair": duplicate_scenario_name_repair_prompt,
    "flow_feature_coverage_repair": flow_feature_coverage_repair_prompt,
    "flow_without_steps": flow_without_steps_prompt,
    "scenario_actor_consistency_repair": scenario_actor_consistency_repair_prompt,
    "scenario_coverage_repair": scenario_coverage_repair_prompt,
    "scope_reason_repair": scope_reason_repair_prompt,
    
    # Single object
    "edit_actor": edit_actor_prompt,
    "edit_business_object": edit_business_object_prompt,
    "edit_feature": edit_feature_prompt,
    "edit_flow": edit_flow_prompt,
    "single_actor": single_actor_prompt,
    "single_business_object": single_business_object_prompt,
    "single_feature": single_feature_prompt,
    "single_flow": single_flow_prompt,
}

# Dump to files
for name, content in prompts.items():
    with open(zh_dir / f"{name}.txt", "w", encoding="utf-8") as f:
        f.write(content.strip())

# Explain prompt (from explain.py lines 78-90 approx)
explain_prompt = """
# 角色
你是项目「{project_name}」的需求分析专家，负责回答用户关于项目的疑问。

# 回答规则
1. 只基于以下提供的项目信息回答，不要假设不存在的信息。
2. 如果信息不足，直接说项目中没有相关信息。
3. 回答时引用具体的对象名称和 ID，让用户知道信息来源。
4. 回答简洁，直接回答问题后可补充相关上下文。

# 项目需求概述
{user_requirements}

# 当前上下文范围：{scope_label}
{context_text}
"""

with open(zh_dir / "explain.txt", "w", encoding="utf-8") as f:
    f.write(explain_prompt.strip())

print("Dumped all remaining zh-CN prompts successfully!")
