import tempfile
from pathlib import Path

import yaml

from api.models import CompanyEntry, CompanyUpdateRequest
from api.routers import companies as companies_router


def _write_companies_file(base_dir: Path, data: dict) -> None:
    profile_dir = base_dir / "default"
    profile_dir.mkdir(parents=True, exist_ok=True)
    (profile_dir / "companies.yaml").write_text(
        yaml.safe_dump(data, sort_keys=False),
        encoding="utf-8",
    )


def _read_companies_file(base_dir: Path) -> dict:
    return yaml.safe_load((base_dir / "default" / "companies.yaml").read_text(encoding="utf-8"))


def test_add_company_persists_cleaned_quality_signals():
    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)
        _write_companies_file(base_dir, {"greenhouse": []})
        original_profiles_dir = companies_router.PROFILES_DIR
        companies_router.PROFILES_DIR = base_dir
        try:
            companies_router.add_company(
                "default",
                CompanyEntry(
                    platform="greenhouse",
                    slug="linear",
                    name="Linear",
                    company_quality_signals=[
                        " strong product company ",
                        "High Engineering Reputation",
                        "strong   product company",
                    ],
                ),
            )
        finally:
            companies_router.PROFILES_DIR = original_profiles_dir

        saved = _read_companies_file(base_dir)
        assert saved["greenhouse"] == [
            {
                "slug": "linear",
                "name": "Linear",
                "company_quality_signals": [
                    "strong product company",
                    "High Engineering Reputation",
                ],
            }
        ]


def test_update_company_replaces_name_and_quality_signals():
    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)
        _write_companies_file(
            base_dir,
            {
                "ashby": [
                    {
                        "slug": "notion",
                        "name": "Notion",
                        "company_quality_signals": ["notable brand"],
                    }
                ]
            },
        )
        original_profiles_dir = companies_router.PROFILES_DIR
        companies_router.PROFILES_DIR = base_dir
        try:
            companies_router.update_company(
                "default",
                "ashby",
                "notion",
                CompanyUpdateRequest(
                    name="Notion Labs",
                    company_quality_signals=[
                        "high engineering reputation",
                        " strong cv value ",
                        "high engineering reputation",
                    ],
                ),
            )
            response = companies_router.get_companies("default")
        finally:
            companies_router.PROFILES_DIR = original_profiles_dir

        saved = _read_companies_file(base_dir)
        assert saved["ashby"][0] == {
            "slug": "notion",
            "name": "Notion Labs",
            "company_quality_signals": [
                "high engineering reputation",
                "strong cv value",
            ],
        }
        response_entry = response.ashby[0]
        response_signals = (
            response_entry["company_quality_signals"]
            if isinstance(response_entry, dict)
            else response_entry.company_quality_signals
        )
        assert response_signals == [
            "high engineering reputation",
            "strong cv value",
        ]


def test_update_company_can_clear_quality_signals():
    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)
        _write_companies_file(
            base_dir,
            {
                "lever": [
                    {
                        "slug": "vercel",
                        "name": "Vercel",
                        "company_quality_signals": ["strong product company"],
                    }
                ]
            },
        )
        original_profiles_dir = companies_router.PROFILES_DIR
        companies_router.PROFILES_DIR = base_dir
        try:
            companies_router.update_company(
                "default",
                "lever",
                "vercel",
                CompanyUpdateRequest(company_quality_signals=[]),
            )
        finally:
            companies_router.PROFILES_DIR = original_profiles_dir

        saved = _read_companies_file(base_dir)
        assert saved["lever"][0] == {
            "slug": "vercel",
            "name": "Vercel",
        }
