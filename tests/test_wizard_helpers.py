from types import SimpleNamespace

import yaml

from api.wizard_helpers import (
    generate_profile_yaml,
    extract_refinable_profile_doc_sections,
    merge_refined_profile_doc_sections,
    extract_refinable_search_config_keywords,
    merge_refined_search_config_keywords,
)


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


def test_generate_profile_yaml_skips_standard_exclusions_for_explicitly_targeted_regions():
    config = yaml.safe_load(generate_profile_yaml(
        _minimal_analysis(),
        {
            "targetRegions": ["North America"],
            "excludedRegions": [],
            "enableStandardExclusions": True,
            "targetRoles": ["Software Engineer"],
            "remotePref": ["remote"],
        },
    ))

    assert config["keywords"]["location_exclusions"] == []


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
    assert r"\bbackend\s+engineer\b" in high_conf
    assert r"\bstaff\s+machine\s+learning\s+engineer\s+\(mle\)\b" in high_conf
    assert r"\bmachine\s+learning\s+engineer\b" in high_conf

    assert r"\bmle\b" in broad


def test_generate_profile_yaml_preserves_user_entered_titles_in_high_confidence():
    analysis = _minimal_analysis()
    analysis.suggested_title_patterns = {
        "high_confidence": [
            r"\bsenior\s+backend\s+engineer\b",
            r"\bbackend\s+engineer\b",
        ],
        "broad": [],
    }

    config = yaml.safe_load(generate_profile_yaml(
        analysis,
        {
            "targetRegions": ["Europe"],
            "excludedRegions": [],
            "enableStandardExclusions": False,
            "targetRoles": ["Senior Backend Engineer"],
            "remotePref": ["remote"],
        },
    ))

    high_conf = config["keywords"]["title_patterns"]["high_confidence"]
    broad = config["keywords"]["title_patterns"]["broad"]

    assert r"\bsenior\s+backend\s+engineer\b" in high_conf
    assert r"\bbackend\s+engineer\b" in high_conf
    assert r"\bsenior\s+backend\s+engineer\b" in broad


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


def test_generate_profile_yaml_uses_authored_career_direction_for_adjacent_roles_and_broad_patterns():
    analysis = SimpleNamespace(
        suggested_title_patterns={
            "high_confidence": [
                r"\bsoftware\s+engineer\s+in\s+test\b",
                r"\bsenior\s+test\s+automation\s+engineer\b",
            ],
            "broad": [],
        },
        suggested_description_signals=[],
        skills={"Core": ["Python"]},
        suggested_exclusions=[],
        suggested_target_roles=[],
        suggested_good_match_signals=[],
        suggested_lower_fit_signals=[],
        suggested_career_direction="",
        portfolio=[],
        inferred_seniority="senior",
    )

    config = yaml.safe_load(generate_profile_yaml(
        analysis,
        {
            "targetRegions": ["Europe"],
            "excludedRegions": [],
            "enableStandardExclusions": False,
            "targetRoles": ["Senior Test Automation Engineer"],
            "remotePref": ["remote"],
            "careerDirection": "Happy to explore Developer Productivity / Test Platform Engineering positions.",
        },
    ))

    assert config["keywords"]["title_patterns"]["high_confidence"] == [
        r"\bsenior\s+test\s+automation\s+engineer\b",
        r"\btest\s+automation\s+engineer\b",
    ]
    assert r"\bsenior\s+test\s+automation\s+engineer\b" in config["keywords"]["title_patterns"]["broad"]
    assert r"\bdeveloper\s+productivity\b" in config["keywords"]["title_patterns"]["broad"]
    assert r"\btest\s+platform\s+engineer\b" in config["keywords"]["title_patterns"]["broad"]
    assert config["scoring_context"]["role_targets"]["adjacent"] == [
        "Developer Productivity",
        "Test Platform Engineer",
    ]


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
            "industries": ["B2B SaaS", "Developer Tools"],
            "goodMatchSignals": ["Product Companies"],
            "companyQualitySignals": ["strong product company", "high engineering reputation"],
            "allowLowerSeniorityAtStrategicCompanies": True,
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
    assert context["career_preferences"]["score_higher_signals"] == ["Product Companies"]
    assert context["career_preferences"]["score_lower_signals"] == ["On-call Heavy"]
    assert context["industry_preferences"]["target_industries"] == ["B2B SaaS", "Developer Tools"]
    assert context["company_preferences"] == {
        "preferred_signals": ["strong product company", "high engineering reputation"],
        "allow_lower_seniority_if_company_matches": True,
    }
    assert context["decision_rules"]["adjacent_roles"] == {
        "enabled": True,
        "requires_bridge_evidence": True,
        "prefer_core_when_equally_viable": True,
        "portfolio_counts_as_bridge_evidence": True,
    }
    assert context["decision_rules"]["lower_seniority_roles"] == {
        "enabled": True,
        "require_unusually_strong_scope": True,
    }
    assert context["decision_rules"]["company_quality"] == {
        "enabled": True,
        "preferred_signals": ["strong product company", "high engineering reputation"],
        "allow_lower_seniority_exception": True,
    }
    assert any("Core target roles should outrank adjacent roles" in line for line in context["conditional_preferences"])


