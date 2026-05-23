# Feature Tree Skill

Generate feature tree JSON from natural language requirements with the OpenAI API.

## Install

From PyPI, after this package is published:

```bash
pip install feature-tree-skill
```

From GitHub:

```bash
pip install git+https://github.com/HarrisClover/feature-tree-skill.git
```

If running the CLI fails with `Client.__init__() got an unexpected keyword argument 'proxies'`, your environment has an old OpenAI SDK with a newer `httpx`. Upgrade the OpenAI SDK:

```bash
python -m pip install --upgrade "openai>=1.56.0"
```

From a local checkout:

```bash
pip install .
```

For editable development:

```bash
pip install -e .
```

## Configure

Set your OpenAI API key before running the CLI.

Windows Command Prompt:

```bat
set OPENAI_API_KEY=your_api_key
```

PowerShell:

```powershell
$env:OPENAI_API_KEY = "your_api_key"
```

macOS/Linux:

```bash
export OPENAI_API_KEY=your_api_key
```

## CLI

### Without actor input

Use this mode when you only have a natural-language requirement. The tool will infer role tags from the requirement and may use `[Role: Common]` for shared or non-role-specific features.

Direct input:

```bash
feature-tree-skill --req "Build a time travel adventure app for children."
```

Generate from a file:

```bash
feature-tree-skill --input examples/raw_requirement.txt --output-dir outputs
```

The file mode writes `features.json` into the output directory.

### With actor input

Use this mode when you have a natural-language requirement and a separate actor txt file. The actor file should contain role names separated by commas.

Example actor txt:

```text
Regular User, Administrator
```

Pass both the requirement and roles directly:

```bash
feature-tree-skill --req "Build a time travel adventure app for children." --role "Regular User, Administrator"
```

`--role` accepts comma-separated role names directly. If both `--role` and `--actors` are provided, `--role` is used.

Generate from direct natural language plus actor txt:

```bash
feature-tree-skill --req "Build a local desktop music player." --actors examples/actors.txt
```

Generate from requirement file plus actor txt:

```bash
feature-tree-skill --input examples/raw_requirement.txt --actors examples/actors.txt --output-dir outputs
```

When `--actors` is provided, each L2 or L3 feature gets at most one role tag. The tag is either one role name from the actor txt file or `[Role: Common]` when the feature is shared, not role-specific, or cannot be clearly matched to one actor.

## Python API

```python
from feature_tree_skill import generate_feature_tree

features_json = generate_feature_tree(
    "Build a time travel adventure app for children."
)
print(features_json)
```

Natural language plus actors:

```python
from feature_tree_skill import generate_feature_tree

features_json = generate_feature_tree(
    requirement="I'd like to create a Time Travel Adventure software application that allows children to explore different time periods and learn about history through interactive storytelling and educational games.",
    actors="Regular User, Administrator",
)
print(features_json)
```

Pipeline usage:

```python
import asyncio
from feature_tree_skill import FeaturesPipeline

async def main():
    pipeline = FeaturesPipeline(
        nl_path="examples/raw_requirement.txt",
        output_dir="outputs",
    )
    result = await pipeline.run()
    print(result["features_path"])

asyncio.run(main())
```

## Publish To PyPI

Install build tools:

```bash
python -m pip install --upgrade build twine
```

Build the package:

```bash
python -m build
```

Upload to TestPyPI first:

```bash
python -m twine upload --repository testpypi dist/*
```

Upload to PyPI:

```bash
python -m twine upload dist/*
```

After the PyPI upload succeeds, users can install it with:

```bash
pip install feature-tree-skill
```
## 2026-5-15 Feature Tree with Role Tag
Each L2 and L3 feature should include a tag in the format `[Role: RoleName]`. When actor txt is provided, `RoleName` should be one role name from the comma-separated actor list; if a feature is common to all roles, shared by multiple roles, not role-specific, or cannot be clearly matched to one actor, it should be marked as `[Role: Common]`.

## Example Output
The following example shows a role-aware Feature Tree generated from user requirements for a time travel adventure software system.

```json
{
  "L1": "Time Travel Adventure Software Application",
  "L2.1": "Interactive Storytelling [Role: Common]",
  "L3.1.1": "Select Time Period [Role: Regular User]",
  "L3.1.2": "Engage with Historical Characters [Role: Regular User]",
  "L3.1.3": "Make Choices that Affect the Story [Role: Regular User]",
  "L2.2": "Educational Games [Role: Common]",
  "L3.2.1": "History Quiz Games [Role: Regular User]",
  "L3.2.2": "Puzzle Games Related to Historical Events [Role: Regular User]",
  "L3.2.3": "Role-Playing Scenarios [Role: Regular User]",
  "L2.3": "User Management [Role: Administrator]",
  "L3.3.1": "Create User Accounts [Role: Administrator]",
  "L3.3.2": "Manage User Permissions [Role: Administrator]",
  "L3.3.3": "Monitor User Activity [Role: Administrator]",
  "L2.4": "Content Management [Role: Administrator]",
  "L3.4.1": "Add New Time Periods [Role: Administrator]",
  "L3.4.2": "Update Educational Content [Role: Administrator]",
  "L3.4.3": "Delete Outdated Information [Role: Administrator]"
}
