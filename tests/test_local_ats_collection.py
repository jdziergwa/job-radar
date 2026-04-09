import asyncio

from src.models import RawJob
from src.providers import local_ats


class _DummySession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


def test_build_platform_semaphores_uses_platform_specific_limits():
    semaphores = local_ats._build_platform_semaphores({
        "greenhouse": [{"slug": "stripe"}],
        "lever": [{"slug": "spotify"}],
        "ashby": [{"slug": "linear"}],
        "workable": [{"slug": "personio"}],
        "unknown": [{"slug": "skip-me"}],
    })

    assert set(semaphores) == {"greenhouse", "lever", "ashby", "workable"}
    assert semaphores["greenhouse"]._value == 5
    assert semaphores["lever"]._value == 3
    assert semaphores["ashby"]._value == 3
    assert semaphores["workable"]._value == 3


def test_platform_timeout_uses_longer_budget_for_lever():
    assert local_ats._platform_timeout("greenhouse") == local_ats.REQUEST_TIMEOUT
    assert local_ats._platform_timeout("ashby") == local_ats.REQUEST_TIMEOUT
    assert local_ats._platform_timeout("workable") == local_ats.REQUEST_TIMEOUT
    assert local_ats._platform_timeout("lever") == 30


def test_collect_all_uses_mixed_platform_fetchers_and_progress(monkeypatch):
    seen: list[tuple[str, str, int]] = []

    async def fake_greenhouse(session, sem, company):
        seen.append(("greenhouse", company["slug"], sem._value))
        return [
            RawJob(
                ats_platform="greenhouse",
                company_slug=company["slug"],
                company_name=company["name"],
                job_id="gh-1",
                title="QA Engineer",
                location="Remote",
                url="https://example.com/gh-1",
                description="Greenhouse description",
                posted_at=None,
                fetched_at="2026-04-09T00:00:00Z",
            )
        ]

    async def fake_lever(session, sem, company):
        seen.append(("lever", company["slug"], sem._value))
        return [
            RawJob(
                ats_platform="lever",
                company_slug=company["slug"],
                company_name=company["name"],
                job_id="lv-1",
                title="SDET",
                location="Remote",
                url="https://example.com/lv-1",
                description="Lever description",
                posted_at=None,
                fetched_at="2026-04-09T00:00:00Z",
            )
        ]

    monkeypatch.setattr(local_ats.aiohttp, "TCPConnector", lambda *args, **kwargs: object())
    monkeypatch.setattr(local_ats.aiohttp, "ClientSession", lambda *args, **kwargs: _DummySession())
    monkeypatch.setattr(local_ats, "FETCHERS", {
        "greenhouse": fake_greenhouse,
        "lever": fake_lever,
    })

    progress: list[tuple[int, int]] = []

    jobs = asyncio.run(local_ats.collect_all(
        {
            "greenhouse": [{"slug": "stripe", "name": "Stripe"}],
            "lever": [{"slug": "spotify", "name": "Spotify"}],
        },
        progress_callback=lambda current, total: progress.append((current, total)),
    ))

    assert len(jobs) == 2
    assert sorted(seen) == [
        ("greenhouse", "stripe", 5),
        ("lever", "spotify", 3),
    ]
    assert progress == [(1, 2), (2, 2)]


def test_collect_all_skips_unknown_platform_and_continues_after_fetcher_failure(monkeypatch):
    async def failing_fetcher(session, sem, company):
        raise RuntimeError("boom")

    async def fake_lever(session, sem, company):
        return [
            RawJob(
                ats_platform="lever",
                company_slug=company["slug"],
                company_name=company["name"],
                job_id="lv-2",
                title="Automation Engineer",
                location="Remote",
                url="https://example.com/lv-2",
                description="Lever description",
                posted_at=None,
                fetched_at="2026-04-09T00:00:00Z",
            )
        ]

    monkeypatch.setattr(local_ats.aiohttp, "TCPConnector", lambda *args, **kwargs: object())
    monkeypatch.setattr(local_ats.aiohttp, "ClientSession", lambda *args, **kwargs: _DummySession())
    monkeypatch.setattr(local_ats, "FETCHERS", {
        "greenhouse": failing_fetcher,
        "lever": fake_lever,
    })

    jobs = asyncio.run(local_ats.collect_all(
        {
            "greenhouse": [{"slug": "broken", "name": "Broken"}],
            "lever": [{"slug": "ok", "name": "Okay"}],
            "unknown": [{"slug": "skip", "name": "Skip"}],
        }
    ))

    assert len(jobs) == 1
    assert jobs[0].company_slug == "ok"