def test_generate_profile_yaml_decision_rules_do_not_depend_on_career_goal():
    analysis = SimpleNamespace(
        suggested_title_patterns={"high_confidence": [], "broad": []},
        suggested_description_signals=[],
        skills={"Core": ["Python"]},
        suggested_exclusions=[],
        suggested_target_roles=["Staff Platform Engineer"],
        suggested_good_match_signals=[],
        suggested_lower_fit_signals=[],
        suggested_career_direction="Broaden toward platform engineering.",
        portfolio=[SimpleNamespace(name="Project")],
        inferred_seniority="senior",
    )

    base_preferences = {
        "targetRegions": ["Europe"],
        "excludedRegions": [],
        "enableStandardExclusions": False,
        "targetRoles": ["Senior Backend Engineer"],
        "seniority": ["senior", "staff"],
        "location": "Warsaw, Poland",
        "workAuth": "eu_citizen",
        "remotePref": ["remote"],
        "primaryRemotePref": "remote",
        "timezonePref": "overlap_strict",
        "careerDirection": "Platform and developer tooling work is interesting.",
    }

    stay = yaml.safe_load(generate_profile_yaml(analysis, {**base_preferences, "careerGoal": "stay"}))
    broaden = yaml.safe_load(generate_profile_yaml(analysis, {**base_preferences, "careerGoal": "broaden"}))

    assert stay["scoring_context"]["decision_rules"] == broaden["scoring_context"]["decision_rules"]
    assert stay["scoring_context"]["conditional_preferences"] == broaden["scoring_context"]["conditional_preferences"]


def test_generate_profile_yaml_company_signals_implicitly_enable_strategic_exception():
    analysis = SimpleNamespace(
        suggested_title_patterns={"high_confidence": [], "broad": []},
        suggested_description_signals=[],
        skills={"Core": ["Python"]},
        suggested_exclusions=[],
        suggested_target_roles=[],
        suggested_good_match_signals=[],
        suggested_lower_fit_signals=[],
        suggested_career_direction="Stay close to backend work.",
        portfolio=[],
        inferred_seniority="senior",
    )

    config = yaml.safe_load(generate_profile_yaml(
        analysis,
        {
            "targetRegions": ["Europe"],
            "excludedRegions": [],
            "enableStandardExclusions": False,
            "targetRoles": ["Senior Backend Engineer"],
            "seniority": ["senior"],
            "location": "Warsaw, Poland",
            "workAuth": "eu_citizen",
            "remotePref": ["remote"],
            "primaryRemotePref": "remote",
            "timezonePref": "overlap_strict",
            "companyQualitySignals": ["strong product company"],
            "allowLowerSeniorityAtStrategicCompanies": False,
            "careerDirection": "Stay close to backend work.",
            "careerGoal": "stay",
        },
    ))

    context = config["scoring_context"]

    assert context["company_preferences"] == {
        "preferred_signals": ["strong product company"],
        "allow_lower_seniority_if_company_matches": True,
    }
    assert context["decision_rules"]["company_quality"] == {
        "enabled": True,
        "preferred_signals": ["strong product company"],
        "allow_lower_seniority_exception": True,
    }


