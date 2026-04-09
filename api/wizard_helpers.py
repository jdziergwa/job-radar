import yaml
import re
from typing import Dict, List, Any
from api.models import CVAnalysisResponse

# Region to regex mapping for common search targets
REGION_MAPPING = {
    "Europe": r"\b(europe|eu)\b",
    "UK": r"\b(uk|united kingdom|england|scotland|wales)\b",
    "Germany": r"\b(germany|deutschland|berlin|munich|hamburg)\b",
    "USA": r"\b(us|usa|united states|america)\b",
    "Canada": r"\b(canada|can)\b",
    "Poland": r"\b(poland|polska|warsaw|krakow|wroclaw|poznan)\b",
    "Spain": r"\b(spain|espana|madrid|barcelona|valencia)\b",
    "Portugal": r"\b(portugal|lisbon|porto)\b",
    "Netherlands": r"\b(netherlands|holland|amsterdam|rotterdam|utrecht)\b",
    "France": r"\b(france|paris|lyon|marseille)\b",
    "Switzerland": r"\b(switzerland|swiss|zurich|geneva|basel)\b",
    "Ireland": r"\b(ireland|dublin|cork)\b",
    "Italy": r"\b(italy|italia|rome|milan)\b",
    "EMEA": r"\bemea\b",
    "LATAM": r"\b(latam|south america|mexico|brazil|argentina|chile|colombia)\b",
    "Asia": r"\b(asia|china|japan|korea|singapore|vietnam|thailand|indonesia)\b",
    "India": r"\b(india|bangalore|mumbai|delhi|hyderabad|pune)\b",
    "Australia": r"\b(australia|new zealand|sydney|melbourne|brisbane)\b",
    "Nordics": r"\b(nordics|sweden|norway|denmark|finland|stockholm|oslo|helsinki|copenhagen)\b",
    "Benelux": r"\b(benelux|belgium|luxembourg|netherlands)\b",
    "North America": r"\b(us|usa|united states|north america|americas|canada)\b",
    "Global": r"\b(global|worldwide)\b",
    "APAC": r"\b(apac|asia-pacific|asia pacific)\b",
    "Middle East": r"\b(middle east|uae|united arab emirates|dubai|abu dhabi|saudi arabia|qatar|oman)\b",
}

REGION_ALIASES = {
    "us/north america": "North America",
    "north america": "North America",
    "americas": "North America",
    "global/worldwide": "Global",
    "worldwide": "Global",
    "asia-pacific": "APAC",
    "asia pacific": "APAC",
}

EUROPE_REGION_EXPANSION = [
    "Europe",
    "EMEA",
    "UK",
    "Germany",
    "Poland",
    "Spain",
    "Portugal",
    "Netherlands",
    "France",
    "Switzerland",
    "Ireland",
    "Italy",
    "Nordics",
    "Benelux",
]

# Standard exclusions to filter out high-volume noise from far-off regions
# This provides the "balanced scoring" by keeping the feed focused.
STANDARD_GLOBAL_EXCLUSIONS = [
    r"\b(us|usa|united states|north america|can|canada|india|latam|south america|australia|asia|philippines|manila|bangalore|san\s+francis|boston|\bma\b|california|\bca\b|texas|\btx\b|florida|\bfl\b)\b"
]

ID_TO_LABEL = {
    # Work Auth
    "eu_citizen": "EU citizen",
    "us_citizen": "US citizen",
    "uk_right_to_work": "UK right to work",
    "need_visa_sponsorship": "Need visa sponsorship",
    "other": "Other",
    # Work Setups
    "remote": "Fully Remote",
    "hybrid": "Hybrid",
    "onsite": "On-site",
    # Timezones
    'overlap_strict': 'Same/Overlap (±2h)',
    'americas': 'Americas (UTC-3 to UTC-8)',
    'emea': 'EMEA (UTC-1 to UTC+4)',
    'apac': 'APAC (UTC+7 to UTC+12)',
    'any': 'Any Timezone',
}

WORK_AUTH_ALIASES = {
    "eu citizen": "eu_citizen",
    "us citizen": "us_citizen",
    "uk right to work": "uk_right_to_work",
    "need visa sponsorship": "need_visa_sponsorship",
    "other": "other",
}

WORK_SETUP_ALIASES = {
    "fully remote": "remote",
    "remote": "remote",
    "hybrid": "hybrid",
    "hybrid ok": "hybrid",
    "on-site": "onsite",
    "on-site ok": "onsite",
    "onsite": "onsite",
}

TIMEZONE_ALIASES = {
    "same/overlap (±2h)": "overlap_strict",
    "same/overlap (+/-2h)": "overlap_strict",
    "americas (utc-3 to utc-8)": "americas",
    "emea (utc-1 to utc+4)": "emea",
    "apac (utc+7 to utc+12)": "apac",
    "any timezone": "any",
    "local": "overlap_strict",
}

STANDARD_EXCLUSION_TARGET_REGIONS = {
    "North America",
    "USA",
    "Canada",
    "India",
    "LATAM",
    "Australia",
    "Asia",
    "APAC",
    "Global",
}

def _get_label(id_val: str) -> str:
    """Map internal ID to pretty label, or return capitalized ID."""
    if not id_val: return ""
    return ID_TO_LABEL.get(id_val.lower(), id_val.replace("_", " ").capitalize())

def _ensure_list(value: Any) -> list[str]:
    """Normalize a string-or-list field into a list of strings."""
    if not value:
        return []
    if isinstance(value, str):
        return [value]
    return [str(v) for v in value if v]


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    """Deduplicate string values case-insensitively while preserving order."""
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        clean = " ".join((value or "").strip().split())
        if not clean:
            continue
        key = clean.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(clean)
    return result


def _user_selected_or_fallback(selected: Any, fallback: Any, confirmed: bool = False) -> list[str]:
    """Prefer explicit user selections; optionally preserve confirmed-empty choices."""
    explicit = _dedupe_preserve_order(_ensure_list(selected))
    if explicit or confirmed:
        return explicit
    return _dedupe_preserve_order(_ensure_list(fallback))


def _normalize_alias(value: str | None, aliases: dict[str, str]) -> str:
    """Normalize a friendly label or legacy value to a canonical id."""
    clean = " ".join((value or "").strip().split())
    if not clean:
        return ""
    return aliases.get(clean.casefold(), clean)

