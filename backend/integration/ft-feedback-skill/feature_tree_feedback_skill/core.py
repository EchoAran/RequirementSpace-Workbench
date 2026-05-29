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
            _resource_text("feature_tree_feedback_skill.resources.config", "config.json")
        )

    Config = namedtuple("Config", config_dict.keys())
    return Config(**config_dict)


class FeatureTreeFeedbackGeneration:
    def __init__(self, config_path: str | None = None, api_key: str | None = None) -> None:
        self.args = _load_config(config_path)
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self._openai = None
        self.client = None
        self._prompt_tpl = self._load_prompt(config_path, "FeatureTreeFeedback2Features.txt")
        self._set_proxy()

    def _set_proxy(self) -> None:
        proxy = getattr(self.args, "proxy", None)
        if not proxy:
            return
        os.environ.setdefault("http_proxy", proxy)
        os.environ.setdefault("https_proxy", proxy)

    def _load_prompt(self, config_path: str | None, filename: str) -> str:
        if config_path and getattr(self.args, "prompt_path", None):
            prompt_file = Path(self.args.prompt_path) / filename
            if not prompt_file.is_absolute():
                config_dir = Path(config_path).resolve().parent
                candidates = [
                    config_dir / prompt_file,
                    Path.cwd() / prompt_file,
                    config_dir.parent / prompt_file,
                ]
                prompt_file = next((path for path in candidates if path.exists()), candidates[0])
            if prompt_file.exists():
                return prompt_file.read_text(encoding="utf-8")

        return _resource_text("feature_tree_feedback_skill.resources.prompts", filename)

    def _ask_chatgpt(self, messages: list[dict[str, str]]):
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
            "messages": messages,
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

    @staticmethod
    def _format_feature_tree(feature_tree: str | dict[str, Any]) -> str:
        if isinstance(feature_tree, dict):
            return json.dumps(feature_tree, ensure_ascii=False, indent=2)

        try:
            parsed = json.loads(feature_tree)
        except json.JSONDecodeError:
            return feature_tree

        if isinstance(parsed, dict):
            return json.dumps(parsed, ensure_ascii=False, indent=2)
        return feature_tree

    def _build_prompt(self, feature_tree: str | dict[str, Any], feedback: str) -> str:
        return (
            self._prompt_tpl.replace(
                "{Feature Tree Replacement Flag}",
                self._format_feature_tree(feature_tree),
            ).replace(
                "{Feedback Replacement Flag}",
                feedback,
            )
        )

    def generate(self, feature_tree: str | dict[str, Any], feedback: str) -> str:
        prompt = self._build_prompt(feature_tree, feedback)
        max_iterations = getattr(self.args, "max_iterations", 5)
        features_dict: dict[str, Any] = {}

        for _ in range(max_iterations):
            messages = [{"role": "user", "content": prompt}]
            response = self._ask_chatgpt(messages)
            content = self._message_content(response)

            try:
                features_dict = json.loads(content)
            except json.JSONDecodeError:
                return content

            if "L1" in features_dict and any(k.startswith(("L2", "L3")) for k in features_dict):
                return json.dumps(features_dict, ensure_ascii=False, indent=2)

        return json.dumps(features_dict, ensure_ascii=False, indent=2)

    def FTgenerate(self, feature_tree: str | dict[str, Any], feedback: str) -> str:
        return self.generate(feature_tree, feedback)


class FeatureTreeFeedbackPipeline:
    """Feature tree + user feedback -> revised feature tree pipeline."""

    def __init__(
        self,
        feature_tree_path: str = "examples/feature_tree.json",
        feedback_path: str = "examples/feedback.txt",
        output_dir: str = "outputs",
        config_path: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self._feature_tree_path = feature_tree_path
        self._feedback_path = feedback_path
        self._output_dir = output_dir
        self._generator = FeatureTreeFeedbackGeneration(
            config_path=config_path,
            api_key=api_key,
        )

    async def _read_feature_tree(self) -> str:
        return await asyncio.to_thread(
            Path(self._feature_tree_path).read_text,
            encoding="utf-8",
        )

    async def _read_feedback(self) -> str:
        return await asyncio.to_thread(
            Path(self._feedback_path).read_text,
            encoding="utf-8",
        )

    async def _write_features(self, features_json: str) -> str:
        out_path = Path(self._output_dir) / "features.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(out_path.write_text, features_json, encoding="utf-8")
        return str(out_path)

    async def run(self) -> dict[str, str]:
        feature_tree_text = await self._read_feature_tree()
        feedback_text = await self._read_feedback()
        loop = asyncio.get_running_loop()
        features_json = await loop.run_in_executor(
            None,
            self._generator.generate,
            feature_tree_text,
            feedback_text,
        )
        saved_path = await self._write_features(features_json)
        return {
            "feature_tree": feature_tree_text,
            "feedback": feedback_text,
            "features_path": saved_path,
            "features_json": features_json,
        }


def revise_feature_tree(
    feature_tree: str | dict[str, Any],
    feedback: str,
    config_path: str | None = None,
    api_key: str | None = None,
) -> str:
    generator = FeatureTreeFeedbackGeneration(config_path=config_path, api_key=api_key)
    return generator.generate(feature_tree, feedback)


async def revise_feature_tree_stream(
    feature_tree_path: str = "examples/feature_tree.json",
    feedback_path: str = "examples/feedback.txt",
    output_dir: str = "outputs",
    config_path: str | None = None,
):
    pipeline = FeatureTreeFeedbackPipeline(
        feature_tree_path=feature_tree_path,
        feedback_path=feedback_path,
        output_dir=output_dir,
        config_path=config_path,
    )
    result = await pipeline.run()
    yield {
        "type": "system",
        "content": f"Feature tree revised and written to {result['features_path']}",
    }
    yield {"type": "result", "content": result["features_json"]}
