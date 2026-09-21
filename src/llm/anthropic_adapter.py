"""Anthropic adapter: explicit prompt caching, default Models per AI Task."""

from __future__ import annotations

import logging
import time
from typing import Any

import anthropic
from anthropic import AsyncAnthropic

from src.claude import HAIKU_MODEL, SONNET_MODEL, message_text
from src.llm.base import (
    AITask,
    LLMAPIError,
    LLMRateLimitError,
    LLMResult,
    Message,
    Usage,
    parse_retry_after_seconds,
)

logger = logging.getLogger(__name__)

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


class AnthropicAdapter:
    name = "anthropic"
    display_name = "Anthropic"
    api_key_env = "ANTHROPIC_API_KEY"
    credential_envs = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")
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
    ) -> LLMResult:
        block: dict = {"type": "text", "text": system}
        if cache_system:
            block["cache_control"] = {"type": "ephemeral"}

        # A timeout is a hard cap: disable the SDK's own retries so they don't multiply it.
        client = self._client if timeout is None else self._client.with_options(timeout=timeout, max_retries=0)
        logger.debug(
            "Anthropic request: model=%s max_tokens=%d timeout=%s cache_system=%s system_chars=%d messages=%d",
            model, max_tokens, timeout, cache_system, len(system), len(messages),
        )
        started = time.monotonic()
        try:
            response = await client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=[block],
                messages=[_to_anthropic(m) for m in messages],
                **self._request_options(model, json_schema),
            )
        except anthropic.RateLimitError as error:
            headers = getattr(getattr(error, "response", None), "headers", None)
            logger.warning("Anthropic rate limited after %.1fs (model=%s): %s", time.monotonic() - started, model, error)
            raise LLMRateLimitError(str(error), parse_retry_after_seconds(headers)) from error
        except anthropic.APIError as error:
            logger.error(
                "Anthropic API error after %.1fs (model=%s, status=%s): %s",
                time.monotonic() - started, model, getattr(error, "status_code", None), error,
            )
            raise LLMAPIError(str(error)) from error
        except Exception:
            logger.exception("Anthropic call raised an unexpected error (model=%s)", model)
            raise
        elapsed = time.monotonic() - started

        usage = getattr(response, "usage", None)
        stop_reason = getattr(response, "stop_reason", None)
        logger.debug(
            "Anthropic response in %.1fs: model=%s stop_reason=%s input_tokens=%s output_tokens=%s "
            "cache_read=%s cache_write=%s",
            elapsed, model, stop_reason,
            getattr(usage, "input_tokens", None), getattr(usage, "output_tokens", None),
            getattr(usage, "cache_read_input_tokens", None), getattr(usage, "cache_creation_input_tokens", None),
        )
        if stop_reason == "max_tokens":
            logger.warning(
                "Anthropic response hit max_tokens=%d (model=%s) — output is likely truncated", max_tokens, model
            )

        try:
            text = message_text(response)
        except ValueError as error:
            logger.error("Anthropic response unusable (model=%s, stop_reason=%s): %s", model, stop_reason, error)
            raise LLMAPIError(str(error)) from error

        return LLMResult(
            text=text,
            usage=Usage(
                input_tokens=getattr(usage, "input_tokens", 0) or 0,
                output_tokens=getattr(usage, "output_tokens", 0) or 0,
                cached_input_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
            ),
        )

    async def aclose(self) -> None:
        await self._client.close()
