import asyncio
import types

import pytest

from src.claude import HAIKU_MODEL, SONNET_MODEL
from src.llm import LLMAPIError
from src.llm.anthropic_adapter import AnthropicAdapter


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


def _run(cache_system: bool = False, model: str = "claude-x", json_schema=None, response=None):
    messages = _Messages(response)
    adapter = AnthropicAdapter(client=types.SimpleNamespace(messages=messages))
    result = asyncio.run(adapter.complete(
        system="sys", messages=[{"role": "user", "content": "hi"}],
        model=model, max_tokens=50, cache_system=cache_system, json_schema=json_schema,
    ))
    return messages.kwargs, result


def test_cacheable_system_prompt_gets_cache_control():
    kwargs, result = _run(True)
    assert kwargs["system"] == [{"type": "text", "text": "sys", "cache_control": {"type": "ephemeral"}}]
    assert kwargs["model"] == "claude-x" and kwargs["max_tokens"] == 50
    assert result.text == "hello"
    assert (result.usage.input_tokens, result.usage.output_tokens, result.usage.cached_input_tokens) == (10, 5, 7)


def test_uncached_system_prompt_has_no_cache_control():
    kwargs, _ = _run(False)
    assert kwargs["system"] == [{"type": "text", "text": "sys"}]


def test_haiku_runs_without_thinking_at_low_effort_with_structured_output():
    schema = {"type": "object"}
    kwargs, _ = _run(model=HAIKU_MODEL, json_schema=schema)
    assert kwargs["thinking"] == {"type": "disabled"}
    assert kwargs["output_config"] == {"effort": "low", "format": {"type": "json_schema", "schema": schema}}


def test_sonnet_runs_at_low_effort_and_ignores_json_schema():
    kwargs, _ = _run(model=SONNET_MODEL, json_schema={"type": "object"})
    assert "thinking" not in kwargs
    assert kwargs["output_config"] == {"effort": "low"}


def test_other_models_get_no_vendor_options():
    kwargs, _ = _run(json_schema={"type": "object"})
    assert "thinking" not in kwargs and "output_config" not in kwargs


def test_text_after_thinking_block_is_returned():
    thinking = types.SimpleNamespace(type="thinking", thinking="...")
    _, result = _run(response=_response(thinking, _text("answer")))
    assert result.text == "answer"


def test_truncated_response_raises_api_error():
    with pytest.raises(LLMAPIError, match="max_tokens"):
        _run(response=_response(_text('{"fit_score": 0'), stop_reason="max_tokens"))


def test_neutral_image_blocks_become_anthropic_image_sources():
    messages = _Messages()
    adapter = AnthropicAdapter(client=types.SimpleNamespace(messages=messages))
    asyncio.run(adapter.complete(
        system="s", model="claude-x", max_tokens=5,
        messages=[{"role": "user", "content": [
            {"type": "image", "media_type": "image/png", "data": "QUJD"},
            {"type": "text", "text": "hi"},
        ]}],
    ))
    assert messages.kwargs["messages"][0]["content"] == [
        {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "QUJD"}},
        {"type": "text", "text": "hi"},
    ]


def _complete_with(messages, **extra):
    adapter = AnthropicAdapter(client=types.SimpleNamespace(messages=messages))
    return asyncio.run(adapter.complete(
        system="s", messages=[{"role": "user", "content": "hi"}],
        model="claude-x", max_tokens=5, **extra,
    ))


def test_timeout_is_passed_to_the_sdk_request():
    messages = _Messages()
    _complete_with(messages, timeout=7.0)
    assert messages.kwargs["timeout"] == 7.0


def test_no_timeout_leaves_sdk_default():
    messages = _Messages()
    _complete_with(messages)
    assert "timeout" not in messages.kwargs

