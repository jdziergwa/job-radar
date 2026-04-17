from __future__ import annotations

import argparse
import json
import ssl
import sys
from pathlib import Path
from urllib.request import urlopen

import yaml


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert career-ops YAML into importer-ready JSON.",
    )
    parser.add_argument("--input", required=True, help="YAML file path or URL.")
    parser.add_argument("--output", help="Optional path to write JSON. Defaults to stdout.")
    return parser


def load_yaml(source: str) -> object:
    if source.startswith(("http://", "https://")):
        context = ssl._create_unverified_context() if source.startswith("https://") else None
        with urlopen(source, context=context) as response:
            return yaml.safe_load(response.read().decode("utf-8"))
    return yaml.safe_load(Path(source).read_text(encoding="utf-8"))


def extract_records(payload: object) -> list[dict[str, str]]:
    if not isinstance(payload, dict):
        print("Extracted 0 records; skipped 0 rows.", file=sys.stderr)
        return []

    companies = payload.get("tracked_companies")
    if not isinstance(companies, list):
        print("Extracted 0 records; skipped 0 rows.", file=sys.stderr)
        return []

    records: list[dict[str, str]] = []
    skipped = 0

    for company in companies:
        if not isinstance(company, dict):
            skipped += 1
            continue

        name = str(company.get("name", "")).strip()
        greenhouse_board_token = str(company.get("greenhouse_board_token", "")).strip()
        careers_url = str(company.get("careers_url", "")).strip()

        if greenhouse_board_token:
            job_board_url = f"https://boards.greenhouse.io/{greenhouse_board_token}"
        else:
            job_board_url = careers_url

        if not name or not job_board_url:
            skipped += 1
            continue

        records.append({"name": name, "jobBoardUrl": job_board_url})

    print(f"Extracted {len(records)} records; skipped {skipped} rows.", file=sys.stderr)
    return records


def write_output(records: list[dict[str, str]], output: str | None) -> None:
    rendered = json.dumps(records, indent=2)
    if output:
        Path(output).write_text(rendered + "\n", encoding="utf-8")
        return
    sys.stdout.write(rendered)
    sys.stdout.write("\n")


def main() -> int:
    args = build_parser().parse_args()
    write_output(extract_records(load_yaml(args.input)), args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
