import types

import pytest
from google.genai import errors

from src.llm import LLMAPIError, LLMRateLimitError
from src.llm.gemini_adapter import THINKING_HEADROOM_TOKENS, GeminiAdapter

pytestmark = pytest.mark.anyio


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


async def _complete(adapter, **overrides):
    args = dict(
        system="sys", messages=[{"role": "user", "content": "hi"}],
        model="gemini-x", max_tokens=50, cache_system=True,
    )
    args.update(overrides)
    return await adapter.complete(**args)


def _response(text="hello"):
    return types.SimpleNamespace(
        text=text,
        usage_metadata=types.SimpleNamespace(
            prompt_token_count=10, candidates_token_count=5, cached_content_token_count=7
        ),
    )


async def test_request_shape_and_usage_extraction():
    models = _Models(_response())
    result = await _complete(_adapter(models), messages=[
        {"role": "user", "content": "hi"}, {"role": "assistant", "content": "yo"},
    ])
    kwargs = models.kwargs
    assert kwargs["model"] == "gemini-x"
    assert kwargs["config"].system_instruction == "sys"
    assert kwargs["config"].max_output_tokens == 50 + THINKING_HEADROOM_TOKENS
    assert kwargs["config"].thinking_config.thinking_budget == THINKING_HEADROOM_TOKENS
    assert kwargs["config"].response_mime_type is None
    assert [(c.role, c.parts[0].text) for c in kwargs["contents"]] == [("user", "hi"), ("model", "yo")]
    assert result.text == "hello"
    assert (result.usage.input_tokens, result.usage.output_tokens, result.usage.cached_input_tokens) == (10, 5, 7)


async def test_cache_hint_is_ignored_safely():
    with_hint = _Models(_response())
    without_hint = _Models(_response())
    await _complete(_adapter(with_hint), cache_system=True)
    await _complete(_adapter(without_hint), cache_system=False)
    assert with_hint.kwargs["config"] == without_hint.kwargs["config"]


async def test_json_output_requests_json_mime_type():
    models = _Models(_response('{"a": 1}'))
    await _complete(_adapter(models), json_output=True)
    assert models.kwargs["config"].response_mime_type == "application/json"


async def test_rate_limit_maps_with_retry_after():
    response = types.SimpleNamespace(headers={"retry-after": "3"})
    error = errors.ClientError(429, {"error": {"message": "slow down"}}, response)
    with pytest.raises(LLMRateLimitError) as info:
        await _complete(_adapter(_Models(error=error)))
    assert info.value.retry_after == 3


async def test_other_api_errors_map_to_llm_api_error():
    error = errors.ServerError(500, {"error": {"message": "boom"}}, None)
    with pytest.raises(LLMAPIError):
        await _complete(_adapter(_Models(error=error)))


async def test_empty_response_is_an_api_error():
    with pytest.raises(LLMAPIError):
        await _complete(_adapter(_Models(_response(text=None))))


async def test_timeout_is_passed_as_http_options_milliseconds():
    models = _Models(_response())
    await _complete(_adapter(models), timeout=2.5)
    assert models.kwargs["config"].http_options.timeout == 2500


async def test_no_timeout_leaves_sdk_default():
    models = _Models(_response())
    await _complete(_adapter(models))
    assert models.kwargs["config"].http_options is None


async def test_timed_out_request_maps_to_llm_api_error():
    import httpx
    with pytest.raises(LLMAPIError):
        await _complete(_adapter(_Models(error=httpx.ReadTimeout("slow"))), timeout=1)
