# LLM Scoring Prompt Documentation

This document explains the logic, structure, and philosophy used by Job Radar's AI to assess job fit. 

> [!NOTE]
> **DEVELOPER REFERENCE**: This document is for human documentation only. The actual prompt sent to the LLM is assembled dynamically at runtime from:
> 1. **Structural Template**: `src/prompts/scoring_structure.md` (Fixed JSON format and instructions)
> 2. **Scoring Philosophy**: `profiles/<name>/scoring_philosophy.md` (Per-profile rubrics and weights)

## Overview

The scorer evaluates each job posting that survives the initial keyword pre-filter. It uses Claude AI to perform a nuanced assessment based on the candidate's profile and stated preferences.

The goal is to provide a structured fit assessment that considers:
- **Technical Alignment**: Matching core skills and identifying critical gaps.
- **Seniority**: ensuring the role matches the candidate's experience level.
- **Location/Remote Fit**: Verifying timezone and geographic eligibility.
- **Growth Potential**: Assessing alignment with career goals.

The concrete score dimensions used by the application are:
- `tech_stack_match`
- `seniority_match`
- `remote_location_fit`
- `growth_potential`

These are the only structured fit dimensions the scorer should produce and the rest of the system should interpret.

## Prompt Architecture

The system prompt is divided into two distinct layers to ensure both flexibility and technical reliability.

### 1. Structural Template (The "System Contract")
Located in `src/prompts/scoring_structure.md`, this layer defines the rules that the AI must follow to remain compatible with the backend parser. It includes:
- **Identity**: Sets the AI's persona as a career assistant.
- **Format Requirements**: Mandates a strict JSON response schema.
- **Field Definitions**: Explains what each field (e.g., `fit_score`, `key_matches`, `skip_reason`) represents.
- **Salary Extraction**: Detailed rules for cleaning and validating compensation data.

### 2. Scoring Philosophy (The "Matching Logic")
Located in `profiles/<name>/scoring_philosophy.md`, this layer contains the criteria for evaluation. It defines:
- **Dimensions**: The specific score dimensions being used: `tech_stack_match`, `seniority_match`, `remote_location_fit`, and `growth_potential`.
- **Rubrics**: Descriptions of what constitutes a High (80-100), Medium (60-80), or Low score.
- **Weights & Penalties**: How different dimensions contribute to the final `fit_score`.
- **Special Rules**: Logic for handling specific scenarios like portfolio projects vs. commercial experience.

### 3. Wizard-Generated Profile Inputs

For most users, the scorer no longer relies on a hand-written `profile_doc.md` alone. The guided wizard now generates and refines that document from structured CV analysis and saved preferences before scoring runs happen.

In practice, that means the scorer often receives a `profile_doc.md` with more explicit matching guidance, including:
- structured role targeting
- a clearer `Core Technical Stack`
- explicit `What Makes a Good Match (Score Higher)` signals
- explicit `Critical Skill Gaps`
- explicit `What Lowers Fit (Score Lower)` guidance
- user-authored career direction preserved from the wizard

The scorer consumes those generated profile files indirectly through the profile on disk. The scoring prompt itself is still assembled dynamically at runtime, but the quality and structure of the wizard-generated profile materially affects scoring consistency.

## Example Scoring logic

While the philosophy can be customized per profile, the standard logic follows these principles:

- **Strict Tech Matching**: Avoiding score inflation from "adjacent" skills if core requirements are missing.
- **Hard Stop on Location**: Automatic "skip" if the role requires on-site presence in a non-commutable location or has a major timezone mismatch (>3h).
- **Dimension Discipline**: Gaps and boosts should be expressed through the real score dimensions above rather than invented labels.
- **Concise Reasoning**: Brief, direct feedback addressed to the user ("You have...", "Your background...").

## Fallback Mechanism

If a profile does not define a custom `scoring_philosophy.md`, the system automatically falls back to the one defined in the **example profile** (`profiles/example/scoring_philosophy.md`). This ensures every scan has a baseline for evaluation.
