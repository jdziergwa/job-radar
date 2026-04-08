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
}

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

def _get_label(id_val: str) -> str:
    """Map internal ID to pretty label, or return capitalized ID."""
    if not id_val: return ""
    return ID_TO_LABEL.get(id_val.lower(), id_val.replace("_", " ").capitalize())

def _to_regex(region: str) -> str:
    """Map a region name to a regex pattern or convert to literal word-boundary regex."""
    if region in REGION_MAPPING:
        return REGION_MAPPING[region]
    # Literal match with word boundaries for freeform entries
    clean = region.lower().strip()
    return rf"\b{clean}\b"

def _merge_title_patterns(llm_patterns: list[str], target_roles: list[str]) -> list[str]:
    """Merge LLM-suggested title patterns with patterns derived from target roles."""
    patterns = list(llm_patterns)
    existing_lower = {p.lower() for p in patterns}
    for role in target_roles:
        # Create a word-boundary regex from the role name
        # e.g. "Data Scientist" -> r"\bdata\s+scientist\b"
        parts = [re.escape(p) for p in role.lower().split()]
        escaped = r"\s+".join(parts)
        pattern = rf"\b{escaped}\b"
        if pattern.lower() not in existing_lower:
            patterns.append(pattern)
            existing_lower.add(pattern.lower())
    return patterns

# Tool/framework names that are too generic to be useful as description signals
_GENERIC_SKILL_TERMS = {
    "testing", "automation", "development", "programming", "engineering",
    "management", "leadership", "strategy", "practices", "tools",
    "architecture", "design", "analysis", "communication",
}

