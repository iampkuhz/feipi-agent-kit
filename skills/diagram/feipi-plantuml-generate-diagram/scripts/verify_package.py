#!/usr/bin/env python3
"""复核 diagram package v1.1 的相对路径与内容 hash。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.package_verifier import verify_package_dir


def verify(package_dir: Path) -> list[str]:
    return verify_package_dir(package_dir)


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify diagram package v1.1")
    parser.add_argument("package_dir")
    args = parser.parse_args()
    errors = verify(Path(args.package_dir).expanduser().resolve())
    if errors:
        for error in errors:
            print(f"[错误] {error}", file=sys.stderr)
        return 1
    print("package_hash_check=ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
