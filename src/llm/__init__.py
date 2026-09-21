"""Vendor-neutral LLM access: adapter interface, adapters and the resolver."""

from src.llm.base import (
    AITask,
    LLMAdapter,
    LLMAPIError,
    LLMConfigError,
    LLMError,
    LLMRateLimitError,
    LLMResult,
    Message,
    Usage,
)
from src.llm.resolver import (
    check_api_key,
    describe_active,
    get_adapter,
    load_model_overrides,
    resolve_model,
    resolve_provider_name,
    set_adapter_override,
    set_model_override,
)

__all__ = [
    "AITask",
    "LLMAdapter",
    "LLMAPIError",
    "LLMConfigError",
    "LLMError",
    "LLMRateLimitError",
    "LLMResult",
    "Message",
    "Usage",
    "check_api_key",
    "describe_active",
    "get_adapter",
    "load_model_overrides",
    "resolve_model",
    "resolve_provider_name",
    "set_adapter_override",
    "set_model_override",
]