def _normalize_region_name(region: str) -> str:
    """Normalize UI labels and aliases to canonical region keys."""
    clean = " ".join((region or "").strip().split())
    if not clean:
        return ""
    return REGION_ALIASES.get(clean.casefold(), clean)


def _normalize_work_auth(value: str | None) -> str:
    return _normalize_alias(value, WORK_AUTH_ALIASES)


def _normalize_work_setup(value: str | None) -> str:
    return _normalize_alias(value, WORK_SETUP_ALIASES)


def _normalize_timezone_pref(value: str | None) -> str:
    return _normalize_alias(value, TIMEZONE_ALIASES)


def _split_location_parts(location: str | None) -> tuple[str, str]:
    """Split a freeform location string into city and country-ish components."""
    clean = " ".join((location or "").strip().split())
    if not clean:
        return "", ""
    parts = [part.strip() for part in clean.split(",") if part.strip()]
    if not parts:
        return "", ""
    city = parts[0]
    country = parts[-1] if len(parts) > 1 else ""
    return city, country


def _compose_location(base_city: str | None, base_country: str | None) -> str:
    """Build a readable location string from explicit base-city/country fields."""
    city = " ".join((base_city or "").strip().split())
    country = " ".join((base_country or "").strip().split())
    if city and country:
        return f"{city}, {country}"
    return city or country


def _resolve_base_location(preferences: Dict[str, Any]) -> tuple[str, str, str]:
    """Resolve base city/country, preferring explicit wizard fields."""
    explicit_city = " ".join((preferences.get("baseCity") or "").strip().split())
    explicit_country = " ".join((preferences.get("baseCountry") or "").strip().split())
    explicit_location = _compose_location(explicit_city, explicit_country)
    if explicit_city or explicit_country:
        return explicit_city, explicit_country, explicit_location

    legacy_location = " ".join((preferences.get("location") or "").strip().split())
    city, country = _split_location_parts(legacy_location)
    return city, country, legacy_location or _compose_location(city, country)

def _build_literal_region_regex(region: str) -> str:
    """Build a safe literal regex for freeform region inputs."""
    parts = [re.escape(part) for part in region.lower().split()]
    if not parts:
        return r"\b\B"
    escaped = r"\s+".join(parts)
    return rf"\b{escaped}\b"

def _to_regex(region: str) -> str:
    """Map a region name to a regex pattern or convert to literal word-boundary regex."""
    normalized = _normalize_region_name(region)
    if normalized in REGION_MAPPING:
        return REGION_MAPPING[normalized]
    return _build_literal_region_regex(normalized)

def _expand_region_patterns(regions: list[str]) -> list[str]:
    """Expand high-level region choices into ATS-friendly pattern bundles."""
    patterns: list[str] = []
    seen: set[str] = set()

    def add_pattern(pattern: str) -> None:
        if pattern and pattern not in seen:
            patterns.append(pattern)
            seen.add(pattern)

    for region in regions:
        normalized = _normalize_region_name(region)
        if not normalized:
            continue
        if normalized == "Europe":
            for expanded in EUROPE_REGION_EXPANSION:
                add_pattern(_to_regex(expanded))
            continue
        add_pattern(_to_regex(normalized))

    return patterns


def _should_apply_standard_exclusions(target_regions: list[str]) -> bool:
    """Avoid applying broad global exclusions when the user explicitly targets those regions."""
    normalized_targets = {_normalize_region_name(region) for region in target_regions if region}
    return not bool(normalized_targets & STANDARD_EXCLUSION_TARGET_REGIONS)

def _format_work_setup_option(setup: str, city: str, country: str, timezone_pref: str) -> str:
    """Format a work setup option into explicit, readable profile text."""
    label = _get_label(setup)
    if setup == "remote":
        tz_label = _get_label(timezone_pref)
        return f"{label} ({tz_label})" if timezone_pref and timezone_pref != "any" and tz_label else label
    if setup in {"hybrid", "onsite"} and city and city != "Location":
        return f"{label} from {city}"
    if setup in {"hybrid", "onsite"} and country:
        return f"{label} in {country}"
    return label


def _format_seniority_preferences(value: Any) -> str:
    """Format one or more seniority preferences for profile text."""
    seniority = [str(v).strip().capitalize() for v in _ensure_list(value) if str(v).strip()]
    if not seniority:
        return ""
    if len(seniority) == 1:
        return seniority[0]
    if len(seniority) == 2:
        return f"{seniority[0]} and {seniority[1]}"
    return ", ".join(seniority[:-1]) + f", and {seniority[-1]}"


def _timezone_constraint_lines(timezone_pref: str) -> list[str]:
    """Translate timezone preferences into operational scoring guidance."""
    normalized = _normalize_timezone_pref(timezone_pref)
    label = _get_label(normalized)
    if not normalized or normalized == "any":
        return []
    if normalized == "overlap_strict":
        return [
            f"- Preferred timezone overlap: {label}",
            "- Meaningful penalty: >3h timezone mismatch",
            "- Reject/skip threshold: >5h timezone mismatch unless the role is explicitly global",
        ]
    return [
        f"- Preferred timezone band: {label}",
        "- Meaningful penalty: roles that explicitly require daily alignment outside this band",
    ]


def _conditional_preference_lines(
    adjacent_roles: list[str],
    seniority_preferences: list[str],
    has_portfolio: bool,
    company_quality_signals: list[str],
    allow_lower_seniority_at_strategic_companies: bool,
) -> list[str]:
    """Generate generic conditional preference guidance for scoring."""
    lines: list[str] = []
    if adjacent_roles:
        lines.append("- Core target roles should outrank adjacent roles when both are otherwise viable.")
        lines.append("- Adjacent roles are acceptable when they build on the current foundation and offer credible bridge evidence.")

    seniority_set = {s.lower() for s in seniority_preferences}
    if seniority_set & {"senior", "lead", "staff", "principal"}:
        lines.append("- Lower-seniority roles should generally rank lower unless the scope and long-term growth case are unusually strong.")
        if allow_lower_seniority_at_strategic_companies and company_quality_signals:
            signal_text = ", ".join(company_quality_signals)
            lines.append(f"- Lower-seniority roles are acceptable only when explicit company-quality signals match your strategic preferences: {signal_text}.")

    if has_portfolio and adjacent_roles:
        lines.append("- Portfolio or side-project evidence can offset some adjacent-skill gaps, but it should not be treated as equal to years of production experience.")

    return lines


