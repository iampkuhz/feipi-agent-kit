#!/usr/bin/env python3
"""Watch the raw OTel file, strip null bytes, extract JSON objects, write clean JSONL."""

import json
import time
import os
import sys

RAW_PATH = "/data/claude-code-otel.raw"
CLEAN_PATH = "/data/claude-code-otel.jsonl"

def extract_json_objects(text):
    """Read the collector's newline-delimited JSON, ignoring NUL padding."""
    for line in text.split('\n'):
        try:
            record = json.loads(line.replace('\0', ''))
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict):
            yield record

def main():
    # Wait for raw file to appear
    while not os.path.exists(RAW_PATH):
        time.sleep(0.5)

    last_size = 0
    known_hashes = set()

    # Truncate clean file on start
    with open(CLEAN_PATH, 'w'):
        pass

    while True:
        try:
            size = os.path.getsize(RAW_PATH)
            if size == last_size:
                time.sleep(0.5)
                continue

            with open(RAW_PATH, 'r', errors='ignore') as f:
                content = f.read()

            objs = extract_json_objects(content)
            with open(CLEAN_PATH, 'a') as clean_f:
                for obj in objs:
                    h = hash(json.dumps(obj, sort_keys=True))
                    if h not in known_hashes:
                        known_hashes.add(h)
                        clean_f.write(json.dumps(obj) + '\n')
                        clean_f.flush()

            last_size = size
        except Exception as e:
            print(f"cleaner error: {e}", file=sys.stderr)

        time.sleep(0.5)

if __name__ == "__main__":
    main()
