"""Vendor-neutral LLM adapter interface, shared types and errors."""

from __future__ import annotations

import email.utils
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Protocol, runtime_checkable


class AITask(str, Enum):
    """A distinct job the app gives to an AI model."""

    SCORING = "scoring"
    WIZARD = "wizard"
    STATS = "stats"


class LLMConfigError(RuntimeError):
    """The LLM Provider, its API key or a Model is misconfigured."""


class LLMError(Exception):
    """Base for errors raised by an adapter call."""


class LLMRateLimitError(LLMError):
    """The LLM Provider asked us to slow down."""

    def __init__(self, message: str = "rate limited", retry_after: float | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class LLMAPIError(LLMError):
    """Any other LLM Provider API failure."""


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0


@dataclass(frozen=True)
class LLMResult:
    text: str
    usage: Usage = Usage()


@runtime_checkable
class LLMAdapter(Protocol):
    """One LLM Provider behind a vendor-neutral completion call."""

    name: str
    display_name: str
    api_key_env: str
    # Env vars that can each authenticate; `api_key_env` is the one named in messages.
    credential_envs: tuple[str, ...]
    default_models: dict[AITask, str]

    def owns_model(self, model: str) -> bool:
        """Whether `model` is a Model of this LLM Provider."""
        ...

    def supports_json_schema(self, model: str) -> bool:
        """Whether `complete` enforces `json_schema` for `model`."""
        ...

    async def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, str]],
        model: str,
        max_tokens: int,
        cache_system: bool = False,
        json_schema: dict[str, Any] | None = None,
    ) -> LLMResult:
        """Return the model's text. `cache_system` hints the system prompt is reusable.

        When `supports_json_schema(model)`, the answer is constrained to `json_schema`;
        otherwise `json_schema` is ignored and callers must parse free-form JSON.
        Raises LLMRateLimitError or LLMAPIError.
        """
        ...

    async def aclose(self) -> None: ...


def parse_retry_after_seconds(headers: Any) -> float | None:
    """Best-effort parsing of retry-after headers from an HTTP response."""
    if headers is None:
        return None

    retry_after_ms = headers.get("retry-after-ms")
    try:
        if retry_after_ms is not None:
            seconds = float(retry_after_ms) / 1000
            if seconds > 0:
                return seconds
    except (TypeError, ValueError):
        pass

    retry_after = headers.get("retry-after")
    try:
        if retry_after is not None:
            seconds = float(retry_after)
            if seconds > 0:
                return seconds
    except (TypeError, ValueError):
        pass

    if retry_after:
        try:
            retry_dt = email.utils.parsedate_to_datetime(retry_after)
            if retry_dt is None:
                return None
            if retry_dt.tzinfo is None:
                retry_dt = retry_dt.replace(tzinfo=timezone.utc)
            seconds = (retry_dt - datetime.now(timezone.utc)).total_seconds()
            if seconds > 0:
                return seconds
        except (TypeError, ValueError, IndexError):
            return None

    return None
