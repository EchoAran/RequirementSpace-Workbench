# Scenario Feedback Skill

Revise existing Gherkin scenarios from user feedback. The skill accepts user feedback and modified Gherkin content, then returns the revised Gherkin as a JSON object.

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

Revise from files:

```bash
scenario-feedback-skill --feedback-input examples/user_feedback.txt --gherkin-input examples/gherkin.json
```

Revise from direct text:

```bash
scenario-feedback-skill --feedback-text "Add invalid input coverage." --gherkin-text "{\"Feature\":\"Submit Customer Feedback\",\"Scenarios\":[]}"
```

Print only the final JSON:

```bash
sf-skill --feedback-input examples/user_feedback.txt --gherkin-input examples/gherkin.json --json-only
```

Use `--feature` when the selected feature should be different from the `Feature` value in the source Gherkin.

## Python API

```python
from scenario_feedback_skill import revise_gherkin

result_json = revise_gherkin(
    user_feedback="Add a negative scenario for invalid input.",
    gherkin_content='{"Feature": "Submit Customer Feedback", "Scenarios": []}',
)
print(result_json)
```

Structured usage:

```python
from scenario_feedback_skill import ScenarioFeedback

generator = ScenarioFeedback()
result = generator.revise(
    user_feedback="Add a negative scenario for invalid input.",
    gherkin_content='{"Feature": "Submit Customer Feedback", "Scenarios": []}',
)
print(result)
```
