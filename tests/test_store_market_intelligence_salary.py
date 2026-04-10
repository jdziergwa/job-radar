from src.models import RawJob
from src.store import Store


def test_market_intelligence_rebuckets_mixed_salary_periods(tmp_path):
    db_path = tmp_path / "jobs.db"
    store = Store(str(db_path))

    jobs = [
        RawJob(
            ats_platform="remoteok",
            company_slug="acme",
            company_name="Acme",
            job_id="hourly-role",
            title="QA Engineer",
            location="Remote",
            url="https://example.com/hourly",
            description="Hourly compensation role",
            posted_at="2026-04-10T08:00:00",
            fetched_at="2026-04-10T08:05:00",
            salary="$50/hour",
        ),
        RawJob(
            ats_platform="remoteok",
            company_slug="acme",
            company_name="Acme",
            job_id="monthly-role",
            title="Test Engineer",
            location="Remote",
            url="https://example.com/monthly",
            description="Monthly compensation role",
            posted_at="2026-04-10T08:00:00",
            fetched_at="2026-04-10T08:05:00",
            salary="$5,000/month",
        ),
        RawJob(
            ats_platform="remoteok",
            company_slug="acme",
            company_name="Acme",
            job_id="range-role",
            title="Automation Engineer",
            location="Remote",
            url="https://example.com/range",
            description="Range compensation role",
            posted_at="2026-04-10T08:00:00",
            fetched_at="2026-04-10T08:05:00",
            salary="$70k - $90k",
        ),
    ]

    inserted = store.upsert_jobs(jobs)
    assert inserted == 3

    candidates = store.get_unscored()
    candidates_by_id = {candidate.job_id: candidate for candidate in candidates}

    # Persist intentionally bad numeric values to simulate older rows that were not annualized.
    store.update_score(
        db_id=candidates_by_id["hourly-role"].db_id,
        fit_score=75,
        reasoning="Looks solid",
        breakdown={"tech_stack_match": 4},
        salary="$50/hour",
        salary_min=50,
        salary_max=50,
        salary_currency="USD",
    )
    store.update_score(
        db_id=candidates_by_id["monthly-role"].db_id,
        fit_score=75,
        reasoning="Looks solid",
        breakdown={"tech_stack_match": 4},
        salary="$5,000/month",
        salary_min=5000,
        salary_max=5000,
        salary_currency="USD",
    )
    store.update_score(
        db_id=candidates_by_id["range-role"].db_id,
        fit_score=75,
        reasoning="Looks solid",
        breakdown={"tech_stack_match": 4},
        salary="$70k - $90k",
        salary_min=70000,
        salary_max=90000,
        salary_currency="USD",
    )

    market = store.get_market_intelligence(days=30)
    distribution = {
        (item["currency"], item["range"]): item["count"]
        for item in market["salary_distribution"]
    }

    assert distribution[("USD", "60k-70k")] == 1
    assert distribution[("USD", "80k-90k")] == 1
    assert distribution[("USD", "100k-110k")] == 1
    assert ("USD", "< 60k") not in distribution


def test_market_intelligence_keeps_currencies_separate(tmp_path):
    db_path = tmp_path / "jobs.db"
    store = Store(str(db_path))

    jobs = [
        RawJob(
            ats_platform="remotive",
            company_slug="acme",
            company_name="Acme",
            job_id="usd-role",
            title="QA Engineer",
            location="Remote",
            url="https://example.com/usd",
            description="USD role",
            posted_at="2026-04-10T08:00:00",
            fetched_at="2026-04-10T08:05:00",
            salary="$80k",
            salary_currency="USD",
        ),
        RawJob(
            ats_platform="remotive",
            company_slug="acme",
            company_name="Acme",
            job_id="eur-role",
            title="QA Engineer",
            location="Remote",
            url="https://example.com/eur",
            description="EUR role",
            posted_at="2026-04-10T08:00:00",
            fetched_at="2026-04-10T08:05:00",
            salary="€80k",
            salary_currency="EUR",
        ),
    ]

    store.upsert_jobs(jobs)
    candidates = {candidate.job_id: candidate for candidate in store.get_unscored()}

    store.update_score(
        db_id=candidates["usd-role"].db_id,
        fit_score=75,
        reasoning="Looks solid",
        breakdown={"tech_stack_match": 4},
        salary="$80k",
        salary_min=80000,
        salary_max=80000,
        salary_currency="USD",
    )
    store.update_score(
        db_id=candidates["eur-role"].db_id,
        fit_score=75,
        reasoning="Looks solid",
        breakdown={"tech_stack_match": 4},
        salary="€80k",
        salary_min=80000,
        salary_max=80000,
        salary_currency="EUR",
    )

    market = store.get_market_intelligence(days=30)
    distribution = {
        (item["currency"], item["range"]): item["count"]
        for item in market["salary_distribution"]
    }

    assert distribution[("USD", "80k-90k")] == 1
    assert distribution[("EUR", "80k-90k")] == 1
