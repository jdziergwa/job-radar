import asyncio
import types

import pytest
from google.genai import errors

from src.llm import LLMAPIError, LLMRateLimitError
from src.llm.gemini_adapter import GeminiAdapter


class _Models:
    def __init__(self, response=None, error=None):
        self.kwargs = None
        self._response = response
        self._error = error

    async def generate_content(self, **kwargs):
        self.kwargs = kwargs
        if self._error:
            raise self._error
        return self._response


def _adapter(models):
    return GeminiAdapter(client=types.SimpleNamespace(aio=types.SimpleNamespace(models=models)))


def _complete(adapter, **overrides):
    args = dict(
        system="sys", messages=[{"role": "user", "content": "hi"}],
        model="gemini-x", max_tokens=50, cache_system=True,
    )
    args.update(overrides)
    return asyncio.run(adapter.complete(**args))


def _response(text="hello"):
    return types.SimpleNamespace(
        text=text,
        usage_metadata=types.SimpleNamespace(
            prompt_token_count=10, candidates_token_count=5, cached_content_token_count=7
        ),
    )


def test_request_shape_and_usage_extraction():
    models = _Models(_response())
    result = _complete(_adapter(models), messages=[
        {"role": "user", "content": "hi"}, {"role": "assistant", "content": "yo"},
    ])
    kwargs = models.kwargs
    assert kwargs["model"] == "gemini-x"
    assert kwargs["config"].system_instruction == "sys"
    assert kwargs["config"].max_output_tokens == 50
    assert [(c.role, c.parts[0].text) for c in kwargs["contents"]] == [("user", "hi"), ("model", "yo")]
    assert result.text == "hello"
    assert (result.usage.input_tokens, result.usage.output_tokens, result.usage.cached_input_tokens) == (10, 5, 7)


def test_cache_hint_is_ignored_safely():
    with_hint = _Models(_response())
    without_hint = _Models(_response())
    _complete(_adapter(with_hint), cache_system=True)
    _complete(_adapter(without_hint), cache_system=False)
    assert with_hint.kwargs["config"] == without_hint.kwargs["config"]


def test_rate_limit_maps_with_retry_after():
    response = types.SimpleNamespace(headers={"retry-after": "3"})
    error = errors.ClientError(429, {"error": {"message": "slow down"}}, response)
    with pytest.raises(LLMRateLimitError) as info:
        _complete(_adapter(_Models(error=error)))
    assert info.value.retry_after == 3


def test_other_api_errors_map_to_llm_api_error():
    error = errors.ServerError(500, {"error": {"message": "boom"}}, None)
    with pytest.raises(LLMAPIError):
        _complete(_adapter(_Models(error=error)))


def test_empty_response_is_an_api_error():
    with pytest.raises(LLMAPIError):
        _complete(_adapter(_Models(_response(text=None))))
