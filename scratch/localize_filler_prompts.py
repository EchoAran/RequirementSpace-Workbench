from pathlib import Path
import re

prompts_dir = Path("e:/PycharmProjects/RequirementSpace-Workbench/backend/core/prompts")
zh_dir = prompts_dir / "zh-CN"
zh_dir.mkdir(parents=True, exist_ok=True)

filler_prompts_dir = Path("e:/PycharmProjects/RequirementSpace-Workbench/backend/core/perceptrons/slot_fillers/prompts")

files = [
    ("acceptance_criteria_fill_agent.py", "acceptance_criteria_fill_prompt", "acceptance_criteria_fill"),
    ("actors_fill_agent.py", "actors_fill_prompt", "actors_fill"),
    ("features_fill_agent.py", "features_fill_prompt", "features_fill"),
    ("scenarios_fill_agent.py", "scenarios_fill_prompt", "scenarios_fill"),
]

for filename, varname, key in files:
    filepath = filler_prompts_dir / filename
    content = filepath.read_text(encoding="utf-8")
    
    # Extract prompt
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
        print(f"ERROR: Could not find prompt in {filename}")

# Specially handle flows_fill_agent.py because it has two prompts:
# flows_fill_prompt and business_objects_actors_label_prompt
flows_filepath = filler_prompts_dir / "flows_fill_agent.py"
flows_content = flows_filepath.read_text(encoding="utf-8")

# Extract flows_fill_prompt
flows_match = re.search(r'flows_fill_prompt\s*=\s*"""(.*?)"""', flows_content, re.DOTALL)
if flows_match:
    flows_text = flows_match.group(1).strip()
    with open(zh_dir / "flows_fill.txt", "w", encoding="utf-8") as f:
        f.write(flows_text)
        
    new_flows_py = """from backend.core.prompt_resolver import LocalizedPromptProxy

flows_fill_prompt = LocalizedPromptProxy("flows_fill")
business_objects_actors_label_prompt = LocalizedPromptProxy("business_objects_actors_label")
"""
    flows_filepath.write_text(new_flows_py, encoding="utf-8")
    print("Processed flows_fill_agent.py -> flows_fill, business_objects_actors_label")
else:
    print("ERROR: Could not find flows_fill_prompt in flows_fill_agent.py")

print("Localized filler prompts successfully!")
