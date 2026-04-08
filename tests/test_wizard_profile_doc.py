from types import SimpleNamespace

from api.wizard_helpers import generate_profile_doc


def _analysis_for_profile_doc():
    return SimpleNamespace(
        suggested_target_roles=[],
        experience_years=8,
        experience=[],
        education=[],
        spoken_languages=[],
        skills={"Core": ["Python"]},
        suggested_good_match_signals=[],
        suggested_skill_gaps=[],
        suggested_lower_fit_signals=[],
        suggested_career_direction="Build deeper technical expertise in the current field.",
        portfolio=[],
        inferred_seniority="senior",
    )


def test_generate_profile_doc_formats_preferred_and_acceptable_work_setup():
    doc = generate_profile_doc(
        _analysis_for_profile_doc(),
        {
            "targetRoles": ["Senior Backend Engineer"],
            "remotePref": ["remote", "hybrid"],
            "primaryRemotePref": "remote",
            "timezonePref": "overlap_strict",
            "location": "Wroclaw, Poland",
            "workAuth": "eu_citizen",
            "targetRegions": ["Europe", "UK"],
            "excludedRegions": [],
            "careerDirection": "Grow as a backend platform engineer.",
            "careerGoal": "stay",
        },
    )

    assert "## Soft Preferences (Score Higher)" in doc
    assert "## Hard Constraints And Low-Fit Signals" in doc
    assert "## Conditional Preferences" in doc
    assert "- Preferred work setup: Fully Remote (Same/Overlap (±2h))" in doc
    assert "- Also acceptable: Hybrid from Wroclaw" in doc
    assert "- Preferred timezone overlap: Same/Overlap (±2h)" in doc
    assert "- Meaningful penalty: >3h timezone mismatch" in doc
    assert "- Reject/skip threshold: >5h timezone mismatch unless the role is explicitly global" in doc
    assert "- Not acceptable: On-site only positions" in doc


def test_generate_profile_doc_does_not_assume_remote_first():
    doc = generate_profile_doc(
        _analysis_for_profile_doc(),
        {
            "targetRoles": ["Product Designer"],
            "remotePref": ["onsite", "hybrid"],
            "primaryRemotePref": "onsite",
            "timezonePref": "any",
            "location": "Berlin, Germany",
            "workAuth": "other",
            "targetRegions": ["Germany"],
            "excludedRegions": ["US/North America"],
            "careerDirection": "Advance as a product designer.",
            "careerGoal": "stay",
        },
    )

    assert "- Preferred work setup: On-site from Berlin" in doc
    assert "- Also acceptable: Hybrid from Berlin" in doc
    assert "- Not acceptable: On-site only positions" not in doc
    assert "- Preferred timezone overlap:" not in doc
    assert "- Excluded regions: US/North America" in doc


def test_generate_profile_doc_normalizes_legacy_preference_labels():
    doc = generate_profile_doc(
        _analysis_for_profile_doc(),
        {
            "targetRoles": ["Data Scientist"],
            "remotePref": ["Fully Remote", "Hybrid OK"],
            "primaryRemotePref": "Fully Remote",
            "timezonePref": "Same/Overlap (±2h)",
            "location": "Paris, France",
            "workAuth": "EU citizen",
            "targetRegions": ["Europe"],
            "excludedRegions": [],
            "careerDirection": "Grow as a data scientist.",
            "careerGoal": "stay",
        },
    )

    assert "- Work authorization: EU citizen" in doc
    assert "- Preferred work setup: Fully Remote (Same/Overlap (±2h))" in doc
    assert "- Also acceptable: Hybrid from Paris" in doc
    assert "- Preferred timezone overlap: Same/Overlap (±2h)" in doc


def test_generate_profile_doc_adds_generic_conditional_preferences_for_broaden_goal():
    analysis = _analysis_for_profile_doc()
    analysis.portfolio = [SimpleNamespace(name="Project", url="https://example.com", technologies=[], description=None)]

    doc = generate_profile_doc(
        analysis,
        {
            "targetRoles": ["Platform Engineer"],
            "seniority": ["senior"],
            "remotePref": ["remote"],
            "primaryRemotePref": "remote",
            "timezonePref": "overlap_strict",
            "location": "Warsaw, Poland",
            "workAuth": "eu_citizen",
            "targetRegions": ["Europe"],
            "excludedRegions": [],
            "careerDirection": "Broaden toward platform and developer tooling work.",
            "careerGoal": "broaden",
        },
    )

    assert "## Conditional Preferences" in doc
    assert "- Adjacent roles are acceptable when they build on the current foundation and expand scope in a credible direction." in doc
    assert "- Lower-seniority roles should generally rank lower unless the scope and long-term growth case are unusually strong." in doc
    assert "- Portfolio or side-project evidence can offset some adjacent-skill gaps, but it should not be treated as equal to years of production experience." in doc
