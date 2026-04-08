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

    assert "- Preferred work setup: Fully Remote (Same/Overlap (±2h))" in doc
    assert "- Also acceptable: Hybrid from Wroclaw" in doc
    assert "- Timezone preference: Same/Overlap (±2h)" in doc
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
    assert "- Excluded regions: US/North America" in doc
