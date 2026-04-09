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
            "baseCity": "Berlin",
            "baseCountry": "Germany",
            "location": "Berlin, Germany",
            "workAuth": "eu_citizen",
            "targetRegions": ["Europe", "UK"],
            "excludedRegions": [],
            "industries": ["B2B SaaS", "Developer Tools"],
            "careerDirection": "Grow as a backend platform engineer.",
            "careerGoal": "stay",
        },
    )

    assert "## What Makes a Good Match (Score Higher)" in doc
    assert "## What Lowers Fit (Score Lower)" in doc
    assert "## Conditional Preferences" in doc
    assert "Primary target roles: Senior Backend Engineer" in doc
    assert "Open to:" not in doc
    assert "- Preferred work setup: Fully Remote (Same/Overlap (±2h))" in doc
    assert "- Also acceptable: Hybrid from Berlin" in doc
    assert "- Hybrid preference is local-first: best fit in/near Berlin; other Germany cities are acceptable with a penalty; cross-border hybrid should score materially lower." in doc
    assert "- Preferred industries: B2B SaaS, Developer Tools" in doc
    assert "**Goal: Deepening expertise in current specialization**" in doc
    assert "- Fully Remote (Same/Overlap (±2h)) roles" not in doc
    assert "- Hybrid from Berlin roles" not in doc
    assert "- Senior-level roles" not in doc
    assert "- Not acceptable: On-site only positions" in doc
    assert "- Preferred timezone overlap: Same/Overlap (±2h)" in doc
    assert "- Meaningful penalty: >3h timezone mismatch" in doc
    assert "- Reject/skip threshold: >5h timezone mismatch unless the role is explicitly global" in doc
    assert "- Work authorization context:" not in doc
    assert "- Base location:" not in doc


