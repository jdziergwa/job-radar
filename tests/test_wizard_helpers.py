from types import SimpleNamespace

import yaml

from api.wizard_helpers import generate_profile_yaml


def _minimal_analysis():
    return SimpleNamespace(
        suggested_title_patterns={"high_confidence": [], "broad": []},
        suggested_description_signals=[],
        skills={},
        suggested_exclusions=[],
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
