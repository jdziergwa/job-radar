"""Anthropic adapter: explicit prompt caching, default Models per AI Task."""

from __future__ import annotations

from typing import Any

import anthropic
from anthropic import AsyncAnthropic

from src.claude import HAIKU_MODEL, SONNET_MODEL, message_text
from src.llm.base import (
    AITask,
    Failure,
    LLMAPIError,
    LLMRateLimitError,
    LLMResult,
    Message,
    Reading,
    call_llm,
    parse_retry_after_seconds,
)

# Models that run at low effort; Haiku also runs without extended thinking.
_LOW_EFFORT_MODELS = {HAIKU_MODEL, SONNET_MODEL}


def _to_anthropic(message: Message) -> Message:
    content = message["content"]
    if isinstance(content, str):
        return message
    blocks = [
        {"type": "image", "source": {"type": "base64", "media_type": b["media_type"], "data": b["data"]}}
        if b["type"] == "image" else b
        for b in content
    ]
    return {**message, "content": blocks}


def classify_error(error: Exception, elapsed: float, model: str) -> Failure | None:
    """Rate limits become `LLMRateLimitError` with the retry-after header; other API errors `LLMAPIError`."""
    if isinstance(error, anthropic.RateLimitError):
        headers = getattr(getattr(error, "response", None), "headers", None)
        return Failure(
            LLMRateLimitError(str(error), parse_retry_after_seconds(headers)),
            f"Anthropic rate limited after {elapsed:.1f}s (model={model}): {error}",
        )
    if isinstance(error, anthropic.APIError):
        return Failure(
            LLMAPIError(str(error)),
            f"Anthropic API error after {elapsed:.1f}s (model={model}, "
            f"status={getattr(error, 'status_code', None)}): {error}",
        )
    return None


def read_response(response: Any, model: str, max_tokens: int) -> Reading:
    """Read text and usage from a Messages response; truncated or empty ones are failures."""
    usage = getattr(response, "usage", None)
    stop_reason = getattr(response, "stop_reason", None)
    summary = (
        f"model={model} stop_reason={stop_reason} input_tokens={getattr(usage, 'input_tokens', None)} "
        f"output_tokens={getattr(usage, 'output_tokens', None)} "
        f"cache_read={getattr(usage, 'cache_read_input_tokens', None)} "
        f"cache_write={getattr(usage, 'cache_creation_input_tokens', None)}"
    )
    warning = (
        f"Anthropic response hit max_tokens={max_tokens} (model={model}) — output is likely truncated"
        if stop_reason == "max_tokens" else None
    )
    counts = {
        "input_tokens": getattr(usage, "input_tokens", 0),
        "output_tokens": getattr(usage, "output_tokens", 0),
        "cached_input_tokens": getattr(usage, "cache_read_input_tokens", 0),
    }
    try:
        text = message_text(response)
    except ValueError as error:
        failure = Failure(
            LLMAPIError(str(error)),
            f"Anthropic response unusable (model={model}, stop_reason={stop_reason}): {error}",
        )
        failure.error.__cause__ = error
        return Reading(summary, warning=warning, failure=failure, **counts)
    return Reading(summary, text, warning=warning, **counts)


class AnthropicAdapter:
    name = "anthropic"
    display_name = "Anthropic"
    default_models = {
        AITask.SCORING: HAIKU_MODEL,
        AITask.WIZARD: SONNET_MODEL,
        AITask.STATS: HAIKU_MODEL,
    }

    def __init__(self, client: AsyncAnthropic | None = None):
        self._client = client or AsyncAnthropic()

    @classmethod
    def owns_model(cls, model: str) -> bool:
        return model.startswith("claude-")

    @staticmethod
    def supports_json_schema(model: str) -> bool:
        return model == HAIKU_MODEL

    @classmethod
    def _request_options(cls, model: str, json_schema: dict[str, Any] | None) -> dict[str, Any]:
        options: dict[str, Any] = {}
        output_config: dict[str, Any] = {}
        if model == HAIKU_MODEL:
            options["thinking"] = {"type": "disabled"}
        if model in _LOW_EFFORT_MODELS:
            output_config["effort"] = "low"
        if json_schema is not None and cls.supports_json_schema(model):
            output_config["format"] = {"type": "json_schema", "schema": json_schema}
        if output_config:
            options["output_config"] = output_config
        return options

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
        # `json_output` is ignored: the prompts already ask for JSON and the callers parse it.
        block: dict = {"type": "text", "text": system}
        if cache_system:
            block["cache_control"] = {"type": "ephemeral"}

        # A timeout is a hard cap: disable the SDK's own retries so they don't multiply it.
        client = self._client if timeout is None else self._client.with_options(timeout=timeout, max_retries=0)
        return await call_llm(
            label="Anthropic",
            model=model,
            request_summary=(
                f"model={model} max_tokens={max_tokens} timeout={timeout} cache_system={cache_system} "
                f"system_chars={len(system)} messages={len(messages)}"
            ),
            send=lambda: client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=[block],
                messages=[_to_anthropic(m) for m in messages],
                **self._request_options(model, json_schema),
            ),
            classify=classify_error,
            read=lambda response, _elapsed: read_response(response, model, max_tokens),
        )

    async def aclose(self) -> None:
        await self._client.close()
