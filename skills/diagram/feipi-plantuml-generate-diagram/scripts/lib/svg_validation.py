#!/usr/bin/env python3
"""Validate that an artifact is a real SVG document, not text containing ``<svg``."""

from __future__ import annotations

import argparse
import xml.etree.ElementTree as ET
from pathlib import Path


SVG_ROOT = "{http://www.w3.org/2000/svg}svg"


def inspect_svg(path: str | Path) -> tuple[bool, bool]:
    """Return ``(is_svg, is_plantuml_error_svg)`` for a local artifact."""
    try:
        root = ET.parse(Path(path)).getroot()
    except (ET.ParseError, OSError):
        return False, False
    if root.tag != SVG_ROOT:
        return False, False
    diagram_type = str(root.attrib.get("data-diagram-type", "")).strip().upper()
    return True, diagram_type == "ERROR"


def is_valid_svg(path: str | Path) -> bool:
    return inspect_svg(path)[0]


def is_success_svg(path: str | Path) -> bool:
    valid, plantuml_error = inspect_svg(path)
    return valid and not plantuml_error


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("svg")
    args = parser.parse_args()
    valid, plantuml_error = inspect_svg(args.svg)
    if not valid:
        print("invalid")
        return 1
    print("error" if plantuml_error else "valid")
    return 2 if plantuml_error else 0


if __name__ == "__main__":
    raise SystemExit(main())
