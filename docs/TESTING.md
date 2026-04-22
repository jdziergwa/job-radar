# Testing

This project uses `pytest` for backend and API test coverage.

## Run The Suite

From the repo root:

```bash
.venv/bin/pytest -q
```

Pytest is configured to run directly from the repository root. You do not need to set `PYTHONPATH=.` manually.

## Layout

All backend tests live in `tests/`.

The suite is organized by behavior rather than by framework:

- `test_*router*` and `test_*http*`: API and router contract tests
- `test_store_*`: persistence, migration, and query behavior
- `test_provider_*`, `test_fetcher_*`, `test_*parsing*`: provider parsing and import/hydration behavior
- `test_scorer_*`: scoring and LLM-facing logic
- `test_wizard_*`, `test_profile_*`, `test_companies_*`: profile and setup flows

## Shared Harness

Core shared fixtures live in `tests/conftest.py`.

The most important fixtures are:

- `store`: creates an isolated SQLite database under `tmp_path`
- `raw_job_factory`: builds `RawJob` objects with sensible defaults
- `seed_sample_jobs`: inserts a small scored/unscored baseline job set used by API tests
- `bind_store`: patches one or more router modules so they all use the same test store
- `client`: shared FastAPI `TestClient`
- `anyio_backend`: pins async pytest tests to `asyncio`

Prefer these fixtures over ad hoc `TemporaryDirectory()`, inline database bootstrapping, or repeated `monkeypatch.setattr(..., "get_store", ...)` blocks.

## Markers

Markers are defined in `pytest.ini`:

- `@pytest.mark.api`: HTTP and router contract tests
- `@pytest.mark.db`: store and persistence tests
- `@pytest.mark.unit`: pure unit tests
- `@pytest.mark.anyio`: async tests executed by pytest through `asyncio`

Because `--strict-markers` is enabled, new markers must be added to `pytest.ini`.

## Preferred Patterns

### API tests

API tests should focus on request/response contracts and observable state transitions:

- bind routers to the shared `store` fixture
- use the shared `client` fixture where possible
- assert status code, payload shape, and persisted side effects
- keep one business rule per test when practical

Example shape:

```python
def test_jobs_list_returns_scored_results(store, seed_sample_jobs, bind_store, client):
    job_ids = seed_sample_jobs()
    bind_store(jobs_router)

    response = client.get("/api/jobs", params={"status": "scored"})

    assert response.status_code == 200
    assert response.json()["jobs"][0]["id"] == job_ids["job-1"]
```

### Async/provider tests

Prefer pytest-native async tests over `asyncio.run(...)`:

```python
@pytest.mark.anyio
async def test_detect_returns_none_for_unknown():
    ...
```

For HTTP-facing provider tests:

- patch `httpx.AsyncClient` once per test with a small reusable fake client/helper
- assert the outbound URL and parameters
- assert the normalized `RawJob` contract, not internal implementation details

### Store tests

Use `tmp_path` or the shared `store` fixture for isolated databases. Tests should verify persisted behavior and migration outcomes, not private incidental state unless that state is the contract being protected.

## External Dependency Rules

Tests must not call real external services.

`tests/conftest.py` installs import-time stubs for:

- `anthropic`
- `dotenv`
- `httpx` when unavailable
- `aiohttp` when unavailable

Network and LLM behavior should always be mocked or faked inside tests.

## When Adding New Tests

Use this order of preference:

1. Reuse an existing fixture from `conftest.py`
2. Add a small helper fixture if several files need the same setup
3. Add a local helper inside one test file only if the behavior is file-specific

Keep tests table-driven when the behavior is naturally matrix-shaped, such as:

- provider URL normalization
- parsing variants
- cache state combinations
- validation/error cases

## Commit-Scale Guidance

When refactoring tests, keep changes grouped by slice:

- `test(pytest)`: bootstrap, markers, shared harness
- `test(fetcher)` or `test(providers)`: async/provider/fetcher refactors
- `test(api)`: router and HTTP contract refactors

This keeps larger testing changes reviewable and bisectable.
