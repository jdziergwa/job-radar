"""Gemini adapter: implicit caching only, default Models per AI Task."""

from __future__ import annotations

from typing import Any

from google import genai
from google.genai import errors, types

from src.llm.base import (
    AITask,
    LLMAPIError,
    LLMRateLimitError,
    LLMResult,
    Usage,
    parse_retry_after_seconds,
)


class GeminiAdapter:
    name = "gemini"
    display_name = "Gemini"
    api_key_env = "GOOGLE_API_KEY"
    credential_envs = ("GOOGLE_API_KEY",)
    default_models = {
        AITask.SCORING: "gemini-2.5-flash",
        AITask.WIZARD: "gemini-2.5-pro",
        AITask.STATS: "gemini-2.5-flash",
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
        messages: list[dict[str, str]],
        model: str,
        max_tokens: int,
        cache_system: bool = False,
        json_schema: dict[str, Any] | None = None,
    ) -> LLMResult:
        # `cache_system` is ignored: Gemini caches repeated prefixes implicitly.
        # `json_schema` is ignored: callers parse the JSON the prompt asks for.
        contents = [
            types.Content(
                role="model" if message["role"] == "assistant" else "user",
                parts=[types.Part(text=message["content"])],
            )
            for message in messages
        ]
        config = types.GenerateContentConfig(system_instruction=system, max_output_tokens=max_tokens)

        try:
            response = await self._client.aio.models.generate_content(
                model=model, contents=contents, config=config
            )
        except errors.APIError as error:
            if error.code == 429:
                headers = getattr(getattr(error, "response", None), "headers", None)
                raise LLMRateLimitError(str(error), parse_retry_after_seconds(headers)) from error
            raise LLMAPIError(str(error)) from error

        text = response.text
        if not text:
            raise LLMAPIError("Gemini returned no text content")

        usage = getattr(response, "usage_metadata", None)
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
