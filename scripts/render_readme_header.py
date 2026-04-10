#!/usr/bin/env python3
"""Render the README header PNG from the committed HTML source.

This wraps the current local macOS flow:
1. Render `.html` via Quick Look (`qlmanage`) into a temporary PNG.
2. Crop the square thumbnail down to the visible content bounds.
3. Write the final committed PNG used by the README.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image


DEFAULT_SOURCE = Path(".github/assets/readme-header-source.html")
DEFAULT_OUTPUT = Path(".github/assets/readme-header.png")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE, help="HTML source file")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT, help="PNG output path")
    parser.add_argument("--size", type=int, default=960, help="Quick Look thumbnail size")
    parser.add_argument("--threshold", type=int, default=18, help="RGB threshold for crop detection")
    parser.add_argument("--margin-x", type=int, default=40, help="Horizontal crop margin")
    parser.add_argument("--margin-top", type=int, default=40, help="Top crop margin")
    parser.add_argument("--margin-bottom", type=int, default=30, help="Bottom crop margin")
    return parser.parse_args()


def render_thumbnail(source: Path, size: int) -> Path:
    qlmanage = shutil.which("qlmanage")
    if qlmanage is None:
        raise RuntimeError("`qlmanage` is required but was not found. This script currently supports macOS only.")

    with tempfile.TemporaryDirectory(prefix="readme-header-") as tmpdir:
        out_dir = Path(tmpdir)
        subprocess.run(
            [qlmanage, "-t", "-s", str(size), "-o", str(out_dir), str(source)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        thumbnail = out_dir / f"{source.name}.png"
        if not thumbnail.exists():
            raise FileNotFoundError(f"Quick Look did not produce {thumbnail}")

        persisted = out_dir / "rendered.png"
        thumbnail.replace(persisted)
        # Return a stable path by copying out of the TemporaryDirectory before it closes.
        final_tmp = Path(tempfile.mkstemp(prefix="readme-header-", suffix=".png")[1])
        final_tmp.write_bytes(persisted.read_bytes())
        return final_tmp


def crop_image(
    image_path: Path,
    threshold: int,
    margin_x: int,
    margin_top: int,
    margin_bottom: int,
) -> Image.Image:
    image = Image.open(image_path).convert("RGBA")
    pixels = image.load()
    width, height = image.size
    min_x, min_y, max_x, max_y = width, height, 0, 0

    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            if a and (r > threshold or g > threshold or b > threshold):
                min_x = min(min_x, x)
                min_y = min(min_y, y)
                max_x = max(max_x, x)
                max_y = max(max_y, y)

    if min_x > max_x or min_y > max_y:
        raise RuntimeError("Could not detect any visible content to crop.")

    left = max(0, min_x - margin_x)
    top = max(0, min_y - margin_top)
    right = min(width, max_x + margin_x)
    bottom = min(height, max_y + margin_bottom)
    return image.crop((left, top, right, bottom))


def main() -> int:
    args = parse_args()
    source = args.source.resolve()
    out_path = args.out.resolve()

    if not source.exists():
        print(f"Source not found: {source}", file=sys.stderr)
        return 1

    rendered_tmp = render_thumbnail(source, args.size)
    try:
        cropped = crop_image(
            rendered_tmp,
            threshold=args.threshold,
            margin_x=args.margin_x,
            margin_top=args.margin_top,
            margin_bottom=args.margin_bottom,
        )
        out_path.parent.mkdir(parents=True, exist_ok=True)
        cropped.save(out_path)
        print(f"Rendered {out_path.relative_to(Path.cwd())}")
        print(f"Source: {source.relative_to(Path.cwd())}")
        print(f"Size: {cropped.width}x{cropped.height}")
    finally:
        rendered_tmp.unlink(missing_ok=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
