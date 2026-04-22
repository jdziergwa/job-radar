import pytest

from src.salary import parse_salary_string


@pytest.mark.parametrize(
    ("salary_text", "expected"),
    [
        ("$100k - $150k", (100000, 150000, "USD")),
        ("120000 - 140000 EUR", (120000, 140000, "EUR")),
        ("$50 - $100 per hour", (104000, 208000, "USD")),
        ("60-80/hr", (124800, 166400, None)),
        ("£40/hour", (83200, 83200, "GBP")),
        ("4 000 - 6 000 USD net/month", (48000, 72000, "USD")),
        ("12 000 - 20 000 PLN net/month", (144000, 240000, "PLN")),
        ("100-120 PLN/h (16k-19.2k PLN/month net, B2B)", (208000, 249600, "PLN")),
        ("Senior Data Science/Full Stack/Backend/Android/iOS/QA positions", (None, None, None)),
        ("Stack Backend", (None, None, None)),
        ("$ Competitive", (None, None, None)),
        ("$70 - 90k", (70000, 90000, "USD")),
    ],
)
def test_parse_salary_string_handles_expected_formats(salary_text, expected):
    assert parse_salary_string(salary_text) == expected
