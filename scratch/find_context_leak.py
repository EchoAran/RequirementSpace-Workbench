import re
from pathlib import Path

root = Path("e:/PycharmProjects/RequirementSpace-Workbench/backend")
pattern = re.compile(r"(\w+)\.set\(")

for pyfile in root.glob("**/*.py"):
    content = pyfile.read_text(encoding="utf-8")
    matches = pattern.findall(content)
    if matches:
        print(f"File: {pyfile.relative_to(root)}")
        for match in matches:
            print(f"  Found set on contextvar: {match}")
