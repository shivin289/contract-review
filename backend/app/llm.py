"""OpenRouter client (OpenAI-compatible): embeddings in batches, JSON chat, streaming chat.
429s are retried with backoff, then surfaced as RateLimited so the UI can show a clear message."""
import json
import logging
import time
from typing import Iterator

import httpx

from .config import settings

log = logging.getLogger("llm")
RATE_MSG = "The free AI model is rate-limited right now. Wait a minute and try again."


class LLMError(Exception):
    pass


class RateLimited(LLMError):
    pass


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.openrouter_key}",
        "HTTP-Referer": "http://localhost:3000",
        "X-Title": "Contract Review Assistant",
    }


def _post(path: str, payload: dict, retries: int = 4) -> dict:
    if not settings.openrouter_key:
        raise LLMError("OPENROUTER_API_KEY is not set.")
    last: Exception = LLMError("Request failed")
    for attempt in range(retries):
        try:
            r = httpx.post(f"{settings.openrouter_base_url}{path}", json=payload, headers=_headers(), timeout=120)
        except httpx.HTTPError as e:
            last = LLMError(f"Network error: {e}")
            time.sleep(2 ** attempt)
            continue
        if r.status_code == 429:
            last = RateLimited(RATE_MSG)
            time.sleep(min(3 * 2 ** attempt, 20))
            continue
        if r.status_code >= 500:
            last = LLMError(f"Model provider error {r.status_code}")
            time.sleep(2 ** (attempt + 1))
            continue
        if r.status_code >= 400:
            raise LLMError(f"Model request rejected ({r.status_code}): {r.text[:200]}")
        data = r.json()
        err = data.get("error")
        if err:  # OpenRouter sometimes returns 200 with an error body
            if err.get("code") == 429:
                last = RateLimited(RATE_MSG)
                time.sleep(min(3 * 2 ** attempt, 20))
                continue
            raise LLMError(str(err.get("message", err))[:200])
        return data
    raise last


def embed(texts: list[str], batch_size: int = 32) -> list[list[float]]:
    out: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        data = _post("/embeddings", {"model": settings.embed_model, "input": texts[i:i + batch_size]})
        out += [d["embedding"] for d in sorted(data["data"], key=lambda d: d["index"])]
    if any(len(v) != settings.embed_dim for v in out):
        raise LLMError(f"Embedding size does not match EMBED_DIM={settings.embed_dim}.")
    return out


def chat_json(system: str, user: str) -> str:
    payload = {
        "model": settings.chat_model, "temperature": 0,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "response_format": {"type": "json_object"},
    }
    try:
        data = _post("/chat/completions", payload)
    except RateLimited:
        raise
    except LLMError:  # some free models reject response_format; retry without it
        payload.pop("response_format")
        data = _post("/chat/completions", payload)
    return data["choices"][0]["message"].get("content") or ""


def chat_stream(messages: list[dict]) -> Iterator[str]:
    payload = {"model": settings.chat_model, "temperature": 0.1, "stream": True, "messages": messages}
    with httpx.stream("POST", f"{settings.openrouter_base_url}/chat/completions",
                      json=payload, headers=_headers(), timeout=120) as r:
        if r.status_code == 429:
            raise RateLimited(RATE_MSG)
        if r.status_code >= 400:
            r.read()
            raise LLMError(f"Model request failed ({r.status_code})")
        for line in r.iter_lines():
            if not line.startswith("data: "):
                continue
            body = line[6:].strip()
            if body == "[DONE]":
                return
            try:
                obj = json.loads(body)
            except json.JSONDecodeError:
                continue
            if obj.get("error"):
                raise RateLimited(RATE_MSG) if obj["error"].get("code") == 429 else LLMError("Model error")
            delta = (obj.get("choices") or [{}])[0].get("delta", {}).get("content")
            if delta:
                yield delta