def _build_decision_rules(
    adjacent_roles: list[str],
    core_roles: list[str],
    seniority_preferences: list[str],
    has_portfolio: bool,
    company_quality_signals: list[str],
    allow_lower_seniority_at_strategic_companies: bool,
) -> dict[str, Any]:
    """Build machine-readable scoring guidance from generic user intent."""
    seniority_set = {s.lower() for s in seniority_preferences}
    prefers_senior_plus = bool(seniority_set & {"senior", "lead", "staff", "principal"})
    has_adjacent_roles = bool(adjacent_roles)

    return {
        "adjacent_roles": {
            "enabled": has_adjacent_roles,
            "requires_bridge_evidence": has_adjacent_roles,
            "prefer_core_when_equally_viable": bool(core_roles and adjacent_roles),
            "portfolio_counts_as_bridge_evidence": has_portfolio and has_adjacent_roles,
        },
        "lower_seniority_roles": {
            "enabled": prefers_senior_plus,
            "require_unusually_strong_scope": prefers_senior_plus,
        },
        "company_quality": {
            "enabled": bool(company_quality_signals),
            "preferred_signals": company_quality_signals,
            "allow_lower_seniority_exception": bool(
                allow_lower_seniority_at_strategic_companies and company_quality_signals
            ),
        },
    }


_ADJACENT_INTENT_MARKERS = (
    "explore",
    "open to",
    "interested in",
)


def _normalize_role_phrase(value: str) -> str:
    """Trim generic role suffix words while preserving user-authored phrasing."""
    clean = " ".join((value or "").strip().split()).strip(" ,.;:-")
    clean = re.sub(r"\b(?:positions?|roles?)\b\s*$", "", clean, flags=re.IGNORECASE).strip(" ,.;:-")
    if clean.lower().endswith(" engineering"):
        clean = clean[:-12].rstrip() + " Engineer"
    return clean


def _extract_adjacent_roles_from_career_direction(career_direction: str, core_roles: list[str]) -> list[str]:
    """Infer only explicit adjacent/open-to roles from authored career-direction text."""
    if not career_direction:
        return []

    core_set = {role.casefold() for role in core_roles}
    adjacent_roles: list[str] = []

    for fragment in re.split(r"[.;\n]+", career_direction):
        fragment = " ".join(fragment.split())
        lower_fragment = fragment.casefold()
        marker = next((m for m in _ADJACENT_INTENT_MARKERS if m in lower_fragment), "")
        if not marker:
            continue

        start = lower_fragment.index(marker) + len(marker)
        trailing = fragment[start:].strip(" :-")
        if not trailing:
            continue

        for candidate in re.split(r"\s*(?:/|,| and )\s*", trailing):
            role = _normalize_role_phrase(candidate)
            if len(role.split()) < 2:
                continue
            if role.casefold() in core_set:
                continue
            adjacent_roles.append(role)

    return _dedupe_preserve_order(adjacent_roles)


def _resolve_adjacent_roles(analysis: CVAnalysisResponse, preferences: Dict[str, Any]) -> list[str]:
    """Combine adjacent-role signals from analysis and explicit authored intent."""
    core_roles = _dedupe_preserve_order(_ensure_list(preferences.get("targetRoles", [])))
    analysis_adjacent = [
        role for role in _ensure_list(getattr(analysis, "suggested_target_roles", []))
        if role.casefold() not in {value.casefold() for value in core_roles}
    ]
    authored_adjacent = _extract_adjacent_roles_from_career_direction(
        preferences.get("careerDirection", ""),
        core_roles,
    )
    return _dedupe_preserve_order(analysis_adjacent + authored_adjacent)


def _build_scoring_context(analysis: CVAnalysisResponse, preferences: Dict[str, Any]) -> dict[str, Any]:
    """Build a compact structured intent payload for scoring."""
    target_roles = _dedupe_preserve_order(_ensure_list(preferences.get("targetRoles", [])))
    adjacent_roles = _resolve_adjacent_roles(analysis, preferences)
    seniority_preferences = [s.lower() for s in _ensure_list(preferences.get("seniority", getattr(analysis, "inferred_seniority", ""))) if s]
    remote_pref = [_normalize_work_setup(v) for v in _ensure_list(preferences.get("remotePref", []))]
    primary_pref = _normalize_work_setup(preferences.get("primaryRemotePref", "")) or (remote_pref[0] if remote_pref else "")
    timezone_pref = _normalize_timezone_pref(preferences.get("timezonePref", ""))
    base_city, base_country, base_location = _resolve_base_location(preferences)
    good_match_signals = _user_selected_or_fallback(
        preferences.get("goodMatchSignals", []),
        getattr(analysis, "suggested_good_match_signals", []),
        bool(preferences.get("goodMatchSignalsConfirmed", False)),
    )
    company_quality_signals = _ensure_list(preferences.get("companyQualitySignals", []))
    allow_lower_seniority_at_strategic_companies = bool(company_quality_signals)
    lower_fit_signals = _user_selected_or_fallback(
        preferences.get("dealBreakers", []),
        getattr(analysis, "suggested_lower_fit_signals", []),
        bool(preferences.get("dealBreakersConfirmed", False)),
    )
    target_industries = _dedupe_preserve_order(_ensure_list(preferences.get("industries", [])))

    return {
        "role_targets": {
            "core": target_roles,
            "adjacent": adjacent_roles,
            "seniority_preferences": seniority_preferences,
        },
        "work_setup": {
            "base_location": base_location,
            "base_city": base_city,
            "base_country": base_country,
            "work_authorization": _normalize_work_auth(preferences.get("workAuth", "")),
            "preferred_setup": primary_pref,
            "acceptable_setups": [setup for setup in remote_pref if setup != primary_pref],
            "location_flexibility": {
                "remote_first": primary_pref == "remote",
                "hybrid": {
                    "anchored_to_base_location": "hybrid" in remote_pref,
                    "base_city": base_city if "hybrid" in remote_pref else "",
                    "base_country": base_country if "hybrid" in remote_pref else "",
                    "same_country_other_city": (
                        "acceptable_with_penalty" if "hybrid" in remote_pref and base_city and base_country
                        else "acceptable" if "hybrid" in remote_pref and base_country
                        else ""
                    ),
                    "cross_border": "strong_penalty" if "hybrid" in remote_pref and base_country else "",
                },
                "onsite": {
                    "anchored_to_base_location": "onsite" in remote_pref,
                    "base_city": base_city if "onsite" in remote_pref else "",
                    "base_country": base_country if "onsite" in remote_pref else "",
                    "same_country_other_city": (
                        "acceptable_with_penalty" if "onsite" in remote_pref and base_city and base_country
                        else "acceptable" if "onsite" in remote_pref and base_country
                        else ""
                    ),
                    "cross_border": "strong_penalty" if "onsite" in remote_pref and base_country else "",
                },
            },
            "target_regions": _ensure_list(preferences.get("targetRegions", [])),
            "excluded_regions": _ensure_list(preferences.get("excludedRegions", [])),
            "timezone": {
                "preference": timezone_pref,
                "guidance": _timezone_constraint_lines(timezone_pref),
            },
        },
        "career_preferences": {
            "direction": preferences.get("careerDirection") or getattr(analysis, "suggested_career_direction", ""),
            "score_higher_signals": good_match_signals,
            "score_lower_signals": lower_fit_signals,
        },
        "industry_preferences": {
            "target_industries": target_industries,
        },
        "company_preferences": {
            "preferred_signals": company_quality_signals,
            "allow_lower_seniority_if_company_matches": allow_lower_seniority_at_strategic_companies,
        },
        "decision_rules": _build_decision_rules(
            adjacent_roles,
            target_roles,
            seniority_preferences,
            bool(getattr(analysis, "portfolio", [])),
            company_quality_signals,
            allow_lower_seniority_at_strategic_companies,
        ),
        "conditional_preferences": _conditional_preference_lines(
            adjacent_roles,
            seniority_preferences,
            bool(getattr(analysis, "portfolio", [])),
            company_quality_signals,
            allow_lower_seniority_at_strategic_companies,
        ),
    }

