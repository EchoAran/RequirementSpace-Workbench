from __future__ import annotations

import asyncio
import json
import os
from collections import namedtuple
from importlib import resources
from pathlib import Path
from typing import Any


def _resource_text(package_path: str, filename: str) -> str:
    return resources.files(package_path).joinpath(filename).read_text(encoding="utf-8")


def _load_config(config_path: str | None = None) -> Any:
    if config_path:
        with open(config_path, "r", encoding="utf-8") as f:
            config_dict = json.load(f)
    else:
        config_dict = json.loads(
            _resource_text("gherkin2code_skill.resources.config", "config.json")
        )

    Config = namedtuple("Config", config_dict.keys())
    return Config(**config_dict)


def _json_or_text(value: str) -> str:
    try:
        return json.dumps(json.loads(value), ensure_ascii=False, indent=2)
    except json.JSONDecodeError:
        return value


def write_code_files(code: dict[str, Any], output_dir: str | Path = "output") -> dict[str, str]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    files = {
        "index.html": str(code.get("HTML", "")),
        "script.js": str(code.get("Javascript", "")),
        "style.css": str(code.get("CSS", "")),
    }
    for name, content in files.items():
        (out / name).write_text(content, encoding="utf-8")
    return {name: str((out / name).resolve()) for name in files}


class Gherkin2Code:
    """User requirement + Gherkin acceptance criteria -> HTML/CSS/JS JSON."""

    def __init__(self, config_path: str | None = None, api_key: str | None = None) -> None:
        self.args = _load_config(config_path)
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self._openai = None
        self.client = None
        self._prompts = self._load_prompts(config_path)
        self._set_proxy()

    def _set_proxy(self) -> None:
        proxy = getattr(self.args, "proxy", None)
        if not proxy:
            return
        os.environ.setdefault("http_proxy", proxy)
        os.environ.setdefault("https_proxy", proxy)

    def _load_prompts(self, config_path: str | None) -> dict[str, str]:
        prompt_names = ["gherkin2code.txt"]
        prompt_path = getattr(self.args, "prompt_path", None)

        if config_path and prompt_path:
            prompt_dir = Path(prompt_path)
            if not prompt_dir.is_absolute():
                config_dir = Path(config_path).resolve().parent
                candidates = [
                    config_dir / prompt_dir,
                    Path.cwd() / prompt_dir,
                    config_dir.parent / prompt_dir,
                ]
                prompt_dir = next((path for path in candidates if path.exists()), candidates[0])
            return {
                name: (prompt_dir / name).read_text(encoding="utf-8")
                for name in prompt_names
            }

        return {
            name: _resource_text("gherkin2code_skill.resources.prompts", name)
            for name in prompt_names
        }

    def _ask_chatgpt(self, prompt: str):
        if self._openai is None:
            import openai

            self._openai = openai
            if hasattr(openai, "OpenAI"):
                self.client = openai.OpenAI(api_key=self._api_key)
            else:
                openai.api_key = self._api_key

        request = {
            "model": self.args.model,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
            "temperature": getattr(self.args, "temperature", 0.2),
        }

        if self.client is not None:
            return self.client.chat.completions.create(**request)
        return self._openai.ChatCompletion.create(**request)

    @staticmethod
    def _message_content(response: Any) -> str:
        try:
            return response.choices[0].message.content or ""
        except AttributeError:
            return response["choices"][0]["message"]["content"] or ""

    def generate(self, user_requirement: str, acceptance_criteria: str) -> dict[str, str]:
        prompt = self._prompts["gherkin2code.txt"]
        prompt = prompt.replace("{User Requirement Replacement Flag}", user_requirement)
        prompt = prompt.replace(
            "{Acceptance Criteria Replacement Flag}",
            _json_or_text(acceptance_criteria),
        )

        response = self._ask_chatgpt(prompt)
        content = self._message_content(response)
        try:
            code = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError(f"OpenAI response was not valid JSON: {content}") from exc

        return {
            "HTML": str(code.get("HTML", "")),
            "Javascript": str(code.get("Javascript", "")),
            "CSS": str(code.get("CSS", "")),
        }

    def generate_json(self, user_requirement: str, acceptance_criteria: str) -> str:
        return json.dumps(
            self.generate(user_requirement, acceptance_criteria),
            ensure_ascii=False,
            indent=2,
        )

    def generate_files(
        self,
        user_requirement: str,
        acceptance_criteria: str,
        output_dir: str | Path = "output",
    ) -> dict[str, str]:
        return write_code_files(
            self.generate(user_requirement, acceptance_criteria),
            output_dir=output_dir,
        )


class Gherkin2CodePipeline:
    """File-based pipeline that generates and writes web application files."""

    def __init__(
        self,
        requirement_path: str = "examples/user_requirement.txt",
        acceptance_path: str = "examples/acceptance_criteria.json",
        output_dir: str = "output",
        config_path: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self._requirement_path = requirement_path
        self._acceptance_path = acceptance_path
        self._output_dir = output_dir
        self._generator = Gherkin2Code(config_path=config_path, api_key=api_key)

    async def _read_text(self, path: str) -> str:
        return await asyncio.to_thread(Path(path).read_text, encoding="utf-8")

    async def run(self) -> dict[str, Any]:
        requirement, acceptance = await asyncio.gather(
            self._read_text(self._requirement_path),
            self._read_text(self._acceptance_path),
        )
        code = await asyncio.to_thread(
            self._generator.generate,
            requirement,
            acceptance,
        )
        written_files = write_code_files(code, output_dir=self._output_dir)
        return {
            "user_requirement": requirement,
            "acceptance_criteria": _json_or_text(acceptance),
            "codes": code,
            "written_files": written_files,
        }


def generate_code(
    user_requirement: str,
    acceptance_criteria: str,
    config_path: str | None = None,
    api_key: str | None = None,
) -> str:
    generator = Gherkin2Code(config_path=config_path, api_key=api_key)
    return generator.generate_json(
        user_requirement=user_requirement,
        acceptance_criteria=acceptance_criteria,
    )
