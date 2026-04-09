from __future__ import annotations

import argparse
import json
import re
import ssl
import sys
from pathlib import Path
from urllib.request import urlopen


DEFAULT_INPUT = "https://raw.githubusercontent.com/sample-resume/awesome-easy-apply/master/README.md"
ROW_PATTERN = re.compile(r"^\|")
LINK_PATTERN = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert Awesome Easy Apply markdown rows into importer-ready JSON.",
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


def extract_records(markdown: str) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    skipped = 0

    for line in markdown.splitlines():
        if not ROW_PATTERN.match(line) or line.startswith("| ---"):
            continue

        links = LINK_PATTERN.findall(line)
        if len(links) < 2:
            skipped += 1
            continue

        name = links[0][0].strip()
        job_board_url = links[-1][1].strip()
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
    markdown = load_markdown(args.input)
    write_output(extract_records(markdown), args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
