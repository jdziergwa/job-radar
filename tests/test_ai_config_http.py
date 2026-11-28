import sys

import pytest

from api.routers import ai_config as ai_config_router
from src.llm import set_adapter_override
from tests.fake_llm import FakeLLMAdapter

pytestmark = pytest.mark.api


@pytest.fixture(autouse=True)
def _reset_adapter():
    yield
    set_adapter_override(None)


@pytest.fixture(autouse=True)
def _bind_store(bind_store):
    bind_store(ai_config_router)


@pytest.fixture(autouse=True)
def _empty_profiles_dir(monkeypatch, tmp_path):
    """No profile YAML unless a test writes one."""
    monkeypatch.setattr("api.deps.PROFILES_DIR", tmp_path)


@pytest.fixture(autouse=True)
def _clean_env(no_ai_key):
    """Every test starts with no LLM Provider key; each sets up the one it needs."""


def test_reports_active_llm_provider_and_models_without_the_key(monkeypatch, client):
    monkeypatch.setenv("GOOGLE_API_KEY", "secret-gemini-key")
    monkeypatch.setenv("WIZARD_MODEL", "gemini-custom")

    response = client.get("/api/ai-config")

    body = response.json()
    assert response.status_code == 200
    assert body["configured"] is True
    assert body["provider"] == "gemini"
    assert body["provider_display_name"] == "Gemini"
    assert body["models"]["wizard"] == "gemini-custom"
    assert set(body["models"]) == {"scoring", "wizard", "stats"}
    assert "secret-gemini-key" not in response.text
    assert body["error"] is None


def test_reports_fake_adapter_via_override(client):
    set_adapter_override(FakeLLMAdapter())
    body = client.get("/api/ai-config").json()
    assert body["configured"] is True
    assert body["provider"] == "fake"
    assert body["models"] == {"scoring": "fake-model", "wizard": "fake-model", "stats": "fake-model"}


def test_reports_not_configured_when_key_missing(monkeypatch, client):

    response = client.get("/api/ai-config")

    body = response.json()
    assert response.status_code == 200
    assert body["configured"] is False
    assert "ANTHROPIC_API_KEY" in body["error"]
    assert "GOOGLE_API_KEY" in body["error"]
    assert "LLM_PROVIDER" in body["error"]
    assert body["models"] is None


def test_reports_not_configured_when_both_keys_and_no_choice(monkeypatch, client):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "a")
    monkeypatch.setenv("GOOGLE_API_KEY", "g")

    body = client.get("/api/ai-config").json()

    assert body["configured"] is False
    assert "LLM_PROVIDER" in body["error"]


def _gemini(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "g")


def test_setting_a_model_override_persists_and_is_reported(monkeypatch, client):
    _gemini(monkeypatch)
    put = client.put("/api/ai-config/models/scoring", json={"model": "gemini-custom"})
    body = client.get("/api/ai-config").json()

    assert put.status_code == 200
    assert body["models"]["scoring"] == "gemini-custom"
    assert body["overrides"] == {"scoring": "gemini-custom"}


def test_clearing_an_override_restores_the_default(monkeypatch, client):
    _gemini(monkeypatch)
    default = client.get("/api/ai-config").json()["models"]["scoring"]
    client.put("/api/ai-config/models/scoring", json={"model": "gemini-custom"})
    body = client.put("/api/ai-config/models/scoring", json={"model": None}).json()

    assert body["models"]["scoring"] == default
    assert body["overrides"] == {}


def test_model_from_another_llm_provider_is_rejected_with_a_clear_message(monkeypatch, client):
    _gemini(monkeypatch)
    response = client.put("/api/ai-config/models/wizard", json={"model": "claude-sonnet-4-5"})
    body = client.get("/api/ai-config").json()

    assert response.status_code == 422
    assert "claude-sonnet-4-5" in response.json()["detail"]
    assert "gemini" in response.json()["detail"]
    assert body["overrides"] == {}


def test_missing_llm_provider_sdk_on_set_override_is_422(monkeypatch, client):
    _gemini(monkeypatch)
    monkeypatch.setitem(sys.modules, "src.llm.gemini_adapter", None)  # makes importing it fail

    response = client.put("/api/ai-config/models/wizard", json={"model": "gemini-custom"})

    assert response.status_code == 422
    assert "pip install google-genai" in response.json()["detail"]


