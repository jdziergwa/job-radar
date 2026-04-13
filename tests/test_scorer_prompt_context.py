import sys
import types
from pathlib import Path


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
from src.scorer import (
    _build_batch_user_message,
    _build_system_prompt,
    _build_user_message,
    _compact_description_for_scoring,
)


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
            "output": {"terminal": True},
            "scoring": {"concurrency": 25},
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
    assert "description_signals" not in text
    assert "output:" not in text
    assert "concurrency: 25" not in text


def test_build_user_message_includes_compact_location_context_when_available():
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
            "location_fragments": ["Remote", "United States", "Canada"],
        },
        url="https://example.com/jobs/1",
        description="<p>Example description</p>",
        posted_at=None,
        first_seen_at="2026-04-08T00:00:00",
    ))

    assert "Company Context:" in message
    assert "strong product company" in message
    assert "source: companies_yaml" not in message
    assert "Location Context:" in message
    assert "Restricted to North America" in message
    assert "Timezone overlap requirement mentioned" in message
    assert "raw_location: Remote" not in message
    assert "location_fragments:" not in message


def test_build_batch_user_message_includes_salary_context():
    message = _build_batch_user_message([
        CandidateJob(
            db_id=1,
            ats_platform="ashby",
            company_slug="example",
            company_name="ExampleCo",
            job_id="role-1",
            title="Platform Engineer",
            location="Remote",
            url="https://example.com/jobs/1",
            description="<p>Example description</p>",
            posted_at=None,
            first_seen_at="2026-04-08T00:00:00",
            salary="€80k-€95k",
        )
    ])

    assert "Salary (extracted): €80k-€95k" in message


def test_compact_description_normalizes_and_truncates():
    compacted = _compact_description_for_scoring(
        """
        We are hiring a Senior Platform Engineer.

        We are an equal opportunity employer and all qualified applicants will receive
        consideration without regard to race, religion, sex, sexual orientation, gender
        identity, national origin, disability, or veteran status.

        Please review our privacy policy and GDPR notice before applying.

        Responsibilities:
          Build Python services for platform tooling.
        """,
        max_chars=800,
    )

    # Important content is preserved
    assert "Senior Platform Engineer" in compacted
    assert "Build Python services for platform tooling." in compacted
    # Whitespace is normalized
    assert "  " not in compacted


def test_compact_description_preserves_order_and_truncates():
    compacted = _compact_description_for_scoring(
        """
        About us: We are building the future of collaboration across multiple markets and
        geographies with a mission-driven team and world-class culture.

        Responsibilities:
        You will design and maintain Python services, PostgreSQL schemas, and CI pipelines.

        Requirements:
        You have 5+ years of backend engineering experience with Python, Docker, and AWS.

        Location:
        This role is remote in EMEA with a requirement for CET timezone overlap.

        Benefits:
        We offer generous socials, snacks, team retreats, and wellness budget.
        """,
        max_chars=320,
    )

    assert compacted.startswith("About us:")
    assert "Responsibilities:" in compacted
    assert compacted.index("About us:") < compacted.index("Responsibilities:")
    assert len(compacted) <= 320


def test_compact_description_deduplicates_repeated_chunks():
    compacted = _compact_description_for_scoring(
        """
        Responsibilities:
        You will build Python services and Playwright-based test automation.

        Responsibilities:
        You will build Python services and Playwright-based test automation.

        Requirements:
        You have 5+ years of backend or QA automation experience with Python and CI/CD.
        """,
        max_chars=340,
    )

    lowered = compacted.lower()
    assert "responsibilities" in lowered
    assert "requirements" in lowered
    assert lowered.count("responsibilities") == 1
    assert len(compacted) <= 340


def test_compact_description_handles_unicode_text():
    """Verify that non-ASCII text (like German, Polish) is preserved through compaction."""
    compacted = _compact_description_for_scoring(
        """
        Aufgaben:
        Sie entwickeln und pflegen Backend-Dienste mit Python und PostgreSQL.

        Anforderungen:
        Sie haben 5+ Jahre Erfahrung in der Softwareentwicklung.

        Über uns:
        Wir suchen engagierte Entwickler für unser Münchner Team.
        """,
        max_chars=800,
    )

    assert "Aufgaben:" in compacted
    assert "Backend-Dienste" in compacted
    assert "Anforderungen:" in compacted
    assert "Münchner" in compacted


def test_compact_description_default_max_chars():
    """The default max_chars should be 12000."""
    # Generate a long description that exceeds 12000 chars
    long_text = "A" * 8000 + "\n\n" + "B" * 8000
    compacted = _compact_description_for_scoring(long_text)
    assert len(compacted) <= 12000
