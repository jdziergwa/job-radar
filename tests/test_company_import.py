from src.company_import import (
    dump_companies_yaml,
    import_companies_from_payload,
    normalize_company_record,
)


def test_normalize_company_record_handles_nested_board_url():
    company = normalize_company_record(
        {
            "name": "Linear",
            "job_board": {
                "provider": "ashby",
                "url": "https://jobs.ashbyhq.com/linear",
            },
        }
    )

    assert company is not None
    assert company.platform == "ashby"
    assert company.slug == "linear"
    assert company.name == "Linear"


def test_import_companies_from_payload_extracts_and_dedupes_supported_companies():
    payload = {
        "companies": [
            {
                "name": "Stripe",
                "careers_url": "https://boards.greenhouse.io/stripe",
            },
            {
                "company_name": "Apollo GraphQL",
                "platform": "lever",
                "slug": "apollographql",
            },
            {
                "name": "Stripe",
                "job_board": {
                    "provider": "greenhouse",
                    "url": "https://boards.greenhouse.io/stripe",
                },
            },
            {
                "name": "Unsupported",
                "careers_url": "https://jobs.example.com/unsupported",
            },
        ]
    }

    companies = import_companies_from_payload(payload)

    assert companies == {
        "greenhouse": [{"slug": "stripe", "name": "Stripe"}],
        "lever": [{"slug": "apollographql", "name": "Apollo GraphQL"}],
    }


def test_dump_companies_yaml_emits_mergeable_fragment():
    rendered = dump_companies_yaml(
        {
            "greenhouse": [{"slug": "stripe", "name": "Stripe"}],
            "lever": [{"slug": "apollographql", "name": "Apollo GraphQL"}],
        }
    )

    assert "greenhouse:" in rendered
    assert "- slug: stripe" in rendered
    assert "lever:" in rendered
    assert "Apollo GraphQL" in rendered
