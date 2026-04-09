# Job Providers — Extension Guide

Job Radar collects jobs through pluggable **providers**. The orchestrator in `src/main.py` stays source-agnostic: it loads one or more providers from `PROVIDER_REGISTRY`, calls `fetch_jobs()`, then runs the shared dedupe, hydration, pre-filter, scoring, and reporting stages.

To add a new source:
1. Implement the `JobProvider` protocol in a new module under `src/providers/`.
2. Register an instance in `src/providers/__init__.py`.

That is enough for the CLI, web UI, and `GET /api/pipeline/providers` to discover it.

---

## Core Abstractions (`src/providers/__init__.py`)

### `ProviderContext`

Passed to every `fetch_jobs()` call:

```python
@dataclass
class ProviderContext:
    companies: dict[str, list[dict[str, Any]]]  # from companies.yaml
    profile_dir: Path                            # profiles/<name>/
    config: dict[str, Any]                       # search_config.yaml + runtime overrides
```

Notes:
- `config` comes from `search_config.yaml`.
- The CLI injects runtime flags into `config["runtime"]`. Today that includes `slow_mode`, which providers such as `local` and `adzuna` use to reduce request rate.

### `ProviderInfo`

Metadata exposed through `GET /api/pipeline/providers`:

```python
@dataclass
class ProviderInfo:
    name: str
    display_name: str
    description: str
    shows_aggregator_badge: bool = False
```

### `JobProvider`

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

Provider contract:
- Return `list[RawJob]`.
- Never raise for normal fetch failures; log and return `[]`.
- Do not pre-filter, score, or persist.
- Call `progress_callback(current, total)` when it provides meaningful UI progress.
- Populate the best description you have, but do not own downstream hydration.

---

## Built-in Providers

Current registry order:

| Provider | `name` | Source type |
|----------|--------|-------------|
| `AggregatorProvider` | `aggregator` | Hosted remote-job aggregator dataset |
| `LocalATSProvider` | `local` | Direct ATS APIs for curated companies |
| `RemotiveProvider` | `remotive` | Public Remotive API |
| `RemoteOKProvider` | `remoteok` | Public Remote OK feed |
| `HackerNewsProvider` | `hackernews` | HN "Who is hiring?" comments via Algolia |
| `ArbeitnowProvider` | `arbeitnow` | Arbeitnow API |
| `WeWorkRemotelyProvider` | `weworkremotely` | We Work Remotely feed |
| `AdzunaProvider` | `adzuna` | Adzuna API (requires keys) |

Providers appear in the web UI in this registration order.

---

## Writing a New Provider

### Minimal example

```python
from __future__ import annotations

from datetime import datetime, timezone

import httpx

from src.models import RawJob
from src.providers import ProviderContext, slugify


class ExampleProvider:
    name = "example"
    display_name = "Example Jobs"
    description = "Fetches jobs from Example's public API."
    shows_aggregator_badge = False

    async def fetch_jobs(self, ctx: ProviderContext, progress_callback=None) -> list[RawJob]:
        jobs: list[RawJob] = []
        now = datetime.now(timezone.utc).isoformat()
        config = ctx.config.get("example", {}) if isinstance(ctx.config, dict) else {}
        query = config.get("query", "")

        async with httpx.AsyncClient() as client:
            response = await client.get("https://api.example.com/jobs", params={"q": query})
            response.raise_for_status()
            payload = response.json()

        for item in payload.get("results", []):
            jobs.append(
                RawJob(
                    ats_platform="example",
                    company_slug=slugify(item.get("company", "example")),
                    company_name=item.get("company", "Example"),
                    job_id=str(item["id"]),
                    title=item.get("title", ""),
                    location=item.get("location", ""),
                    url=item.get("url", ""),
                    description=item.get("description", ""),
                    posted_at=item.get("posted_at"),
                    fetched_at=now,
                )
            )

        if progress_callback:
            progress_callback(len(jobs), len(jobs))

        return jobs
```

Register it in `src/providers/__init__.py`:

```python
from src.providers.example import ExampleProvider

register(ExampleProvider())
```

The provider will then work in:
- `python -m src.main --source example`
- `GET /api/pipeline/providers`
- the pipeline trigger dialog in the web UI

### Provider-specific config

Read provider config from `ctx.config`. Document the expected keys against `search_config.yaml`, for example:

```yaml
example:
  query: "qa automation"
  location: "Germany"
  limit: 50
```

### Provider metadata

If your provider exposes upstream freshness or version metadata, store it on the provider instance after `fetch_jobs()`. The orchestrator will persist values such as `last_updated` when present.

---

## Description Hydration

Providers are not responsible for full description hydration. Return the best description you have and let the shared hydration layer handle the rest.

Important current behavior:
- Jobs with missing descriptions are hydrated downstream.
- Jobs with **sparse** descriptions are also hydrated downstream.
- Short source text can be merged into the hydrated description instead of being discarded.

This logic lives in `src/description_hydration.py` and is applied by the pipeline after collection.

Practical guidance:
- Always return the canonical posting URL in `url`.
- Return `description=""` when the source truly has no usable text.
- Do not try to reimplement HTML or JSON-LD fallback scraping in the provider itself.

---

## Registry API

```python
from src.providers import PROVIDER_REGISTRY, get_all_info, register

provider = PROVIDER_REGISTRY["local"]
infos = get_all_info()
register(MyProvider())
```

---

## API Endpoint

`GET /api/pipeline/providers` returns all registered providers in registration order:

```json
[
  {
    "name": "aggregator",
    "display_name": "Global Aggregator",
    "description": "Broad market remote scan",
    "shows_aggregator_badge": true
  },
  {
    "name": "local",
    "display_name": "Tracked Companies",
    "description": "Direct ATS fetch from companies.yaml",
    "shows_aggregator_badge": false
  }
]
```

---

## Implementation Checklist

- [ ] Create a provider module under `src/providers/`
- [ ] Expose `name`, `display_name`, `description`, and `shows_aggregator_badge`
- [ ] Implement `fetch_jobs()` as `async` and return `list[RawJob]`
- [ ] Handle normal upstream failures without crashing the run; log and return `[]` or a partial list
- [ ] Call `progress_callback(current, total)` when the source can report meaningful progress
- [ ] Set `ats_platform` to a stable source identifier on every `RawJob`
- [ ] Set `job_id` to a stable unique ID within that platform
- [ ] Set `url` to the canonical posting URL so downstream hydration has a reliable target
- [ ] Return the best available description text, or `""` if the source truly does not provide usable content
- [ ] Register the provider in `src/providers/__init__.py`
- [ ] Add parser or normalization tests with mocked payloads, not live network calls
- [ ] Verify the provider works in `python -m src.main --source <name> --dry-run`
- [ ] Document any required environment variables or config keys
