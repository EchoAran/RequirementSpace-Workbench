import os
from pathlib import Path
import re

root_dir = Path("e:/PycharmProjects/RequirementSpace-Workbench/backend/core")

for py_path in root_dir.glob("**/*.py"):
    if "prompts" in py_path.parts or "tests" in py_path.parts or "__pycache__" in py_path.parts:
        continue
    content = py_path.read_text(encoding="utf-8")
    imports = re.findall(r"from .*import.*prompt", content, re.IGNORECASE)
    usages = re.findall(r"[a-zA-Z0-9_]*prompt[a-zA-Z0-9_]*", content, re.IGNORECASE)
    # filter out imports/usages that don't actually do anything
    filtered_usages = [u for u in usages if u not in ("LLMPromptEvent", "LLM_PROMPT_SAMPLE")]
    if imports or filtered_usages:
        print(f"File: {py_path.relative_to(root_dir)}")
        if imports:
            print(f"  Imports: {imports}")
        if filtered_usages:
            print(f"  Usages: {set(filtered_usages)}")