def test_generate_profile_doc_does_not_assume_remote_first():
    doc = generate_profile_doc(
        _analysis_for_profile_doc(),
        {
            "targetRoles": ["Product Designer"],
            "remotePref": ["onsite", "hybrid"],
            "primaryRemotePref": "onsite",
            "timezonePref": "any",
            "baseCity": "Berlin",
            "baseCountry": "Germany",
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


def test_generate_profile_doc_country_only_location_uses_country_scoped_language():
    doc = generate_profile_doc(
        _analysis_for_profile_doc(),
        {
            "targetRoles": ["Senior Backend Engineer"],
            "remotePref": ["remote", "hybrid"],
            "primaryRemotePref": "remote",
            "timezonePref": "overlap_strict",
            "baseCountry": "Germany",
            "location": "Germany",
            "workAuth": "eu_citizen",
            "targetRegions": ["Europe"],
            "excludedRegions": [],
            "careerDirection": "Grow as a backend engineer.",
            "careerGoal": "stay",
        },
    )

    assert "- Based in: Germany" in doc
    assert "- Also acceptable: Hybrid in Germany" in doc
    assert "- Hybrid preference is country-scoped: roles in Germany are acceptable; cross-border hybrid should score materially lower." in doc


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


def test_generate_profile_doc_adds_generic_conditional_preferences_from_adjacent_roles():
    analysis = _analysis_for_profile_doc()
    analysis.suggested_target_roles = ["Platform Engineer"]
    analysis.portfolio = [SimpleNamespace(name="Project", url="https://example.com", technologies=[], description=None)]

    doc = generate_profile_doc(
        analysis,
        {
            "targetRoles": ["Senior Backend Engineer"],
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
    assert "- Core target roles should outrank adjacent roles when both are otherwise viable." in doc
    assert "- Adjacent roles are acceptable when they build on the current foundation and offer credible bridge evidence." in doc
    assert "- Lower-seniority roles should generally rank lower unless the scope and long-term growth case are unusually strong." in doc
    assert "- Portfolio or side-project evidence can offset some adjacent-skill gaps, but it should not be treated as equal to years of production experience." in doc
    assert "Adjacent/stretch roles: Platform Engineer" in doc


def test_generate_profile_doc_uses_authored_career_direction_for_adjacent_roles():
    analysis = _analysis_for_profile_doc()

    doc = generate_profile_doc(
        analysis,
        {
            "targetRoles": ["Senior Test Automation Engineer"],
            "seniority": ["senior"],
            "remotePref": ["remote"],
            "primaryRemotePref": "remote",
            "timezonePref": "overlap_strict",
            "location": "Berlin, Germany",
            "workAuth": "eu_citizen",
            "targetRegions": ["Europe"],
            "excludedRegions": [],
            "careerDirection": "Happy to explore Developer Productivity / Test Platform Engineering positions.",
            "careerGoal": "broaden",
        },
    )

    assert "Adjacent/stretch roles: Developer Productivity, Test Platform Engineer" in doc
    assert "- Adjacent/open-to roles: Developer Productivity, Test Platform Engineer" in doc
    assert "- Core target roles should outrank adjacent roles when both are otherwise viable." in doc


def test_generate_profile_doc_omits_adjacent_role_line_when_no_distinct_roles_exist():
    analysis = _analysis_for_profile_doc()
    analysis.suggested_target_roles = ["Senior Backend Engineer"]

    doc = generate_profile_doc(
        analysis,
        {
            "targetRoles": ["Senior Backend Engineer"],
            "remotePref": ["remote"],
            "primaryRemotePref": "remote",
            "timezonePref": "overlap_strict",
            "location": "Warsaw, Poland",
            "workAuth": "eu_citizen",
            "targetRegions": ["Europe"],
            "excludedRegions": [],
            "careerDirection": "Stay close to backend/platform work.",
            "careerGoal": "stay",
        },
    )

    assert "Adjacent/stretch roles:" not in doc
    assert "Adjacent/open-to roles:" not in doc


def test_generate_profile_doc_career_goal_does_not_change_conditional_preferences():
    analysis = _analysis_for_profile_doc()
    analysis.suggested_target_roles = ["Platform Engineer"]
    analysis.portfolio = [SimpleNamespace(name="Project", url="https://example.com", technologies=[], description=None)]

    base_preferences = {
        "targetRoles": ["Senior Backend Engineer"],
        "seniority": ["senior"],
        "remotePref": ["remote"],
        "primaryRemotePref": "remote",
        "timezonePref": "overlap_strict",
        "location": "Warsaw, Poland",
        "workAuth": "eu_citizen",
        "targetRegions": ["Europe"],
        "excludedRegions": [],
        "careerDirection": "Platform and developer tooling work is interesting.",
    }

    stay_doc = generate_profile_doc(analysis, {**base_preferences, "careerGoal": "stay"})
    broaden_doc = generate_profile_doc(analysis, {**base_preferences, "careerGoal": "broaden"})

    stay_conditional = stay_doc.split("## Conditional Preferences\n", 1)[1].split("\n## Career Direction", 1)[0]
    broaden_conditional = broaden_doc.split("## Conditional Preferences\n", 1)[1].split("\n## Career Direction", 1)[0]

    assert stay_conditional == broaden_conditional


def test_generate_profile_doc_prefers_explicit_signals_over_inferred_ones():
    analysis = _analysis_for_profile_doc()
    analysis.suggested_good_match_signals = ["Developer Tooling"]
    analysis.suggested_lower_fit_signals = ["Agency Work"]

    doc = generate_profile_doc(
        analysis,
        {
            "targetRoles": ["Senior Backend Engineer"],
            "remotePref": ["remote"],
            "primaryRemotePref": "remote",
            "timezonePref": "overlap_strict",
            "location": "Warsaw, Poland",
            "workAuth": "eu_citizen",
            "targetRegions": ["Europe"],
            "excludedRegions": [],
            "careerDirection": "Stay close to backend/platform work.",
            "careerGoal": "stay",
            "goodMatchSignals": ["Distributed Systems"],
            "dealBreakers": ["Heavy on-call"],
        },
    )

    assert "- Distributed Systems" in doc
    assert "- Developer Tooling" not in doc
    assert "- Heavy on-call" in doc
    assert "- Agency Work" not in doc


def test_generate_profile_doc_preserves_confirmed_empty_deal_breakers():
    analysis = _analysis_for_profile_doc()
    analysis.suggested_lower_fit_signals = ["Agency Work"]

    doc = generate_profile_doc(
        analysis,
        {
            "targetRoles": ["Senior Backend Engineer"],
            "remotePref": ["remote"],
            "primaryRemotePref": "remote",
            "timezonePref": "overlap_strict",
            "location": "Warsaw, Poland",
            "workAuth": "eu_citizen",
            "targetRegions": ["Europe"],
            "excludedRegions": [],
            "careerDirection": "Stay close to backend/platform work.",
            "careerGoal": "stay",
            "dealBreakers": [],
            "dealBreakersConfirmed": True,
        },
    )

    assert "- Agency Work" not in doc


def test_generate_profile_doc_includes_strategic_company_exception_when_signals_are_selected():
    analysis = _analysis_for_profile_doc()

    doc = generate_profile_doc(
        analysis,
        {
            "targetRoles": ["Senior Backend Engineer"],
            "seniority": ["senior"],
            "remotePref": ["remote"],
            "primaryRemotePref": "remote",
            "timezonePref": "overlap_strict",
            "location": "Warsaw, Poland",
            "workAuth": "eu_citizen",
            "targetRegions": ["Europe"],
            "excludedRegions": [],
            "careerDirection": "Stay close to backend/platform work.",
            "careerGoal": "stay",
            "companyQualitySignals": ["strong product company", "high engineering reputation"],
            "allowLowerSeniorityAtStrategicCompanies": False,
        },
    )

    assert "- Preferred company signals: strong product company, high engineering reputation" in doc
    assert "- Lower-seniority roles are acceptable only when explicit company-quality signals match your strategic preferences: strong product company, high engineering reputation." in doc


def test_generate_profile_doc_adds_portfolio_evidenced_skills_subsection():
    analysis = _analysis_for_profile_doc()
    analysis.portfolio = [
        SimpleNamespace(
            name="Resume Parser",
            url="https://example.com/resume-parser",
            technologies=["FastAPI", "OpenAI API"],
            description="Document parsing and enrichment",
        ),
        SimpleNamespace(
            name="Notes",
            url="https://example.com/notes",
            technologies=[],
            description="No tech list",
        ),
    ]

    doc = generate_profile_doc(
        analysis,
        {
            "targetRoles": ["Backend Engineer"],
            "remotePref": ["remote"],
            "primaryRemotePref": "remote",
            "timezonePref": "overlap_strict",
            "location": "Warsaw, Poland",
            "workAuth": "eu_citizen",
            "targetRegions": ["Europe"],
            "excludedRegions": [],
            "careerDirection": "Stay close to backend work.",
            "careerGoal": "stay",
        },
    )

    assert "### Portfolio-Evidenced Skills" in doc
    assert "- Resume Parser: FastAPI, OpenAI API (portfolio project, not commercial production)" in doc
    assert "- Notes:" not in doc


def test_generate_profile_doc_adds_goal_label_for_broaden_career_direction():
    analysis = _analysis_for_profile_doc()

    doc = generate_profile_doc(
        analysis,
        {
            "targetRoles": ["Backend Engineer"],
            "remotePref": ["remote"],
            "primaryRemotePref": "remote",
            "timezonePref": "overlap_strict",
            "location": "Warsaw, Poland",
            "workAuth": "eu_citizen",
            "targetRegions": ["Europe"],
            "excludedRegions": [],
            "careerDirection": "Explore adjacent platform engineering work.",
            "careerGoal": "broaden",
        },
    )

    assert "## Career Direction" in doc
    assert "**Goal: Broadening scope within the current domain family**" in doc
    assert "Explore adjacent platform engineering work." in doc
