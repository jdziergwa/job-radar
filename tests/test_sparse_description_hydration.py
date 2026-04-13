from src.description_hydration import (
    SPARSE_DESCRIPTION_THRESHOLD,
    description_text_length,
    merge_hydrated_description,
    should_hydrate_description,
)
from src.models import CandidateJob


def _candidate(description: str) -> CandidateJob:
    return CandidateJob(
        db_id=1,
        ats_platform="hackernews",
        company_slug="example",
        company_name="Example",
        job_id="job-1",
        title="Senior Test Engineer",
        location="Remote",
        url="https://example.com/jobs/1",
        description=description,
        posted_at=None,
        first_seen_at="2026-04-09T00:00:00Z",
    )


def test_description_text_length_uses_plain_text_not_html_markup():
    description = "<div><p>Hello</p><p>World</p></div>"

    assert description_text_length(description) == len("Hello\n\nWorld")


def test_should_hydrate_description_for_empty_and_sparse_content():
    empty_job = _candidate("")
    sparse_job = _candidate("Remote role. Small team. Apply with email.")

    assert should_hydrate_description(empty_job) is True
    assert should_hydrate_description(sparse_job) is True


def test_should_not_hydrate_description_when_plain_text_is_substantial():
    rich_text = "Platform engineering ownership. " * (SPARSE_DESCRIPTION_THRESHOLD // 30 + 5)

    assert should_hydrate_description(_candidate(f"<p>{rich_text}</p>")) is False


def test_merge_hydrated_description_prepends_original_comment_context():
    original = "Remote in Europe only. Salary up to 140k EUR."
    hydrated = "<p>Build backend services, own CI/CD, and improve reliability.</p>"

    merged = merge_hydrated_description(original, hydrated)

    assert merged.startswith(original)
    assert "\n\n---\n" in merged
    assert merged.endswith(hydrated)


def test_merge_hydrated_description_avoids_duplicate_content():
    merged = merge_hydrated_description("Remote role", "<p>Remote role</p>")

    assert merged == "<p>Remote role</p>"
