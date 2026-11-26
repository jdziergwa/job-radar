import importlib.util
import os
from pathlib import Path
import sys
import types

# Keep test runs out of the real logs/ debug file (src/log_file.py).
os.environ["JOB_RADAR_LOG_FILE"] = ""

from fastapi.testclient import TestClient
import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


if "dotenv" not in sys.modules:
    dotenv = types.ModuleType("dotenv")

    def load_dotenv(*args, **kwargs):  # pragma: no cover - no-op test stub
        return False

    dotenv.load_dotenv = load_dotenv
    sys.modules["dotenv"] = dotenv


if "anthropic" not in sys.modules:
    anthropic = types.ModuleType("anthropic")

    class _FakeMessages:
        async def create(self, *args, **kwargs):  # pragma: no cover - fail fast if a test hits the real scoring path
            raise AssertionError("Tests must not call the real Anthropic API")

    class AsyncAnthropic:  # pragma: no cover - import-only stub
        def __init__(self, *args, **kwargs):
            self.messages = _FakeMessages()

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class Anthropic:  # pragma: no cover - import-only stub
        def __init__(self, *args, **kwargs):
            self.messages = _FakeMessages()

    anthropic.AsyncAnthropic = AsyncAnthropic
    anthropic.Anthropic = Anthropic
    anthropic.RateLimitError = Exception
    anthropic.APIError = Exception
    sys.modules["anthropic"] = anthropic


if "httpx" not in sys.modules and importlib.util.find_spec("httpx") is None:
    httpx = types.ModuleType("httpx")

    class AsyncClient:  # pragma: no cover - import-only stub
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, *args, **kwargs):
            raise AssertionError("Tests must not perform real HTTPX requests")

    httpx.AsyncClient = AsyncClient
    sys.modules["httpx"] = httpx


if "aiohttp" not in sys.modules and importlib.util.find_spec("aiohttp") is None:
    aiohttp = types.ModuleType("aiohttp")

    class ClientSession:  # pragma: no cover - import-only stub
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def get(self, *args, **kwargs):
            raise AssertionError("Tests must not perform real aiohttp requests")

    class TCPConnector:  # pragma: no cover - import-only stub
        def __init__(self, *args, **kwargs):
            pass

    class ClientTimeout:  # pragma: no cover - import-only stub
        def __init__(self, *args, **kwargs):
            pass

    aiohttp.ClientSession = ClientSession
    aiohttp.TCPConnector = TCPConnector
    aiohttp.ClientTimeout = ClientTimeout
    sys.modules["aiohttp"] = aiohttp


from api.main import app
from src.models import RawJob
from src.store import Store


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def store(tmp_path) -> Store:
    return Store(str(tmp_path / "jobs.db"))


@pytest.fixture
def raw_job_factory():
    def factory(**overrides) -> RawJob:
        payload = {
            "ats_platform": "ashby",
            "company_slug": "acme",
            "company_name": "Acme",
            "job_id": "job-1",
            "title": "Senior QA Engineer",
            "location": "Remote",
            "url": "https://example.com/jobs/1",
            "description": "Own the test platform.",
            "posted_at": "2026-04-08T00:00:00Z",
            "fetched_at": "2026-04-08T00:00:00Z",
            "match_tier": None,
        }
        payload.update(overrides)
        return RawJob(**payload)

    return factory


@pytest.fixture
def seed_sample_jobs(store: Store, raw_job_factory):
    def seed() -> dict[str, int]:
        store.upsert_jobs(
            [
                raw_job_factory(match_tier="high_confidence"),
                raw_job_factory(
                    ats_platform="lever",
                    company_slug="globex",
                    company_name="Globex",
                    job_id="job-2",
                    title="Backend Engineer",
                    location="Berlin",
                    url="https://example.com/jobs/2",
                    description="Backend APIs.",
                ),
            ]
        )

        seeded: dict[str, int] = {}
        for candidate in store.get_unscored():
            seeded[candidate.job_id] = candidate.db_id
            if candidate.job_id == "job-1":
                store.update_score(
                    db_id=candidate.db_id,
                    fit_score=82,
                    reasoning="Strong fit for SDET scope.",
                    breakdown={
                        "tech_stack_match": 84,
                        "seniority_match": 80,
                        "remote_location_fit": 90,
                        "growth_potential": 76,
                    },
                    fit_category="core_fit",
                    apply_priority="medium",
                )

        return seeded

    return seed


@pytest.fixture
def bind_store(monkeypatch, store: Store):
    def bind(*modules) -> Store:
        for module in modules:
            monkeypatch.setattr(module, "get_store", lambda profile="default", _store=store: _store)
        return store

    return bind


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def _isolated_data_dir(tmp_path_factory, monkeypatch):
    """Keep API paths that open the app-side store off the real data/ directory."""
    monkeypatch.setattr("api.deps.DATA_DIR", tmp_path_factory.mktemp("appdata"))


@pytest.fixture
def fake_ai():
    """Inject the fake LLM adapter so the AI-configured check passes without a key."""
    from src.llm import set_adapter_override
    from tests.fake_llm import FakeLLMAdapter

    set_adapter_override(FakeLLMAdapter())
    yield
    set_adapter_override(None)


@pytest.fixture
def no_ai_key(monkeypatch):
    """No LLM Provider selected, no key, no Model env overrides and no injected adapter."""
    from src.llm import set_adapter_override

    for env in (
        "LLM_PROVIDER", "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "GOOGLE_API_KEY",
        "SCORING_MODEL", "WIZARD_MODEL", "STATS_MODEL",
    ):
        monkeypatch.delenv(env, raising=False)
    set_adapter_override(None)


@pytest.fixture
def pipeline_workspace(tmp_path, monkeypatch):
    """An empty profiles/ + data/ workspace as the cwd, for tests that run the CLI pipeline."""
    (tmp_path / "profiles" / "default").mkdir(parents=True)
    (tmp_path / "data").mkdir()
    monkeypatch.chdir(tmp_path)
    return tmp_path
