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


def _clear_env(monkeypatch):
    for var in ("LLM_PROVIDER", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY",
                "SCORING_MODEL", "WIZARD_MODEL", "STATS_MODEL"):
        monkeypatch.delenv(var, raising=False)


def test_reports_active_llm_provider_and_models_without_the_key(monkeypatch, client):
    _clear_env(monkeypatch)
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
    _clear_env(monkeypatch)

    response = client.get("/api/ai-config")

    body = response.json()
    assert response.status_code == 200
    assert body["configured"] is False
    assert "ANTHROPIC_API_KEY" in body["error"]
    assert body["models"] is None


def test_reports_not_configured_when_both_keys_and_no_choice(monkeypatch, client):
    _clear_env(monkeypatch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "a")
    monkeypatch.setenv("GOOGLE_API_KEY", "g")

    body = client.get("/api/ai-config").json()

    assert body["configured"] is False
    assert "LLM_PROVIDER" in body["error"]


def _gemini(monkeypatch):
    _clear_env(monkeypatch)
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

    assert stale["configured"] is False
    assert stale["overrides"] == {"scoring": "gemini-custom"}
    assert cleared["configured"] is True
    assert cleared["overrides"] == {}
