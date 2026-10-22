"""Thin LLM wrapper so the rest of the code (and the tests) never touch the SDK directly."""

from __future__ import annotations

import re
from typing import Protocol

from openai import OpenAI

_THINK = re.compile(r"<think>.*?</think>", re.DOTALL)


class LLMError(RuntimeError):
    pass


class LLM(Protocol):
    def complete(self, system: str, user: str, *, temperature: float = 0.2, max_tokens: int = 1024) -> str: ...


def strip_thinking(text: str) -> tuple[str, str]:
    """Split a reply into (answer, reasoning) when the model emits <think> blocks."""
    thoughts = "\n".join(m.strip() for m in re.findall(r"<think>(.*?)</think>", text, flags=re.DOTALL))
    answer = _THINK.sub("", text)
    # An unterminated <think> means the model ran out of tokens mid-thought.
    answer = re.sub(r"</?think>", "", answer).strip()
    return answer, thoughts.strip()


class OpenAICompatibleLLM:
    """Any OpenAI-compatible chat endpoint."""

    def __init__(self, api_key: str | None, base_url: str, model: str, timeout: float = 90.0):
        if not api_key:
            raise LLMError("No LLM API key configured. Set LLM_API_KEY in backend/.env.")
        self._client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)
        self._model = model

    def complete(self, system: str, user: str, *, temperature: float = 0.2, max_tokens: int = 1024) -> str:
        try:
            resp = self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as exc:  # SDK raises many transport/HTTP error types
            raise LLMError(f"LLM request failed: {exc}") from exc
        if not resp.choices:
            raise LLMError("LLM returned no choices.")
        return resp.choices[0].message.content or ""