_SENIORITY_PREFIXES = {
    "junior", "jr", "jr.", "mid", "middle", "senior", "sr", "sr.",
    "lead", "staff", "principal", "head",
}

_ROLE_ATOM_EXPANSIONS = {
    "qa": r"(?:qa|quality\s+assurance)",
    "sdet": r"(?:sdet|software\s+engineer\s+in\s+test)",
    "devops": r"(?:devops|dev\s*ops)",
    "sre": r"(?:sre|site\s+reliability(?:\s+engineer)?)",
    "ml": r"(?:ml|machine\s+learning)",
    "mle": r"(?:mle|machine\s+learning\s+engineer)",
    "ai": r"(?:ai|artificial\s+intelligence)",
    "ux": r"(?:ux|user\s+experience)",
    "ui": r"(?:ui|user\s+interface)",
}

_GENERIC_ROLE_SUFFIXES = {
    "engineer", "developer", "manager", "architect", "specialist",
    "analyst", "consultant", "designer", "researcher", "scientist",
    "tester", "lead", "head",
}

_GENERIC_SIGNAL_TERMS = {
    "role", "roles", "team", "teams", "product", "products", "system",
    "systems", "work", "working", "delivery", "strategy", "operations",
}

def _role_to_regex(role: str) -> str:
    """Convert a role string into a literal word-boundary regex."""
    parts = [re.escape(p) for p in role.lower().split()]
    escaped = r"\s+".join(parts)
    return rf"\b{escaped}\b"


def _derive_role_patterns(target_roles: list[str]) -> tuple[list[str], list[str]]:
    """Derive exact and broader regex patterns from selected target roles."""
    high_confidence: list[str] = []
    broad: list[str] = []
    high_seen: set[str] = set()
    broad_seen: set[str] = set()

    def add_high(pattern: str) -> None:
        if pattern and pattern.lower() not in high_seen:
            high_confidence.append(pattern)
            high_seen.add(pattern.lower())

    def add_broad(pattern: str) -> None:
        if pattern and pattern.lower() not in broad_seen and pattern.lower() not in high_seen:
            broad.append(pattern)
            broad_seen.add(pattern.lower())

    for raw_role in target_roles:
        role = " ".join((raw_role or "").strip().split())
        if not role:
            continue

        add_high(_role_to_regex(role))

        no_parens = re.sub(r"\s*\([^)]*\)", "", role).strip()
        if no_parens and no_parens != role:
            add_broad(_role_to_regex(no_parens))

        tokens = no_parens.split() if no_parens else role.split()
        while tokens and tokens[0].lower() in _SENIORITY_PREFIXES:
            tokens = tokens[1:]
        if len(tokens) >= 2:
            add_broad(_role_to_regex(" ".join(tokens)))
        elif len(tokens) == 1 and re.fullmatch(r"[A-Za-z0-9\-/+]{3,10}", tokens[0]):
            add_broad(_role_to_regex(tokens[0]))

        acronym_matches = re.findall(r"\(([A-Za-z0-9][A-Za-z0-9\-/+]{1,9})\)", role)
        for acronym in acronym_matches:
            add_broad(_role_to_regex(acronym))

    return high_confidence, broad


def _derive_semantic_title_patterns(target_roles: list[str]) -> list[str]:
    """Extract seniority-agnostic role-family patterns from selected titles."""
    patterns: list[str] = []
    seen: set[str] = set()

    def add_pattern(pattern: str) -> None:
        key = pattern.lower()
        if pattern and key not in seen:
            patterns.append(pattern)
            seen.add(key)

    for raw_role in target_roles:
        role = " ".join((raw_role or "").strip().split())
        if not role:
            continue

        clean = re.sub(r"\s*\([^)]*\)", "", role).strip()
        tokens = clean.split()
        while tokens and tokens[0].lower() in _SENIORITY_PREFIXES:
            tokens = tokens[1:]
        if not tokens:
            continue

        for token in tokens:
            expansion = _ROLE_ATOM_EXPANSIONS.get(token.lower())
            if expansion:
                add_pattern(rf"\b{expansion}\b")

        add_pattern(_role_to_regex(" ".join(tokens)))

    return patterns


