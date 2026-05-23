# Kano Skill

The inputs required for Kano-Skill are:

- an initial requirement
- a feature tree JSON object

The participant count is fixed at `5`. The participant distribution is fixed inside the skill. You can modify the scale and distribution in core.py.

```json
{
  "age": {"0-14": 0.1601, "15-64": 0.6933, "65+": 0.1467},
  "edu": {"Tertiary": 0.1612, "Secondary": 0.1565, "<=Primary": 0.6823},
  "gender": {"Female": 0.4906, "Male": 0.5094}
}
```

The final Kano label follows:

- `O` = `Performance`
- `A` = `Attractive`
- `M` = `Must-be`
- `I` = `Indifference`

## Install Locally

From this repository:

```bash
pip install .
```

For editable development:

```bash
pip install -e .
```

## Install From GitHub
```bash
pip install git+https://github.com/HarrisClover/kano-skill.git
```

## Configure

Set your OpenAI API key before running.

PowerShell:

```powershell
$env:OPENAI_API_KEY = "your_api_key"
```

macOS/Linux:

```bash
export OPENAI_API_KEY="your_api_key"
```

## CLI

Run with bundled examples:

```bash
kano-skill
```

Equivalent source checkout command:

```bash
python main_kano.py
```

Print only the JSON array:

```bash
kano-skill --json-only
```

Use custom input files:

```bash
kano-skill ^
  --requirement-input path\to\requirement.txt ^
  --feature-tree-input path\to\feature_tree.json
```

Use direct text input:

```bash
kano-skill ^
  --requirement-text "Time Travel Adventure Software" ^
  --feature-tree-text "{\"L1\":\"Time Travel Adventure Software\",\"L3.1.1\":\"Choose Time Period\",\"L3.1.2\":\"Engage with Historical Characters\",\"L3.1.3\":\"Make Decisions that Affect the Story\"}"
```

Write output to a custom directory under `kano-skill/`:

```bash
kano-skill --output-dir output
```

## Python API

```python
from kano_skill import analyze_kano_json

result = analyze_kano_json(
    requirement_text="Time Travel Adventure Software",
    feature_tree={
        "L1": "Time Travel Adventure Software",
        "L3.1.1": "Choose Time Period",
        "L3.1.2": "Engage with Historical Characters",
        "L3.1.3": "Make Decisions that Affect the Story"
    }
)
print(result)
```

## Example Input

`examples/requirement.txt`

```text
Time Travel Adventure Software
```

`examples/feature_tree.json`

```json
{
  "L1": "Time Travel Adventure Software",
  "L2.1": "Interactive Storytelling [Role: Common]",
  "L3.1.1": "Choose Time Period [Role: Regular User]",
  "L3.1.2": "Engage with Historical Characters [Role: Regular User]",
  "L3.1.3": "Make Decisions that Affect the Story [Role: Regular User]"
}
```

## Example Output

The output is shown from `output/feature_satisfaction_reasons.json`.

Satisfaction Evaluation scale for every feature.

A: I like it that way.
B: It must be that way.
C: I am neutral.
D: I can live with it that way.
E: I dislike it that way.

```json
[
  {
    "Feature": "Choose Time Period [Role: Regular User]",
    "Kano_Category": "O",
    "Kano_Category_Name": "Performance",
    "satisfaction_distribution": {
      "functional": {
        "A": {"count": 3, "ratio": 0.6},
        "B": {"count": 2, "ratio": 0.4},
        "C": {"count": 0, "ratio": 0.0},
        "D": {"count": 0, "ratio": 0.0},
        "E": {"count": 0, "ratio": 0.0}
      },
      "dysfunctional": {
        "A": {"count": 0, "ratio": 0.0},
        "B": {"count": 0, "ratio": 0.0},
        "C": {"count": 0, "ratio": 0.0},
        "D": {"count": 0, "ratio": 0.0},
        "E": {"count": 5, "ratio": 1.0}
      }
    },
    "reason_summary": {
      "functional_viewpoint": "The majority of people believe that choosing different time periods to explore is essential for an immersive and enjoyable experience.",
      "dysfunctional_viewpoint": "The majority of people believe that having the ability to choose a time period is essential for an enjoyable experience, as it adds excitement and prevents boredom."
    },
    "explanation": "Users valued its presence because the feature supports immersive exploration. When absent, users felt the experience would lose excitement and variety."
  }
]
```
