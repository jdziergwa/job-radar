import pytest

from src.claude import HAIKU_MODEL, SONNET_MODEL
from src.llm import (
    AITask,
    LLMConfigError,
    check_api_key,
    resolve_model,
    resolve_provider_name,
)

ENV_VARS = [
    "LLM_PROVIDER", "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "GOOGLE_API_KEY",
    "SCORING_MODEL", "WIZARD_MODEL", "STATS_MODEL",
]


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for name in ENV_VARS:
        monkeypatch.delenv(name, raising=False)


def test_llm_provider_defaults_to_anthropic_when_only_its_key_is_set(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    assert resolve_provider_name() == "anthropic"


def test_explicit_llm_provider_wins(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    assert resolve_provider_name() == "anthropic"


def test_unknown_llm_provider_is_rejected(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "nope")
    with pytest.raises(LLMConfigError, match="nope.*Supported: anthropic, gemini"):
        resolve_provider_name()


def test_no_key_and_no_llm_provider_falls_back_to_anthropic_default():
    # Keeps the existing behaviour: the missing-key error then names ANTHROPIC_API_KEY.
    assert resolve_provider_name() == "anthropic"


def test_missing_key_error_names_exact_env_var():
    with pytest.raises(LLMConfigError, match="ANTHROPIC_API_KEY"):
        check_api_key()


def test_check_api_key_passes_when_set(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    check_api_key()


def test_check_api_key_accepts_anthropic_auth_token(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "t")
    check_api_key()


def test_default_models_per_task():
    assert resolve_model(AITask.SCORING) == HAIKU_MODEL
    assert resolve_model(AITask.WIZARD) == SONNET_MODEL
    assert resolve_model(AITask.STATS) == HAIKU_MODEL


def test_env_overrides_default(monkeypatch):
    monkeypatch.setenv("SCORING_MODEL", "claude-sonnet-4-5")
    assert resolve_model(AITask.SCORING) == "claude-sonnet-4-5"


def test_settings_override_beats_env(monkeypatch):
    monkeypatch.setenv("SCORING_MODEL", "claude-env")
    result = resolve_model(AITask.SCORING, settings_overrides={AITask.SCORING: "claude-settings"})
    assert result == "claude-settings"


def test_profile_model_beats_settings_and_env(monkeypatch):
    monkeypatch.setenv("SCORING_MODEL", "claude-env")
    result = resolve_model(
        AITask.SCORING,
        profile_model="claude-profile",
        settings_overrides={AITask.SCORING: "claude-settings"},
    )
    assert result == "claude-profile"


def test_blank_overrides_are_ignored(monkeypatch):
    monkeypatch.setenv("WIZARD_MODEL", "  ")
    assert resolve_model(AITask.WIZARD, profile_model="") == SONNET_MODEL


def test_model_from_another_llm_provider_fails_fast(monkeypatch):
    monkeypatch.setenv("SCORING_MODEL", "gemini-3.8-flash")
    with pytest.raises(LLMConfigError, match="gemini-3.8-flash"):
        resolve_model(AITask.SCORING)


def test_gemini_selected_explicitly(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    assert resolve_provider_name() == "gemini"
    assert resolve_model(AITask.SCORING) == "gemini-3.8-flash"
    assert resolve_model(AITask.WIZARD) == "gemini-3.1-pro-preview"


def test_auto_detects_gemini_when_only_its_key_is_set(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "k")
    assert resolve_provider_name() == "gemini"


def test_both_keys_without_llm_provider_asks_user_to_choose(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    monkeypatch.setenv("GOOGLE_API_KEY", "k")
    with pytest.raises(LLMConfigError, match="LLM_PROVIDER"):
        resolve_provider_name()


def test_anthropic_auth_token_counts_for_detection(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "t")
    assert resolve_provider_name() == "anthropic"
    monkeypatch.setenv("GOOGLE_API_KEY", "k")
    with pytest.raises(LLMConfigError, match="ANTHROPIC_AUTH_TOKEN and GOOGLE_API_KEY"):
        resolve_provider_name()


def test_explicit_llm_provider_resolves_ambiguity(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    monkeypatch.setenv("GOOGLE_API_KEY", "k")
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    assert resolve_provider_name() == "gemini"


def test_gemini_missing_key_names_exact_env_var(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    with pytest.raises(LLMConfigError, match="GOOGLE_API_KEY"):
        check_api_key()


def test_claude_model_with_gemini_fails_fast(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("SCORING_MODEL", "claude-sonnet-4-5")
    with pytest.raises(LLMConfigError, match="claude-sonnet-4-5"):
        resolve_model(AITask.SCORING)


def test_profile_model_beats_settings_override_and_settings_beats_env(monkeypatch):
    from src.llm import AITask, resolve_model

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "g")
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("SCORING_MODEL", "gemini-env")
    overrides = {AITask.SCORING: "gemini-settings"}

    assert resolve_model(AITask.SCORING, settings_overrides=overrides) == "gemini-settings"
    assert resolve_model(AITask.SCORING, profile_model="gemini-profile", settings_overrides=overrides) == "gemini-profile"


def test_foreign_settings_override_fails_fast(monkeypatch):
    from src.llm import AITask, LLMConfigError, resolve_model

    monkeypatch.setenv("GOOGLE_API_KEY", "g")
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    with pytest.raises(LLMConfigError, match="does not belong"):
        resolve_model(AITask.WIZARD, settings_overrides={AITask.WIZARD: "claude-sonnet-4-5"})


def test_foreign_profile_model_error_names_profile_yaml_as_source(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "g")
    monkeypatch.delenv("LLM_PROVIDER", raising=False)

    with pytest.raises(LLMConfigError, match="from profile YAML `scoring.model`\\) does not belong to LLM Provider 'gemini'"):
        resolve_model(AITask.SCORING, profile_model=HAIKU_MODEL)
