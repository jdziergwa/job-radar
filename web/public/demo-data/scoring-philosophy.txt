SCORING DIMENSIONS:

1. tech_stack_match (0-100): How well does the job's required/preferred tech stack overlap with the candidate's skills and stated preferences?
   - 85-100: Strong overlap on the job's PRIMARY required technologies — candidate can hit the ground running on the core work. Matches the user's "high_confidence" patterns.
   - 65-80: Good overlap on most primary techs; gaps are secondary/nice-to-have.
   - 40-60: Partial overlap — candidate has related skills but is missing 1-2 CORE technologies that define the role's day-to-day work.
   - 20-35: Significant gaps — missing multiple core technologies that define the role's primary focus.
   - 0-15: Almost no overlap with the role's technical requirements.
   CRITICAL RULE: Do NOT inflate this score using "adjacent" or "transferable" skills when the job's headline required technologies are absent from the candidate's profile. If the role's primary technical focus is a known gap for the candidate (see their "Critical Skill Gaps" section), cap this dimension at 50 or below. Also check the candidate's "Exclusions" or "What Lowers Fit" section — if the job explicitly requires skills listed there, apply a meaningful penalty (−15 to −25 points on tech_stack_match).
   PORTFOLIO VS. COMMERCIAL EXPERIENCE RULE:
   - If a core required skill for the job is found in the candidate's profile ONLY via portfolio/personal projects and NOT through commercial/professional experience, treat it as "Partial but unproven overlap".
   - Apply a slight penalty to the tech_stack_match score (reduce it by 5 to 10 points).
   - Do NOT penalize it heavily or treat it as a completely missing skill. The candidate possesses the practical capability and is looking to migrate these portfolio skills into professional roles, so these jobs should remain viable.

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
   - CITY MISMATCH/UNCERTAINTY RULE: Pay attention to the specific city mentioned in the posting. If the job specifies a city different from the candidate's home city, but does NOT explicitly state whether it is "on-site" or "remote", treat this as uncertainty rather than an automatic hard stop. Score it moderately (40-60) reducing the fit due to the geographic distance, but keeping it viable enough to not trigger an automatic skip, in case they are actually open to remote work.

4. growth_potential (0-100): Does this role align with the candidate's stated career direction and goals?
   - 90-100: Directly aligns with the candidate's stated career goals and trajectory.
   - 70-85: Has significant elements that support career growth in the desired direction.
   - 50-65: Standard role in the candidate's field with some growth opportunity.
   - 20-40: Narrow role with limited growth, or a sideways move that doesn't advance goals.
   - 0-20: Completely unrelated to the candidate's field or future goals.

fit_score: Weighted average — tech_stack_match (30%) + seniority_match (25%) + remote_location_fit (25%) + growth_potential (20%). IMPORTANT: Penalize the final score based on the severity of any red flags found:
- Minor red flags (e.g., missing a nice-to-have skill, slightly unclear terms): apply a small penalty of -2 to -5 points (allowing exceptionally strong matches to remain 'high' >= 80).
- Major concerns (e.g., missing a core required skill, notable domain mismatch): apply a significant penalty of -10 to -20 points (pulling the score into 'medium' or lower).
Round the final result to the nearest integer.

APPLY PRIORITY Rules (Strictly tied to fit_score):
- "high": fit_score >= 80
- "medium": fit_score 60-79
- "low": fit_score 40-59
- "skip": fit_score < 40 OR remote_location_fit < 30 (MANDATORY HARD STOP)

GARBAGE / BROKEN DESCRIPTION RULE:
- If the job description is completely missing, consists mostly of raw JavaScript/code, or is otherwise completely unreadable or nonsensical, you MUST score the job a 0 across all dimensions. Do NOT hallucinate a high score based solely on the job title. Set apply_priority to "skip" and note the broken description in the reasoning.

SPARSE DESCRIPTION RULE:
- Often, sources like HackerNews, RemoteOK, or Remotive provide "teaser" postings (typically < 600 characters) that provide a high-level mission statement and a link, but lack detailed technical requirements, frameworks, or daily responsibilities.
- If you find a posting fits this description, you MUST set `is_sparse: true` in the JSON response.
- Do NOT automatically score these as 0, but acknowledge the limited information in your reasoning.

SKIP REASON CLASSIFICATION:
Set skip_reason to the single dominant reason a job receives apply_priority "skip" or "low".
Use "none" for priority "high" or "medium", or when no single reason dominates.
- "location_onsite"    — job requires physical presence the candidate cannot reach
- "location_timezone"  — remote but timezone mismatch >3h from candidate's base
- "tech_gap"           — missing 1+ core technologies that define the role's primary work
- "seniority_mismatch" — role is clearly too junior or too senior
- "growth_mismatch"    — role contradicts the candidate's career direction
- "none"               — no single dominant disqualifier, or priority is high/medium
