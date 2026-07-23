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
            _resource_text("scenario_generation_skill.resources.config", "config.json")
        )

    Config = namedtuple("Config", config_dict.keys())
    return Config(**config_dict)


class ScenarioGeneration:
    """NL + one feature -> user story -> system requirement -> Gherkin."""

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
        prompt_names = ["Features2Story.txt", "Story2Sys.txt", "sys2Gherkin.txt"]
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
            name: _resource_text("scenario_generation_skill.resources.prompts", name)
            for name in prompt_names
        }

    def _ask_chatgpt(self, prompt: str):
        if self._openai is None:
            import openai

            self._openai = openai
            if hasattr(openai, "OpenAI"):
                try:
                    self.client = openai.OpenAI(api_key=self._api_key)
                except TypeError as exc:
                    if "proxies" in str(exc):
                        raise RuntimeError(
                            "Incompatible OpenAI/httpx versions detected. "
                            "Upgrade the OpenAI SDK with: "
                            "python -m pip install --upgrade 'openai>=1.56.0'"
                        ) from exc
                    raise
            else:
                openai.api_key = self._api_key

        request = {
            "model": self.args.model,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
            "temperature": getattr(self.args, "temperature", 0.5),
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

    def _do_step(self, prompt_name: str, replacements: dict[str, str]) -> dict[str, Any]:
        prompt = self._prompts[prompt_name]
        for flag, val in replacements.items():
            prompt = prompt.replace(flag, val)

        response = self._ask_chatgpt(prompt)
        content = self._message_content(response)
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError(f"OpenAI response was not valid JSON: {content}") from exc

    def generate(self, requirement: str, feature: str) -> dict[str, Any]:
        story = self._do_step(
            "Features2Story.txt",
            {
                "{Features Replacement Flag}": feature,
                "{Requirement Replacement Flag}": requirement,
            },
        )

        system: dict[str, Any] = {}
        for story_key, story_val in story.items():
            system.update(
                self._do_step(
                    "Story2Sys.txt",
                    {
                        "{Story Key Replacement Flag}": story_key,
                        "{User Story Replacement Flag}": str(story_val),
                    },
                )
            )

        gherkin: dict[str, Any] = {}
        for sys_key, sys_val in system.items():
            gherkin.update(
                self._do_step(
                    "sys2Gherkin.txt",
                    {
                        "{Story Key Replacement Flag}": sys_key,
                        "{System Requirement Replacement Flag}": str(sys_val),
                    },
                )
            )

        return {"story": story, "system": system, "gherkin": gherkin}

    def generate_json(self, requirement: str, feature: str) -> str:
        return json.dumps(
            self.generate(requirement=requirement, feature=feature),
            ensure_ascii=False,
            indent=2,
        )

    def SGgenerate(self, requirement: str, feature: str) -> str:
        return self.generate_json(requirement=requirement, feature=feature)


class ScenarioPipeline:
    """File-based NL input pipeline that prints or returns generated scenarios."""

    def __init__(
        self,
        nl_path: str = "examples/raw_requirement.txt",
        feature: str = "Select Time Periods from Predefined Historical Eras",
        config_path: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self._nl_path = nl_path
        self._feature = feature
        self._generator = ScenarioGeneration(config_path=config_path, api_key=api_key)

    async def _read_requirement(self) -> str:
        return await asyncio.to_thread(
            Path(self._nl_path).read_text,
            encoding="utf-8",
        )

    async def run(self) -> dict[str, Any]:
        nl_text = await self._read_requirement()
        result = await asyncio.to_thread(
            self._generator.generate,
            nl_text,
            self._feature,
        )
        return {
            "nl": nl_text,
            "feature": self._feature,
            **result,
        }


def generate_scenarios(
    requirement: str,
    feature: str,
    config_path: str | None = None,
    api_key: str | None = None,
) -> str:
    generator = ScenarioGeneration(config_path=config_path, api_key=api_key)
    return generator.generate_json(requirement=requirement, feature=feature)


async def generate_scenarios_stream(
    nl_path: str = "examples/raw_requirement.txt",
    feature: str = "Select Time Periods from Predefined Historical Eras",
    config_path: str | None = None,
):
    pipeline = ScenarioPipeline(
        nl_path=nl_path,
        feature=feature,
        config_path=config_path,
    )
    result = await pipeline.run()
    yield {"type": "story", "content": result["story"]}
    yield {"type": "system_req", "content": result["system"]}
    yield {"type": "gherkin", "content": result["gherkin"]}
    yield {
        "type": "result",
        "content": json.dumps(
            {
                "story": result["story"],
                "system": result["system"],
                "gherkin": result["gherkin"],
            },
            ensure_ascii=False,
            indent=2,
        ),
    }