def test_generate_profile_yaml_falls_back_to_inferred_signals_when_user_left_them_blank():
    analysis = SimpleNamespace(
        suggested_title_patterns={"high_confidence": [], "broad": []},
        suggested_description_signals=[],
        skills={"Core": ["Python"]},
        suggested_exclusions=[],
        suggested_target_roles=[],
        suggested_good_match_signals=["Developer Tooling"],
        suggested_lower_fit_signals=["Agency Work"],
        suggested_career_direction="Broaden toward platform engineering.",
        portfolio=[],
        inferred_seniority="senior",
    )

    config = yaml.safe_load(generate_profile_yaml(
        analysis,
        {
            "targetRegions": ["Europe"],
            "excludedRegions": [],
            "enableStandardExclusions": False,
            "targetRoles": ["Senior Backend Engineer"],
            "seniority": ["senior"],
            "location": "Warsaw, Poland",
            "workAuth": "eu_citizen",
            "remotePref": ["remote"],
            "primaryRemotePref": "remote",
            "timezonePref": "overlap_strict",
            "goodMatchSignals": [],
            "dealBreakers": [],
            "careerDirection": "",
            "careerGoal": "broaden",
        },
    ))

    context = config["scoring_context"]

    assert context["career_preferences"]["score_higher_signals"] == ["Developer Tooling"]
    assert context["career_preferences"]["score_lower_signals"] == ["Agency Work"]


def test_generate_profile_yaml_preserves_confirmed_empty_lists():
    analysis = SimpleNamespace(
        suggested_title_patterns={"high_confidence": [], "broad": []},
        suggested_description_signals=[],
        skills={"Core": ["Python"]},
        suggested_exclusions=[],
        suggested_target_roles=[],
        suggested_good_match_signals=["Developer Tooling"],
        suggested_lower_fit_signals=["Agency Work"],
        suggested_career_direction="Broaden toward platform engineering.",
        portfolio=[],
        inferred_seniority="senior",
    )

    config = yaml.safe_load(generate_profile_yaml(
        analysis,
        {
            "targetRegions": ["Europe"],
            "excludedRegions": [],
            "enableStandardExclusions": False,
            "targetRoles": ["Senior Backend Engineer"],
            "seniority": ["senior"],
            "location": "Warsaw, Poland",
            "workAuth": "eu_citizen",
            "remotePref": ["remote"],
            "primaryRemotePref": "remote",
            "timezonePref": "overlap_strict",
            "goodMatchSignals": [],
            "goodMatchSignalsConfirmed": True,
            "dealBreakers": [],
            "dealBreakersConfirmed": True,
            "careerDirection": "",
            "careerGoal": "broaden",
        },
    ))

    context = config["scoring_context"]

    assert context["career_preferences"]["score_higher_signals"] == []
    assert context["career_preferences"]["score_lower_signals"] == []


def test_extract_refinable_profile_doc_sections_returns_only_editable_headings():
    doc = """# Candidate Profile

## Role Target
Something

## Experience Summary
- A

## Core Technical Stack
### Backend
- Python

## What Makes a Good Match (Score Higher)
- Strongest fit

## Critical Skill Gaps
Gap text

## What Lowers Fit (Score Lower)
- Weak fit

## Conditional Preferences
Locked conditional text

## Career Direction
Exact user text.

## Portfolio
- Project
"""

    sections = extract_refinable_profile_doc_sections(doc)

    assert set(sections.keys()) == {
        "Experience Summary",
        "Core Technical Stack",
        "What Makes a Good Match (Score Higher)",
        "Critical Skill Gaps",
        "What Lowers Fit (Score Lower)",
    }
    assert "Role Target" not in sections
    assert "Conditional Preferences" not in sections
    assert "Career Direction" not in sections
    assert "Portfolio" not in sections


def test_merge_refined_profile_doc_sections_only_replaces_editable_headings():
    original_doc = """# Candidate Profile

## Role Target
Locked role target

## Experience Summary
Old experience

## What Makes a Good Match (Score Higher)
Old matches

## Career Direction
Locked career text

## Portfolio
Old portfolio
"""

    merged = merge_refined_profile_doc_sections(
        original_doc,
        {
            "Experience Summary": "New experience",
            "What Makes a Good Match (Score Higher)": "New matches",
            "Role Target": "Should be ignored",
        },
    )

    assert "## Experience Summary\nNew experience" in merged
    assert "## What Makes a Good Match (Score Higher)\nNew matches" in merged
    assert "## Career Direction\nLocked career text" in merged
    assert "## Portfolio\nOld portfolio" in merged
    assert "## Role Target\nLocked role target" in merged


