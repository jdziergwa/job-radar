from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.company_import import dump_companies_yaml, import_companies_from_payload, load_payload


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
    return parser


def main() -> int:
    args = build_parser().parse_args()
    payload = load_payload(args.input)
    companies = import_companies_from_payload(payload)
    rendered = dump_companies_yaml(companies)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(rendered)
    else:
        sys.stdout.write(rendered)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
