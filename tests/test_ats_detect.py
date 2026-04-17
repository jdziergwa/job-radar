import asyncio

import httpx

from src.ats_detect import detect_ats, detect_ats_batch


def test_detect_from_redirect():
    async def _run():
        def handler(request: httpx.Request) -> httpx.Response:
            if str(request.url) == "https://example.com/careers":
                return httpx.Response(302, headers={"Location": "https://jobs.lever.co/example"}, request=request)
            if str(request.url) == "https://jobs.lever.co/example":
                return httpx.Response(200, text="<html></html>", request=request)
            raise AssertionError(f"Unexpected URL: {request.url}")

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, follow_redirects=True) as client:
            return await detect_ats("https://example.com/careers", client)

    assert asyncio.run(_run()) == ("lever", "example")


def test_detect_from_html_iframe():
    async def _run():
        html = '<iframe src="https://boards.greenhouse.io/acme/embed_iframe"></iframe>'

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text=html, request=request)

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, follow_redirects=True) as client:
            return await detect_ats("https://example.com/careers", client)

    assert asyncio.run(_run()) == ("greenhouse", "acme")


def test_detect_returns_none_for_unknown():
    async def _run():
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="<html><body>No ATS here</body></html>", request=request)

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, follow_redirects=True) as client:
            return await detect_ats("https://example.com/careers", client)

    assert asyncio.run(_run()) == (None, None)


def test_detect_batch_respects_concurrency(monkeypatch):
    active = 0
    max_active = 0

    async def fake_detect_ats(_career_url, _client):
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0.01)
        active -= 1
        return "lever", "example"

    monkeypatch.setattr("src.ats_detect.detect_ats", fake_detect_ats)

    companies = [{"name": f"Company {index}", "jobBoardUrl": f"https://example.com/{index}"} for index in range(5)]
    results = asyncio.run(detect_ats_batch(companies, concurrency=2, request_delay_seconds=0))

    assert max_active == 2
    assert all(result["platform"] == "lever" for result in results)
    assert all(result["slug"] == "example" for result in results)


def test_detect_handles_timeout():
    async def _run():
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("timed out", request=request)

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, follow_redirects=True) as client:
            return await detect_ats("https://example.com/careers", client)

    assert asyncio.run(_run()) == (None, None)
