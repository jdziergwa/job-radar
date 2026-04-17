from pathlib import Path

from scripts.merge_companies import (
    load_companies_yaml,
    merge_company_maps,
    read_header_comment,
    render_companies_yaml,
    summarize_additions,
)


def test_merge_preserves_existing():
    base = {
        "greenhouse": [
            {"slug": "stripe", "name": "Stripe"},
            {"slug": "airbnb", "name": "Airbnb"},
        ]
    }
    fragments = [
        {
            "greenhouse": [
                {"slug": "stripe", "name": "Stripe Renamed"},
                {"slug": "linear", "name": "Linear"},
            ]
        }
    ]

    merged, added_counts = merge_company_maps(base, fragments)

    assert merged == {
        "greenhouse": [
            {"slug": "airbnb", "name": "Airbnb"},
            {"slug": "linear", "name": "Linear"},
            {"slug": "stripe", "name": "Stripe"},
        ]
    }
    assert added_counts == {"greenhouse": 1}


def test_merge_adds_new_platforms():
    base = {"greenhouse": [{"slug": "stripe", "name": "Stripe"}]}
    fragments = [{"ashby": [{"slug": "notion", "name": "Notion"}]}]

    merged, added_counts = merge_company_maps(base, fragments)

    assert merged["greenhouse"] == [{"slug": "stripe", "name": "Stripe"}]
    assert merged["ashby"] == [{"slug": "notion", "name": "Notion"}]
    assert added_counts == {"ashby": 1}


def test_merge_reports_counts():
    summary = summarize_additions({"greenhouse": 2, "lever": 3})

    assert summary == "Added 5 new companies (greenhouse: +2, lever: +3)."


def test_render_preserves_header_comment(tmp_path):
    base_path = tmp_path / "companies.yaml"
    base_path.write_text(
        "# header line 1\n# header line 2\n\n"
        "greenhouse:\n"
        "- slug: stripe\n"
        "  name: Stripe\n",
        encoding="utf-8",
    )

    header = read_header_comment(base_path)
    payload = load_companies_yaml(base_path)
    rendered = render_companies_yaml(header, payload)

    assert rendered.startswith("# header line 1\n# header line 2\n\n")
    assert "greenhouse:" in rendered


def test_read_header_comment_returns_empty_without_comments(tmp_path):
    base_path = tmp_path / "companies.yaml"
    base_path.write_text("greenhouse: []\n", encoding="utf-8")

    assert read_header_comment(base_path) == ""
