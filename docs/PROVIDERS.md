# Job Providers — Extension Guide

Job Radar collects jobs through **providers** — pluggable modules that each implement a common interface. The pipeline orchestrator (`src/main.py`) knows nothing about specific sources; it asks the registry for the right provider and calls `fetch_jobs()`.

Adding a new data source (LinkedIn, Indeed, a custom internal board, etc.) requires:
1. Implementing the `JobProvider` interface in a new class
2. Calling `register()` at the bottom of `src/providers.py`

That's it. The pipeline, pre-filter, scoring, web UI pipeline dialog, and the `/api/pipeline/providers` endpoint all pick up the new provider automatically.

---

## Core Abstractions (`src/providers.py`)

### `ProviderContext`

Passed to every `fetch_jobs()` call. Contains everything a provider might need — use only what's relevant.

```python
@dataclass
class ProviderContext:
    companies: dict[str, list[dict[str, str]]]  # from companies.yaml, keyed by platform
    profile_dir: Path                            # profiles/<name>/
    config: dict[str, Any]                       # full profile.yaml dict
```

### `ProviderInfo`

UI metadata returned by `GET /api/pipeline/providers`. Drives the pipeline trigger dialog in the web UI.

```python
@dataclass
class ProviderInfo:
    name: str                    # machine name; used as --source value
    display_name: str            # card title in the UI
    description: str             # card subtitle in the UI
    shows_aggregator_badge: bool # whether to show an aggregator freshness badge
```

### `JobProvider` (Protocol)

```python
@runtime_checkable
class JobProvider(Protocol):
    name: str
    display_name: str
    description: str
    shows_aggregator_badge: bool

    async def fetch_jobs(
        self,
        ctx: ProviderContext,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> list[RawJob]:
        ...
```

**Contract:**
- Return a flat `list[RawJob]` — never raise, return `[]` on failure
- Do not filter, score, or persist — only fetch
- Call `progress_callback(current, total)` at meaningful intervals if provided
- Description hydration is handled downstream by `src/fetcher.py`; return `description=""` if not available from your source

---

## Built-in Providers

| Provider | `name` | Source |
|----------|--------|--------|
| `HybridProvider` | `hybrid` | Runs AggregatorProvider then LocalATSProvider |
| `AggregatorProvider` | `aggregator` | Hosted static chunk download (~910k jobs) |
| `LocalATSProvider` | `local` | Direct ATS APIs (Greenhouse, Lever, Ashby, Workable) |

### Provider order in the registry

Providers appear in the web UI in registration order. The current order is: `hybrid → aggregator → local`, which puts the most useful option first.

---

## Writing a New Provider

### Minimal example

```python
# Can live in src/providers.py or a separate file (e.g. src/provider_linkedin.py)

class LinkedInProvider:
    name = "linkedin"
    display_name = "LinkedIn Jobs"
    description = "Searches LinkedIn's public job listings by keyword and location."
    shows_aggregator_badge = False

    async def fetch_jobs(
        self,
        ctx: ProviderContext,
        progress_callback=None,
    ) -> list[RawJob]:
        from datetime import datetime, timezone
        import httpx

        linkedin_cfg = ctx.config.get("linkedin", {})
        search_terms = linkedin_cfg.get("search_terms", [])
        location = linkedin_cfg.get("location", "")

        if not search_terms:
            return []

        jobs: list[RawJob] = []
        now = datetime.now(timezone.utc).isoformat()

        async with httpx.AsyncClient() as client:
            for i, term in enumerate(search_terms):
                results = await self._search(client, term, location)
                for r in results:
                    jobs.append(RawJob(
                        ats_platform="linkedin",
                        company_slug=r["company_slug"],
                        company_name=r["company_name"],
                        job_id=str(r["id"]),
                        title=r["title"],
                        location=r["location"],
                        url=r["url"],
                        description="",       # fetcher.py hydrates lazily
                        posted_at=r.get("posted_at"),
                        fetched_at=now,
                    ))
                if progress_callback:
                    progress_callback(i + 1, len(search_terms))

        return jobs

    async def _search(self, client, term, location) -> list[dict]:
        # your actual API / scraper call here
        ...
```

