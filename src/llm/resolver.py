"""Single place that reads LLM_PROVIDER, API keys and Model overrides."""

from __future__ import annotations

import logging
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

logger = logging.getLogger(__name__)

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
        logger.debug("LLM Provider '%s' chosen by LLM_PROVIDER", explicit)
        return explicit

    configured = {
        name: env
        for name in _PROVIDERS
        if (env := next((env for env in _CREDENTIAL_ENVS[name] if os.getenv(env)), None))
    }
    if len(configured) == 1:
        name, env = next(iter(configured.items()))
        logger.debug("LLM Provider '%s' inferred from the only API key set (%s)", name, env)
        return name
    if configured:
        keys = " and ".join(configured.values())
        raise LLMConfigError(f"Both {keys} are set. Set LLM_PROVIDER to {' or '.join(configured)}.")
    # No key at all: default to Anthropic so the missing-key error names its env var.
    logger.debug("No LLM API key set; defaulting LLM Provider to 'anthropic'")
    return "anthropic"


def check_api_key() -> None:
    """Raise LLMConfigError naming the exact missing env var."""
    if _adapter_override is not None:
        return
    adapter_class = _adapter_class(resolve_provider_name())
    if not any(os.getenv(env) for env in adapter_class.credential_envs):
        logger.error("%s not found in environment or .env file", adapter_class.api_key_env)
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
        ("profile YAML", profile_model if task is AITask.SCORING else None),
        ("Settings override", (settings_overrides or {}).get(task)),
        (_MODEL_ENV[task], os.getenv(_MODEL_ENV[task])),
    ]
    for source, candidate in candidates:
        model = (candidate or "").strip()
        if model:
            _require_owned(provider, model)
            logger.debug("Model for %s: '%s' (from %s, provider=%s)", task.value, model, source, provider.name)
            return model
    model = provider.default_models[task]
    logger.debug("Model for %s: '%s' (provider default, provider=%s)", task.value, model, provider.name)
    return model


def _require_owned(provider, model: str) -> None:
    if not provider.owns_model(model):
        logger.error("Model '%s' does not belong to LLM Provider '%s'", model, provider.name)
        raise LLMConfigError(
            f"Model '{model}' does not belong to LLM Provider '{provider.name}'."
        )


_OVERRIDE_KEY = "model_override."


def load_model_overrides(store) -> dict[AITask, str]:
    """Settings-page Model overrides persisted app-side in the store's metadata."""
    overrides = {}
    for task in AITask:
        value = (store.get_metadata(_OVERRIDE_KEY + task.value) or "").strip()
        if value:
            overrides[task] = value
    return overrides


def set_model_override(store, task: AITask, model: str | None) -> None:
    """Set, or with an empty `model` clear, a Settings override. Rejects foreign Models."""
    model = (model or "").strip()
    if model:
        provider = _adapter_override or _adapter_class(resolve_provider_name())
        _require_owned(provider, model)
    store.set_metadata(_OVERRIDE_KEY + task.value, model)


def describe_active(store=None) -> dict:
    """Public, key-free view of the active LLM Provider and per-task Models.

    Never raises: a misconfiguration is reported as `configured: False` with the
    reason in `error`, so the UI can show an "AI not configured" state.
    """
    try:
        check_api_key()
        provider = _adapter_override or _adapter_class(resolve_provider_name())
        overrides = load_model_overrides(store) if store is not None else None
        models = {task.value: resolve_model(task, settings_overrides=overrides) for task in AITask}
    except (LLMConfigError, ImportError) as e:
        return {"configured": False, "provider": None, "provider_display_name": None,
                "models": None, "error": str(e)}
    return {"configured": True, "provider": provider.name,
            "provider_display_name": provider.display_name, "models": models, "error": None}
