import asyncio
import re
from datetime import datetime, timezone
import pytest
from src.providers import local_ats
from src.models import RawJob

class _DummyResponse:
    def __init__(self, text, status=200):
        self._text = text
        self.status = status

    async def text(self):
        return self._text

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

class _DummySession:
    def __init__(self, text, status=200):
        self._text = text
        self._status = status

    def get(self, url, **kwargs):
        return _DummyResponse(self._text, self._status)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

def test_fetch_bamboohr_parsing():
    html = """
    <html>
        <body>
            <div class="ResY">
                <a href="//10web.bamboohr.com/jobs/view.php?id=123" target="_top">Senior QA Engineer</a>
                <a href="/jobs/view.php?id=456" target="_top">SDET</a>
                <a href="https://10web.bamboohr.com/careers/789" target="_top">Automation Lead</a>
            </div>
        </body>
    </html>
    """
    session = _DummySession(html)
    sem = asyncio.Semaphore(1)
    company = {"slug": "10web", "name": "10Web"}

    jobs = asyncio.run(local_ats.fetch_bamboohr(session, sem, company))

    assert len(jobs) == 3
    
    # Check first job (protocol-relative)
    assert jobs[0].job_id == "123"
    assert jobs[0].title == "Senior QA Engineer"
    assert jobs[0].url == "https://10web.bamboohr.com/jobs/view.php?id=123"
    assert jobs[0].ats_platform == "bamboohr"
    
    # Check second job (relative path)
    assert jobs[1].job_id == "456"
    assert jobs[1].title == "SDET"
    assert jobs[1].url == "https://10web.bamboohr.com/jobs/view.php?id=456"

    # Check third job (careers format)
    assert jobs[2].job_id == "789"
    assert jobs[2].title == "Automation Lead"
    assert jobs[2].url == "https://10web.bamboohr.com/careers/789"

def test_fetch_bamboohr_handles_404():
    session = _DummySession("", status=404)
    sem = asyncio.Semaphore(1)
    company = {"slug": "dead-slug", "name": "Dead"}

    jobs = asyncio.run(local_ats.fetch_bamboohr(session, sem, company))
    assert len(jobs) == 0
