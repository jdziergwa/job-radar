"""Gemini adapter: implicit caching only, default Models per AI Task."""

from __future__ import annotations

import asyncio
import base64
import importlib
from typing import Any

import httpx
from google import genai
from google.auth import exceptions as auth_exceptions
from google.genai import errors, types

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

# Gemini counts thinking tokens against max_output_tokens. Thinking is capped at this budget and
# the same amount is added on top of the caller's max_tokens, so the answer always keeps its room.
THINKING_HEADROOM_TOKENS = 8192


def _to_parts(content) -> list[types.Part]:
    if isinstance(content, str):
        return [types.Part(text=content)]
    return [
        types.Part.from_bytes(data=base64.b64decode(b["data"]), mime_type=b["media_type"])
        if b["type"] == "image" else types.Part(text=b["text"])
        for b in content
    ]


def _optional_exceptions(module: str, *names: str) -> tuple[type[Exception], ...]:
    """Exception classes of an HTTP client the Gemini SDK may use, or none when it isn't installed."""
    try:
        imported = importlib.import_module(module)
    except ImportError:
        return ()
    return tuple(getattr(imported, name) for name in names)


# The SDK re-raises connection failures from whichever HTTP client it uses: aiohttp when installed,
# otherwise httpx (or its httpx2 fork), plus google-auth transport errors.
_CONNECTION_ERRORS = (
    (httpx.TransportError, auth_exceptions.TransportError)
    + _optional_exceptions("httpx2", "TransportError")
    + _optional_exceptions("aiohttp", "ClientError")
)


def _part_kinds(parts) -> list[str]:
    """Name the populated field of each response part, e.g. ['thought', 'function_call']."""
    return [
        next((field for field, value in part if value is not None and field != "thought_signature"), "empty")
        for part in parts
    ]


def classify_error(error: Exception, elapsed: float, model: str) -> Failure | None:
    """HTTP 429 becomes `LLMRateLimitError` with the retry-after header; other API errors, timeouts and connection errors `LLMAPIError`."""
    if isinstance(error, errors.APIError):
        if error.code == 429:
            headers = getattr(getattr(error, "response", None), "headers", None)
            return Failure(
                LLMRateLimitError(str(error), parse_retry_after_seconds(headers)),
                f"Gemini rate limited after {elapsed:.1f}s (model={model}): {error}",
            )
        return Failure(
            LLMAPIError(str(error)),
            f"Gemini API error after {elapsed:.1f}s (model={model}, code={error.code}, "
            f"status={getattr(error, 'status', None)}): {error}",
        )
    if isinstance(error, (asyncio.TimeoutError, httpx.TimeoutException)):
        return Failure(
            LLMAPIError(f"Gemini request timed out: {error}"),
            f"Gemini request timed out after {elapsed:.1f}s (model={model})",
        )
    if isinstance(error, _CONNECTION_ERRORS):
        return Failure(
            LLMAPIError(f"Gemini connection error: {error}"),
            f"Gemini connection error after {elapsed:.1f}s (model={model}, {type(error).__name__}): {error}",
        )
    return None


def read_response(response: Any, model: str, max_output_tokens: int) -> Reading:
    """Read text and usage from a generate_content response; one without text is a failure."""
    usage = getattr(response, "usage_metadata", None)
    candidate = (getattr(response, "candidates", None) or [None])[0]
    finish_reason = getattr(candidate, "finish_reason", None)
    prompt_feedback = getattr(response, "prompt_feedback", None)
    thinking_tokens = getattr(usage, "thoughts_token_count", None)
    summary = (
        f"model={model} finish_reason={finish_reason} prompt_tokens={getattr(usage, 'prompt_token_count', None)} "
        f"output_tokens={getattr(usage, 'candidates_token_count', None)} thinking_tokens={thinking_tokens} "
        f"cached_tokens={getattr(usage, 'cached_content_token_count', None)} prompt_feedback={prompt_feedback}"
    )
    counts = {
        "input_tokens": getattr(usage, "prompt_token_count", 0),
        "output_tokens": getattr(usage, "candidates_token_count", 0),
        "cached_input_tokens": getattr(usage, "cached_content_token_count", 0),
    }
    text = response.text
    if not text:
        parts = getattr(getattr(candidate, "content", None), "parts", None) or []
        failure = Failure(
            LLMAPIError(f"Gemini returned no text content (finish_reason={finish_reason})"),
            f"Gemini returned no text (model={model}, finish_reason={finish_reason}, "
            f"thinking_tokens={thinking_tokens}, max_output_tokens={max_output_tokens}, "
            f"prompt_feedback={prompt_feedback}, part_kinds={_part_kinds(parts)})",
        )
        return Reading(summary, failure=failure, **counts)
    warning = None
    if finish_reason is not None and getattr(finish_reason, "name", str(finish_reason)) != "STOP":
        warning = (
            f"Gemini response not cleanly finished (model={model}, finish_reason={finish_reason}, "
            f"output_chars={len(text)}, thinking_tokens={thinking_tokens}, "
            f"max_output_tokens={max_output_tokens}) — output is likely truncated"
        )
    return Reading(summary, text, warning=warning, **counts)


class GeminiAdapter:
    name = "gemini"
    display_name = "Gemini"
    default_models = {
        AITask.SCORING: "gemini-3.8-flash",
        AITask.WIZARD: "gemini-3.1-pro-preview",
        AITask.STATS: "gemini-3.8-flash",
    }

    def __init__(self, client: genai.Client | None = None):
        self._client = client or genai.Client()

    @classmethod
    def owns_model(cls, model: str) -> bool:
        return model.startswith("gemini-")

    @staticmethod
    def supports_json_schema(model: str) -> bool:
        return False

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
        # `cache_system` is ignored: Gemini caches repeated prefixes implicitly.
        # `json_schema` is ignored: callers parse the JSON the prompt asks for.
        contents = [
            types.Content(
                role="model" if message["role"] == "assistant" else "user",
                parts=_to_parts(message["content"]),
            )
            for message in messages
        ]
        config = types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=max_tokens + THINKING_HEADROOM_TOKENS,
            thinking_config=types.ThinkingConfig(thinking_budget=THINKING_HEADROOM_TOKENS),
            response_mime_type="application/json" if json_output else None,
            http_options=None if timeout is None else types.HttpOptions(timeout=int(timeout * 1000)),
        )

        return await call_llm(
            label="Gemini",
            model=model,
            request_summary=(
                f"model={model} max_tokens={max_tokens} (+{THINKING_HEADROOM_TOKENS} thinking) "
                f"json_output={json_output} timeout={timeout} system_chars={len(system)} messages={len(messages)}"
            ),
            send=lambda: self._client.aio.models.generate_content(model=model, contents=contents, config=config),
            classify=classify_error,
            read=lambda response, _elapsed: read_response(response, model, config.max_output_tokens),
        )

    async def aclose(self) -> None:
        await self._client.aio.aclose()
