"""Shared Claude model defaults and response handling."""

from typing import Any


HAIKU_MODEL = "claude-haiku-5-5"
SONNET_MODEL = "claude-sonnet-5-5"


def message_text(response: Any) -> str:
    """Read text from a complete response, including messages that start with thinking."""
    stop_reason = getattr(response, "stop_reason", None)
    if stop_reason in {"max_tokens", "model_context_window_exceeded", "refusal"}:
        raise ValueError(f"Claude did not complete the response ({stop_reason})")

    text = "".join(block.text for block in response.content if block.type == "text")
    if not text.strip():
        raise ValueError("Claude returned no text")
    return text