def _merge_description_signals(llm_signals: list[str], skills: dict[str, list[str]]) -> list[str]:
    """Merge LLM signals with patterns auto-generated from skill names."""
    signals = list(llm_signals)
    existing_lower = {s.lower() for s in signals}
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
    
    target_regions = preferences.get("targetRegions", [])
    excluded_regions = preferences.get("excludedRegions", [])
    enable_standard_exclusions = preferences.get("enableStandardExclusions", True)
    
    location_patterns = [_to_regex(r) for r in target_regions]
    location_exclusions = [_to_regex(r) for r in excluded_regions]
    
    # Add standard global exclusions for "Noise Reduction" if enabled
    # Only adds it if user hasn't explicitly targeted those regions
    if enable_standard_exclusions:
        for ex in STANDARD_GLOBAL_EXCLUSIONS:
            if ex not in location_exclusions:
                location_exclusions.append(ex)
    
    # Sensible defaults for remote patterns
    remote_patterns = [r"\b(remote|worldwide|global|distributed|anywhere|flexible)\b"]
    
    config = {
        "keywords": {
            "title_patterns": {
                "high_confidence": _merge_title_patterns(
                    analysis.suggested_title_patterns.get("high_confidence", []),
                    preferences.get("targetRoles", [])
                ),
                "broad": analysis.suggested_title_patterns.get("broad", []),
            },
            "description_signals": {
                "min_matches": 1,
                "patterns": _merge_description_signals(
                    analysis.suggested_description_signals,
                    analysis.skills
                ),
            },
            "exclusions": analysis.suggested_exclusions,
            "location_exclusions": location_exclusions,
            "location_patterns": location_patterns + (
                [r"\bhybrid\b"] if "hybrid" in preferences.get("remotePref", []) else []
            ),
            "remote_patterns": remote_patterns,
            "fallback_tier": "signal_match",
        },
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

def generate_profile_doc(analysis: CVAnalysisResponse, preferences: Dict[str, Any]) -> str:
    """Build profile_doc.md from CV analysis + user preferences."""
    
    sections = []
    
    sections.append("# Candidate Profile")
    
    # ## Role Target
    target_roles = " / ".join(preferences.get("targetRoles", []))
    role_target_lines = [f"## Role Target", target_roles]
    if analysis.suggested_target_roles:
        suggested = " / ".join(analysis.suggested_target_roles)
        role_target_lines.append(f"Open to: {suggested}")
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
    sections.append("\n".join(tech_stack_lines))
    
    # ## What Makes a Good Match (Score Higher)
    good_match_lines = ["## What Makes a Good Match (Score Higher)"]
    
    # Deduplicate signals using a set while maintaining order
    raw_signals = preferences.get("goodMatchSignals", []) + analysis.suggested_good_match_signals
    seen_signals = set()
    signals = []
    for s in raw_signals:
        if s and s.lower() not in seen_signals:
            signals.append(s)
            seen_signals.add(s.lower())
    
    # Inferred defaults based on preferences
    remote_pref = preferences.get("remotePref", [])
    if isinstance(remote_pref, str): remote_pref = [remote_pref]
    
    primary_pref = preferences.get("primaryRemotePref", "")
    timezone_pref = preferences.get("timezonePref", "")

    if "remote" in remote_pref:
        tz_label = f" in {ID_TO_LABEL.get(timezone_pref, timezone_pref)}" if timezone_pref else ""
        signals.append(f"Fully remote roles{tz_label} (preferred setup)")
    if "hybrid" in remote_pref:
        city = preferences.get("location", "").split(",")[0].strip() or "local"
        signals.append(f"Hybrid roles from {city}")
    
    seniority_val = preferences.get("seniority", getattr(analysis, "inferred_seniority", None))
    if isinstance(seniority_val, list):
        seniority_str = " and ".join([s.capitalize() for s in seniority_val])
    elif seniority_val:
        seniority_str = seniority_val.capitalize()
    else:
        seniority_str = None

    if seniority_str:
        signals.append(f"{seniority_str}-level roles (seniority match)")
        
    for signal in signals:
        good_match_lines.append(f"- {signal}")
    sections.append("\n".join(good_match_lines))
    
    # ## Critical Skill Gaps
    gap_lines = ["## Critical Skill Gaps"]

    # Career goal context — describes what kind of gaps matter for the scorer,
    # without prescribing specific score numbers (those belong in scoring_philosophy.md)
    goal = preferences.get("careerGoal", "stay")
    if goal == "broaden":
        context_text = "Career goal: expanding into adjacent domains. Gaps in new areas are expected — distinguish between gaps where the candidate shows bridge evidence (portfolio, secondary experience) vs gaps with zero evidence."
    elif goal == "pivot":
        context_text = "Career goal: pivoting to a new field. Transferable skills and bridge evidence (e.g., portfolio projects) partially offset gaps in the new domain. Gaps without any supporting evidence remain significant."
    elif goal == "step_up":
        context_text = "Career goal: stepping up to higher scope or leadership. Look for leadership signals in prior roles (led teams, defined strategy, mentored). Management-specific gaps are less critical if leadership evidence exists elsewhere."
    else:  # stay
        context_text = "Career goal: deepening current specialization. Gaps in core required skills for the target roles are significant and should not be downplayed."

    gap_lines.append(f"**Career Context: {goal.replace('_', ' ').title()}**")
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
    
    # Deduplicate deal breakers
    raw_db = preferences.get("dealBreakers", []) + analysis.suggested_lower_fit_signals
    seen_db = set()
    deal_breakers = []
    for db in raw_db:
        if db and db.lower() not in seen_db:
            deal_breakers.append(db)
            seen_db.add(db.lower())
    
    # Standard entries based on seniority
    seniority_val = preferences.get("seniority", getattr(analysis, "inferred_seniority", ""))
    if isinstance(seniority_val, str):
        seniority_list = [seniority_val.lower()]
    elif isinstance(seniority_val, list):
        seniority_list = [s.lower() for s in seniority_val]
    else:
        seniority_list = []

    if any(s in ["senior", "lead", "staff", "principal"] for s in seniority_list):
        lower_fit_lines.append("- Junior or entry-level positions")
    
    remote_pref = preferences.get("remotePref", [])
    if isinstance(remote_pref, str): remote_pref = [remote_pref]

    if "remote" in remote_pref:
        lower_fit_lines.append("- On-site only positions")
    if "hybrid" in remote_pref or "onsite" in remote_pref:
        # If they are open to hybrid/onsite, they probably shouldn't penalize them globally 
        # unless it's a relocation mismatch, which scoring_philosophy handled via remote_location_fit
        pass
        
    for db in deal_breakers:
        lower_fit_lines.append(f"- {db}")
    sections.append("\n".join(lower_fit_lines))
    
    # ## Location & Work Setup
    loc_lines = ["## Location & Work Setup"]
    location = preferences.get('location', 'Unknown')
    work_auth = _get_label(preferences.get('workAuth', ''))
    
    remote_pref = preferences.get("remotePref", [])
    if isinstance(remote_pref, str): remote_pref = [remote_pref]
    primary_pref = preferences.get("primaryRemotePref", "")
    timezone_pref = preferences.get("timezonePref", "")

    city = location.split(",")[0].strip() or "Location"
    
    # Build beautiful natural language setup string
    setup_parts = []
    if primary_pref:
        setup_parts.append(f"Prefer {_get_label(primary_pref)}")
        if primary_pref == 'remote' and timezone_pref:
            setup_parts[-1] += f" ({_get_label(timezone_pref)})"
    
    other_setups = [s for s in remote_pref if s != primary_pref]
    if other_setups:
        pretty_others = []
        for s in other_setups:
            if s == 'remote': pretty_others.append("Fully Remote")
            else: pretty_others.append(f"{_get_label(s)} from {city}")
        setup_parts.append(f"but also open to {', '.join(pretty_others)}")

    setup_str = " ".join(setup_parts)
    
    loc_lines.append(f"- Based in: {location}")
    loc_lines.append(f"- Work authorization: {work_auth}")
    loc_lines.append(f"- Work setup: {setup_str}")
    
    target_regions = ", ".join(preferences.get("targetRegions", []))
    loc_lines.append(f"- Acceptable regions: {target_regions}")
    
    excluded = ", ".join(preferences.get("excludedRegions", []))
    if excluded:
        loc_lines.append(f"- Not acceptable: {excluded}")
    
    # Add setup negatives
    remote_pref_set = set(remote_pref)
    if "onsite" not in remote_pref_set:
        loc_lines.append("- Not acceptable: On-site only positions")
    if timezone_pref and timezone_pref != "any":
        tz_label = _get_label(timezone_pref)
        loc_lines.append(f"- Timezone requirement: {tz_label}")
        
    sections.append("\n".join(loc_lines))
    
    # ## Career Direction
    career_dir = preferences.get("careerDirection") or analysis.suggested_career_direction
    sections.append(f"## Career Direction\n{career_dir}")
    
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
