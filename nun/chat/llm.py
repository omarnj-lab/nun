"""Chat model providers: local Ollama (default, e.g. qwen3.6) or Anthropic Claude (claude-opus-5).

Both expose complete(system, messages) -> str and complete_json(system, messages, schema) -> dict.
"""

from __future__ import annotations

import json
import os
import urllib.request

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11435")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3.6:latest")
ANTHROPIC_MODEL = "claude-opus-5"


class Ollama:
    name = "local"

    def __init__(self, model: str = OLLAMA_MODEL, url: str = OLLAMA_URL) -> None:
        self.model, self.url = model, url

    def _chat(self, system: str, messages: list[dict], fmt=None) -> str:
        body = {
            "model": self.model,
            "stream": False,
            "think": False,
            "keep_alive": "24h",
            "options": {"temperature": 0.2, "num_ctx": 16384},
            "messages": [{"role": "system", "content": system}, *messages],
        }
        if fmt is not None:
            body["format"] = fmt
        req = urllib.request.Request(
            self.url + "/api/chat", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=600) as r:
            return json.load(r)["message"]["content"]

    def complete(self, system: str, messages: list[dict]) -> str:
        return self._chat(system, messages)

    def complete_json(self, system: str, messages: list[dict], schema: dict) -> dict:
        return json.loads(self._chat(system, messages, fmt=schema))


class Claude:
    name = "anthropic"

    def __init__(self, model: str = ANTHROPIC_MODEL) -> None:
        import anthropic
        from dotenv import load_dotenv

        load_dotenv(override=True)  # the key in .env wins over a stale shell variable
        self.client = anthropic.Anthropic()
        self.model = model

    def _create(self, system: str, messages: list[dict], output_config: dict) -> str:
        resp = self.client.beta.messages.create(
            model=self.model,
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config=output_config,
            system=system,
            messages=messages,
        )
        if resp.stop_reason == "refusal":
            raise RuntimeError("model declined")
        return next(b.text for b in resp.content if b.type == "text")

    def complete(self, system: str, messages: list[dict]) -> str:
        return self._create(system, messages, {"effort": os.environ.get("ANSWER_EFFORT", "low")})

    def complete_json(self, system: str, messages: list[dict], schema: dict) -> dict:
        fmt = {"effort": "low", "format": {"type": "json_schema", "schema": schema}}
        return json.loads(self._create(system, messages, fmt))


_cache: dict[str, object] = {}


def provider(name: str | None = None):
    name = (name or os.environ.get("CHAT_PROVIDER", "local")).lower()
    if name not in ("local", "anthropic"):
        raise ValueError("provider must be 'local' or 'anthropic'")
    if name not in _cache:
        _cache[name] = Ollama() if name == "local" else Claude()
    return _cache[name]
