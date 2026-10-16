"""Local-only Ollama transport. No hosted model names, redirects or fallback."""
from __future__ import annotations

import os
from urllib.parse import urlsplit

import httpx


class Ollama:
    def __init__(self, url: str | None = None, timeout: float = 180):
        self.url = (url or os.environ.get("KKH_OLLAMA_URL", "http://127.0.0.1:11434")).rstrip("/")
        parsed = urlsplit(self.url)
        if (parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
                or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment):
            raise ValueError("Ollama must use a local loopback HTTP endpoint")
        self.http = httpx.Client(timeout=timeout, trust_env=False, follow_redirects=False)

    def models(self) -> list[dict]:
        response = self.http.get(self.url + "/api/tags")
        response.raise_for_status()
        return [m for m in response.json()["models"] if not self._cloud(m["name"])
                and not m.get("remote_host") and not m.get("remote_model")]

    @staticmethod
    def _cloud(model: str) -> bool:
        return "cloud" in model.lower() or "/" in model or "://" in model

    def chat(self, messages: list[dict], model: str = "qwen3:4b", schema: dict | None = None,
             seed: int = 42, max_tokens: int = 1200, num_ctx: int = 8192) -> dict:
        available = {m["name"] for m in self.models()}
        if self._cloud(model) or model not in available:
            raise ValueError("Select an already installed local Ollama model")
        payload = {"model": model, "messages": messages, "stream": False, "think": False,
                   "keep_alive": "5m", "options": {"temperature": 0, "seed": seed,
                   "num_ctx": num_ctx, "num_predict": max_tokens}}
        if schema is not None:
            payload["format"] = schema
        response = self.http.post(self.url + "/api/chat", json=payload)
        response.raise_for_status()
        out = response.json()
        if not out.get("done") or out.get("done_reason") == "length":
            raise RuntimeError("Ollama response was incomplete; reduce context or increase token budget")
        return {"content": out["message"]["content"], "model": out["model"],
                "metrics": {k: out.get(k) for k in ("total_duration", "load_duration", "prompt_eval_count",
                                                    "eval_count", "eval_duration")}}

    def close(self):
        self.http.close()
