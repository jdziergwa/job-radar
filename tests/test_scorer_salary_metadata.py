from src.scorer import _extract_metadata


def test_extract_metadata_preserves_salary_bounds_without_score_clamping():
    data = {
        "salary_info": {
            "salary": "4 000 - 6 000 USD net/month",
            "min": 48000,
            "max": 72000,
            "currency": "USD",
        }
    }

    metadata = _extract_metadata(data)

    assert metadata["salary"] == "4 000 - 6 000 USD net/month"
    assert metadata["salary_min"] == 48000
    assert metadata["salary_max"] == 72000
    assert metadata["salary_currency"] == "USD"
