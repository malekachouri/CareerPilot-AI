"""LLM provider abstraction (docs/06 §2). Local by default: no paid API is required or used."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

import httpx
import structlog

from careerpilot.core.config import get_settings


class LLMUnavailableError(Exception):
    """No model is reachable (Ollama not running, model not pulled, provider disabled)."""


class LLMTimeoutError(LLMUnavailableError):
    """The model is reachable but too slow: almost always not enough free RAM (the model swaps to disk)."""


@dataclass(frozen=True)
class Message:
    role: str  # system | user | assistant
    content: str


class LLMProvider(Protocol):
    name: str
    model: str

    async def structured(
        self, messages: list[Message], schema: dict[str, Any], *, temperature: float = 0.4
    ) -> dict[str, Any]: ...

    async def health(self) -> bool: ...


class OllamaProvider:
    """Ollama native API with JSON-schema structured outputs (`format` = schema)."""

    name = "ollama"

    def __init__(
        self,
        base_url: str,
        model: str,
        timeout: float,
        *,
        num_ctx: int = 4096,
        keep_alive: str = "30m",
        max_tokens: int = 1200,
    ) -> None:
        self.base_url, self.model, self.timeout = base_url.rstrip("/"), model, timeout
        # A shorter context uses less RAM; keep_alive avoids reloading the model between coach steps.
        self.num_ctx, self.keep_alive = num_ctx, keep_alive
        # Hard cap on generated tokens: small models constrained to JSON can loop until the context is full,
        # which takes many minutes on a CPU.
        self.max_tokens = max_tokens

    async def structured(
        self, messages: list[Message], schema: dict[str, Any], *, temperature: float = 0.4
    ) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "format": schema,
            "stream": False,
            "think": False,
            "keep_alive": self.keep_alive,
            "options": {"temperature": temperature, "num_ctx": self.num_ctx, "num_predict": self.max_tokens},
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                r = await client.post(f"{self.base_url}/api/chat", json=payload)
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(
                f"The model '{self.model}' did not answer within {self.timeout:.0f}s"
            ) from exc
        except httpx.HTTPError as exc:
            raise LLMUnavailableError(f"Ollama is not reachable at {self.base_url}: {exc}") from exc
        if r.status_code == 404:
            raise LLMUnavailableError(f"Model '{self.model}' is not available. Run: ollama pull {self.model}")
        if r.status_code != 200:
            raise LLMUnavailableError(f"Ollama returned {r.status_code}: {r.text[:200]}")
        body = r.json()
        structlog.get_logger("llm").info(
            "llm_call",
            model=self.model,
            seconds=round(body.get("total_duration", 0) / 1e9, 1),
            load_seconds=round(body.get("load_duration", 0) / 1e9, 1),
            prompt_tokens=body.get("prompt_eval_count"),
            output_tokens=body.get("eval_count"),
            done_reason=body.get("done_reason"),
        )
        if body.get("done_reason") == "length":
            raise ValueError(
                f"the model's answer was cut off after {self.max_tokens} tokens; "
                "retry (or raise LLM_MAX_TOKENS)"
            )
        content = body.get("message", {}).get("content", "")
        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError("model output is not valid JSON") from exc
        if not isinstance(data, dict):
            raise ValueError("model output is not a JSON object")
        return data

    async def health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                r = await client.get(f"{self.base_url}/api/tags")
            names = {m.get("name") for m in r.json().get("models", [])} if r.status_code == 200 else set()
            return self.model in names or f"{self.model}:latest" in names
        except (httpx.HTTPError, ValueError):
            return False


class DisabledProvider:
    name = "none"
    model = "none"

    async def structured(
        self, messages: list[Message], schema: dict[str, Any], *, temperature: float = 0.4
    ) -> dict[str, Any]:
        raise LLMUnavailableError("The AI provider is disabled (LLM_PROVIDER=none).")

    async def health(self) -> bool:
        return False


_override: LLMProvider | None = None


def get_llm() -> LLMProvider:
    if _override is not None:
        return _override
    s = get_settings()
    if s.llm_provider == "ollama":
        return OllamaProvider(
            s.ollama_url,
            s.llm_model,
            s.llm_timeout_seconds,
            num_ctx=s.llm_num_ctx,
            keep_alive=s.llm_keep_alive,
            max_tokens=s.llm_max_tokens,
        )
    return DisabledProvider()


def set_llm_override(provider: LLMProvider | None) -> None:
    """Tests (and future provider plug-ins) can swap the provider."""
    global _override
    _override = provider


# --- Embeddings ------------------------------------------------------------------------------------------


class Embedder(Protocol):
    name: str
    model: str
    dim: int

    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class OllamaEmbedder:
    """Ollama `/api/embed`. Default model nomic-embed-text (Apache-2.0, 768 dimensions)."""

    name = "ollama"

    def __init__(self, base_url: str, model: str, dim: int, timeout: float = 120.0) -> None:
        self.base_url, self.model, self.dim, self.timeout = base_url.rstrip("/"), model, dim, timeout

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                r = await client.post(
                    f"{self.base_url}/api/embed",
                    json={"model": self.model, "input": texts, "keep_alive": "30m"},
                )
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(f"The embedding model '{self.model}' did not answer in time") from exc
        except httpx.HTTPError as exc:
            raise LLMUnavailableError(f"Ollama is not reachable at {self.base_url}: {exc}") from exc
        if r.status_code != 200:
            raise LLMUnavailableError(f"Embedding model '{self.model}' unavailable ({r.status_code})")
        vectors: list[list[float]] = r.json().get("embeddings", [])
        if len(vectors) != len(texts) or any(len(v) != self.dim for v in vectors):
            raise LLMUnavailableError(f"Embedding model '{self.model}' must return {self.dim}-d vectors")
        return vectors


class DisabledEmbedder:
    name, model, dim = "none", "none", 0

    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise LLMUnavailableError("Embeddings are disabled")


_embedder_override: Embedder | None = None


def get_embedder() -> Embedder:
    if _embedder_override is not None:
        return _embedder_override
    s = get_settings()
    if s.llm_provider == "ollama" and s.embedding_model:
        from careerpilot.modules.kb.models import EMBEDDING_DIM

        return OllamaEmbedder(s.ollama_url, s.embedding_model, EMBEDDING_DIM)
    return DisabledEmbedder()


def set_embedder_override(embedder: Embedder | None) -> None:
    global _embedder_override
    _embedder_override = embedder
