import json
import logging
import sys

import pytest
from fastapi.testclient import TestClient

import src.main as main_module
from api.main import app
from src.llm import LLMNonRetryableError, set_adapter_override
from tests.fake_llm import FakeLLMAdapter


class _CountingProvider:
    name = "stub"
    display_name = "Stub"
    description = "Counts fetches"
    shows_aggregator_badge = False

    def __init__(self, jobs):
        self._jobs = jobs
        self.fetches = 0

    async def fetch_jobs(self, ctx, progress_callback=None):
        self.fetches += 1
        return list(self._jobs)


@pytest.fixture(autouse=True)
def _workspace(no_ai_key, pipeline_workspace):
    """Every test here starts with no AI configured, in an empty workspace."""


def _setup(monkeypatch, jobs, argv_extra=(), config=None):
    provider = _CountingProvider(jobs)
    monkeypatch.setitem(main_module.PROVIDER_REGISTRY, "stub", provider)
    monkeypatch.setattr(
        main_module, "load_config",
        lambda profile_dir: config or {"keywords": {"title_patterns": ["Engineer"]}, "output": {"markdown_report": False}},
    )
    monkeypatch.setattr(main_module, "load_companies", lambda profile_dir: {})
    monkeypatch.setattr(main_module, "load_profile_doc", lambda profile_dir: "Profile doc")
    monkeypatch.setattr(main_module, "print_scan_summary", lambda *a, **k: None)
    monkeypatch.setattr(main_module, "print_candidates", lambda *a, **k: None)
    monkeypatch.setattr(sys, "argv", ["main.py", "--profile", "default", "--source", "stub", *argv_extra])
    return provider


@pytest.mark.anyio
@pytest.mark.parametrize("with_candidates", [True, False], ids=["with-candidates", "no-candidates"])
async def test_missing_key_fails_before_any_job_provider_is_called(monkeypatch, raw_job_factory, with_candidates):
    provider = _setup(monkeypatch, [raw_job_factory()] if with_candidates else [])

    with pytest.raises(SystemExit) as exit_info:
        await main_module.run()

    assert exit_info.value.code == 1
    assert provider.fetches == 0


@pytest.mark.anyio
async def test_foreign_profile_scoring_model_fails_before_any_job_provider_is_called(monkeypatch, raw_job_factory):
    provider = _setup(
        monkeypatch, [raw_job_factory()],
        config={"keywords": {"title_patterns": ["Engineer"]}, "scoring": {"model": "claude-sonnet-4-5"}},
    )
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")

    with pytest.raises(SystemExit) as exit_info:
        await main_module.run()

    assert exit_info.value.code == 1
    assert provider.fetches == 0


@pytest.mark.anyio
async def test_missing_sdk_prints_the_clear_message_and_stops_before_fetching(monkeypatch, raw_job_factory, caplog):
    provider = _setup(monkeypatch, [raw_job_factory()])
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    monkeypatch.setitem(sys.modules, "src.llm.gemini_adapter", None)  # makes importing it fail

    with caplog.at_level(logging.ERROR), pytest.raises(SystemExit) as exit_info:
        await main_module.run()

    assert exit_info.value.code == 1
    assert provider.fetches == 0
    assert "pip install google-genai" in caplog.text


@pytest.mark.anyio
async def test_failed_scoring_tells_the_web_run_why(monkeypatch, raw_job_factory, capsys):
    _setup(monkeypatch, [raw_job_factory()], argv_extra=["--json-progress"])
    monkeypatch.setattr(main_module, "print_results", lambda *a, **k: None)
    set_adapter_override(FakeLLMAdapter([LLMNonRetryableError("402 Your prepayment credits are depleted.")]))
    try:
        await main_module.run()
    finally:
        set_adapter_override(None)

    events = [json.loads(line)["progress"] for line in capsys.readouterr().out.splitlines() if line.startswith("{")]
    assert events[-1]["name"] == "Done"
    assert "credits are depleted" in events[-1]["detail"]


@pytest.mark.anyio
async def test_dry_run_without_a_key_still_fetches(monkeypatch, raw_job_factory):
    provider = _setup(monkeypatch, [raw_job_factory()], argv_extra=["--dry-run"])

    await main_module.run()

    assert provider.fetches == 1


def test_api_startup_warns_once_when_ai_is_not_configured_and_still_serves(caplog):
    # Startup is what logs the warning, so the client must be opened inside the capture.
    with caplog.at_level(logging.WARNING), TestClient(app) as client:
        assert client.get("/api/health").status_code == 200

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING and "AI is not configured" in r.getMessage()]
    assert len(warnings) == 1
    assert "API key" in warnings[0].getMessage()
