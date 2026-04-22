from src.fetcher import _extract_adzuna_salary, _extract_salary_details


def test_extract_adzuna_salary_from_detail_html():
    html = """
    <section class="lg:flex mb-4">
        <div class="ui-job-card-info flex-1 grid md:grid-cols-2 gap-3">
            <div class="ui-company row-end-1">Example Co</div>
            <div class="ui-location row-start-1 row-end-2"><span>Example City</span></div>
            <div class="ui-salary row-start-2">4 000 - 6 000 USD net/month</div>
        </div>
    </section>
    """

    assert _extract_adzuna_salary(html) == "4 000 - 6 000 USD net/month"


def test_extract_salary_details_parses_adzuna_salary_range():
    html = '<div class="ui-salary row-start-2">4 000 - 6 000 USD net/month</div>'

    assert _extract_salary_details("https://jobs.adzuna.test/details/example-role-123", html) == {
        "salary": "4 000 - 6 000 USD net/month",
        "salary_min": 48000,
        "salary_max": 72000,
        "salary_currency": "USD",
    }
