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
            _resource_text("feature_tree_skill.resources.config", "config.json")
        )

    Config = namedtuple("Config", config_dict.keys())
    return Config(**config_dict)


class NL2FeaturesGeneration:
    def __init__(self, config_path: str | None = None, api_key: str | None = None) -> None:
        self.args = _load_config(config_path)
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self._openai = None
        self.client = None
        self._features_prompt_tpl = self._load_prompt(config_path, "NL2Features.txt")
        self._features_with_actors_prompt_tpl = self._load_prompt(
            config_path,
            "NLActors2Features.txt",
        )
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

        return _resource_text("feature_tree_skill.resources.prompts", filename)

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

    @staticmethod
    def _parse_json_text(text: str) -> Any | None:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None

    @staticmethod
    def _extract_requirement_and_actors(
        requirement: str,
        actors: str | list[str] | None = None,
    ) -> tuple[str, list[str] | None]:
        parsed_requirement = NL2FeaturesGeneration._parse_json_text(requirement)
        parsed_actors = None

        if actors is not None:
            if isinstance(actors, str):
                parsed_actors = (
                    NL2FeaturesGeneration._parse_json_text(actors)
                    or NL2FeaturesGeneration._parse_actor_names(actors)
                )
            else:
                parsed_actors = actors

        if isinstance(parsed_requirement, dict):
            if parsed_actors is None and isinstance(parsed_requirement.get("actors"), list):
                parsed_actors = parsed_requirement["actors"]

            parts = []
            project_name = parsed_requirement.get("project_name")
            project_description = parsed_requirement.get("project_description")
            raw_requirement = parsed_requirement.get("requirement")
            if project_name:
                parts.append(f"Project name: {project_name}")
            if project_description:
                parts.append(f"Project description: {project_description}")
            if raw_requirement:
                parts.append(f"Requirement: {raw_requirement}")
            if parts:
                requirement = "\n".join(parts)

        if isinstance(parsed_actors, dict):
            parsed_actors = parsed_actors.get("actors")

        if not isinstance(parsed_actors, list) or not parsed_actors:
            return requirement, None

        normalized_actors = NL2FeaturesGeneration._normalize_actor_names(parsed_actors)
        return requirement, normalized_actors or None

    @staticmethod
    def _parse_actor_names(text: str) -> list[str]:
        return [name.strip() for name in text.replace("\n", ",").split(",") if name.strip()]

    @staticmethod
    def _normalize_actor_names(actors: list[Any]) -> list[str]:
        normalized_actors = []
        for actor in actors:
            if isinstance(actor, str):
                actor_name = actor.strip()
            elif isinstance(actor, dict):
                actor_name = str(actor.get("actor_name", "")).strip()
            else:
                actor_name = ""

            if actor_name and actor_name not in normalized_actors:
                normalized_actors.append(actor_name)

        return normalized_actors

    @staticmethod
    def _actors_to_prompt_text(actors: list[str]) -> str:
        return ", ".join(actors)

    def _build_prompt(
        self,
        requirement: str,
        actors: str | list[str] | None = None,
    ) -> str:
        requirement_text, actor_list = self._extract_requirement_and_actors(requirement, actors)
        if not actor_list:
            return self._features_prompt_tpl.replace(
                "{Requirement Replacement Flag}",
                requirement_text,
            )

        return (
            self._features_with_actors_prompt_tpl.replace(
                "{Requirement Replacement Flag}",
                requirement_text,
            ).replace(
                "{Actors Replacement Flag}",
                self._actors_to_prompt_text(actor_list),
            )
        )

    def generate(
        self,
        nl: str,
        actors: str | list[str] | None = None,
    ) -> str:
        prompt = self._build_prompt(nl, actors)
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

            if any(k.startswith(("L2", "L3")) for k in features_dict):
                return json.dumps(features_dict, ensure_ascii=False, indent=2)

        return json.dumps(features_dict, ensure_ascii=False, indent=2)

    def FTgenerate(
        self,
        nl: str,
        actors: str | list[str] | None = None,
    ) -> str:
        return self.generate(nl, actors)


class FeaturesPipeline:
    """NL -> Feature Tree pipeline."""

    def __init__(
        self,
        nl_path: str = "examples/raw_requirement.txt",
        actors_path: str | None = None,
        actors_text: str | None = None,
        output_dir: str = "outputs",
        config_path: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self._nl_path = nl_path
        self._actors_path = actors_path
        self._actors_text = actors_text
        self._output_dir = output_dir
        self._generator = NL2FeaturesGeneration(config_path=config_path, api_key=api_key)

    async def _read_requirement(self) -> str:
        return await asyncio.to_thread(
            Path(self._nl_path).read_text,
            encoding="utf-8",
        )

    async def _read_actors(self) -> str | None:
        if self._actors_text is not None:
            return self._actors_text
        if not self._actors_path:
            return None
        return await asyncio.to_thread(
            Path(self._actors_path).read_text,
            encoding="utf-8",
        )

    async def _write_features(self, features_json: str) -> str:
        out_path = Path(self._output_dir) / "features.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(out_path.write_text, features_json, encoding="utf-8")
        return str(out_path)

    async def run(self) -> dict[str, str]:
        nl_text = await self._read_requirement()
        actors_text = await self._read_actors()
        loop = asyncio.get_running_loop()
        features_json = await loop.run_in_executor(
            None,
            self._generator.generate,
            nl_text,
            actors_text,
        )
        saved_path = await self._write_features(features_json)
        return {
            "nl": nl_text,
            "features_path": saved_path,
            "features_json": features_json,
        }


def generate_feature_tree(
    requirement: str,
    actors: str | list[str] | None = None,
    config_path: str | None = None,
    api_key: str | None = None,
) -> str:
    generator = NL2FeaturesGeneration(config_path=config_path, api_key=api_key)
    return generator.generate(requirement, actors=actors)


async def generate_features_stream(
    nl_path: str = "examples/raw_requirement.txt",
    actors_path: str | None = None,
    actors_text: str | None = None,
    output_dir: str = "outputs",
    config_path: str | None = None,
):
    pipeline = FeaturesPipeline(
        nl_path=nl_path,
        actors_path=actors_path,
        actors_text=actors_text,
        output_dir=output_dir,
        config_path=config_path,
    )
    result = await pipeline.run()
    yield {
        "type": "system",
        "content": f"Features generated and written to {result['features_path']}",
    }
    yield {"type": "result", "content": result["features_json"]}
