# In-repo adapter per LLM Provider, not a multi-vendor library

The app must run on Anthropic or Google Gemini, chosen by the user via `LLM_PROVIDER`. We wrote a thin in-repo interface (text/JSON completion, usage, error mapping, and a cacheable-system-prompt hint) with one adapter per LLM Provider, instead of adopting a library such as LiteLLM. Our needs are plain completions, so the surface is small, it avoids a heavy dependency, and it lets the Anthropic adapter keep explicit `cache_control` prompt caching.

## Considered Options

- **LiteLLM (or similar):** less adapter code and many vendors for free, but a large dependency and a lowest-common-denominator view of vendor features like caching. Revisit if we need many more LLM Providers.
