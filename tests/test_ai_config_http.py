import pytest
from fastapi.testclient import TestClient

from api.main import app
from src.llm import set_adapter_override
from tests.fake_llm import FakeLLMAdapter


@pytest.fixture(autouse=True)
def _reset_adapter():
    yield
    set_adapter_override(None)


def _clear_env(monkeypatch):
    for var in ("LLM_PROVIDER", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY",
                "SCORING_MODEL", "WIZARD_MODEL", "STATS_MODEL"):
        monkeypatch.delenv(var, raising=False)


def test_reports_active_provider_and_models_without_the_key(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("GOOGLE_API_KEY", "secret-gemini-key")
    monkeypatch.setenv("WIZARD_MODEL", "gemini-custom")

    with TestClient(app) as client:
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


def test_reports_fake_adapter_via_override():
    set_adapter_override(FakeLLMAdapter())
    with TestClient(app) as client:
        body = client.get("/api/ai-config").json()
    assert body["configured"] is True
    assert body["provider"] == "fake"
    assert body["models"] == {"scoring": "fake-model", "wizard": "fake-model", "stats": "fake-model"}


def test_reports_not_configured_when_key_missing(monkeypatch):
    _clear_env(monkeypatch)

    with TestClient(app) as client:
        response = client.get("/api/ai-config")

    body = response.json()
    assert response.status_code == 200
    assert body["configured"] is False
    assert "ANTHROPIC_API_KEY" in body["error"]
    assert body["models"] is None


def test_reports_not_configured_when_both_keys_and_no_choice(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "a")
    monkeypatch.setenv("GOOGLE_API_KEY", "g")

    with TestClient(app) as client:
        body = client.get("/api/ai-config").json()

    assert body["configured"] is False
    assert "LLM_PROVIDER" in body["error"]
