from types import SimpleNamespace

import yaml

from api.wizard_helpers import generate_profile_yaml


def _minimal_analysis():
    return SimpleNamespace(
        suggested_title_patterns={"high_confidence": [], "broad": []},
        suggested_description_signals=[],
        skills={},
        suggested_exclusions=[],
        suggested_target_roles=[],
        suggested_good_match_signals=[],
    )


def test_generate_profile_yaml_expands_europe_regions():
    config = yaml.safe_load(generate_profile_yaml(
        _minimal_analysis(),
        {
            "targetRegions": ["Europe"],
            "excludedRegions": [],
            "enableStandardExclusions": True,
            "targetRoles": [],
            "remotePref": ["remote"],
        },
    ))

    patterns = config["keywords"]["location_patterns"]

    assert r"\b(europe|eu)\b" in patterns
    assert r"\bemea\b" in patterns
    assert r"\b(poland|polska|warsaw|krakow|wroclaw|poznan)\b" in patterns
    assert r"\b(germany|deutschland|berlin|munich|hamburg)\b" in patterns
    assert r"\b(netherlands|holland|amsterdam|rotterdam|utrecht)\b" in patterns
    assert r"\b(spain|espana|madrid|barcelona|valencia)\b" in patterns
    assert r"\b(portugal|lisbon|porto)\b" in patterns


def test_generate_profile_yaml_normalizes_ui_region_labels():
    config = yaml.safe_load(generate_profile_yaml(
        _minimal_analysis(),
        {
            "targetRegions": ["US/North America", "Global/Worldwide", "Asia-Pacific"],
            "excludedRegions": [],
            "enableStandardExclusions": False,
            "targetRoles": [],
            "remotePref": ["remote"],
        },
    ))

    patterns = config["keywords"]["location_patterns"]

    assert r"\b(us|usa|united states|north america|americas|canada)\b" in patterns
    assert r"\b(global|worldwide)\b" in patterns
    assert r"\b(apac|asia-pacific|asia pacific)\b" in patterns


def test_generate_profile_yaml_escapes_freeform_region_regex():
    config = yaml.safe_load(generate_profile_yaml(
        _minimal_analysis(),
        {
            "targetRegions": ["C++ / ML Platform"],
            "excludedRegions": [],
            "enableStandardExclusions": False,
            "targetRoles": [],
            "remotePref": ["remote"],
        },
    ))

    patterns = config["keywords"]["location_patterns"]

    assert patterns == [r"\bc\+\+\s+/\s+ml\s+platform\b"]


def test_generate_profile_yaml_derives_broad_role_patterns_from_target_roles():
    config = yaml.safe_load(generate_profile_yaml(
        _minimal_analysis(),
        {
            "targetRegions": ["Europe"],
            "excludedRegions": [],
            "enableStandardExclusions": False,
            "targetRoles": ["Senior Backend Engineer", "Staff Machine Learning Engineer (MLE)"],
            "remotePref": ["remote"],
        },
    ))

    high_conf = config["keywords"]["title_patterns"]["high_confidence"]
    broad = config["keywords"]["title_patterns"]["broad"]

    assert r"\bsenior\s+backend\s+engineer\b" in high_conf
    assert r"\bstaff\s+machine\s+learning\s+engineer\s+\(mle\)\b" in high_conf

    assert r"\bbackend\s+engineer\b" in broad
    assert r"\bstaff\s+machine\s+learning\s+engineer\b" in broad or r"\bmachine\s+learning\s+engineer\b" in broad
    assert r"\bmle\b" in broad


def test_generate_profile_yaml_normalizes_legacy_remote_pref_labels():
    config = yaml.safe_load(generate_profile_yaml(
        _minimal_analysis(),
        {
            "targetRegions": ["Europe"],
            "excludedRegions": [],
            "enableStandardExclusions": False,
            "targetRoles": [],
            "remotePref": ["Hybrid OK"],
        },
    ))

    patterns = config["keywords"]["location_patterns"]

    assert r"\bhybrid\b" in patterns


