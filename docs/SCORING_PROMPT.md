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
- **Dimensions**: The specific categories being scored (Tech Stack, Seniority, etc.).
- **Rubrics**: Descriptions of what constitutes a High (80-100), Medium (60-80), or Low score.
- **Weights & Penalties**: How different dimensions contribute to the final `fit_score`.
- **Special Rules**: Logic for handling specific scenarios like portfolio projects vs. commercial experience.

## Example Scoring logic

While the philosophy can be customized per profile, the standard logic follows these principles:

- **Strict Tech Matching**: Avoiding score inflation from "adjacent" skills if core requirements are missing.
- **Hard Stop on Location**: Automatic "skip" if the role requires on-site presence in a non-commutable location or has a major timezone mismatch (>3h).
- **Concise Reasoning**: Brief, direct feedback addressed to the user ("You have...", "Your background...").

## Fallback Mechanism

If a profile does not define a custom `scoring_philosophy.md`, the system automatically falls back to the one defined in the **example profile** (`profiles/example/scoring_philosophy.md`). This ensures every scan has a baseline for evaluation.
