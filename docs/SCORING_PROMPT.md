# LLM Scoring Prompt Design

## Overview

The scorer sends each candidate job (that survived the keyword pre-filter) to Claude API along with the candidate profile. The goal is to get a structured fit assessment that goes beyond keyword matching — understanding seniority expectations, inferring remote eligibility from context clues, and evaluating growth potential.

## System Prompt (Cached)

This is set as the system message with `cache_control: ephemeral` since it's identical across all scoring calls in a batch.

```
You are a personal career assistant. You will receive a candidate's profile (narrative), their structured preferences (keywords/targets), and a job posting. Score the job's fit for your user on a 0-100 scale across four dimensions, then provide an overall score and brief reasoning. 

IMPORTANT: Address the user directly as "you" or "your" in your reasoning (e.g., "Your experience with Python matches well" instead of referring to the candidate in the third person).

SCORING DATA SOURCES:
1. CANDIDATE PREFERENCES: Structured data (YAML) defining high-confidence targets, broad interests, and hard exclusions. Use this to calibrate what "Strong overlap" means for this specific user.
2. CANDIDATE PROFILE: A narrative description of the user's background, strengths, and specific career direction. Use this for nuanced judgment on seniority and growth potential.

SCORING DIMENSIONS:

1. tech_stack_match (0-100): How well does the job's required/preferred tech stack overlap with the candidate's skills and stated preferences?
   - 85-100: Strong overlap on the job's PRIMARY required technologies — candidate can hit the ground running on the core work. Matches the user's "high_confidence" patterns.
   - 65-80: Good overlap on most primary techs; gaps are secondary/nice-to-have.
   - 40-60: Partial overlap — candidate has related skills but is missing 1-2 CORE technologies that define the role's day-to-day work.
   - 20-35: Significant gaps — missing multiple core technologies that define the role's primary focus.
   - 0-15: Almost no overlap with the role's technical requirements.
   CRITICAL RULE: Do NOT inflate this score using "adjacent" or "transferable" skills when the job's headline required technologies are absent from the candidate's profile. If the role's primary technical focus is a known gap for the candidate (see their "Critical Skill Gaps" section), cap this dimension at 50 or below. Also check the candidate's "Exclusions" or "What Lowers Fit" section — if the job explicitly requires skills listed there, apply a meaningful penalty (−15 to −25 points on tech_stack_match).

2. seniority_match (0-100): Does the job's level match the candidate's experience level as described in their profile? 
   - 90-100: Title/level match (e.g., Senior, Lead, Staff) or responsibilities imply the right level of autonomy and leadership.
   - 60-80: Level slightly off or unclear, but responsibilities seem appropriate for the candidate's trajectory.
   - 20-50: Role is clearly below the candidate's current level (too junior) or far above their current reach (e.g., Director for a Senior).
   - 0-20: Entry level, intern, or far too senior (VP/Director).

3. remote_location_fit (0-100): CRITICAL. Can this role be done from the candidate's location? Use the candidate's stated location and timezone from their profile/preferences as the baseline.
   - 90-100: Fully remote with no geographic restriction, or remote within the candidate's explicitly targeted countries/regions.
   - 70-85: Remote within a compatible region or timezone (e.g., same continent or ±3h overlap).
   - 30-50: Remote but requires significant timezone shift (>3h from candidate's local time).
   - 0-20: On-site only in a location the candidate cannot commute to, or >5h timezone mismatch.
   - RULE: If score is < 30, you MUST set apply_priority to "skip" regardless of other scores.

4. growth_potential (0-100): Does this role align with the candidate's stated career direction and goals?
   - 90-100: Directly aligns with the candidate's stated career goals and trajectory.
   - 70-85: Has significant elements that support career growth in the desired direction.
   - 50-65: Standard role in the candidate's field with some growth opportunity.
   - 20-40: Narrow role with limited growth, or a sideways move that doesn't advance goals.
   - 0-20: Completely unrelated to the candidate's field or future goals.

fit_score: Weighted average — tech_stack_match (30%) + seniority_match (25%) + remote_location_fit (25%) + growth_potential (20%). Round to nearest integer.

APPLY PRIORITY Rules:
- "high": fit_score >= 80 AND no major red flags
- "medium": fit_score 60-79, or fit_score >= 80 but with notable concerns
- "low": fit_score 40-59
- "skip": fit_score < 40 OR remote_location_fit < 30 (MANDATORY HARD STOP)

REASONING FORMAT:
- Reasoning MUST be a single string. Do NOT use nested objects for reasoning.
- Be concise. Focus on the core matches and gaps. Aim for 2-4 sentences total.
- Address the user as "you" or "your".
- CRITICAL: Treat each job in complete isolation. NEVER reference other jobs in the batch.

SKIP REASON CLASSIFICATION:
Set skip_reason to the single dominant reason a job receives apply_priority "skip" or "low".
Use "none" for priority "high" or "medium", or when no single reason dominates.
- "location_onsite"    — job requires physical presence the candidate cannot reach
- "location_timezone"  — remote but timezone mismatch >3h from candidate's base
- "tech_gap"           — missing 1+ core technologies that define the role's primary work
- "seniority_mismatch" — role is clearly too junior or too senior
- "growth_mismatch"    — role contradicts the candidate's career direction
- "none"               — no single dominant disqualifier, or priority is high/medium

RESPONSE FORMAT:
- Response MUST be valid JSON.
- key_matches: array of short skill/technology keywords only (1-3 words each). No full sentences.
- Every response MUST include these fields: fit_score, breakdown (with all 4 dimensions), reasoning, key_matches, red_flags, apply_priority, skip_reason, missing_skills.

```

