"""Single place that reads LLM_PROVIDER, API keys and Model overrides."""

from __future__ import annotations

import importlib
import logging
import os
from dataclasses import dataclass
from typing import Mapping

from src.llm.base import AITask, LLMAdapter, LLMConfigError


@dataclass(frozen=True)
class _LLMProviderEntry:
    """One LLM Provider: lazy adapter import and the env vars that authenticate it."""

    display_name: str
    pip_package: str
    module: str
    class_name: str
    credential_envs: tuple[str, ...]  # the first is the one named in missing-key errors
    sdk_loggers: tuple[str, ...]  # the SDK's noisy loggers; named here so no SDK import is needed

    def adapter_class(self):
        """Imported lazily so only the active LLM Provider's SDK is needed."""
        try:
            return getattr(importlib.import_module(self.module), self.class_name)
        except ImportError as e:
            raise LLMConfigError(
                f"The {self.display_name} SDK isn't installed. Install it with: pip install {self.pip_package}"
            ) from e


_REGISTRY = {
    "anthropic": _LLMProviderEntry(
        "Anthropic", "anthropic", "src.llm.anthropic_adapter", "AnthropicAdapter", ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"),
        ("anthropic",),
    ),
    "gemini": _LLMProviderEntry("Gemini", "google-genai", "src.llm.gemini_adapter", "GeminiAdapter", ("GOOGLE_API_KEY",), ("google_genai",)),
}
_MODEL_ENV = {
    AITask.SCORING: "SCORING_MODEL",
    AITask.WIZARD: "WIZARD_MODEL",
    AITask.STATS: "STATS_MODEL",
}

logger = logging.getLogger(__name__)

_adapter_override: LLMAdapter | None = None


def set_adapter_override(adapter: LLMAdapter | None) -> None:
    """Inject an adapter (tests) that bypasses LLM Provider selection and key checks."""
    global _adapter_override
    _adapter_override = adapter


def sdk_logger_names() -> tuple[str, ...]:
    """Logger names of every LLM Provider SDK, so the CLI can quiet them without naming any."""
    return tuple(name for entry in _REGISTRY.values() for name in entry.sdk_loggers)


def describe_defaults(provider_name: str) -> dict:
    """Name, display name and default Models of a named LLM Provider (no key needed)."""
    adapter_class = _REGISTRY[provider_name].adapter_class()
    return {
        "provider": adapter_class.name,
        "provider_display_name": adapter_class.display_name,
        "models": {task.value: model for task, model in adapter_class.default_models.items()},
    }


def _active_adapter_or_class():
    """The injected test adapter instance, or the active LLM Provider's adapter class.

    Either way it has the class-level `name`, `display_name`, `default_models` and `owns_model`.
    """
    return _adapter_override or _REGISTRY[resolve_provider_name()].adapter_class()


def resolve_provider_name() -> str:
    explicit = os.getenv("LLM_PROVIDER", "").strip().lower()
    if explicit:
        if explicit not in _REGISTRY:
            supported = ", ".join(_REGISTRY)
            raise LLMConfigError(f"Unsupported LLM_PROVIDER '{explicit}'. Supported: {supported}.")
        logger.debug("LLM Provider '%s' chosen by LLM_PROVIDER", explicit)
        return explicit

    configured = {
        name: env
        for name, entry in _REGISTRY.items()
        if (env := next((env for env in entry.credential_envs if os.getenv(env)), None))
    }
    if len(configured) == 1:
        name, env = next(iter(configured.items()))
        logger.debug("LLM Provider '%s' inferred from the only API key set (%s)", name, env)
        return name
    if configured:
        keys = " and ".join(configured.values())
        raise LLMConfigError(f"Both {keys} are set. Set LLM_PROVIDER to {' or '.join(configured)}.")
    keys = [entry.credential_envs[0] for entry in _REGISTRY.values()]
    named = keys[0] if len(keys) == 1 else f"{', '.join(keys[:-1])} or {keys[-1]}"
    raise LLMConfigError(
        f"No LLM Provider API key found. Set {named} in your environment or .env file "
        "(set LLM_PROVIDER to choose when both are set)."
    )


