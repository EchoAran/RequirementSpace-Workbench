from pathlib import Path
import re

prompts_dir = Path("e:/PycharmProjects/RequirementSpace-Workbench/backend/core/prompts")
zh_dir = prompts_dir / "zh-CN"
zh_dir.mkdir(parents=True, exist_ok=True)

perceptron_prompts_dir = Path("e:/PycharmProjects/RequirementSpace-Workbench/backend/core/perceptrons/prompts")

files = [
    ("actors_perceive_agent.py", "actors_perceive_prompt", "actors_perceive"),
    ("features_perceive_agent.py", "features_perceive_prompt", "features_perceive"),
    ("flows_perceive_agent.py", "flows_perceive_prompt", "flows_perceive"),
    ("scenarios_perceive_agent.py", "scenarios_perceive_prompt", "scenarios_perceive"),
    ("acceptance_criteria_perceive_agent.py", "acceptance_criteria_perceive_prompt", "acceptance_criteria_perceive"),
]

for filename, varname, key in files:
    filepath = perceptron_prompts_dir / filename
    content = filepath.read_text(encoding="utf-8")
    
    # Extract prompt
    pattern = rf'{varname}\s*=\s*"""(.*?)"""'
    match = re.search(pattern, content, re.DOTALL)
    
    if match:
        prompt_text = match.group(1).strip()
        
        # Write to txt files
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

print("Localized perceptron prompts successfully!")
