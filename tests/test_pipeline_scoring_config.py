import asyncio
import logging
import sys

import pytest

import src.main as main_module
from src.llm import LLMConfigError
from tests.test_pipeline_run_metadata import _make_raw_job, _prepare_workspace


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


def _setup(monkeypatch, tmp_path, jobs, argv_extra=(), config=None):
    _prepare_workspace(tmp_path, monkeypatch)
    for env in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "GOOGLE_API_KEY", "LLM_PROVIDER", "SCORING_MODEL"):
        monkeypatch.delenv(env, raising=False)
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


@pytest.mark.parametrize("jobs", [[_make_raw_job()], []], ids=["with-candidates", "no-candidates"])
def test_missing_key_fails_before_any_job_provider_is_called(monkeypatch, tmp_path, jobs):
    provider = _setup(monkeypatch, tmp_path, jobs)

    with pytest.raises(SystemExit) as exit_info:
        asyncio.run(main_module.run())

    assert exit_info.value.code == 1
    assert provider.fetches == 0


def test_foreign_profile_scoring_model_fails_before_any_job_provider_is_called(monkeypatch, tmp_path):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    provider = _setup(
        monkeypatch, tmp_path, [_make_raw_job()],
        config={"keywords": {"title_patterns": ["Engineer"]}, "scoring": {"model": "claude-sonnet-4-5"}},
    )
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")

    with pytest.raises(SystemExit) as exit_info:
        asyncio.run(main_module.run())

    assert exit_info.value.code == 1
    assert provider.fetches == 0


def test_dry_run_without_a_key_still_fetches(monkeypatch, tmp_path):
    provider = _setup(monkeypatch, tmp_path, [_make_raw_job()], argv_extra=["--dry-run"])

    asyncio.run(main_module.run())

    assert provider.fetches == 1


def test_api_startup_warns_once_when_ai_is_not_configured_and_still_serves(monkeypatch, caplog):
    from fastapi.testclient import TestClient
    from api.main import app

    for env in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "GOOGLE_API_KEY", "LLM_PROVIDER"):
        monkeypatch.delenv(env, raising=False)

    with caplog.at_level(logging.WARNING):
        with TestClient(app) as client:
            assert client.get("/api/health").status_code == 200

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING and "AI is not configured" in r.getMessage()]
    assert len(warnings) == 1
    assert "API key" in warnings[0].getMessage()
