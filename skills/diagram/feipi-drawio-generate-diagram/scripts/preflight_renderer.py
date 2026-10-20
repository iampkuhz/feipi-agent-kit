#!/usr/bin/env python3
"""预检已准备好的 Podman 本地 renderer。"""
import argparse
import json
import sys

from renderer import failure, preflight

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--existing-only', action='store_true')
    args = parser.parse_args()
    try:
        print(json.dumps(preflight(args.existing_only), ensure_ascii=False))
    except Exception as exc:
        print(json.dumps(failure(exc), ensure_ascii=False))
        sys.exit(2)
