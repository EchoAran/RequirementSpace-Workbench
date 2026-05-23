# Scenario Generation Skill

Generate a user story, system requirement, and Gherkin scenarios from natural language requirement context plus one feature description.

## Install

From PyPI, after this package is published:

```bash
pip install scenario-generation-skill
```

From GitHub:

```bash
pip install git+https://github.com/HarrisClover/scenario-generation-skill.git
```

If pip reports that it cannot find `setuptools>=61` or `wheel`, make sure pip is allowed to use package indexes. In PowerShell:

```powershell
Remove-Item Env:PIP_NO_INDEX -ErrorAction SilentlyContinue
python -m pip install --upgrade pip setuptools wheel
python -m pip install --user git+https://github.com/HarrisClover/scenario-generation-skill.git
```

If you are installing in an offline environment where `setuptools`, `wheel`, and `openai` are already installed, use:

```bash
pip install --no-build-isolation git+https://github.com/HarrisClover/scenario-generation-skill.git
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

PowerShell:

```powershell
$env:OPENAI_API_KEY = "your_api_key"
```

macOS/Linux:

```bash
export OPENAI_API_KEY=your_api_key
```

## CLI

> [!IMPORTANT]
> When providing a feature as input, the role tag must be appended directly after the feature name. ``Feature Name [Role: tag]``
>
> Example:
>
> ```text
> Select Time Periods from Predefined Historical Eras [Role: Regular User]
> ```
>
> If the role tag is not included in the input feature, it will not be passed to the generated Gherkin scenarios.

Generate from direct text:

```bash
scenario-generation-skill --text "Build a time travel adventure app for children." --feature "Select Time Periods from Predefined Historical Eras [Role: Regular User]"
```

Generate from a file:

```bash
scenario-generation-skill --input examples/raw_requirement.txt --feature "Select Time Periods from Predefined Historical Eras [Role: Regular User]"
```

The CLI prints formatted results to stdout and does not write output files.

You can also use the short command:

```bash
sg-skill --text "Build an educational game for children." --feature "Multiple Choice and True/False Quizzes on Historical Facts [Role: Regular User]"
```

## Python API

```python
from scenario_generation_skill import generate_scenarios

result_json = generate_scenarios(
    requirement="Build a time travel adventure app for children.",
    feature="Select Time Periods from Predefined Historical Eras [Role: Regular User]",
)
print(result_json)
```

Structured usage:

```python
from scenario_generation_skill import ScenarioGeneration

generator = ScenarioGeneration()
result = generator.generate(
    requirement="Build a time travel adventure app for children.",
    feature="Select Time Periods from Predefined Historical Eras [Role: Regular User]",
)
print(result["gherkin"])
```
## Example Output
```json
{
  "story": {
    "Select Time Periods from Predefined Historical Eras [Role: Administrator]": "If the administrator selects a time period from the predefined list, then the system should display the corresponding historical events and characters associated with that era. If the selected time period is the Ancient Egypt era, then the system should enable interactive storytelling features related to pharaohs and pyramids. If the selected time period is the Renaissance, then the system should provide educational games focused on famous artists and inventions. If the administrator attempts to select a time period that is not in the predefined list, then the system should display an error message indicating that the selection is invalid. If the administrator successfully selects a time period, then the system should log the selection for future reference."
  },
  "system": {
    "Select Time Periods from Predefined Historical Eras [Role: Administrator]": "When the administrator selects a time period from the predefined list of historical eras, the system will check if the selected time period is valid. If the selection corresponds to the Ancient Egypt era, the system will enable interactive storytelling features that include content related to pharaohs and pyramids. If the selected time period is the Renaissance, the system will provide educational games that focus on famous artists and inventions. If the administrator selects a time period that is not included in the predefined list, the system will display an error message indicating that the selection is invalid. Upon successful selection of a valid time period, the system will log the selection for future reference, ensuring that the administrator's choices are recorded."
  },
  "gherkin": {
    "Select Time Periods from Predefined Historical Eras [Role: Administrator]": {
      "Feature": "Select Time Periods from Predefined Historical Eras [Role: Administrator]",
      "Narrative": {
        "As": "an administrator",
        "I want": "to select a valid time period from predefined historical eras",
        "So that": "the system can provide appropriate educational content and log my selection"
      },
      "Background": {
        "Given": "the administrator has access to a predefined list of historical eras",
        "And": "the system is operational"
      },
      "Scenarios": [
        {
          "Scenario": "Valid selection of Ancient Egypt",
          "Given": "the administrator selects the Ancient Egypt era",
          "When": "the selection is processed",
          "Then": "the interactive storytelling features are enabled",
          "And": "the selection is logged for future reference"
        },
        {
          "Scenario": "Valid selection of Renaissance",
          "Given": "the administrator selects the Renaissance era",
          "When": "the selection is processed",
          "Then": "educational games related to famous artists and inventions are provided",
          "And": "the selection is logged for future reference"
        },
        {
          "Scenario": "Invalid selection of an unlisted era",
          "Given": "the administrator selects a time period that is not in the predefined list",
          "When": "the selection is processed",
          "Then": "an error message indicating that the selection is invalid is displayed"
        }
      ]
    }
  }
}
```