def test_settings_override_beats_env_override(monkeypatch, client):
    _gemini(monkeypatch)
    monkeypatch.setenv("STATS_MODEL", "gemini-from-env")
    client.put("/api/ai-config/models/stats", json={"model": "gemini-from-settings"})
    body = client.get("/api/ai-config").json()

    assert body["models"]["stats"] == "gemini-from-settings"


def test_stale_override_from_another_llm_provider_can_still_be_cleared(monkeypatch, client):
    _gemini(monkeypatch)
    client.put("/api/ai-config/models/scoring", json={"model": "gemini-custom"})
    monkeypatch.delenv("GOOGLE_API_KEY")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "a")
    stale = client.get("/api/ai-config").json()
    cleared = client.put("/api/ai-config/models/scoring", json={"model": ""}).json()

    assert stale["configured"] is True
    assert set(stale["model_errors"]) == {"scoring"}
    assert stale["overrides"] == {"scoring": "gemini-custom"}
    assert cleared["configured"] is True
    assert cleared["model_errors"] == {}
    assert cleared["overrides"] == {}


def _write_profile(tmp_path, monkeypatch, scoring_model):
    profile_dir = tmp_path / "default"
    profile_dir.mkdir()
    scoring = f"scoring:\n  model: {scoring_model}\n" if scoring_model else "scoring:\n  concurrency: 5\n"
    (profile_dir / "search_config.yaml").write_text(scoring, encoding="utf-8")
    monkeypatch.setattr("api.deps.PROFILES_DIR", tmp_path)


def test_profile_scoring_model_is_reported_and_flagged_as_from_profile(monkeypatch, client, tmp_path):
    monkeypatch.setenv("GOOGLE_API_KEY", "k")
    _write_profile(tmp_path, monkeypatch, "gemini-from-profile")

    body = client.get("/api/ai-config").json()

    assert body["configured"] is True
    assert body["models"]["scoring"] == "gemini-from-profile"
    assert body["scoring_from_profile"] is True
    assert body["models"]["wizard"] == "gemini-3.8-flash"


def test_profile_without_scoring_model_is_not_flagged(monkeypatch, client, tmp_path):
    monkeypatch.setenv("GOOGLE_API_KEY", "k")
    _write_profile(tmp_path, monkeypatch, None)

    body = client.get("/api/ai-config").json()

    assert body["models"]["scoring"] == "gemini-3.8-flash"
    assert body["scoring_from_profile"] is False


def test_foreign_profile_scoring_model_only_makes_scoring_unavailable(monkeypatch, client, tmp_path):
    monkeypatch.setenv("GOOGLE_API_KEY", "k")
    _write_profile(tmp_path, monkeypatch, "claude-haiku-5-5")

    response = client.get("/api/ai-config")

    body = response.json()
    assert response.status_code == 200
    assert body["configured"] is True
    assert body["provider"] == "gemini"
    assert body["error"] is None
    assert body["models"]["scoring"] == "claude-haiku-5-5"
    assert body["models"]["wizard"] == "gemini-3.8-flash"
    assert set(body["model_errors"]) == {"scoring"}
    assert "profile YAML `scoring.model`" in body["model_errors"]["scoring"]


@pytest.mark.parametrize("task", ["scoring", "wizard", "stats"])
def test_foreign_env_model_flags_only_its_ai_task(monkeypatch, client, task):
    _gemini(monkeypatch)
    monkeypatch.setenv(f"{task.upper()}_MODEL", "claude-sonnet-4-5")

    body = client.get("/api/ai-config").json()

    assert body["configured"] is True
    assert set(body["model_errors"]) == {task}
    assert f"{task.upper()}_MODEL" in body["model_errors"][task]


def test_model_errors_is_empty_when_all_models_are_fine(monkeypatch, client):
    _gemini(monkeypatch)
    assert client.get("/api/ai-config").json()["model_errors"] == {}


def test_missing_llm_provider_sdk_is_reported_not_configured(monkeypatch, client):
    _gemini(monkeypatch)
    monkeypatch.setitem(sys.modules, "src.llm.gemini_adapter", None)  # makes importing it fail

    body = client.get("/api/ai-config").json()

    assert body["configured"] is False
    assert "pip install google-genai" in body["error"]
