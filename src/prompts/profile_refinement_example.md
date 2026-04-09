REFERENCE EXAMPLE -- STRUCTURE ONLY

Use this example only for output shape and level of specificity.
Do NOT copy facts, roles, wording, or skills unless they are grounded in the
provided CV analysis and user preferences.

Example response:

{
  "profile_doc_sections": {
    "Experience Summary": "- 8+ years of experience\n- Senior Backend Engineer at ...",
    "Core Technical Stack": "### Backend Development (Primary Strength)\n- Python ecosystem: Python, FastAPI, Django -- strong production experience",
    "What Makes a Good Match (Score Higher)": "- Roles centered on backend platform ownership with clear production depth\n- Preferred industries such as developer tooling are a bonus, not a requirement\n- Adjacent platform roles are reasonable when tooling work is already present",
    "Critical Skill Gaps": "**Scoring Context**\nThese are confirmed gaps -- not 'learning quickly' adjacencies.\n- **Distributed Systems**: No direct evidence in the CV. Lower `tech_stack_match` when it is a core requirement; do not lower `growth_potential` when adjacent infrastructure evidence exists.",
    "What Lowers Fit (Score Lower)": "- Junior or entry-level positions\n- Roles requiring deep mobile expertise with no supporting evidence"
  },
  "search_config_keywords": {
    "title_patterns": {
      "high_confidence": [
        "\\bsenior\\s+backend\\s+engineer\\b",
        "\\bbackend\\s+engineer\\b",
        "\\bplatform\\s+engineer\\b"
      ],
      "broad": [
        "\\bplatform\\s+engineer\\b",
        "\\bdeveloper\\s+productivity\\s+engineer\\b",
        "\\bsite\\s+reliability\\s+engineer\\b"
      ]
    },
    "description_signals": {
      "min_matches": 1,
      "patterns": [
        "\\b(kafka|postgresql|redis)\\b",
        "\\bdeveloper\\s+tooling\\b",
        "\\b(ci/cd|github\\s+actions|jenkins)\\b",
        "\\b(test\\s+architecture|framework\\s+design)\\b"
      ]
    }
  },
  "changes_made": [
    "Tightened experience-summary bullets to remove overlap",
    "Expanded critical skill gaps with more specific scoring guidance",
    "Broadened title-pattern coverage while preserving prefilter recall"
  ]
}
