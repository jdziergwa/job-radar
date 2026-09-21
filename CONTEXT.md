# Job Radar

Finds job postings from many sources, scores them against a candidate profile using an AI model, and presents them on a board.

## Language

**Job Provider**:
A pluggable source of job postings, such as a job board or company careers API.
_Avoid_: Provider (unqualified), source, scraper

**LLM Provider**:
The vendor whose API serves the AI models, such as Anthropic or Google Gemini. One LLM Provider is active at a time.
_Avoid_: Provider (unqualified), vendor, backend, AI

**Model**:
A specific model offered by an LLM Provider, identified by its model name (e.g. `gemini-2.5-flash`).
_Avoid_: engine, LLM

**AI Task**:
A distinct job the app gives to an AI model: scoring, CV wizard analysis, or stats insight.
_Avoid_: feature, call

**Model Assignment**:
The binding of an AI Task to a Model of the active LLM Provider.
_Avoid_: model config, model setting
