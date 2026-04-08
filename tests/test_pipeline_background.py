from api.background import _build_process_error_detail


def test_build_process_error_detail_includes_recent_output_tail():
    recent_output = [f"line {idx}" for idx in range(12)]

    detail = _build_process_error_detail(1, recent_output)

    assert detail.startswith("Pipeline exited with code 1")
    assert "Last output:" in detail
    assert "line 3" not in detail
    assert "line 4" in detail
    assert "line 11" in detail
