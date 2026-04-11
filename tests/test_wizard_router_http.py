from pathlib import Path

from fastapi.testclient import TestClient

from api.main import app
from api.routers import wizard as wizard_router


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


class _FakeAnthropicResponse:
    def __init__(self, text: str) -> None:
        self.content = [type("Block", (), {"text": text})()]


class _FakeAnthropicClient:
    def __init__(self, response_text: str) -> None:
        self._response_text = response_text
        self.messages = self

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def create(self, *args, **kwargs):
        return _FakeAnthropicResponse(self._response_text)


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
    monkeypatch.setattr(
        wizard_router,
        "AsyncAnthropic",
        lambda *args, **kwargs: _FakeAnthropicClient(
            """{
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
            }"""
        ),
    )

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
