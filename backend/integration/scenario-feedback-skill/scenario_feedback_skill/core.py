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
            _resource_text("scenario_feedback_skill.resources.config", "config.json")
        )

    Config = namedtuple("Config", config_dict.keys())
    return Config(**config_dict)


def _json_or_text(value: str) -> str:
    try:
        return json.dumps(json.loads(value), ensure_ascii=False, indent=2)
    except json.JSONDecodeError:
        return value


def _infer_feature(gherkin_content: str, fallback: str = "Selected Feature") -> str:
    try:
        parsed = json.loads(gherkin_content)
    except json.JSONDecodeError:
        return fallback

    if isinstance(parsed, dict):
        feature = parsed.get("Feature")
        if isinstance(feature, str) and feature.strip():
            return feature.strip()

        if len(parsed) == 1:
            only_key = next(iter(parsed))
            if isinstance(only_key, str) and only_key.strip():
                return only_key.strip()

    return fallback


class ScenarioFeedback:
    """User feedback + existing Gherkin -> revised Gherkin JSON."""

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
        prompt_names = ["feedback2Gherkin.txt"]
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
            name: _resource_text("scenario_feedback_skill.resources.prompts", name)
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

    def _do_step(self, replacements: dict[str, str]) -> dict[str, Any]:
        prompt = self._prompts["feedback2Gherkin.txt"]
        for flag, val in replacements.items():
            prompt = prompt.replace(flag, val)

        response = self._ask_chatgpt(prompt)
        content = self._message_content(response)
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError(f"OpenAI response was not valid JSON: {content}") from exc

    def revise(
        self,
        user_feedback: str,
        gherkin_content: str,
        feature: str | None = None,
    ) -> dict[str, Any]:
        selected_feature = feature or _infer_feature(gherkin_content)
        return self._do_step(
            {
                "{User Feedback Replacement Flag}": user_feedback,
                "{Gherkin Content Replacement Flag}": _json_or_text(gherkin_content),
                "{Selected Feature Replacement Flag}": selected_feature,
            }
        )

    def revise_json(
        self,
        user_feedback: str,
        gherkin_content: str,
        feature: str | None = None,
    ) -> str:
        return json.dumps(
            self.revise(
                user_feedback=user_feedback,
                gherkin_content=gherkin_content,
                feature=feature,
            ),
            ensure_ascii=False,
            indent=2,
        )

    def SFgenerate(
        self,
        user_feedback: str,
        gherkin_content: str,
        feature: str | None = None,
    ) -> str:
        return self.revise_json(
            user_feedback=user_feedback,
            gherkin_content=gherkin_content,
            feature=feature,
        )


class ScenarioFeedbackPipeline:
    """File-based feedback pipeline that returns revised Gherkin JSON."""

    def __init__(
        self,
        feedback_path: str = "examples/user_feedback.txt",
        gherkin_path: str = "examples/gherkin.json",
        feature: str | None = None,
        config_path: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self._feedback_path = feedback_path
        self._gherkin_path = gherkin_path
        self._feature = feature
        self._generator = ScenarioFeedback(config_path=config_path, api_key=api_key)

    async def _read_text(self, path: str) -> str:
        return await asyncio.to_thread(Path(path).read_text, encoding="utf-8")

    async def run(self) -> dict[str, Any]:
        feedback, gherkin = await asyncio.gather(
            self._read_text(self._feedback_path),
            self._read_text(self._gherkin_path),
        )
        loop = asyncio.get_running_loop()
        revised = await loop.run_in_executor(
            None,
            self._generator.revise,
            feedback,
            gherkin,
            self._feature,
        )
        return {
            "user_feedback": feedback,
            "gherkin_content": _json_or_text(gherkin),
            "revised_gherkin": revised,
        }


def revise_gherkin(
    user_feedback: str,
    gherkin_content: str,
    feature: str | None = None,
    config_path: str | None = None,
    api_key: str | None = None,
) -> str:
    generator = ScenarioFeedback(config_path=config_path, api_key=api_key)
    return generator.revise_json(
        user_feedback=user_feedback,
        gherkin_content=gherkin_content,
        feature=feature,
    )


async def revise_gherkin_stream(
    feedback_path: str = "examples/user_feedback.txt",
    gherkin_path: str = "examples/gherkin.json",
    feature: str | None = None,
    config_path: str | None = None,
):
    pipeline = ScenarioFeedbackPipeline(
        feedback_path=feedback_path,
        gherkin_path=gherkin_path,
        feature=feature,
        config_path=config_path,
    )
    result = await pipeline.run()
    yield {"type": "revised_gherkin", "content": result["revised_gherkin"]}
    yield {
        "type": "result",
        "content": json.dumps(result["revised_gherkin"], ensure_ascii=False, indent=2),
    }