def test_generate_profile_yaml_derives_literal_signals_from_roles_and_match_chips():
    analysis = SimpleNamespace(
        suggested_title_patterns={"high_confidence": [], "broad": []},
        suggested_description_signals=[r"\b(playwright|cypress)\b"],
        skills={
            "Testing": ["Playwright", "GitHub Actions", "Appium", "REST API"],
        },
        suggested_exclusions=[],
        suggested_target_roles=[],
        suggested_good_match_signals=["Developer Productivity", "Test Platform"],
    )

    config = yaml.safe_load(generate_profile_yaml(
        analysis,
        {
            "targetRegions": ["Europe"],
            "excludedRegions": [],
            "enableStandardExclusions": False,
            "targetRoles": ["QA Automation Engineer", "Test Platform Engineer"],
            "goodMatchSignals": [],
            "careerDirection": "",
            "remotePref": ["remote"],
        },
    ))

    patterns = config["keywords"]["description_signals"]["patterns"]

    assert r"\b(playwright|cypress)\b" in patterns
    assert r"\btest\s+platform\b" in patterns
    assert r"\bdeveloper\s+productivity\b" in patterns


def test_generate_profile_yaml_derives_literal_signals_from_career_direction():
    analysis = SimpleNamespace(
        suggested_title_patterns={"high_confidence": [], "broad": []},
        suggested_description_signals=[r"\b(python|go)\b"],
        skills={
            "Platform": ["Kafka", "GitHub Actions", "Docker"],
        },
        suggested_exclusions=[],
        suggested_target_roles=[],
        suggested_good_match_signals=["Distributed Systems", "Developer Tooling"],
    )

    config = yaml.safe_load(generate_profile_yaml(
        analysis,
        {
            "targetRegions": ["Europe"],
            "excludedRegions": [],
            "enableStandardExclusions": False,
            "targetRoles": ["Senior Platform Engineer"],
            "goodMatchSignals": ["Internal Tooling"],
            "careerDirection": "Platform engineering. Developer tooling.",
            "remotePref": ["remote"],
        },
    ))

    patterns = config["keywords"]["description_signals"]["patterns"]

    assert r"\bdeveloper\s+tooling\b" in patterns
    assert r"\binternal\s+tooling\b" in patterns
    assert r"\bdistributed\s+systems\b" in patterns
    assert r"\bplatform\s+engineering\b" in patterns


def test_generate_profile_yaml_includes_structured_scoring_context():
    analysis = SimpleNamespace(
        suggested_title_patterns={"high_confidence": [], "broad": []},
        suggested_description_signals=[],
        skills={"Core": ["Python"]},
        suggested_exclusions=[],
        suggested_target_roles=["Staff Platform Engineer"],
        suggested_good_match_signals=["Developer Tooling"],
        suggested_lower_fit_signals=["Agency Work"],
        suggested_career_direction="Broaden toward platform engineering.",
        portfolio=[SimpleNamespace(name="Project")],
        inferred_seniority="senior",
    )

    config = yaml.safe_load(generate_profile_yaml(
        analysis,
        {
            "targetRegions": ["Europe"],
            "excludedRegions": ["North America"],
            "enableStandardExclusions": False,
            "targetRoles": ["Senior Backend Engineer"],
            "seniority": ["senior", "staff"],
            "location": "Warsaw, Poland",
            "workAuth": "eu_citizen",
            "remotePref": ["remote", "hybrid"],
            "primaryRemotePref": "remote",
            "timezonePref": "overlap_strict",
            "goodMatchSignals": ["Product Companies"],
            "dealBreakers": ["On-call Heavy"],
            "careerDirection": "Broaden toward platform engineering.",
            "careerGoal": "broaden",
        },
    ))

    context = config["scoring_context"]

    assert context["role_targets"]["core"] == ["Senior Backend Engineer"]
    assert context["role_targets"]["adjacent"] == ["Staff Platform Engineer"]
    assert context["role_targets"]["seniority_preferences"] == ["senior", "staff"]
    assert context["work_setup"]["preferred_setup"] == "remote"
    assert context["work_setup"]["acceptable_setups"] == ["hybrid"]
    assert context["work_setup"]["target_regions"] == ["Europe"]
    assert context["work_setup"]["excluded_regions"] == ["North America"]
    assert context["work_setup"]["timezone"]["preference"] == "overlap_strict"
    assert context["career_preferences"]["goal"] == "broaden"
    assert context["career_preferences"]["score_higher_signals"] == ["Product Companies", "Developer Tooling"]
    assert context["career_preferences"]["score_lower_signals"] == ["On-call Heavy", "Agency Work"]
    assert context["decision_rules"]["adjacent_roles"] == {
        "enabled": True,
        "requires_bridge_evidence": True,
        "prefer_core_when_equally_viable": False,
        "portfolio_counts_as_bridge_evidence": True,
    }
    assert context["decision_rules"]["lower_seniority_roles"] == {
        "enabled": True,
        "require_unusually_strong_scope": True,
    }
    assert any("Adjacent roles are acceptable" in line for line in context["conditional_preferences"])