def test_extract_refinable_search_config_keywords_returns_only_editable_keyword_blocks():
    profile_yaml = """# Generated search_config.yaml
keywords:
  title_patterns:
    high_confidence:
      - locked
    broad:
      - editable
  description_signals:
    min_matches: 1
    patterns: []
  location_patterns:
    - foo
scoring_context:
  role_targets:
    core:
      - Role
"""

    keywords = extract_refinable_search_config_keywords(profile_yaml)

    assert set(keywords.keys()) == {"title_patterns", "description_signals"}
    assert keywords["title_patterns"] == {
        "high_confidence": ["locked"],
        "broad": ["editable"],
    }
    assert "location_patterns" not in keywords


def test_merge_refined_search_config_keywords_only_adds_editable_keyword_blocks():
    original_yaml = """# Generated search_config.yaml
keywords:
  title_patterns:
    high_confidence:
      - old
    broad: []
  description_signals:
    min_matches: 1
    patterns:
      - old-signal
  location_patterns:
    - keep-me
"""

    merged = yaml.safe_load(merge_refined_search_config_keywords(
        original_yaml,
        {
            "title_patterns": {
                "high_confidence": ["new-high"],
                "broad": ["broader"],
            },
            "description_signals": {
                "min_matches": 1,
                "patterns": ["new-signal"],
            },
            "location_patterns": ["should-not-change"],
        },
    ))

    assert merged["keywords"]["title_patterns"]["high_confidence"] == ["new-high"]
    assert merged["keywords"]["title_patterns"]["broad"] == ["broader"]
    assert merged["keywords"]["description_signals"]["patterns"] == ["old-signal", "new-signal"]
    assert merged["keywords"]["location_patterns"] == ["keep-me"]


def test_merge_refined_search_config_keywords_preserves_core_target_titles_in_high_confidence():
    original_yaml = """# Generated search_config.yaml
keywords:
  title_patterns:
    high_confidence:
      - old
    broad: []
scoring_context:
  role_targets:
    core:
      - Senior Backend Engineer
"""

    merged = yaml.safe_load(merge_refined_search_config_keywords(
        original_yaml,
        {
            "title_patterns": {
                "high_confidence": [r"\bbackend\s+engineer\b"],
            },
        },
    ))

    assert merged["keywords"]["title_patterns"]["high_confidence"] == [
        r"\bbackend\s+engineer\b",
        r"\bsenior\s+backend\s+engineer\b",
    ]


def test_merge_refined_search_config_keywords_demotes_non_protected_high_confidence_patterns_to_broad():
    original_yaml = """# Generated search_config.yaml
keywords:
  title_patterns:
    high_confidence:
      - \\bqa\\s+engineer\\b
      - \\bsenior\\s+backend\\s+engineer\\b
    broad:
      - \\bplatform\\s+engineer\\b
scoring_context:
  role_targets:
    core:
      - Senior Backend Engineer
"""

    merged = yaml.safe_load(merge_refined_search_config_keywords(
        original_yaml,
        {
            "title_patterns": {
                "high_confidence": [r"\bbackend\s+engineer\b"],
                "broad": [r"\btest\s+engineer\b"],
            },
        },
    ))

    assert merged["keywords"]["title_patterns"]["high_confidence"] == [
        r"\bbackend\s+engineer\b",
        r"\bsenior\s+backend\s+engineer\b",
    ]
    assert merged["keywords"]["title_patterns"]["broad"] == [
        r"\bplatform\s+engineer\b",
        r"\btest\s+engineer\b",
        r"\bqa\s+engineer\b",
    ]


def test_generate_profile_yaml_preserves_llm_high_confidence_when_no_target_roles_are_selected():
    analysis = _minimal_analysis()
    analysis.suggested_title_patterns = {
        "high_confidence": [r"\bsdet\b"],
        "broad": [r"\bqa\s+engineer\b"],
    }

    config = yaml.safe_load(generate_profile_yaml(
        analysis,
        {
            "targetRegions": ["Europe"],
            "excludedRegions": [],
            "enableStandardExclusions": False,
            "targetRoles": [],
            "remotePref": ["remote"],
        },
    ))

    assert config["keywords"]["title_patterns"]["high_confidence"] == [r"\bsdet\b"]
    assert config["keywords"]["title_patterns"]["broad"] == [r"\bqa\s+engineer\b"]
