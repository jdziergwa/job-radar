from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert remoteintech company markdown files into importer-ready JSON.",
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to the remote-jobs checkout root or its src/companies directory.",
    )
    parser.add_argument("--output", help="Optional path to write JSON. Defaults to stdout.")
    return parser


def _resolve_companies_dir(input_path: str) -> Path:
    path = Path(input_path).expanduser()
    if path.is_dir() and (path / "src" / "companies").is_dir():
        return path / "src" / "companies"
    return path


def parse_frontmatter(markdown: str) -> dict[str, object] | None:
    lines = markdown.splitlines()
    if not lines or lines[0].strip() != "---":
        return None

    closing_index = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            closing_index = index
            break

    if closing_index is None:
        return None

    payload = yaml.safe_load("\n".join(lines[1:closing_index])) or {}
    return payload if isinstance(payload, dict) else None


def extract_records_from_company_dir(input_path: str) -> list[dict[str, str]]:
    companies_dir = _resolve_companies_dir(input_path)
    records: list[dict[str, str]] = []
    skipped = 0

    for path in sorted(companies_dir.glob("*.md")):
        payload = parse_frontmatter(path.read_text(encoding="utf-8"))
        if not payload:
            skipped += 1
            continue

        name = str(payload.get("title", "")).strip()
        job_board_url = str(payload.get("careers_url", "")).strip()
        website = str(payload.get("website", "")).strip()
        if not name or not job_board_url:
            skipped += 1
            continue

        record = {"name": name, "jobBoardUrl": job_board_url}
        if website:
            record["website"] = website
        records.append(record)

    print(f"Extracted {len(records)} records; skipped {skipped} files.", file=sys.stderr)
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
    write_output(extract_records_from_company_dir(args.input), args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