Then register it at the bottom of `src/providers.py`:

```python
from src.provider_linkedin import LinkedInProvider
register(LinkedInProvider())
```

The provider now appears in:
- `python src/main.py --source linkedin`
- `GET /api/pipeline/providers` response
- The pipeline trigger dialog in the web UI

### Adding provider-specific config

Providers read their own config key from `ctx.config`. Document the expected keys in your provider's class docstring:

```python
class LinkedInProvider:
    """
    Config (in profile.yaml):

      linkedin:
        search_terms: ["SDET", "QA Engineer", "Test Automation"]
        location: "Germany"
        limit: 50
    """
```

### Returning metadata alongside jobs

If your provider fetches version/timestamp metadata alongside jobs (like `AggregatorProvider` does), store it as an instance attribute after `fetch_jobs()` returns and let the orchestrator read it:

```python
class MyProvider:
    name = "my-source"
    last_updated: str = "unknown"

    async def fetch_jobs(self, ctx, progress_callback=None):
        jobs, version = await my_api.fetch(...)
        self.last_updated = version
        return jobs
```

In `src/main.py` the orchestrator already handles this pattern:

```python
if hasattr(provider, "last_updated") and provider.last_updated != "unknown":
    store.set_metadata(f"{provider.name}_version", provider.last_updated)
```

---

## Registry API

```python
from src.providers import PROVIDER_REGISTRY, get_all_info, register

# Look up a provider by name
provider = PROVIDER_REGISTRY["aggregator"]

# List all providers (returns list[ProviderInfo])
infos = get_all_info()

# Register a new provider (call at module load time)
register(MyProvider())
```

---

## Description Hydration

Providers are not responsible for fetching full job descriptions. Return `description=""` when the source doesn't include it (e.g. aggregator, Ashby, Workable). The pipeline's lazy hydration step (`src/fetcher.py`) will attempt to fetch descriptions later using:

1. Platform-specific APIs (if `ats_platform` matches a known fetcher)
2. JSON-LD structured data parsing (for standard career sites)
3. HTML scraping fallback (for custom domains)

Jobs that still lack a description after hydration are dismissed automatically, so ensure `url` points to the canonical job posting page.

---

## API Endpoint

`GET /api/pipeline/providers` returns all registered providers in registration order:

```json
[
  {
    "name": "hybrid",
    "display_name": "Comprehensive Scan",
    "description": "Global Aggregator + Targeted Boards: ...",
    "shows_aggregator_badge": true
  },
  {
    "name": "aggregator",
    "display_name": "Global Aggregator",
    "description": "Broad Market: Scans 910k+ jobs ...",
    "shows_aggregator_badge": true
  },
  {
    "name": "local",
    "display_name": "Targeted Boards",
    "description": "Direct Source: Scans your curated company list ...",
    "shows_aggregator_badge": false
  }
]
```

The web UI's pipeline trigger dialog (`web/src/components/pipeline/PipelineTrigger.tsx`) fetches this endpoint on open and renders a card for each provider dynamically. A static "Bulk Rescore Library" card is appended by the frontend since rescore calls a different API endpoint (`POST /api/jobs/rescore/all`).

---

## Checklist for a New Provider

- [ ] Class has `name`, `display_name`, `description`, `shows_aggregator_badge` attributes
- [ ] `fetch_jobs()` is `async` and returns `list[RawJob]`
- [ ] Never raises — wraps failures in `try/except` and returns `[]` or a partial list
- [ ] Calls `progress_callback(current, total)` periodically (enables web UI progress bar)
- [ ] Sets `ats_platform` on each `RawJob` to a consistent string (used for deduplication)
- [ ] Sets `job_id` to a stable, unique identifier within the platform
- [ ] Sets `url` to the canonical job posting URL (needed for description hydration)
- [ ] `register(MyProvider())` called at the bottom of `src/providers.py`
- [ ] Provider-specific config documented in the class docstring