def _merge_title_patterns(llm_patterns: list[str], derived_patterns: list[str]) -> list[str]:
    """Merge pattern lists while preserving order and deduplicating case-insensitively."""
    patterns = list(llm_patterns)
    existing_lower = {p.lower() for p in patterns}
    for pattern in derived_patterns:
        if pattern.lower() not in existing_lower:
            patterns.append(pattern)
            existing_lower.add(pattern.lower())
    return patterns


def _stabilize_title_patterns(
    llm_high_confidence: list[str],
    llm_broad: list[str],
    derived_high_confidence: list[str],
    derived_broad: list[str],
) -> tuple[list[str], list[str]]:
    """Anchor high_confidence to derived semantic cores and push everything else to broad."""
    merged_broad = _merge_title_patterns(llm_broad, derived_broad)

    if not derived_high_confidence:
        return list(llm_high_confidence), merged_broad

    exact_core = {pattern.lower() for pattern in derived_high_confidence}
    demoted: list[str] = []
    for pattern in llm_high_confidence:
        key = pattern.lower()
        if key not in exact_core:
            demoted.append(pattern)

    existing_broad = {pattern.lower() for pattern in merged_broad}
    for pattern in demoted:
        key = pattern.lower()
        if key not in existing_broad:
            merged_broad.append(pattern)
            existing_broad.add(key)

    return list(derived_high_confidence), merged_broad


def _ensure_patterns_present(base_patterns: list[str], required_patterns: list[str]) -> list[str]:
    """Append required patterns while preserving order and avoiding duplicates."""
    merged = list(base_patterns)
    existing = {pattern.lower() for pattern in merged}
    for pattern in required_patterns:
        key = pattern.lower()
        if key not in existing:
            merged.append(pattern)
            existing.add(key)
    return merged


def _merge_list_preserve_existing(existing_values: list[Any], refined_values: list[Any]) -> list[Any]:
    """Keep existing list items and append refined additions without subtraction."""
    merged = list(existing_values)
    existing_keys = {
        value.lower() if isinstance(value, str) else str(value).lower()
        for value in merged
    }
    for value in refined_values:
        key = value.lower() if isinstance(value, str) else str(value).lower()
        if key not in existing_keys:
            merged.append(value)
            existing_keys.add(key)
    return merged

# Tool/framework names that are too generic to be useful as description signals
_GENERIC_SKILL_TERMS = {
    "testing", "automation", "development", "programming", "engineering",
    "management", "leadership", "strategy", "practices", "tools",
    "architecture", "design", "analysis", "communication",
}


def _phrase_to_regex(phrase: str) -> str:
    parts = [re.escape(part) for part in phrase.lower().split()]
    escaped = r"\s+".join(parts)
    return rf"\b{escaped}\b"


def _extract_role_focus_phrase(role: str) -> str:
    """Extract a role focus phrase that is useful in job descriptions."""
    clean = re.sub(r"\s*\([^)]*\)", "", role or "").strip()
    if not clean:
        return ""

    tokens = clean.split()
    while tokens and tokens[0].lower() in _SENIORITY_PREFIXES:
        tokens = tokens[1:]
    while tokens and tokens[-1].lower() in _GENERIC_ROLE_SUFFIXES:
        tokens = tokens[:-1]

    if len(tokens) < 2:
        return ""

    return " ".join(tokens)


def _derive_literal_description_signals(
    target_roles: list[str],
    good_match_signals: list[str],
    career_direction: str,
) -> list[str]:
    """Derive exact phrase signals from role focus phrases and chip-like signals."""
    phrases: list[str] = []
    seen: set[str] = set()

    def add_phrase(value: str) -> None:
        clean = " ".join((value or "").strip().split())
        if not clean:
            return
        tokens = [token for token in re.split(r"[\s/,&-]+", clean.lower()) if token]
        if len(tokens) < 2 or len(tokens) > 4:
            return
        if all(token in _GENERIC_SIGNAL_TERMS for token in tokens):
            return
        key = clean.casefold()
        if key not in seen:
            phrases.append(clean)
            seen.add(key)

    for role in target_roles:
        add_phrase(_extract_role_focus_phrase(role))

    for signal in good_match_signals:
        add_phrase(signal)

    if career_direction:
        for chunk in re.split(r"[.;:\n]+", career_direction):
            add_phrase(chunk)

    return [_phrase_to_regex(phrase) for phrase in phrases]


def _merge_description_signals(
    llm_signals: list[str],
    skills: dict[str, list[str]],
    derived_signals: list[str] | None = None,
) -> list[str]:
    """Merge LLM, derived, and exact-skill description signals."""
    signals = list(llm_signals)
    existing_lower = {s.lower() for s in signals}
    for pattern in derived_signals or []:
        if pattern.lower() not in existing_lower:
            signals.append(pattern)
            existing_lower.add(pattern.lower())
    for category, skill_list in skills.items():
        for skill in skill_list:
            # Skip generic terms and very short names
            clean = skill.strip().lower()
            if clean in _GENERIC_SKILL_TERMS or len(clean) < 3:
                continue
            # Check if already covered by an existing pattern
            if any(clean in existing.lower() for existing in signals):
                continue
            pattern = rf"\b{re.escape(clean)}\b"
            if pattern.lower() not in existing_lower:
                signals.append(pattern)
                existing_lower.add(pattern.lower())
    return signals[:15]  # Cap at 15 to avoid over-filtering

