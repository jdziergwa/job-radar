"""Single place that reads LLM_PROVIDER, API keys and Model overrides."""

from __future__ import annotations

import os
from typing import Mapping

from src.llm.base import AITask, LLMAdapter, LLMConfigError

_PROVIDERS = ("anthropic", "gemini")
# Env vars that authenticate each LLM Provider, mirrored from the adapters so detection
# does not import every vendor SDK.
_CREDENTIAL_ENVS = {"anthropic": ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"), "gemini": ("GOOGLE_API_KEY",)}
_MODEL_ENV = {
    AITask.SCORING: "SCORING_MODEL",
    AITask.WIZARD: "WIZARD_MODEL",
    AITask.STATS: "STATS_MODEL",
}

_adapter_override: LLMAdapter | None = None


def set_adapter_override(adapter: LLMAdapter | None) -> None:
    """Inject an adapter (tests) that bypasses provider selection and key checks."""
    global _adapter_override
    _adapter_override = adapter


def _adapter_class(name: str):
    """Adapters are imported lazily so only the active vendor SDK is needed."""
    if name == "anthropic":
        from src.llm.anthropic_adapter import AnthropicAdapter

        return AnthropicAdapter
    if name == "gemini":
        from src.llm.gemini_adapter import GeminiAdapter

        return GeminiAdapter
    raise LLMConfigError(f"Unsupported LLM_PROVIDER '{name}'.")


def resolve_provider_name() -> str:
    explicit = os.getenv("LLM_PROVIDER", "").strip().lower()
    if explicit:
        if explicit not in _PROVIDERS:
            supported = ", ".join(_PROVIDERS)
            raise LLMConfigError(f"Unsupported LLM_PROVIDER '{explicit}'. Supported: {supported}.")
        return explicit

    configured = {
        name: env
        for name in _PROVIDERS
        if (env := next((env for env in _CREDENTIAL_ENVS[name] if os.getenv(env)), None))
    }
    if len(configured) == 1:
        return next(iter(configured))
    if configured:
        keys = " and ".join(configured.values())
        raise LLMConfigError(f"Both {keys} are set. Set LLM_PROVIDER to {' or '.join(configured)}.")
    # No key at all: default to Anthropic so the missing-key error names its env var.
    return "anthropic"


def check_api_key() -> None:
    """Raise LLMConfigError naming the exact missing env var."""
    if _adapter_override is not None:
        return
    adapter_class = _adapter_class(resolve_provider_name())
    if not any(os.getenv(env) for env in adapter_class.credential_envs):
        raise LLMConfigError(f"{adapter_class.api_key_env} not found in environment or .env file.")


def get_adapter() -> LLMAdapter:
    """Return the active adapter. Callers own it and should `await aclose()` it."""
    if _adapter_override is not None:
        return _adapter_override
    check_api_key()
    return _adapter_class(resolve_provider_name())()


def resolve_model(
    task: AITask,
    *,
    profile_model: str | None = None,
    settings_overrides: Mapping[AITask, str] | None = None,
) -> str:
    """Precedence: profile YAML (scoring), Settings override, env, provider default."""
    provider = _adapter_override or _adapter_class(resolve_provider_name())

    candidates = [
        profile_model if task is AITask.SCORING else None,
        (settings_overrides or {}).get(task),
        os.getenv(_MODEL_ENV[task]),
    ]
    for candidate in candidates:
        model = (candidate or "").strip()
        if model:
            _require_owned(provider, model)
            return model
    return provider.default_models[task]


def _require_owned(provider, model: str) -> None:
    if not provider.owns_model(model):
        raise LLMConfigError(
            f"Model '{model}' does not belong to LLM Provider '{provider.name}'."
        )


def describe_active() -> dict:
    """Public, key-free view of the active LLM Provider and per-task Models.

    Never raises: a misconfiguration is reported as `configured: False` with the
    reason in `error`, so the UI can show an "AI not configured" state.
    """
    try:
        check_api_key()
        provider = _adapter_override or _adapter_class(resolve_provider_name())
        models = {task.value: resolve_model(task) for task in AITask}
    except (LLMConfigError, ImportError) as e:
        return {"configured": False, "provider": None, "provider_display_name": None,
                "models": None, "error": str(e)}
    return {"configured": True, "provider": provider.name,
            "provider_display_name": provider.display_name, "models": models, "error": None}
