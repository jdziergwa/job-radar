from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Merge one or more companies.yaml fragments into a base companies.yaml file.",
    )
    parser.add_argument("--base", required=True, help="Path to the base companies.yaml file.")
    parser.add_argument(
        "--fragments",
        required=True,
        nargs="+",
        help="One or more companies.yaml fragments to merge into the base file.",
    )
    parser.add_argument("--output", help="Optional path to write merged YAML. Defaults to stdout.")
    return parser


def read_header_comment(path: Path) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    header_lines: list[str] = []

    for line in lines:
        if line.startswith("#") or (not line.strip() and header_lines):
            header_lines.append(line)
            continue
        break

    if not header_lines:
        return ""
    return "\n".join(header_lines).rstrip() + "\n\n"


def load_companies_yaml(path: Path) -> dict[str, list[dict[str, Any]]]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"{path} does not contain a mapping at the top level")
    return payload


def merge_company_maps(
    base: dict[str, list[dict[str, Any]]],
    fragments: list[dict[str, list[dict[str, Any]]]],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, int]]:
    merged: dict[str, dict[str, dict[str, Any]]] = {}
    added_counts: dict[str, int] = {}

    for platform, entries in base.items():
        if not isinstance(entries, list):
            continue
        platform_entries: dict[str, dict[str, Any]] = {}
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            slug = entry.get("slug")
            if isinstance(slug, str) and slug.strip():
                platform_entries[slug.strip()] = dict(entry)
        merged[platform] = platform_entries

    for fragment in fragments:
        for platform, entries in fragment.items():
            if not isinstance(entries, list):
                continue
            platform_entries = merged.setdefault(platform, {})
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                slug = entry.get("slug")
                if not isinstance(slug, str) or not slug.strip():
                    continue
                normalized_slug = slug.strip()
                if normalized_slug in platform_entries:
                    continue
                platform_entries[normalized_slug] = dict(entry)
                added_counts[platform] = added_counts.get(platform, 0) + 1

    rendered = {
        platform: sorted(entries.values(), key=lambda item: str(item.get("name", "")).lower())
        for platform, entries in merged.items()
        if entries
    }
    return rendered, added_counts


def render_companies_yaml(header_comment: str, companies: dict[str, list[dict[str, Any]]]) -> str:
    body = yaml.safe_dump(companies, sort_keys=False, allow_unicode=False)
    if not header_comment:
        return body
    return header_comment + body


def summarize_additions(added_counts: dict[str, int]) -> str:
    total_added = sum(added_counts.values())
    if total_added == 0:
        return "Added 0 new companies."

    details = ", ".join(f"{platform}: +{count}" for platform, count in sorted(added_counts.items()))
    return f"Added {total_added} new companies ({details})."


def main() -> int:
    args = build_parser().parse_args()
    base_path = Path(args.base)
    fragment_paths = [Path(path) for path in args.fragments]

    header_comment = read_header_comment(base_path)
    base = load_companies_yaml(base_path)
    fragments = [load_companies_yaml(path) for path in fragment_paths]
    merged, added_counts = merge_company_maps(base, fragments)
    rendered = render_companies_yaml(header_comment, merged)

    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)

    print(summarize_additions(added_counts), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
