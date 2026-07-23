from pathlib import Path
import re

prompts_dir = Path("e:/PycharmProjects/RequirementSpace-Workbench/backend/core/prompts")
zh_dir = prompts_dir / "zh-CN"
zh_dir.mkdir(parents=True, exist_ok=True)

single_prompts_dir = Path("e:/PycharmProjects/RequirementSpace-Workbench/backend/core/generators/single_object/prompts")

files = [
    ("edit_actor_prompt.py", "EDIT_ACTOR_GENERATE_PROMPT", "edit_actor"),
    ("edit_business_object_prompt.py", "EDIT_BUSINESS_OBJECT_GENERATE_PROMPT", "edit_business_object"),
    ("edit_feature_prompt.py", "EDIT_FEATURE_GENERATE_PROMPT", "edit_feature"),
    ("edit_flow_prompt.py", "EDIT_FLOW_GENERATE_PROMPT", "edit_flow"),
    ("single_actor_prompt.py", "SINGLE_ACTOR_GENERATE_PROMPT", "single_actor"),
    ("single_business_object_prompt.py", "SINGLE_BUSINESS_OBJECT_GENERATE_PROMPT", "single_business_object"),
    ("single_feature_prompt.py", "SINGLE_FEATURE_GENERATE_PROMPT", "single_feature"),
    ("single_flow_prompt.py", "SINGLE_FLOW_GENERATE_PROMPT", "single_flow"),
]

for filename, varname, key in files:
    filepath = single_prompts_dir / filename
    content = filepath.read_text(encoding="utf-8")
    
    # Extract string literal
    # We look for: varname = """..."""
    pattern = rf'{varname}\s*=\s*"""(.*?)"""'
    match = re.search(pattern, content, re.DOTALL)
    if match:
        prompt_text = match.group(1).strip()
        # Write to txt file
        with open(zh_dir / f"{key}.txt", "w", encoding="utf-8") as f:
            f.write(prompt_text)
            
        # Rewrite py file
        new_py_content = f"""from backend.core.prompt_resolver import LocalizedPromptProxy

{varname} = LocalizedPromptProxy("{key}")
"""
        filepath.write_text(new_py_content, encoding="utf-8")
        print(f"Processed {filename} -> {key}")
    else:
        print(f"ERROR: Could not find {varname} in {filename}")

print("Localized single object prompts successfully!")
