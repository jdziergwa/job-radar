import pytest
from unittest.mock import MagicMock, AsyncMock
import aiohttp
import asyncio
from src.providers.local_ats import fetch_lever

@pytest.mark.anyio
async def test_fetch_lever_concatenates_all_fields():
    # Mock data based on Minted AI & Automation Engineer example
    mock_data = [
        {
            "id": "lever-123",
            "text": "Software Engineer",
            "hostedUrl": "https://jobs.lever.co/company/lever-123",
            "categories": {"location": "Remote"},
            "description": "Intro paragraph.",
            "lists": [
                {
                    "text": "Responsibilities",
                    "content": "<ul><li>Code</li></ul>"
                },
                {
                    "text": "Requirements",
                    "content": "<ul><li>Write tests</li></ul>"
                }
            ],
            "additional": "Extra info."
        }
    ]

    session = MagicMock(spec=aiohttp.ClientSession)
    resp = MagicMock()
    resp.status = 200
    resp.json = AsyncMock(return_value=mock_data)
    
    # Mocking session.get as an async context manager
    session.get.return_value.__aenter__ = AsyncMock(return_value=resp)
    session.get.return_value.__aexit__ = AsyncMock(return_value=None)
    
    sem = asyncio.Semaphore(1)
    company = {"slug": "test-company", "name": "Test Company"}

    jobs = await fetch_lever(session, sem, company)

    assert len(jobs) == 1
    job = jobs[0]
    
    # This is expected to FAIL currently because fetch_lever only takes 'description'
    assert "Responsibilities" in job.description
    assert "Requirements" in job.description
    assert "Extra info" in job.description
    assert "Code" in job.description
    assert "Write tests" in job.description
