# Gherkin2Code Skill

Generate a web prototype from two inputs:

- A user requirement text file
- Gherkin acceptance criteria in JSON format

The skill returns code in this JSON shape and writes it into separate files:

```json
{
  "HTML": "...",
  "Javascript": "...",
  "CSS": "..."
}
```

Generated files are written as:

- `output/index.html`
- `output/script.js`
- `output/style.css`

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
gherkin2code-skill --requirement-input examples/user_requirement.txt --acceptance-input examples/acceptance_criteria.json --output-dir output
```

Print only the generated JSON:

```bash
g2c-skill --json-only
```

Generate from direct text:

```bash
gherkin2code-skill --requirement-text "Build a learning app." --acceptance-text "{\"Features\":[]}"
```

## Python API

```python
from gherkin2code_skill import generate_code

result_json = generate_code(
    user_requirement="Build a learning app.",
    acceptance_criteria='{"Features":[]}',
)
print(result_json)
```
