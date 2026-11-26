import types

import pytest
from google.genai import errors

from src.llm import LLMAPIError, LLMRateLimitError
from src.llm.gemini_adapter import THINKING_HEADROOM_TOKENS, GeminiAdapter, classify_error

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


def test_classifier_maps_429_to_rate_limit_with_retry_after():
    response = types.SimpleNamespace(headers={"retry-after": "3"})
    error = errors.ClientError(429, {"error": {"message": "slow down"}}, response)
    failure = classify_error(error, 1.0, "gemini-x")
    assert isinstance(failure.error, LLMRateLimitError)
    assert failure.error.retry_after == 3


def test_classifier_maps_429_without_headers_to_rate_limit_without_retry_after():
    error = errors.ClientError(429, {"error": {"message": "slow down"}}, None)
    assert classify_error(error, 1.0, "gemini-x").error.retry_after is None


def test_classifier_maps_other_api_errors_to_llm_api_error():
    error = errors.ServerError(500, {"error": {"message": "boom"}}, None)
    failure = classify_error(error, 1.0, "gemini-x")
    assert type(failure.error) is LLMAPIError


def test_classifier_maps_timeouts_to_llm_api_error():
    import httpx
    failure = classify_error(httpx.ReadTimeout("slow"), 1.0, "gemini-x")
    assert type(failure.error) is LLMAPIError
    assert "timed out" in str(failure.error)


def _connection_errors():
    import aiohttp
    import httpx
    import httpx2
    from google.auth import exceptions as auth_exceptions

    return [
        aiohttp.ClientConnectionError("refused"),
        aiohttp.ServerDisconnectedError("dropped"),
        httpx.ConnectError("refused"),
        httpx.ReadError("reset"),
        httpx2.ConnectError("refused"),
        auth_exceptions.TransportError("no route"),
    ]


@pytest.mark.parametrize("error", _connection_errors(), ids=lambda e: type(e).__module__ + "." + type(e).__name__)
async def test_connection_errors_map_to_llm_api_error(error):
    with pytest.raises(LLMAPIError, match="Gemini connection error"):
        await _complete(_adapter(_Models(error=error)))


@pytest.mark.parametrize("error", _connection_errors(), ids=lambda e: type(e).__module__ + "." + type(e).__name__)
def test_classifier_maps_connection_errors_to_llm_api_error(error):
    failure = classify_error(error, 1.0, "gemini-x")
    assert type(failure.error) is LLMAPIError
    assert "Gemini connection error" in str(failure.error)


def test_classifier_passes_other_exceptions_through():
    assert classify_error(ValueError("bug"), 1.0, "gemini-x") is None
