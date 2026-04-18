from src.providers import local_ats
from src.providers.ats_registry import (
    BULK_FETCH_ATS_PLATFORMS,
    BULK_FETCHERS,
    SINGLE_JOB_IMPORT_ATS_PLATFORMS,
)
from src.providers.ats_resolvers import SINGLE_JOB_FETCHERS


def test_bulk_fetch_registry_matches_local_ats_fetchers():
    assert set(BULK_FETCH_ATS_PLATFORMS) == set(local_ats.FETCHERS)
    assert local_ats.FETCHERS is BULK_FETCHERS


def test_single_job_import_registry_matches_single_job_fetchers():
    assert set(SINGLE_JOB_IMPORT_ATS_PLATFORMS) == set(SINGLE_JOB_FETCHERS)


def test_single_job_import_platforms_are_bulk_fetch_supported():
    assert set(SINGLE_JOB_IMPORT_ATS_PLATFORMS).issubset(set(BULK_FETCH_ATS_PLATFORMS))
