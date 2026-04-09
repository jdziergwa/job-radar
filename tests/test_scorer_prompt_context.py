import sys
import types


if "anthropic" not in sys.modules:
    anthropic = types.ModuleType("anthropic")

    class AsyncAnthropic:  # pragma: no cover - stub for import only
        pass

    anthropic.AsyncAnthropic = AsyncAnthropic
    anthropic.Anthropic = AsyncAnthropic
    anthropic.RateLimitError = Exception
    anthropic.APIError = Exception
    sys.modules["anthropic"] = anthropic

from src.models import CandidateJob
from src.scorer import _build_system_prompt, _build_user_message


def test_build_system_prompt_includes_scoring_context_block():
    prompt = _build_system_prompt(
        "Scoring instructions",
        "Profile doc",
        {
            "keywords": {"title_patterns": {"high_confidence": [r"\bbackend\s+engineer\b"]}},
            "scoring_context": {
                "role_targets": {"core": ["Senior Backend Engineer"]},
                "work_setup": {
                    "preferred_setup": "remote",
                    "base_city": "Berlin",
                    "location_flexibility": {
                        "remote_first": True,
                        "hybrid": {"cross_border": "strong_penalty"},
                    },
                },
                "company_preferences": {
                    "preferred_signals": ["strong product company"],
                    "allow_lower_seniority_if_company_matches": True,
                },
            },
        },
    )

    text = prompt[0]["text"]

    assert "CANDIDATE PREFERENCES (from search_config.yaml):" in text
    assert "scoring_context:" in text
    assert "role_targets:" in text
    assert "preferred_setup: remote" in text
    assert "base_city: Berlin" in text
    assert "cross_border: strong_penalty" in text
    assert "company_preferences:" in text
    assert "strong product company" in text


def test_build_user_message_includes_location_context_when_available():
    message = _build_user_message(CandidateJob(
        db_id=1,
        ats_platform="ashby",
        company_slug="example",
        company_name="ExampleCo",
        job_id="role-1",
        title="Platform Engineer",
        location="Remote",
        company_metadata={
            "quality_signals": ["strong product company"],
            "source": "companies_yaml",
        },
        location_metadata={
            "raw_location": "Remote",
            "derived_geographic_signals": [
                "Restricted to North America",
                "Timezone overlap requirement mentioned",
            ],
        },
        url="https://example.com/jobs/1",
        description="<p>Example description</p>",
        posted_at=None,
        first_seen_at="2026-04-08T00:00:00",
    ))

    assert "Company Context:" in message
    assert "strong product company" in message
    assert "Location Context:" in message
    assert "raw_location: Remote" in message
    assert "Restricted to North America" in message
