import json
from pathlib import Path

import fitz
import pytest

from fastapi.testclient import TestClient

from api.main import app
from api.routers import wizard as wizard_router
from src.llm import LLMAPIError, LLMRateLimitError, set_adapter_override
from tests.fake_llm import FakeLLMAdapter


@pytest.fixture(autouse=True)
def _reset_adapter():
    yield
    set_adapter_override(None)


def _pdf_bytes(text: str) -> bytes:
    doc = fitz.open()
    doc.new_page().insert_textbox(fitz.Rect(50, 50, 550, 800), text)
    data = doc.tobytes()
    doc.close()
    return data


_LONG_CV = "Senior Backend Engineer with many years of platform experience " * 12


def _llm_cv_json() -> str:
    """What the model returns: the analysis minus fields the router fills in."""
    payload = _sample_cv_analysis_payload()
    del payload["page_count"], payload["extraction_method"]
    return json.dumps(payload)


def _analyze(client, pdf: bytes | None = None):
    return client.post(
        "/api/wizard/analyze-cv",
        files={"file": ("cv.pdf", pdf or _pdf_bytes(_LONG_CV), "application/pdf")},
    )


def _sample_cv_analysis_payload() -> dict:
    return {
        "page_count": 1,
        "current_role": "Senior Backend Engineer",
        "experience_years": 8,
        "experience_summary": "Backend engineer with platform experience.",
        "experience": [
            {
                "company": "Example",
                "role": "Senior Backend Engineer",
                "dates": "2021 - Present",
                "industry": "SaaS",
                "highlights": ["Built APIs"],
            }
        ],
        "skills": {"Backend": ["Python", "PostgreSQL"]},
        "education": [],
        "portfolio": [],
        "spoken_languages": ["English"],
        "inferred_seniority": "senior",
        "suggested_target_roles": ["Senior Backend Engineer"],
        "suggested_title_patterns": {"high_confidence": [], "broad": []},
        "suggested_description_signals": [],
        "suggested_exclusions": [],
        "suggested_skill_gaps": [],
        "suggested_career_direction": "Stay on backend/platform path.",
        "suggested_narratives": {},
        "suggested_good_match_signals": ["Distributed Systems"],
        "suggested_lower_fit_signals": ["Heavy on-call"],
        "extraction_method": "text",
    }


def _sample_user_preferences_payload() -> dict:
    return {
        "targetRoles": ["Senior Backend Engineer"],
        "seniority": ["senior"],
        "location": "Berlin, Germany",
        "baseCity": "Berlin",
        "baseCountry": "Germany",
        "workAuth": "eu_citizen",
        "remotePref": ["remote", "hybrid"],
        "primaryRemotePref": "remote",
        "timezonePref": "overlap_strict",
        "targetRegions": ["Europe"],
        "excludedRegions": [],
        "industries": ["SaaS"],
        "careerDirection": "Backend/platform growth.",
        "careerGoal": "stay",
        "careerDirectionEdited": False,
        "goodMatchSignals": ["Distributed Systems"],
        "goodMatchSignalsConfirmed": False,
        "companyQualitySignals": [],
        "allowLowerSeniorityAtStrategicCompanies": False,
        "dealBreakers": ["Heavy on-call"],
        "dealBreakersConfirmed": False,
        "enableStandardExclusions": True,
        "additionalContext": None,
    }


def _write_example_profile(base_dir: Path) -> None:
    example_dir = base_dir / "example"
    example_dir.mkdir(parents=True, exist_ok=True)
    (example_dir / "search_config.yaml").write_text("keywords: {}\n", encoding="utf-8")
    (example_dir / "profile_doc.md").write_text("# Candidate Profile\n", encoding="utf-8")
    (example_dir / "scoring_philosophy.md").write_text("Score by evidence.\n", encoding="utf-8")
    (example_dir / "companies.yaml").write_text("greenhouse: []\n", encoding="utf-8")


def test_wizard_generate_save_state_and_template_endpoints(monkeypatch, tmp_path):
    _write_example_profile(tmp_path)
    monkeypatch.setattr(wizard_router, "PROFILES_DIR", tmp_path)

    payload = {
        "profile_name": "default",
        "cv_analysis": _sample_cv_analysis_payload(),
        "user_preferences": _sample_user_preferences_payload(),
    }

    with TestClient(app) as client:
        generate_response = client.post("/api/wizard/generate-profile", json=payload)

        assert generate_response.status_code == 200
        generated = generate_response.json()
        assert "keywords:" in generated["profile_yaml"]
        assert "Senior Backend Engineer" in generated["profile_doc"]

        save_response = client.post(
            "/api/wizard/save-profile",
            json={
                **payload,
                "profile_yaml": generated["profile_yaml"],
                "profile_doc": generated["profile_doc"],
            },
        )

        assert save_response.status_code == 200
        assert (tmp_path / "default" / "profile_doc.md").exists()
        assert (tmp_path / "default" / "cv_analysis.json").exists()
        assert (tmp_path / "default" / "preferences.json").exists()

        state_response = client.get("/api/wizard/state", params={"profile": "default"})
        template_response = client.get("/api/wizard/template")

        assert state_response.status_code == 200
        state = state_response.json()
        assert state["profile_name"] == "default"
        assert state["cv_analysis"]["current_role"] == "Senior Backend Engineer"
        assert state["user_preferences"]["baseCity"] == "Berlin"

        assert template_response.status_code == 200
        assert template_response.json()["profile_yaml"] == "keywords: {}\n"


