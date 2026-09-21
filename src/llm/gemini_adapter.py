"""Gemini adapter: implicit caching only, default Models per AI Task."""

from __future__ import annotations

import asyncio
import base64
import logging
import time
from typing import Any

import httpx
from google import genai
from google.genai import errors, types

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


def _to_parts(content) -> list[types.Part]:
    if isinstance(content, str):
        return [types.Part(text=content)]
    return [
        types.Part.from_bytes(data=base64.b64decode(b["data"]), mime_type=b["media_type"])
        if b["type"] == "image" else types.Part(text=b["text"])
        for b in content
    ]


class GeminiAdapter:
    name = "gemini"
    display_name = "Gemini"
    api_key_env = "GOOGLE_API_KEY"
    credential_envs = ("GOOGLE_API_KEY",)
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
            max_output_tokens=max_tokens,
            http_options=None if timeout is None else types.HttpOptions(timeout=int(timeout * 1000)),
        )

        logger.debug(
            "Gemini request: model=%s max_tokens=%d timeout=%s system_chars=%d messages=%d",
            model, max_tokens, timeout, len(system), len(messages),
        )
        started = time.monotonic()
        try:
            response = await self._client.aio.models.generate_content(
                model=model, contents=contents, config=config
            )
        except errors.APIError as error:
            elapsed = time.monotonic() - started
            if error.code == 429:
                headers = getattr(getattr(error, "response", None), "headers", None)
                logger.warning("Gemini rate limited after %.1fs (model=%s): %s", elapsed, model, error)
                raise LLMRateLimitError(str(error), parse_retry_after_seconds(headers)) from error
            logger.error(
                "Gemini API error after %.1fs (model=%s, code=%s, status=%s): %s",
                elapsed, model, error.code, getattr(error, "status", None), error,
            )
            raise LLMAPIError(str(error)) from error
        except (asyncio.TimeoutError, httpx.TimeoutException) as error:
            logger.error("Gemini request timed out after %.1fs (model=%s)", time.monotonic() - started, model)
            raise LLMAPIError(f"Gemini request timed out: {error}") from error
        except Exception:
            logger.exception("Gemini call raised an unexpected error (model=%s)", model)
            raise
        elapsed = time.monotonic() - started

        usage = getattr(response, "usage_metadata", None)
        candidate = (getattr(response, "candidates", None) or [None])[0]
        finish_reason = getattr(candidate, "finish_reason", None)
        prompt_feedback = getattr(response, "prompt_feedback", None)
        logger.debug(
            "Gemini response in %.1fs: model=%s finish_reason=%s prompt_tokens=%s output_tokens=%s "
            "thinking_tokens=%s cached_tokens=%s prompt_feedback=%s",
            elapsed, model, finish_reason,
            getattr(usage, "prompt_token_count", None),
            getattr(usage, "candidates_token_count", None),
            getattr(usage, "thoughts_token_count", None),
            getattr(usage, "cached_content_token_count", None),
            prompt_feedback,
        )

        text = response.text
        if not text:
            logger.error(
                "Gemini returned no text (model=%s, finish_reason=%s, thinking_tokens=%s, max_tokens=%d, prompt_feedback=%s)",
                model, finish_reason, getattr(usage, "thoughts_token_count", None), max_tokens, prompt_feedback,
            )
            raise LLMAPIError(f"Gemini returned no text content (finish_reason={finish_reason})")
        if finish_reason is not None and getattr(finish_reason, "name", str(finish_reason)) != "STOP":
            logger.warning(
                "Gemini response not cleanly finished (model=%s, finish_reason=%s, output_chars=%d, "
                "thinking_tokens=%s, max_tokens=%d) — output is likely truncated",
                model, finish_reason, len(text), getattr(usage, "thoughts_token_count", None), max_tokens,
            )

        return LLMResult(
            text=text,
            usage=Usage(
                input_tokens=getattr(usage, "prompt_token_count", 0) or 0,
                output_tokens=getattr(usage, "candidates_token_count", 0) or 0,
                cached_input_tokens=getattr(usage, "cached_content_token_count", 0) or 0,
            ),
        )

    async def aclose(self) -> None:
        await self._client.aio.aclose()
