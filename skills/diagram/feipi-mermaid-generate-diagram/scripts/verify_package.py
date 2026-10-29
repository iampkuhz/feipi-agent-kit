#!/usr/bin/env python3
"""独立、只读地复核当前图包。"""
import argparse
import json
import sys
from package import verify

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package')
    args = parser.parse_args()
    try:
        report = verify(args.package)
        print(json.dumps({'verified': True, 'diagram_type': report['diagram_type']}, ensure_ascii=False))
    except Exception as exc:
        print(json.dumps({'verified': False, 'reason': str(exc)}, ensure_ascii=False))
        sys.exit(1)
