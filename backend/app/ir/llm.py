from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LLMConfig:
    base_url: str
    api_key: str
    model: str
    temperature: float


def load_llm_config() -> LLMConfig:
    base_url = (os.getenv("RS_LLM_BASE_URL") or "").strip().rstrip("/")
    api_key = (os.getenv("RS_LLM_API_KEY") or "").strip()
    model = (os.getenv("RS_LLM_MODEL") or "").strip()
    temperature_raw = (os.getenv("RS_LLM_TEMPERATURE") or "0.2").strip()
    try:
        temperature = float(temperature_raw)
    except Exception:
        temperature = 0.2

    if not base_url:
        raise RuntimeError("缺少 RS_LLM_BASE_URL（请在 .env 中配置）")
    if not api_key:
        raise RuntimeError("缺少 RS_LLM_API_KEY（请在 .env 中配置）")
    if not model:
        raise RuntimeError("缺少 RS_LLM_MODEL（请在 .env 中配置）")
    return LLMConfig(base_url=base_url, api_key=api_key, model=model, temperature=temperature)


def _extract_first_json_object(text: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except Exception:
        pass

    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        raise ValueError(f"未找到 JSON 对象，模型输出为: {text[:200]}")
    try:
        return json.loads(match.group(0))
    except Exception as e:
        raise ValueError(f"找到的 JSON 无法解析: {e}，片段: {match.group(0)[:200]}")


class LLMProvider:
    def __init__(self, config: LLMConfig):
        self.config = config

    def complete_json(
        self,
        *,
        system: str,
        user: str,
        temperature: float | None = None,
        timeout_s: int = 35,
    ) -> dict[str, Any]:
        url = f"{self.config.base_url}/v1/chat/completions"
        payload = {
            "model": self.config.model,
            "temperature": self.config.temperature if temperature is None else temperature,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }

        req = urllib.request.Request(
            url,
            method="POST",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.config.api_key}",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                raw_bytes = resp.read()
                
                # Handle gzip compressed response
                if resp.info().get("Content-Encoding") == "gzip":
                    import gzip
                    raw_bytes = gzip.decompress(raw_bytes)
                    
                raw = raw_bytes.decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            raw_bytes = e.read() if hasattr(e, "read") else b""
            if e.headers.get("Content-Encoding") == "gzip" and raw_bytes:
                import gzip
                try:
                    raw_bytes = gzip.decompress(raw_bytes)
                except Exception:
                    pass
            raw = raw_bytes.decode("utf-8", errors="replace") if raw_bytes else str(e)
            raise RuntimeError(f"LLM 请求失败: HTTP {getattr(e, 'code', '?')} {raw}") from e
        except Exception as e:
            raise RuntimeError(f"LLM 请求失败: {e}") from e

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            # If the response is not valid JSON, it might be an HTML error page from a proxy
            # or an empty string. We should include the raw response in the error message
            # for easier debugging.
            snippet = raw[:200] + ("..." if len(raw) > 200 else "")
            raise RuntimeError(f"LLM 响应不是合法的 JSON (HTTP {getattr(resp, 'status', 200)}): {snippet} (原始错误: {e})") from e

        content = (
            (((data.get("choices") or [{}])[0]).get("message") or {}).get("content")
            or ""
        )
        if not content.strip():
            raise RuntimeError("LLM 返回为空")
        return _extract_first_json_object(content)