def test_wizard_refine_profile_uses_mocked_llm_response(monkeypatch, tmp_path):
    _write_example_profile(tmp_path)
    monkeypatch.setattr(wizard_router, "PROFILES_DIR", tmp_path)
    fake = FakeLLMAdapter(
        ["""{
              "profile_doc_sections": {
                "Experience Summary": "Refined summary"
              },
              "search_config_keywords": {
                "title_patterns": {
                  "high_confidence": ["\\\\bsdet\\\\b"],
                  "broad": ["\\\\bqa\\\\s+engineer\\\\b"]
                },
                "description_signals": {
                  "patterns": ["test automation"]
                }
              },
              "changes_made": ["Refined focus areas"]
            }"""]
    )
    set_adapter_override(fake)

    with TestClient(app) as client:
        response = client.post(
            "/api/wizard/refine-profile",
            json={
                "cv_analysis": _sample_cv_analysis_payload(),
                "user_preferences": _sample_user_preferences_payload(),
                "draft_doc": "## Experience Summary\nOld summary\n\n## Role Target\nLocked",
                "draft_yaml": (
                    "# Generated search_config.yaml\n"
                    "keywords:\n"
                    "  title_patterns:\n"
                    "    high_confidence:\n"
                    "      - old\n"
                    "    broad: []\n"
                    "  description_signals:\n"
                    "    min_matches: 1\n"
                    "    patterns: []\n"
                ),
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert "Refined summary" in payload["profile_doc"]
        assert "## Role Target\nLocked" in payload["profile_doc"]
        assert "\\bsdet\\b" in payload["profile_yaml"]
        assert payload["changes_made"] == ["Refined focus areas"]
        assert fake.calls[0]["timeout"] == 120.0


def test_analyze_cv_uses_adapter_and_wizard_model():
    fake = FakeLLMAdapter([_llm_cv_json()])
    set_adapter_override(fake)

    with TestClient(app) as client:
        response = _analyze(client)

    assert response.status_code == 200
    assert response.json()["current_role"] == "Senior Backend Engineer"
    assert response.json()["extraction_method"] == "text"
    assert fake.calls[0]["model"] == "fake-model"
    assert fake.calls[0]["timeout"] == 120.0


def test_analyze_cv_retries_invalid_json_once_with_fix_up():
    fake = FakeLLMAdapter(["not json", _llm_cv_json()])
    set_adapter_override(fake)

    with TestClient(app) as client:
        response = _analyze(client)

    assert response.status_code == 200
    assert len(fake.calls) == 2
    assert [c["timeout"] for c in fake.calls] == [120.0, 120.0]
    assert fake.calls[1]["messages"][1] == {"role": "assistant", "content": "not json"}


def test_analyze_cv_vision_fallback_sends_neutral_image_blocks():
    fake = FakeLLMAdapter([_llm_cv_json()])
    set_adapter_override(fake)

    with TestClient(app) as client:
        response = _analyze(client, _pdf_bytes("x"))

    assert response.status_code == 200
    content = fake.calls[0]["messages"][0]["content"]
    assert content[0]["type"] == "image" and content[0]["media_type"] == "image/png"
    assert "source" not in content[0]


def test_analyze_cv_maps_rate_limit_and_api_errors_to_502(monkeypatch):
    async def no_sleep(_):
        pass

    monkeypatch.setattr(wizard_router.asyncio, "sleep", no_sleep)

    set_adapter_override(FakeLLMAdapter([LLMRateLimitError()] * 3))
    with TestClient(app) as client:
        response = _analyze(client)
    assert response.status_code == 502
    assert "Rate Limit" in response.json()["detail"]

    set_adapter_override(FakeLLMAdapter([LLMAPIError("boom")] * 3))
    with TestClient(app) as client:
        response = _analyze(client)
    assert response.status_code == 502
    assert "API Error: boom" in response.json()["detail"]


def test_analyze_cv_missing_key_returns_ai_not_configured(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    with TestClient(app) as client:
        response = _analyze(client)

    assert response.status_code == 503
    assert response.json()["detail"].startswith("AI not configured")
    assert "ANTHROPIC_API_KEY" in response.json()["detail"]


def test_refine_profile_without_key_falls_back_to_drafts(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    with TestClient(app) as client:
        response = client.post(
            "/api/wizard/refine-profile",
            json={
                "cv_analysis": _sample_cv_analysis_payload(),
                "user_preferences": _sample_user_preferences_payload(),
                "draft_doc": "## Experience Summary\nOld",
                "draft_yaml": "keywords:\n  title_patterns:\n    high_confidence: []\n    broad: []\n",
            },
        )

    assert response.status_code == 200
    assert response.json()["profile_doc"] == "## Experience Summary\nOld"
    assert response.json()["changes_made"][0].startswith("Refinement skipped")


def test_wizard_generated_profile_scores_with_the_gemini_default(monkeypatch, tmp_path):
    for var in ("LLM_PROVIDER", "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "SCORING_MODEL"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "gemini-key")
    _write_example_profile(tmp_path)
    monkeypatch.setattr(wizard_router, "PROFILES_DIR", tmp_path)
    monkeypatch.setattr("api.deps.PROFILES_DIR", tmp_path)
    payload = {
        "profile_name": "default",
        "cv_analysis": _sample_cv_analysis_payload(),
        "user_preferences": _sample_user_preferences_payload(),
    }

    with TestClient(app) as client:
        generated = client.post("/api/wizard/generate-profile", json=payload).json()
        saved = client.post("/api/wizard/save-profile", json={**payload, **generated})
        assert saved.status_code == 200

        body = client.get("/api/ai-config", params={"profile": "default"}).json()

    assert body["configured"] is True
    assert body["provider"] == "gemini"
    assert body["models"]["scoring"] == "gemini-3.8-flash"
    assert body["scoring_from_profile"] is False