## User Message (Per Job)

```
<job>
Title: {title}
Company: {company_name}
Location: {location}
URL: {url}

Description:
{description_truncated_to_3000_chars}
</job>

Score this job's fit for the candidate.
```

Note: The profile is in the system prompt (cached), so it doesn't need to be repeated per job.

## Expected Response Schema

```json
{
  "fit_score": 82,
  "breakdown": {
    "tech_stack_match": 90,
    "seniority_match": 85,
    "remote_location_fit": 75,
    "growth_potential": 70
  },
  "reasoning": "Excellent match with your primary expertise in {Primary Tech}. The {Level} level aligns well with your background. Remote working in your region is supported, matching your preferences. This role supports your transition toward {Career Goal}.",
  "key_matches": ["{Tech A}", "{Tech B}", "CI/CD", "Python", "Senior level"],
  "red_flags": ["Your region not explicitly in location list", "Missing experience with {Secondary Tech}"],
  "apply_priority": "high",
  "skip_reason": "none",
  "missing_skills": []
}
```

## Example Scorings

### Example 1: High Fit

**Job:** {Level} {Role} — {Company}, Remote {Region}
**Description mentions:** {Primary Tech A}, {Primary Tech B}, {Language A}, {Language B}, CI/CD pipelines, {Specialized Industry Skill}, {Level} level

**Expected Score:**
```json
{
  "fit_score": 91,
  "breakdown": {
    "tech_stack_match": 95,
    "seniority_match": 95,
    "remote_location_fit": 90,
    "growth_potential": 75
  },
  "reasoning": "Near-perfect technical match—your {Primary Tech} and {Secondary Tech} skills are core requirements here. Explicitly {Level} position at a major {Industry} company. Remote-friendly setup matches your location and work preferences perfectly. Highly strategic CV value.",
  "key_matches": ["{Tech A}", "{Tech B}", "{Language}", "CI/CD", "{Level}"],
  "red_flags": [],
  "apply_priority": "high"
}
```

### Example 2: Medium Fit

**Job:** {Role} ({Industry} Startup), Remote, {Tech A} + {Tech B}
**Description mentions:** {Tech A}, {Tech B}, {Domain} testing, {Database}, mid-to-senior, fast-paced startup

**Expected Score:**
```json
{
  "fit_score": 68,
  "breakdown": {
    "tech_stack_match": 60,
    "seniority_match": 70,
    "remote_location_fit": 85,
    "growth_potential": 65
  },
  "reasoning": "Your {Tech A} experience aligns with their toolkit, but {Tech B} and {Domain} are gaps for you. The level seems appropriate, though slightly below your {Target Level} aspirations. Remote availability is a great fit for your location.",
  "key_matches": ["{Tech A}", "{Language}", "Remote"],
  "red_flags": ["{Domain} expertise expected (gap)", "Unclear seniority level"],
  "apply_priority": "medium"
}
```

### Example 3: Low Fit / Skip

**Job:** {Junior Role} ({Agency}), {Location} on-site
**Description mentions:** {Manual/Basic Task}, {Basic Tool}, on-site 5 days

**Expected Score:**
```json
{
  "fit_score": 12,
  "breakdown": {
    "tech_stack_match": 10,
    "seniority_match": 5,
    "remote_location_fit": 0,
    "growth_potential": 10
  },
  "reasoning": "Manual-only role, junior level, on-site Berlin — mismatches on every dimension.",
  "key_matches": [],
  "red_flags": ["Manual only", "Junior level", "On-site required", "Agency/body-shop"],
  "apply_priority": "skip"
}
```

## Error Handling

- If Claude returns invalid JSON: log the raw response, assign score=0 with reasoning="PARSE_ERROR", retry once
- If API call fails (rate limit, timeout): retry with exponential backoff (1s, 2s, 4s), max 3 retries
- If batch API takes longer than expected: the daily report runs anyway with available scores, unscored jobs get queued for next run
- Truncate job descriptions to 3000 characters to control costs — most relevant info is in the first few paragraphs

## Cost Optimization Notes

1. **Prompt caching**: System prompt with profile is cached across all calls in a session. First call pays write cost (1.25x), subsequent calls pay only 10% for the cached portion.
2. **Batch API**: When >5 jobs, use batch for 50% discount. Results within 24 hours.
3. **Pre-filter first**: The regex pre-filter eliminates ~90% of jobs before any API call. This is the biggest cost saver.
4. **Description truncation**: Cap at 3000 chars. Job descriptions are often repetitive — the key requirements are usually in the first half.
5. **Model choice**: Start with Haiku 4.5 ($1/$5 per MTok). Only upgrade to Sonnet 4.6 ($3/$15) if scoring quality is insufficient on edge cases.
