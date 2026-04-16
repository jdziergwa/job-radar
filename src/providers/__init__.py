"""JobProvider protocol and registry.

To add a new provider:
  1. Implement a class with a `name` attribute and an async `fetch_jobs()` method.
  2. Optionally set `display_name`, `description`, and `shows_aggregator_badge`.
  3. Call register(YourProvider()) at the bottom of this file.

The provider will automatically appear in the web UI pipeline trigger dialog.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional, Protocol, runtime_checkable

from src.models import RawJob
from src.providers.utils import parse_salary_string, slugify, strip_html
from src.providers.aggregator import AggregatorProvider
from src.providers.local_ats import LocalATSProvider


@dataclass
class ProviderContext:
    """Everything a provider may need. Use only what's relevant to your provider."""
    companies: dict[str, list[dict[str, Any]]]  # from companies.yaml
    profile_dir: Path                            # profiles/<name>/
    config: dict[str, Any]                       # from profile.yaml


@dataclass
class ProviderInfo:
    """Metadata for a provider — used by the web UI to render pipeline options."""
    name: str               # machine name; used as --source value
    display_name: str       # shown as card title in the UI
    description: str        # shown as card subtitle in the UI
    shows_aggregator_badge: bool = False  # whether to show aggregator freshness badge


ProgressCallback = Optional[Callable[[int, int], None]]


@runtime_checkable
class JobProvider(Protocol):
    """Interface all job providers must satisfy.

    Fetches raw jobs from one source. Does NOT filter, score, or hydrate descriptions.
    Return [] on any error — never raise.

    Standardization:
      - Use `src.providers.slugify(company_name)` for `company_slug`.
      - Use `src.providers.parse_salary_string(raw_string)` to populate numeric salary fields.
    """

    #: Machine name; used as --source value and registry key.
    name: str
    #: Human-readable title shown in UI cards.
    display_name: str
    #: Short description shown in UI cards.
    description: str
    #: Whether the UI should show an aggregator freshness badge on this card.
    shows_aggregator_badge: bool

    async def fetch_jobs(
        self,
        ctx: ProviderContext,
        progress_callback: ProgressCallback = None,
    ) -> list[RawJob]:
        """Fetch and return all available jobs. Never raise — return [] on failure."""
        ...




# ── Registry ─────────────────────────────────────────────────────────

#: Map of source-name → provider instance.
#: Providers appear in the web UI in insertion order.
PROVIDER_REGISTRY: dict[str, JobProvider] = {}


def register(provider: JobProvider) -> None:
    """Register a provider instance by its name."""
    PROVIDER_REGISTRY[provider.name] = provider


def get_all_info() -> list[ProviderInfo]:
    """Return UI metadata for all registered providers, in registration order."""
    return [
        ProviderInfo(
            name=p.name,
            display_name=p.display_name,
            description=p.description,
            shows_aggregator_badge=p.shows_aggregator_badge,
        )
        for p in PROVIDER_REGISTRY.values()
    ]


register(AggregatorProvider())
register(LocalATSProvider())

# ── New providers ──
from src.providers.remotive import RemotiveProvider
from src.providers.remoteok import RemoteOKProvider
from src.providers.hackernews import HackerNewsProvider
from src.providers.arbeitnow import ArbeitnowProvider
from src.providers.weworkremotely import WeWorkRemotelyProvider
from src.providers.adzuna import AdzunaProvider
from src.providers.himalayas import HimalayasProvider

register(RemotiveProvider())
register(RemoteOKProvider())
register(HackerNewsProvider())
register(ArbeitnowProvider())
register(WeWorkRemotelyProvider())
register(AdzunaProvider())
register(HimalayasProvider())
