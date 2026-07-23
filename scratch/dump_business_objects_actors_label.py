from pathlib import Path
from backend.core.perceptrons.slot_fillers.prompts.flows_fill_agent import business_objects_actors_label_prompt

zh_dir = Path("e:/PycharmProjects/RequirementSpace-Workbench/backend/core/prompts/zh-CN")
with open(zh_dir / "business_objects_actors_label.txt", "w", encoding="utf-8") as f:
    f.write(business_objects_actors_label_prompt.strip())

print("Dumped business_objects_actors_label_prompt successfully!")
