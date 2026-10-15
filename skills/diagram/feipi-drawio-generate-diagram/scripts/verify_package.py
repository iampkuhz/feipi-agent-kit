#!/usr/bin/env python3
"""独立复核产物哈希、覆盖、渲染几何与 SVG/PNG，不调用服务。"""
import argparse
import json
import sys
from core import verify_package

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package')
    args = parser.parse_args()
    try:
        verify_package(args.package)
        print(json.dumps({'status': 'passed', 'visual_review': 'pending'}, ensure_ascii=False))
    except Exception as exc:
        print(json.dumps({'status': 'failed', 'reason': str(exc)}, ensure_ascii=False))
        sys.exit(1)
