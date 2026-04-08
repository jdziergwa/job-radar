from src.reporter import _format_normalization_audit


def test_format_normalization_audit_formats_changed_fields():
    note = _format_normalization_audit({
        "raw_fit_score": 90,
        "weighted_fit_score": 74,
        "normalized_fit_score": 39,
        "raw_apply_priority": "high",
        "normalized_apply_priority": "skip",
        "raw_skip_reason": "none",
        "normalized_skip_reason": "location_timezone",
    })

    assert note == (
        "fit 90 -> 39 (weighted 74); "
        "priority high -> skip; "
        "skip none -> location_timezone"
    )


def test_format_normalization_audit_returns_empty_string_without_changes():
    note = _format_normalization_audit({
        "raw_fit_score": 85,
        "weighted_fit_score": 85,
        "normalized_fit_score": 85,
        "raw_apply_priority": "high",
        "normalized_apply_priority": "high",
        "raw_skip_reason": "none",
        "normalized_skip_reason": "none",
    })

    assert note == ""
