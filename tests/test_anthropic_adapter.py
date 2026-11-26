import types

import pytest

from src.claude import HAIKU_MODEL, SONNET_MODEL
from src.llm import LLMAPIError, LLMRateLimitError
from src.llm import anthropic_adapter
from src.llm.anthropic_adapter import AnthropicAdapter, classify_error

pytestmark = pytest.mark.anyio


def _response(*blocks, stop_reason="end_turn"):
    return types.SimpleNamespace(
        content=list(blocks),
        stop_reason=stop_reason,
        usage=types.SimpleNamespace(input_tokens=10, output_tokens=5, cache_read_input_tokens=7),
    )


def _text(text):
    return types.SimpleNamespace(type="text", text=text)


class _Messages:
    def __init__(self, response=None):
        self.kwargs = None
        self._response = response or _response(_text("hello"))

    async def create(self, **kwargs):
        self.kwargs = kwargs
        return self._response


async def _run(cache_system: bool = False, model: str = "claude-x", json_schema=None, response=None):
    messages = _Messages(response)
    adapter = AnthropicAdapter(client=types.SimpleNamespace(messages=messages))
    result = await adapter.complete(
        system="sys", messages=[{"role": "user", "content": "hi"}],
        model=model, max_tokens=50, cache_system=cache_system, json_schema=json_schema,
    )
    return messages.kwargs, result


async def test_cacheable_system_prompt_gets_cache_control():
    kwargs, result = await _run(True)
    assert kwargs["system"] == [{"type": "text", "text": "sys", "cache_control": {"type": "ephemeral"}}]
    assert kwargs["model"] == "claude-x" and kwargs["max_tokens"] == 50
    assert result.text == "hello"
    assert (result.usage.input_tokens, result.usage.output_tokens, result.usage.cached_input_tokens) == (10, 5, 7)


async def test_uncached_system_prompt_has_no_cache_control():
    kwargs, _ = await _run(False)
    assert kwargs["system"] == [{"type": "text", "text": "sys"}]


async def test_haiku_runs_without_thinking_at_low_effort_with_structured_output():
    schema = {"type": "object"}
    kwargs, _ = await _run(model=HAIKU_MODEL, json_schema=schema)
    assert kwargs["thinking"] == {"type": "disabled"}
    assert kwargs["output_config"] == {"effort": "low", "format": {"type": "json_schema", "schema": schema}}


async def test_sonnet_runs_at_low_effort_and_ignores_json_schema():
    kwargs, _ = await _run(model=SONNET_MODEL, json_schema={"type": "object"})
    assert "thinking" not in kwargs
    assert kwargs["output_config"] == {"effort": "low"}


async def test_other_models_get_no_effort_or_thinking_options():
    kwargs, _ = await _run(json_schema={"type": "object"})
    assert "thinking" not in kwargs and "output_config" not in kwargs


async def test_text_after_thinking_block_is_returned():
    thinking = types.SimpleNamespace(type="thinking", thinking="...")
    _, result = await _run(response=_response(thinking, _text("answer")))
    assert result.text == "answer"


async def test_truncated_response_raises_api_error():
    with pytest.raises(LLMAPIError, match="max_tokens"):
        await _run(response=_response(_text('{"fit_score": 0'), stop_reason="max_tokens"))


async def test_neutral_image_blocks_become_anthropic_image_sources():
    messages = _Messages()
    adapter = AnthropicAdapter(client=types.SimpleNamespace(messages=messages))
    await adapter.complete(
        system="s", model="claude-x", max_tokens=5,
        messages=[{"role": "user", "content": [
            {"type": "image", "media_type": "image/png", "data": "QUJD"},
            {"type": "text", "text": "hi"},
        ]}],
    )
    assert messages.kwargs["messages"][0]["content"] == [
        {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "QUJD"}},
        {"type": "text", "text": "hi"},
    ]


class _Client:
    def __init__(self, messages):
        self.messages = messages
        self.options = None

    def with_options(self, **options):
        self.options = options
        return self


async def _complete_with(client, **extra):
    adapter = AnthropicAdapter(client=client)
    return await adapter.complete(
        system="s", messages=[{"role": "user", "content": "hi"}],
        model="claude-x", max_tokens=5, **extra,
    )


async def test_timeout_is_a_hard_cap_without_sdk_retries():
    client = _Client(_Messages())
    await _complete_with(client, timeout=7.0)
    assert client.options == {"timeout": 7.0, "max_retries": 0}


async def test_no_timeout_leaves_sdk_defaults():
    client = _Client(_Messages())
    await _complete_with(client)
    assert client.options is None


class _SDKAPIError(Exception):
    def __init__(self, message, status_code=500, headers=None):
        super().__init__(message)
        self.status_code = status_code
        self.response = types.SimpleNamespace(headers=headers) if headers is not None else None


class _SDKRateLimitError(_SDKAPIError):
    pass


@pytest.fixture
def sdk_errors(monkeypatch):
    """Stand in for the SDK's error hierarchy, which the test stub flattens to bare Exception."""
    monkeypatch.setattr(anthropic_adapter.anthropic, "APIError", _SDKAPIError)
    monkeypatch.setattr(anthropic_adapter.anthropic, "RateLimitError", _SDKRateLimitError)


def test_classifier_maps_rate_limit_with_retry_after(sdk_errors):
    error = _SDKRateLimitError("slow down", 429, headers={"retry-after": "3"})
    failure = classify_error(error, 1.0, HAIKU_MODEL)
    assert isinstance(failure.error, LLMRateLimitError)
    assert failure.error.retry_after == 3


def test_classifier_maps_rate_limit_without_response_to_no_retry_after(sdk_errors):
    failure = classify_error(_SDKRateLimitError("slow down", 429), 1.0, HAIKU_MODEL)
    assert isinstance(failure.error, LLMRateLimitError)
    assert failure.error.retry_after is None


def test_classifier_maps_other_api_errors_to_llm_api_error(sdk_errors):
    failure = classify_error(_SDKAPIError("boom"), 1.0, HAIKU_MODEL)
    assert type(failure.error) is LLMAPIError


def test_classifier_passes_other_exceptions_through(sdk_errors):
    assert classify_error(ValueError("bug"), 1.0, HAIKU_MODEL) is None
