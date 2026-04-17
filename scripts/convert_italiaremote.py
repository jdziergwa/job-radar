from __future__ import annotations

import argparse
import json
import re
import ssl
import sys
from pathlib import Path
from urllib.request import urlopen


DEFAULT_INPUT = "https://raw.githubusercontent.com/italiaremote/awesome-italia-remote/main/README.md"
ROW_PATTERN = re.compile(r"^\|")
SEPARATOR_PATTERN = re.compile(r"^\|\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$")
LINK_PATTERN = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
URL_PATTERN = re.compile(r"https?://[^\s|)]+")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert awesome-italia-remote markdown rows into importer-ready JSON.",
    )
    parser.add_argument("--input", default=DEFAULT_INPUT, help="Markdown file path or URL.")
    parser.add_argument("--output", help="Optional path to write JSON. Defaults to stdout.")
    return parser


def load_markdown(source: str) -> str:
    if source.startswith(("http://", "https://")):
        context = ssl._create_unverified_context() if source.startswith("https://") else None
        with urlopen(source, context=context) as response:
            return response.read().decode("utf-8")
    return Path(source).read_text(encoding="utf-8")


def _split_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _find_target_table(markdown: str) -> tuple[list[str], list[str]] | None:
    lines = markdown.splitlines()
    for index in range(len(lines) - 1):
        header_line = lines[index]
        separator_line = lines[index + 1]
        if not ROW_PATTERN.match(header_line) or not SEPARATOR_PATTERN.match(separator_line):
            continue

        headers = _split_row(header_line)
        normalized = [header.lower() for header in headers]
        if "career page" not in normalized:
            continue
        if "name" not in normalized and "company" not in normalized:
            continue

        data_lines: list[str] = []
        for line in lines[index + 2 :]:
            if not ROW_PATTERN.match(line):
                break
            if SEPARATOR_PATTERN.match(line):
                continue
            data_lines.append(line)

        return headers, data_lines

    return None


def _extract_name(cell: str) -> str:
    links = LINK_PATTERN.findall(cell)
    if links:
        return links[0][0].strip()
    return re.sub(r"[*_`]", "", cell).strip()


def _extract_job_board_url(career_cell: str, row: str) -> str:
    links = LINK_PATTERN.findall(career_cell)
    if links:
        return links[-1][1].strip()

    match = URL_PATTERN.search(career_cell)
    if match:
        return match.group(0).strip()

    row_links = LINK_PATTERN.findall(row)
    if len(row_links) >= 2:
        return row_links[1][1].strip()

    row_url = URL_PATTERN.search(row)
    return row_url.group(0).strip() if row_url else ""


def extract_records(markdown: str) -> list[dict[str, str]]:
    table = _find_target_table(markdown)
    if table is None:
        print("Extracted 0 records; skipped 0 rows.", file=sys.stderr)
        return []

    headers, rows = table
    header_map = {header.lower(): index for index, header in enumerate(headers)}
    name_index = header_map.get("name", header_map.get("company"))
    career_index = header_map["career page"]

    records: list[dict[str, str]] = []
    skipped = 0

    for row in rows:
        cells = _split_row(row)
        if name_index is None or name_index >= len(cells) or career_index >= len(cells):
            skipped += 1
            continue

        name = _extract_name(cells[name_index])
        job_board_url = _extract_job_board_url(cells[career_index], row)
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
    write_output(extract_records(load_markdown(args.input)), args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
