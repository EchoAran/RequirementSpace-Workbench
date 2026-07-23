from pathlib import Path
import re

prompts_dir = Path("e:/PycharmProjects/RequirementSpace-Workbench/backend/core/prompts")
zh_dir = prompts_dir / "zh-CN"
zh_dir.mkdir(parents=True, exist_ok=True)

issue_prompts_dir = Path("e:/PycharmProjects/RequirementSpace-Workbench/backend/core/issue_resolution/ai/prompts")

files = [
    ("actor_feature_coverage_repair_prompt.py", "ACTOR_FEATURE_COVERAGE_SYSTEM_PROMPT", "ACTOR_FEATURE_COVERAGE_USER_PROMPT_TEMPLATE", "actor_feature_coverage"),
    ("actor_feature_reverse_coverage_repair_prompt.py", "ACTOR_FEATURE_REVERSE_COVERAGE_SYSTEM_PROMPT", "ACTOR_FEATURE_REVERSE_COVERAGE_USER_PROMPT_TEMPLATE", "actor_feature_reverse_coverage"),
    ("business_object_attribute_repair_prompt.py", "SYSTEM_PROMPT", "USER_PROMPT_TEMPLATE", "business_object_attribute"),
    ("business_object_without_usage_prompt.py", "BUSINESS_OBJECT_WITHOUT_USAGE_SYSTEM_PROMPT", "BUSINESS_OBJECT_WITHOUT_USAGE_USER_PROMPT_TEMPLATE", "business_object_without_usage"),
    ("duplicate_scenario_name_repair_prompt.py", "DUPLICATE_SCENARIO_NAME_SYSTEM_PROMPT", "DUPLICATE_SCENARIO_NAME_USER_PROMPT_TEMPLATE", "duplicate_scenario_name"),
    ("flow_feature_coverage_repair_prompt.py", "SYSTEM_PROMPT", "USER_PROMPT_TEMPLATE", "flow_feature_coverage"),
    ("flow_without_steps_prompt.py", "FLOW_WITHOUT_STEPS_SYSTEM_PROMPT", "FLOW_WITHOUT_STEPS_USER_PROMPT_TEMPLATE", "flow_without_steps"),
    ("scenario_actor_consistency_repair_prompt.py", "SCENARIO_ACTOR_CONSISTENCY_SYSTEM_PROMPT", "SCENARIO_ACTOR_CONSISTENCY_USER_PROMPT_TEMPLATE", "scenario_actor_consistency"),
    ("scenario_coverage_repair_prompt.py", "SYSTEM_PROMPT", "USER_PROMPT_TEMPLATE", "scenario_coverage"),
    ("scope_reason_repair_prompt.py", "SCOPE_REASON_SYSTEM_PROMPT", "SCOPE_REASON_USER_PROMPT_TEMPLATE", "scope_reason"),
]

for filename, sys_var, usr_var, key in files:
    filepath = issue_prompts_dir / filename
    content = filepath.read_text(encoding="utf-8")
    
    # Extract system prompt
    sys_pattern = rf'{sys_var}\s*=\s*"""(.*?)"""'
    sys_match = re.search(sys_pattern, content, re.DOTALL)
    
    # Extract user prompt
    usr_pattern = rf'{usr_var}\s*=\s*"""(.*?)"""'
    usr_match = re.search(usr_pattern, content, re.DOTALL)
    
    if sys_match and usr_match:
        sys_text = sys_match.group(1).strip()
        usr_text = usr_match.group(1).strip()
        
        # Write to txt files
        with open(zh_dir / f"{key}_system.txt", "w", encoding="utf-8") as f:
            f.write(sys_text)
        with open(zh_dir / f"{key}_user.txt", "w", encoding="utf-8") as f:
            f.write(usr_text)
            
        # Rewrite py file
        new_py_content = f"""from backend.core.prompt_resolver import LocalizedPromptProxy

{sys_var} = LocalizedPromptProxy("{key}_system")
{usr_var} = LocalizedPromptProxy("{key}_user")
"""
        filepath.write_text(new_py_content, encoding="utf-8")
        print(f"Processed {filename} -> {key}")
    else:
        print(f"ERROR: Could not find prompts in {filename}")

print("Localized issue resolution prompts successfully!")