def check_api_key() -> None:
    """Raise LLMConfigError naming the exact missing env var."""
    if _adapter_override is not None:
        return
    envs = _REGISTRY[resolve_provider_name()].credential_envs
    if not any(os.getenv(env) for env in envs):
        logger.error("%s not found in environment or .env file", envs[0])
        raise LLMConfigError(f"{envs[0]} not found in environment or .env file.")


def get_adapter() -> LLMAdapter:
    """Return the active adapter. Callers own it and should `await aclose()` it."""
    check_api_key()
    return _adapter_override or _active_adapter_or_class()()  # override is already an instance


def resolve_model(
    task: AITask,
    *,
    profile_model: str | None = None,
    settings_overrides: Mapping[AITask, str] | None = None,
) -> str:
    """Precedence: profile YAML (scoring), Settings override, env, LLM Provider default."""
    llm_provider = _active_adapter_or_class()
    model, source = _configured_model(task, llm_provider, profile_model, settings_overrides)
    if source is None:
        logger.debug("Model for %s: '%s' (default of LLM Provider '%s')", task.value, model, llm_provider.name)
        return model
    _require_owned(llm_provider, model, source)
    logger.debug("Model for %s: '%s' (from %s, LLM Provider '%s')", task.value, model, source, llm_provider.name)
    return model


def _configured_model(task, llm_provider, profile_model, settings_overrides) -> tuple[str, str | None]:
    """The Model an AI Task would use and where it came from (None source = LLM Provider default)."""
    candidates = [
        ("profile YAML `scoring.model`", profile_model if task is AITask.SCORING else None),
        ("Settings override", (settings_overrides or {}).get(task)),
        (_MODEL_ENV[task], os.getenv(_MODEL_ENV[task])),
    ]
    for source, candidate in candidates:
        model = (candidate or "").strip()
        if model:
            return model, source
    return llm_provider.default_models[task], None


def _require_owned(llm_provider, model: str, source: str | None = None) -> None:
    if not llm_provider.owns_model(model):
        logger.error("Model '%s' does not belong to LLM Provider '%s'", model, llm_provider.name)
        origin = f" (from {source})" if source else ""
        raise LLMConfigError(
            f"Model '{model}'{origin} does not belong to LLM Provider '{llm_provider.name}'."
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
        llm_provider = _active_adapter_or_class()
        _require_owned(llm_provider, model)
    store.set_metadata(_OVERRIDE_KEY + task.value, model)


def check_scoring_config(
    profile_model: str | None = None,
    settings_overrides: Mapping[AITask, str] | None = None,
) -> str:
    """The one check that the AI setup can score: LLM Provider, key and an owned Model.

    Returns the resolved scoring Model; raises LLMConfigError naming the problem.
    """
    check_api_key()
    return resolve_model(AITask.SCORING, profile_model=profile_model, settings_overrides=settings_overrides)


def describe_active(store=None, profile_model: str | None = None) -> dict:
    """Public, key-free view of the active LLM Provider and per-task Models.

    Never raises. `configured` means the LLM Provider resolves and its key is set; otherwise
    the reason is in `error`. A foreign Model only makes its own AI Task unavailable: it is
    shown in `models` and explained in `model_errors` (keyed by AI Task value).
    `profile_model` is the profile YAML `scoring.model`; when set it wins for scoring.
    """
    try:
        check_api_key()
        llm_provider = _active_adapter_or_class()
    except LLMConfigError as e:
        return {"configured": False, "provider": None, "provider_display_name": None,
                "models": None, "model_errors": {}, "error": str(e), "scoring_from_profile": False}
    overrides = load_model_overrides(store) if store is not None else None
    models, model_errors = {}, {}
    for task in AITask:
        try:
            models[task.value] = resolve_model(task, profile_model=profile_model, settings_overrides=overrides)
        except LLMConfigError as e:
            models[task.value] = _configured_model(task, llm_provider, profile_model, overrides)[0]
            model_errors[task.value] = str(e)
    return {"configured": True, "provider": llm_provider.name,
            "provider_display_name": llm_provider.display_name, "models": models,
            "model_errors": model_errors, "error": None,
            "scoring_from_profile": bool((profile_model or "").strip())}
