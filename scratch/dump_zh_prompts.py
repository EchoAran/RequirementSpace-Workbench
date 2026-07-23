import os
from pathlib import Path

# Create directories
prompts_dir = Path("e:/PycharmProjects/RequirementSpace-Workbench/backend/core/prompts")
zh_dir = prompts_dir / "zh-CN"
en_dir = prompts_dir / "en-US"

zh_dir.mkdir(parents=True, exist_ok=True)
en_dir.mkdir(parents=True, exist_ok=True)

# Import and dump generators prompts
from backend.core.generators.prompts.actors_generate_agent import actors_generate_prompt
from backend.core.generators.prompts.features_generate_agent import features_generate_prompt
from backend.core.generators.prompts.flows_generate_agent import (
    business_object_in_flows_prompt,
    business_objects_generate_prompt,
    flows_generate_prompt,
    flows_generate_prompt_old,
)
from backend.core.generators.prompts.scenarios_generate_agent import scenarios_generate_prompt
from backend.core.generators.prompts.scopes_generate_agent import scopes_generate_prompt
from backend.core.generators.prompts.acceptance_criteria_generate_agent import acceptance_criteria_generate_prompt
from backend.core.generators.prompts.blank_project_generate_agent import blank_project_generate_prompt
from backend.core.generators.prompts.project_interview_prompt import PROJECT_INTERVIEW_SYSTEM_PROMPT

prompts = {
    "actors_generate": actors_generate_prompt,
    "features_generate": features_generate_prompt,
    "business_object_in_flows": business_object_in_flows_prompt,
    "business_objects_generate": business_objects_generate_prompt,
    "flows_generate": flows_generate_prompt,
    "flows_generate_old": flows_generate_prompt_old,
    "scenarios_generate": scenarios_generate_prompt,
    "scopes_generate": scopes_generate_prompt,
    "acceptance_criteria_generate": acceptance_criteria_generate_prompt,
    "blank_project_generate": blank_project_generate_prompt,
    "project_interview": PROJECT_INTERVIEW_SYSTEM_PROMPT,
}

# Dump to files
for name, content in prompts.items():
    with open(zh_dir / f"{name}.txt", "w", encoding="utf-8") as f:
        f.write(content.strip())

print("Dumped zh-CN prompts successfully!")
