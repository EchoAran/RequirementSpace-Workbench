# Feature Tree Feedback Skill

Revise an existing feature tree JSON document according to user feedback.

The skill accepts two inputs:

- A feature tree, usually JSON in the format `{"L1": "...", "L2.1": "...", "L3.1.1": "..."}`
- A user feedback txt that describes additions, deletions, renames, moves, merges, splits, or role-tag changes

The output is the modified feature tree JSON.

## Install

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

PowerShell:

```powershell
$env:OPENAI_API_KEY = "your_api_key"
```

macOS/Linux:

```bash
export OPENAI_API_KEY=your_api_key
```

## CLI

Generate from files:

```bash
feature-tree-feedback-skill --input examples/feature_tree.json --feedback-input examples/feedback.txt --output-dir outputs
```

The file mode writes `features.json` into the output directory.

Pass both inputs directly and print JSON to stdout:

```bash
feature-tree-feedback-skill --feature-tree '{"L1":"Music App","L2.1":"Playback [Role: Common]"}' --feedback "Add playlist management."
```

## Python API

```python
from feature_tree_feedback_skill import revise_feature_tree

updated_json = revise_feature_tree(
    feature_tree='{"L1":"Music App","L2.1":"Playback [Role: Common]"}',
    feedback="Add playlist management with create, edit, and delete playlist features.",
)
print(updated_json)
```

Pipeline usage:

```python
import asyncio
from feature_tree_feedback_skill import FeatureTreeFeedbackPipeline

async def main():
    pipeline = FeatureTreeFeedbackPipeline(
        feature_tree_path="examples/feature_tree.json",
        feedback_path="examples/feedback.txt",
        output_dir="outputs",
    )
    result = await pipeline.run()
    print(result["features_path"])

asyncio.run(main())
```