def generate_profile_yaml(analysis: CVAnalysisResponse, preferences: Dict[str, Any]) -> str:
    """Build search_config.yaml content from CV analysis + user preferences."""

    target_roles = _dedupe_preserve_order(_ensure_list(preferences.get("targetRoles", [])))
    adjacent_roles = _resolve_adjacent_roles(analysis, preferences)
    target_regions = preferences.get("targetRegions", [])
    excluded_regions = preferences.get("excludedRegions", [])
    enable_standard_exclusions = preferences.get("enableStandardExclusions", True)
    remote_pref = [_normalize_work_setup(v) for v in _ensure_list(preferences.get("remotePref", []))]
    good_match_signals = _ensure_list(preferences.get("goodMatchSignals", []))
    good_match_signals += _ensure_list(getattr(analysis, "suggested_good_match_signals", []))
    exact_target_high_conf, exact_target_broad = _derive_role_patterns(target_roles)
    semantic_high_conf = _derive_semantic_title_patterns(target_roles)
    adjacent_high_conf, adjacent_broad = _derive_role_patterns(adjacent_roles)
    all_broad = _dedupe_preserve_order(
        exact_target_high_conf + exact_target_broad + adjacent_high_conf + adjacent_broad
    )
    title_high_conf, title_broad = _stabilize_title_patterns(
        analysis.suggested_title_patterns.get("high_confidence", []),
        analysis.suggested_title_patterns.get("broad", []),
        _dedupe_preserve_order(exact_target_high_conf + semantic_high_conf),
        all_broad,
    )
    derived_description_signals = _derive_literal_description_signals(
        target_roles,
        good_match_signals,
        preferences.get("careerDirection", ""),
    )
    
    location_patterns = _expand_region_patterns(target_regions)
    location_exclusions = _expand_region_patterns(excluded_regions)
    
    # Add standard global exclusions for "Noise Reduction" if enabled
    # Only adds it if user hasn't explicitly targeted those regions
    if enable_standard_exclusions and _should_apply_standard_exclusions(target_regions):
        for ex in STANDARD_GLOBAL_EXCLUSIONS:
            if ex not in location_exclusions:
                location_exclusions.append(ex)
    
    # Sensible defaults for remote patterns
    remote_patterns = [r"\b(remote|worldwide|global|distributed|anywhere|flexible)\b"]
    
    config = {
        "keywords": {
            "title_patterns": {
                "high_confidence": title_high_conf,
                "broad": title_broad,
            },
            "description_signals": {
                "min_matches": 1,
                "patterns": _merge_description_signals(
                    analysis.suggested_description_signals,
                    analysis.skills,
                    derived_description_signals,
                ),
            },
            "exclusions": analysis.suggested_exclusions,
            "location_exclusions": location_exclusions,
            "location_patterns": location_patterns + (
                [r"\bhybrid\b"] if "hybrid" in remote_pref else []
            ),
            "remote_patterns": remote_patterns,
            "fallback_tier": "signal_match",
        },
        "scoring_context": _build_scoring_context(analysis, preferences),
        "scoring": {
            "model": "claude-haiku-4-5-20251001",
            "max_description_chars": 20000,
            "min_score_to_display": 50,
            "concurrency": 25,
            "batch_size": 5,
        },
        "output": {
            "terminal": True,
            "markdown_report": True,
            "telegram": {"enabled": False, "top_n": 5},
        },
    }
    
    # Use yaml.dump with sort_keys=False to preserve order and default_flow_style=False for readability
    yaml_header = "# Generated search_config.yaml\n"
    return yaml_header + yaml.dump(config, sort_keys=False, default_flow_style=False)


EDITABLE_PROFILE_DOC_SECTIONS = (
    "Experience Summary",
    "Core Technical Stack",
    "What Makes a Good Match (Score Higher)",
    "Critical Skill Gaps",
    "What Lowers Fit (Score Lower)",
)

EDITABLE_SEARCH_KEYWORD_KEYS = (
    "description_signals",
)


def _split_markdown_level2_sections(doc: str) -> tuple[list[str], list[tuple[str, str]]]:
    """Split markdown into preamble lines and ordered level-2 sections."""
    preamble: list[str] = []
    sections: list[tuple[str, str]] = []
    current_heading: str | None = None
    current_lines: list[str] = []

    for line in doc.splitlines():
        if line.startswith("## "):
            if current_heading is None:
                pass
            else:
                sections.append((current_heading, "\n".join(current_lines).strip()))
            current_heading = line[3:].strip()
            current_lines = []
            continue

        if current_heading is None:
            preamble.append(line)
        else:
            current_lines.append(line)

    if current_heading is not None:
        sections.append((current_heading, "\n".join(current_lines).strip()))

    return preamble, sections


def extract_refinable_profile_doc_sections(doc: str) -> dict[str, str]:
    """Return only the markdown sections the LLM is allowed to refine."""
    _, sections = _split_markdown_level2_sections(doc)
    return {
        heading: body
        for heading, body in sections
        if heading in EDITABLE_PROFILE_DOC_SECTIONS
    }


def merge_refined_profile_doc_sections(original_doc: str, refined_sections: Dict[str, Any]) -> str:
    """Replace only editable markdown sections by heading name."""
    preamble, sections = _split_markdown_level2_sections(original_doc)
    merged_parts: list[str] = []

    preamble_text = "\n".join(preamble).strip()
    if preamble_text:
        merged_parts.append(preamble_text)

    for heading, body in sections:
        replacement = body
        if heading in EDITABLE_PROFILE_DOC_SECTIONS and isinstance(refined_sections.get(heading), str):
            replacement = refined_sections[heading].strip()
        section_text = f"## {heading}"
        if replacement:
            section_text += f"\n{replacement}"
        merged_parts.append(section_text)

    return "\n\n".join(merged_parts).strip()


def extract_refinable_search_config_keywords(profile_yaml: str) -> dict[str, Any]:
    """Return only the keyword subsections the LLM is allowed to refine."""
    config = yaml.safe_load(profile_yaml)
    if not isinstance(config, dict):
        return {}
    keywords = config.get("keywords", {})
    if not isinstance(keywords, dict):
        return {}
    editable_keywords: dict[str, Any] = {}
    title_patterns = keywords.get("title_patterns")
    if isinstance(title_patterns, dict):
        editable_title_patterns: dict[str, Any] = {}
        if "high_confidence" in title_patterns:
            editable_title_patterns["high_confidence"] = title_patterns["high_confidence"]
        if "broad" in title_patterns:
            editable_title_patterns["broad"] = title_patterns["broad"]
        if editable_title_patterns:
            editable_keywords["title_patterns"] = editable_title_patterns
    for key in EDITABLE_SEARCH_KEYWORD_KEYS:
        if key in keywords:
            editable_keywords[key] = keywords[key]
    return editable_keywords


