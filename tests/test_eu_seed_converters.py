from scripts.convert_career_ops import extract_records as extract_career_ops_records
from scripts.convert_italiaremote import extract_records as extract_italiaremote_records
from scripts.convert_remoteintech import extract_records_from_company_dir


def test_convert_remoteintech_parses_frontmatter(tmp_path):
    companies_dir = tmp_path / "src" / "companies"
    companies_dir.mkdir(parents=True)
    (companies_dir / "acme.md").write_text(
        """---
title: Acme
website: https://acme.example
careers_url: https://jobs.lever.co/acme
---
Body
""",
        encoding="utf-8",
    )

    records = extract_records_from_company_dir(str(tmp_path))

    assert records == [
        {
            "name": "Acme",
            "jobBoardUrl": "https://jobs.lever.co/acme",
            "website": "https://acme.example",
        }
    ]


def test_convert_italiaremote_parses_markdown_table():
    markdown = """
# Awesome Italia Remote

| Name | Career Page | Type |
| --- | --- | --- |
| [Alfa](https://alfa.example) | [Jobs](https://boards.greenhouse.io/alfa) | Remote-first |
| [Beta](https://beta.example) | https://jobs.lever.co/beta | Hybrid |
"""

    records = extract_italiaremote_records(markdown)

    assert records == [
        {"name": "Alfa", "jobBoardUrl": "https://boards.greenhouse.io/alfa"},
        {"name": "Beta", "jobBoardUrl": "https://jobs.lever.co/beta"},
    ]


def test_convert_career_ops_uses_greenhouse_token():
    records = extract_career_ops_records(
        {
            "tracked_companies": [
                {
                    "name": "Gamma",
                    "careers_url": "https://gamma.example/careers",
                    "greenhouse_board_token": "gamma",
                }
            ]
        }
    )

    assert records == [{"name": "Gamma", "jobBoardUrl": "https://boards.greenhouse.io/gamma"}]


def test_convert_career_ops_falls_back_to_careers_url():
    records = extract_career_ops_records(
        {
            "tracked_companies": [
                {
                    "name": "Delta",
                    "careers_url": "https://delta.example/jobs",
                }
            ]
        }
    )

    assert records == [{"name": "Delta", "jobBoardUrl": "https://delta.example/jobs"}]
