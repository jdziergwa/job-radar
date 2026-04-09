import asyncio
import tempfile
from pathlib import Path

from api.models import CVAnalysisResponse, ExperienceEntry, ProfileSaveRequest, UserPreferences
from api.routers import wizard as wizard_router


def _sample_cv_analysis() -> CVAnalysisResponse:
    return CVAnalysisResponse(
        page_count=1,
        current_role="Senior Backend Engineer",
        experience_years=8,
        experience_summary="Backend engineer with platform experience.",
        experience=[
            ExperienceEntry(
                company="Example",
                role="Senior Backend Engineer",
                dates="2021 - Present",
                industry="SaaS",
                highlights=["Built APIs"],
            )
        ],
        skills={"Backend": ["Python", "PostgreSQL"]},
        education=[],
        portfolio=[],
        spoken_languages=["English"],
        inferred_seniority="senior",
        suggested_target_roles=["Senior Backend Engineer"],
        suggested_title_patterns={"high_confidence": [], "broad": []},
        suggested_description_signals=[],
        suggested_exclusions=[],
        suggested_skill_gaps=[],
        suggested_career_direction="Stay on backend/platform path.",
        suggested_narratives={},
        suggested_good_match_signals=["Distributed Systems"],
        suggested_lower_fit_signals=["Heavy on-call"],
        extraction_method="text",
    )


def _sample_preferences() -> UserPreferences:
    return UserPreferences(
        targetRoles=["Senior Backend Engineer"],
        seniority=["senior"],
        location="Berlin, Germany",
        baseCity="Berlin",
        baseCountry="Germany",
        workAuth="eu_citizen",
        remotePref=["remote", "hybrid"],
        primaryRemotePref="remote",
        timezonePref="overlap_strict",
        targetRegions=["Europe"],
        excludedRegions=[],
        industries=["SaaS"],
        careerDirection="Backend/platform growth.",
        careerGoal="stay",
        goodMatchSignals=["Distributed Systems"],
        companyQualitySignals=[],
        dealBreakers=["Heavy on-call"],
    )


def test_save_profile_persists_wizard_state_and_can_reload_it():
    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)
        example_dir = base_dir / "example"
        example_dir.mkdir(parents=True, exist_ok=True)
        (example_dir / "scoring_philosophy.md").write_text("Scoring philosophy", encoding="utf-8")
        (example_dir / "companies.yaml").write_text("greenhouse: []\n", encoding="utf-8")

        original_profiles_dir = wizard_router.PROFILES_DIR
        wizard_router.PROFILES_DIR = base_dir
        try:
            cv_analysis = _sample_cv_analysis()
            user_preferences = _sample_preferences()

            response = asyncio.run(wizard_router.save_profile(
                ProfileSaveRequest(
                    profile_name="default",
                    profile_yaml="keywords: {}\n",
                    profile_doc="# Candidate Profile\n",
                    cv_analysis=cv_analysis,
                    user_preferences=user_preferences,
                )
            ))

            assert response["ok"] is True

            state = asyncio.run(wizard_router.get_wizard_state("default"))
        finally:
            wizard_router.PROFILES_DIR = original_profiles_dir

        assert state.profile_name == "default"
        assert state.cv_analysis is not None
        assert state.cv_analysis.current_role == "Senior Backend Engineer"
        assert state.user_preferences is not None
        assert state.user_preferences.baseCity == "Berlin"
        assert state.user_preferences.baseCountry == "Germany"
