from types import SimpleNamespace

import yaml

from api.wizard_helpers import generate_profile_yaml
from src.models import CandidateJob
from src.prefilter import prefilter


def _analysis_for_prefilter():
    return SimpleNamespace(
        suggested_title_patterns={
            "high_confidence": [
                r"\bsdet\b",
                r"\bsoftware\s+engineer\s+in\s+test\b",
                r"\btest\s+automation\s+engineer\b",
            ],
            "broad": [
                r"\bqa\s+engineer\b",
                r"\bquality\s+engineer\b",
                r"\bautomation\s+engineer\b",
                r"\btest\s+engineer\b",
            ],
        },
        suggested_description_signals=[
            r"\b(playwright|cypress|selenium|appium|espresso|xcuitest|detox)\b",
            r"\b(ci/cd|pipeline|github\s+actions|jenkins)\b",
            r"\b(automation|automated\s+test(ing|s)?)\b",
            r"\b(e2e|end-to-end)\b",
            r"\b(api\s+testing|rest\s+api)\b",
        ],
        skills={},
        suggested_exclusions=[],
        suggested_target_roles=[],
        suggested_good_match_signals=[],
    )


def _generated_keywords():
    config = yaml.safe_load(generate_profile_yaml(
        _analysis_for_prefilter(),
        {
            "targetRegions": ["Europe"],
            "excludedRegions": [],
            "enableStandardExclusions": True,
            "targetRoles": [],
            "remotePref": ["remote"],
        },
    ))
    return config["keywords"]


def _analysis_for_sparse_testing_signals():
    return SimpleNamespace(
        suggested_title_patterns={
            "high_confidence": [
                r"\btest\s+automation\s+engineer\b",
            ],
            "broad": [
                r"\bautomation\s+engineer\b",
                r"\btest\s+engineer\b",
            ],
        },
        suggested_description_signals=[
            r"\b(playwright|selenium)\b",
        ],
        skills={
            "Testing": ["GitHub Actions", "Appium"],
        },
        suggested_exclusions=[],
        suggested_target_roles=[],
        suggested_good_match_signals=["Test Platform", "Developer Productivity"],
    )


def _generated_keywords_for_sparse_testing_signals():
    config = yaml.safe_load(generate_profile_yaml(
        _analysis_for_sparse_testing_signals(),
        {
            "targetRegions": ["Europe"],
            "excludedRegions": [],
            "enableStandardExclusions": True,
            "targetRoles": ["QA Automation Engineer", "Test Platform Engineer"],
            "goodMatchSignals": [],
            "careerDirection": "",
            "remotePref": ["remote"],
        },
    ))
    return config["keywords"]


def _job(
    title: str,
    location: str,
    description: str,
    job_id: int,
) -> CandidateJob:
    return CandidateJob(
        db_id=job_id,
        ats_platform="test",
        company_slug="example",
        company_name="ExampleCo",
        job_id=str(job_id),
        title=title,
        location=location,
        url=f"https://example.com/jobs/{job_id}",
        description=description,
        posted_at=None,
        first_seen_at="2026-04-08T00:00:00",
    )


def _prefilter_result(*jobs: CandidateJob):
    keywords = _generated_keywords()
    survivors, rejected = prefilter(list(jobs), keywords)
    survivor_ids = {job.db_id for job in survivors}
    rejected_by_id = {job.db_id: reason for job, reason in rejected}
    return survivor_ids, rejected_by_id


def _prefilter_result_with_keywords(keywords, *jobs: CandidateJob):
    survivors, rejected = prefilter(list(jobs), keywords)
    survivor_ids = {job.db_id for job in survivors}
    rejected_by_id = {job.db_id: reason for job, reason in rejected}
    return survivor_ids, rejected_by_id


def test_prefilter_generated_config_accepts_european_testing_roles():
    qa_poland = _job(
        "QA Engineer",
        "Krakow, Poland",
        "Automated testing with Playwright and CI/CD pipelines.",
        1,
    )
    seit_netherlands = _job(
        "Software Engineer in Test",
        "Amsterdam, Netherlands",
        "TypeScript, API testing, end-to-end automation.",
        2,
    )

    survivors, rejected = _prefilter_result(qa_poland, seit_netherlands)

    assert survivors == {1, 2}
    assert rejected == {}


def test_prefilter_generated_config_rejects_ambiguous_automation_without_testing_signals():
    automation_noise = _job(
        "Automation Engineer",
        "Berlin, Germany",
        "Industrial controls, PLC systems, and factory process optimization.",
        3,
    )

    survivors, rejected = _prefilter_result(automation_noise)

    assert survivors == set()
    assert rejected[3].startswith("Insufficient Signals")


def test_prefilter_generated_config_accepts_broad_roles_via_literal_derived_description_signals():
    keywords = _generated_keywords_for_sparse_testing_signals()
    automation_testing = _job(
        "Automation Engineer",
        "Berlin, Germany",
        "Own the test platform, mobile release pipeline, and regression testing for customer journeys.",
        5,
    )

    survivors, rejected = _prefilter_result_with_keywords(keywords, automation_testing)

    assert survivors == {5}
    assert rejected == {}


def test_prefilter_generated_config_rejects_excluded_regions_even_with_testing_signals():
    us_qa = _job(
        "QA Engineer",
        "Austin, Texas",
        "Automated testing with Playwright and CI/CD pipelines.",
        4,
    )

    survivors, rejected = _prefilter_result(us_qa)

    assert survivors == set()
    assert rejected[4].startswith("Location Excluded:")
