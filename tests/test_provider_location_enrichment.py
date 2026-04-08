import sys
import types


if "httpx" not in sys.modules:
    httpx = types.ModuleType("httpx")

    class AsyncClient:  # pragma: no cover - stub for import only
        pass

    httpx.AsyncClient = AsyncClient
    sys.modules["httpx"] = httpx

if "aiohttp" not in sys.modules:
    aiohttp = types.ModuleType("aiohttp")

    class ClientSession:  # pragma: no cover - stub for import only
        pass

    class TCPConnector:  # pragma: no cover - stub for import only
        def __init__(self, *args, **kwargs):
            pass

    class ClientTimeout:  # pragma: no cover - stub for import only
        def __init__(self, *args, **kwargs):
            pass

    aiohttp.ClientSession = ClientSession
    aiohttp.TCPConnector = TCPConnector
    aiohttp.ClientTimeout = ClientTimeout
    sys.modules["aiohttp"] = aiohttp

from src.providers.local_ats import _build_ashby_location_metadata, _extract_ashby_description


def test_extract_ashby_description_prefers_inline_board_description():
    item = {
        "descriptionHtml": "<p>Remote across North America only.</p>",
        "descriptionPlain": "Fallback description",
    }

    assert _extract_ashby_description(item) == "<p>Remote across North America only.</p>"


def test_build_ashby_location_metadata_preserves_raw_location_and_restrictions():
    item = {
        "workplaceType": "Remote",
        "employmentType": "Full-time",
        "secondaryLocations": [{"name": "United States"}, {"name": "Canada"}],
    }

    metadata = _build_ashby_location_metadata(
        item,
        "Remote",
        "Remote across North America only. Must overlap at least 4 hours with Eastern Time.",
    )

    assert metadata["raw_location"] == "Remote"
    assert metadata["workplace_type"] == "Remote"
    assert metadata["employment_type"] == "Full-time"
    assert metadata["location_fragments"] == ["Remote", "United States", "Canada"]
    assert metadata["derived_geographic_signals"] == [
        "Remote role",
        "Restricted to North America",
        "Timezone overlap requirement mentioned",
    ]


def test_build_ashby_location_metadata_marks_global_remote_without_region_default():
    metadata = _build_ashby_location_metadata(
        {"workplaceType": "Remote"},
        "Remote",
        "This role is open worldwide and can be done from anywhere.",
    )

    assert metadata["raw_location"] == "Remote"
    assert metadata["derived_geographic_signals"] == [
        "Remote role",
        "Explicitly global or worldwide remote",
    ]