def merge_refined_search_config_keywords(original_yaml: str, refined_keywords: Dict[str, Any]) -> str:
    """Add refined keyword suggestions without subtracting existing generated rules."""
    config = yaml.safe_load(original_yaml)
    if not isinstance(config, dict):
        return original_yaml

    keywords = config.get("keywords")
    if not isinstance(keywords, dict):
        return original_yaml

    refined_title_patterns = refined_keywords.get("title_patterns")
    existing_title_patterns = keywords.get("title_patterns")
    if isinstance(existing_title_patterns, dict) and isinstance(refined_title_patterns, dict):
        role_targets = config.get("scoring_context", {}).get("role_targets", {})
        core_roles = role_targets.get("core", []) if isinstance(role_targets, dict) else []
        required_high_conf = [_role_to_regex(role) for role in _ensure_list(core_roles)]
        existing_high = existing_title_patterns.get("high_confidence")
        existing_broad = existing_title_patterns.get("broad")
        refined_high = refined_title_patterns.get("high_confidence")
        refined_broad = refined_title_patterns.get("broad")

        if isinstance(existing_high, list):
            if isinstance(refined_high, list):
                final_high = _ensure_patterns_present(refined_high, required_high_conf)
            else:
                final_high = _ensure_patterns_present(existing_high, required_high_conf)

            final_high_keys = {pattern.lower() for pattern in final_high}
            protected_high_keys = {pattern.lower() for pattern in required_high_conf}

            if isinstance(existing_broad, list):
                final_broad = list(existing_broad)
            else:
                final_broad = []

            if isinstance(refined_broad, list):
                final_broad = _merge_list_preserve_existing(final_broad, refined_broad)

            demoted_existing_high = [
                pattern for pattern in existing_high
                if pattern.lower() not in protected_high_keys and pattern.lower() not in final_high_keys
            ]
            final_broad = _merge_list_preserve_existing(final_broad, demoted_existing_high)

            existing_title_patterns["high_confidence"] = final_high
            existing_title_patterns["broad"] = final_broad
        keywords["title_patterns"] = existing_title_patterns

    for key in EDITABLE_SEARCH_KEYWORD_KEYS:
        value = refined_keywords.get(key)
        existing_value = keywords.get(key)
        if isinstance(existing_value, dict) and isinstance(value, dict):
            merged_dict = dict(existing_value)
            existing_patterns = existing_value.get("patterns")
            refined_patterns = value.get("patterns")
            if isinstance(existing_patterns, list) and isinstance(refined_patterns, list):
                merged_dict["patterns"] = _merge_list_preserve_existing(existing_patterns, refined_patterns)
            if "min_matches" in value and "min_matches" not in merged_dict:
                merged_dict["min_matches"] = value["min_matches"]
            keywords[key] = merged_dict

    config["keywords"] = keywords
    return "# Generated search_config.yaml\n" + yaml.dump(
        config,
        sort_keys=False,
        default_flow_style=False,
    )

