"""LLM Provider-agnostic adapter interface, shared types and errors."""

from __future__ import annotations

import email.utils
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


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


# A message's `content` is plain text or a list of neutral blocks:
#   {"type": "text", "text": str}
#   {"type": "image", "media_type": "image/png", "data": <base64 str>}
Message = dict[str, Any]


@runtime_checkable
class LLMAdapter(Protocol):
    """One LLM Provider behind a completion call shared by every LLM Provider."""

    name: str
    display_name: str
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
        messages: list[Message],
        model: str,
        max_tokens: int,
        cache_system: bool = False,
        timeout: float | None = None,
        json_schema: dict[str, Any] | None = None,
        json_output: bool = False,
    ) -> LLMResult:
        """Return the model's text. `cache_system` hints the system prompt is reusable.

        `max_tokens` bounds the answer, not any hidden reasoning the Model does first.
        `json_output` hints the answer must be a bare JSON document. When
        `supports_json_schema(model)`, the answer is also constrained to `json_schema`;
        otherwise `json_schema` is ignored and callers must parse free-form JSON.

        `timeout` is seconds for the request; None keeps the LLM Provider SDK's default.
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


@dataclass(frozen=True)
class Failure:
    """An LLM error to raise and the log line that explains it."""

    error: LLMError
    log: str


@dataclass(frozen=True)
class Reading:
    """What an adapter read from a response: its debug summary, text and token counts.

    `warning` is logged but not fatal; `failure` replaces the result with an error.
    """

    summary: str
    text: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cached_input_tokens: int | None = None
    warning: str | None = None
    failure: Failure | None = None


Classifier = Callable[[Exception, float, str], Failure | None]


async def call_llm(
    *,
    label: str,
    model: str,
    request_summary: str,
    send: Callable[[], Awaitable[Any]],
    classify: Classifier,
    read: Callable[[Any, float], Reading],
) -> LLMResult:
    """Time and log one SDK call, wrap its errors and build the `LLMResult`.

    `classify(error, elapsed, model)` turns an SDK exception into a `Failure`, or None to let it pass.
    """
    logger.debug("%s request: %s", label, request_summary)
    started = time.monotonic()
    try:
        response = await send()
    except Exception as error:
        failure = classify(error, time.monotonic() - started, model)
        if failure is None:
            logger.exception("%s call raised an unexpected error (model=%s)", label, model)
            raise
        log = logger.warning if isinstance(failure.error, LLMRateLimitError) else logger.error
        log("%s", failure.log)
        raise failure.error from error
    elapsed = time.monotonic() - started

    reading = read(response, elapsed)
    logger.debug("%s response in %.1fs: %s", label, elapsed, reading.summary)
    if reading.warning:
        logger.warning("%s", reading.warning)
    if reading.failure:
        logger.error("%s", reading.failure.log)
        raise reading.failure.error
    return LLMResult(
        text=reading.text or "",
        usage=Usage(
            input_tokens=reading.input_tokens or 0,
            output_tokens=reading.output_tokens or 0,
            cached_input_tokens=reading.cached_input_tokens or 0,
        ),
    )
