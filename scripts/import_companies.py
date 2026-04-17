from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ats_detect import detect_ats_batch
from src.company_import import (
    dump_companies_yaml,
    extract_candidate_records,
    import_companies_from_payload,
    import_companies_from_records,
    load_payload,
    normalize_company_record,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Import ATS company mappings from an external JSON source and emit a mergeable companies.yaml fragment.",
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path or URL to a JSON dataset containing company/ATS metadata.",
    )
    parser.add_argument(
        "--output",
        help="Optional path to write the generated YAML fragment. Defaults to stdout.",
    )
    parser.add_argument(
        "--detect-ats",
        action="store_true",
        help="Probe career URLs to detect ATS platform for companies that don't match URL patterns directly.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    payload = load_payload(args.input)
    companies = import_companies_from_payload(payload)

    if args.detect_ats:
        rejected_records = [record for record in extract_candidate_records(payload) if normalize_company_record(record) is None]
        detected_records = asyncio.run(detect_ats_batch(rejected_records))
        detected_companies = import_companies_from_records(detected_records)
        for platform, entries in detected_companies.items():
            existing_by_slug = {entry["slug"]: entry for entry in companies.get(platform, [])}
            for entry in entries:
                existing_by_slug[entry["slug"]] = entry
            companies[platform] = sorted(existing_by_slug.values(), key=lambda item: item["name"].lower())

    rendered = dump_companies_yaml(companies)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(rendered)
    else:
        sys.stdout.write(rendered)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