def generate_profile_doc(analysis: CVAnalysisResponse, preferences: Dict[str, Any]) -> str:
    """Build profile_doc.md from CV analysis + user preferences."""

    sections = []

    sections.append("# Candidate Profile")

    # ## Role Target
    target_roles_list = _dedupe_preserve_order(_ensure_list(preferences.get("targetRoles", [])))
    target_roles = " / ".join(target_roles_list)
    adjacent_roles = _resolve_adjacent_roles(analysis, preferences)
    role_target_lines = [f"## Role Target"]
    if target_roles:
        role_target_lines.append(f"Primary target roles: {target_roles}")
    if adjacent_roles:
        role_target_lines.append(f"Adjacent/stretch roles: {', '.join(adjacent_roles)}")
    sections.append("\n".join(role_target_lines))
    
    # ## Experience Summary
    exp_summary_lines = ["## Experience Summary"]
    if analysis.experience_years:
        exp_summary_lines.append(f"- {analysis.experience_years}+ years of professional experience")
    
    for exp in analysis.experience:
        industry_str = f" ({exp.industry})" if exp.industry else ""
        base = f"- {exp.role} at {exp.company}{industry_str}, {exp.dates}"
        # Append top 2 highlights if available
        if exp.highlights:
            top_highlights = exp.highlights[:2]
            base += " — " + "; ".join(top_highlights)
        exp_summary_lines.append(base)
    
    for edu in analysis.education:
        dates = f" ({edu.start_year} — {edu.end_year})" if edu.start_year and edu.end_year else ""
        exp_summary_lines.append(f"- {edu.degree} — {edu.school}{dates}")
    
    if analysis.spoken_languages:
        exp_summary_lines.append(f"- Languages: {', '.join(analysis.spoken_languages)}")
    
    sections.append("\n".join(exp_summary_lines))
    
    # ## Core Technical Stack
    tech_stack_lines = ["## Core Technical Stack"]
    for category, skills in analysis.skills.items():
        tech_stack_lines.append(f"\n### {category}")
        for skill in skills:
            tech_stack_lines.append(f"- {skill}")
    portfolio_evidenced_skills = [
        project for project in getattr(analysis, "portfolio", [])
        if getattr(project, "technologies", None)
    ]
    if portfolio_evidenced_skills:
        tech_stack_lines.append("\n### Portfolio-Evidenced Skills")
        for project in portfolio_evidenced_skills:
            tech_tags = ", ".join(project.technologies)
            tech_stack_lines.append(
                f"- {project.name}: {tech_tags} (portfolio project, not commercial production)"
            )
    sections.append("\n".join(tech_stack_lines))
    
    # ## What Makes a Good Match (Score Higher)
    good_match_lines = ["## What Makes a Good Match (Score Higher)"]

    signals = _user_selected_or_fallback(
        preferences.get("goodMatchSignals", []),
        analysis.suggested_good_match_signals,
        bool(preferences.get("goodMatchSignalsConfirmed", False)),
    )
    
    # Inferred defaults based on preferences
    remote_pref = [_normalize_work_setup(v) for v in _ensure_list(preferences.get("remotePref", []))]
    
    primary_pref = _normalize_work_setup(preferences.get("primaryRemotePref", ""))
    timezone_pref = _normalize_timezone_pref(preferences.get("timezonePref", ""))
    city, country, location = _resolve_base_location(preferences)
    city = city or "Location"
    target_regions = ", ".join(preferences.get("targetRegions", []))
    target_industries = ", ".join(_dedupe_preserve_order(_ensure_list(preferences.get("industries", []))))
    company_quality_signals = _ensure_list(preferences.get("companyQualitySignals", []))
    allow_lower_seniority_at_strategic_companies = bool(company_quality_signals)
    preferred_setup = _format_work_setup_option(primary_pref, city, country, timezone_pref) if primary_pref else ""
    acceptable_setups = [
        _format_work_setup_option(setup, city, country, timezone_pref)
        for setup in remote_pref
        if setup != primary_pref
    ]

    if adjacent_roles:
        good_match_lines.append(f"- Adjacent/open-to roles: {', '.join(adjacent_roles)}")
    if target_industries:
        good_match_lines.append(f"- Preferred industries: {target_industries}")
    if company_quality_signals:
        good_match_lines.append(f"- Preferred company signals: {', '.join(company_quality_signals)}")

    for signal in signals:
        good_match_lines.append(f"- {signal}")
    sections.append("\n".join(good_match_lines))
    
    # ## Critical Skill Gaps
    gap_lines = ["## Critical Skill Gaps"]

    has_adjacent_roles = bool(adjacent_roles)
    context_text = (
        "These are confirmed gaps -- not 'learning quickly' adjacencies. "
        "When a job's primary focus depends on these, lower tech_stack_match significantly. "
        "Each gap includes per-dimension scoring guidance."
    )
    if has_adjacent_roles and analysis.portfolio:
        context_text += (
            " Distinguish core target-role gaps from adjacent-role gaps. "
            "Portfolio or secondary evidence can soften adjacent gaps, but it should not "
            "be treated as equal to years of production experience."
        )
    elif has_adjacent_roles:
        context_text += (
            " Distinguish core target-role gaps from adjacent-role gaps. "
            "Adjacent-role gaps should stay meaningful when there is no supporting bridge evidence."
        )

    gap_lines.append("**Scoring Context**")
    gap_lines.append(context_text)

    for gap in analysis.suggested_skill_gaps:
        if ":" in gap:
            skill, explanation = gap.split(":", 1)
            gap_lines.append(f"- **{skill.strip()}**: {explanation.strip()}")
        else:
            gap_lines.append(f"- {gap}")
    sections.append("\n".join(gap_lines))
    
    # ## What Lowers Fit (Score Lower)
    lower_fit_lines = ["## What Lowers Fit (Score Lower)"]

    deal_breakers = _user_selected_or_fallback(
        preferences.get("dealBreakers", []),
        analysis.suggested_lower_fit_signals,
        bool(preferences.get("dealBreakersConfirmed", False)),
    )
    
    # Standard entries based on seniority
    seniority_val = preferences.get("seniority", getattr(analysis, "inferred_seniority", ""))
    if isinstance(seniority_val, str):
        seniority_list = [seniority_val.lower()]
    elif isinstance(seniority_val, list):
        seniority_list = [s.lower() for s in seniority_val]
    else:
        seniority_list = []

    work_auth = _get_label(_normalize_work_auth(preferences.get('workAuth', '')))
    excluded = ", ".join(preferences.get("excludedRegions", []))
    remote_pref_set = set(remote_pref)

    if any(s in ["senior", "lead", "staff", "principal"] for s in seniority_list):
        lower_fit_lines.append("- Junior or entry-level positions")
        
    for db in deal_breakers:
        lower_fit_lines.append(f"- {db}")
    sections.append("\n".join(lower_fit_lines))
    
    # ## Location, Timezone, And Work Setup Constraints
    loc_lines = ["## Location, Timezone, And Work Setup Constraints"]
    loc_lines.append(f"- Based in: {location}")
    loc_lines.append(f"- Work authorization: {work_auth}")
    if preferred_setup:
        loc_lines.append(f"- Preferred work setup: {preferred_setup}")
    if acceptable_setups:
        loc_lines.append(f"- Also acceptable: {', '.join(acceptable_setups)}")
    if primary_pref == "remote" and "hybrid" in remote_pref and country:
        if city != "Location":
            loc_lines.append(
                f"- Hybrid preference is local-first: best fit in/near {city}; other {country} cities are acceptable with a penalty; cross-border hybrid should score materially lower."
            )
        else:
            loc_lines.append(
                f"- Hybrid preference is country-scoped: roles in {country} are acceptable; cross-border hybrid should score materially lower."
            )
    if primary_pref == "remote" and "onsite" in remote_pref and country:
        if city != "Location":
            loc_lines.append(
                f"- On-site preference is local-first: best fit in/near {city}; other {country} cities are acceptable only with a clear tradeoff; cross-border on-site should score materially lower."
            )
        else:
            loc_lines.append(
                f"- On-site preference is country-scoped: roles in {country} are acceptable; cross-border on-site should score materially lower."
            )
    
    if target_regions:
        loc_lines.append(f"- Acceptable regions: {target_regions}")
    if excluded:
        loc_lines.append(f"- Excluded regions: {excluded}")
    
    # Add setup negatives
    if "onsite" not in remote_pref_set:
        loc_lines.append("- Not acceptable: On-site only positions")
    loc_lines.extend(_timezone_constraint_lines(timezone_pref))
        
    sections.append("\n".join(loc_lines))

    # ## Conditional Preferences
    conditional_lines = ["## Conditional Preferences"]
    conditional_lines.extend(_conditional_preference_lines(
        adjacent_roles,
        seniority_list,
        bool(analysis.portfolio),
        company_quality_signals,
        allow_lower_seniority_at_strategic_companies,
    ))
    sections.append("\n".join(conditional_lines))
    
    # ## Career Direction
    career_dir = preferences.get("careerDirection") or analysis.suggested_career_direction
    career_goal = preferences.get("careerGoal", "stay")
    goal_labels = {
        "stay": "Deepening expertise in current specialization",
        "pivot": "Transitioning to a new career direction",
        "step_up": "Stepping up to higher scope and leadership",
        "broaden": "Broadening scope within the current domain family",
    }
    goal_label = goal_labels.get(career_goal, "")
    goal_line = f"**Goal: {goal_label}**\n" if goal_label else ""
    sections.append(f"## Career Direction\n{goal_line}{career_dir}")
    
    # ## Portfolio
    if analysis.portfolio:
        portfolio_lines = ["## Portfolio"]
        for p in analysis.portfolio:
            portfolio_lines.append(f"- **{p.name}** ({p.url})")
            if p.technologies:
                tech_tags = ", ".join(p.technologies)
                portfolio_lines.append(f"  - {tech_tags}")
            if p.description:
                portfolio_lines.append(f"  - Demonstrates: {p.description}")
        sections.append("\n".join(portfolio_lines))
    
    return "\n\n".join(sections)
