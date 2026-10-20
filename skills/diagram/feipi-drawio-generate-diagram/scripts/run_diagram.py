#!/usr/bin/env python3
"""从 brief 生成或验证已有 draw.io，输出可复核图包。"""
import argparse
import base64
import fcntl
import hashlib
import json
from pathlib import Path
import sys
import time

from core import (CONTRACT, digest, generate, inspect_source, layout_issues, read_json,
                  require, validate_brief, validate_images, verify_package)
from renderer import failure, preflight, request


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def run(args):
    out = args.out_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    require(not (out / '.lock').is_symlink(), '图包锁不得为符号链接')
    with (out / '.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError('该图包正在处理，请等待当前任务结束') from exc
        return run_locked(args)


def run_locked(args):
    started = time.monotonic()
    out = args.out_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    require(not any(p.is_symlink() for p in out.iterdir()), '输出目录不得包含符号链接')
    report_path = out / 'validation.json'
    old = read_json(report_path) if report_path.exists() else {}
    attempts = old.get('render_attempts', 0)
    require(type(attempts) is int and 0 <= attempts <= 2, '渲染次数记录无效')
    report = {'contract': CONTRACT, 'status': 'failed', 'stage': 'input', 'issues': [],
              'render_attempts': attempts, 'visual_review': 'pending', 'sha256': {}}
    for key in ('last_render_stage', 'last_render_source_hash'):
        if key in old:
            report[key] = old[key]
    code = 1
    try:
        brief = validate_brief(read_json(args.brief))
        raw = args.diagram.read_text(encoding='utf-8') if args.diagram else generate(brief)
        model = inspect_source(brief, raw)
        brief_hash = hashlib.sha256(json.dumps(brief, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        source_hash = hashlib.sha256(raw.encode()).hexdigest()
        report.update(brief_hash=brief_hash, source_hash=source_hash)
        if old.get('status') == 'passed' and args.reuse_valid_package:
            require(old.get('source_hash') == source_hash and old.get('brief_hash') == brief_hash, '输入已变，不能复用旧图包')
            valid = verify_package(out)
            return 0, {**valid, 'cache_reused': True}
        if attempts:
            require(old.get('status') != 'passed', '成功图包请复用或为新需求选择新目录')
            require(attempts < 2, '同一图包最多两次渲染')
            require(old.get('last_render_source_hash') != source_hash, '失败源码未修改，不重复渲染')
            require(old.get('last_render_stage') == 'layout', '只有布局失败允许一次定点修复')
        # 写入本轮实际输入并清理旧派生产物，避免失败后误交付旧图。
        write_json(out / 'brief.json', brief)
        (out / 'diagram.drawio').write_text(raw, encoding='utf-8')
        for name in ('diagram.svg', 'diagram.png', 'render.json'):
            (out / name).unlink(missing_ok=True)
        report['stage'] = 'renderer'
        report['preflight'] = preflight(args.existing_only)
        report['render_attempts'] = attempts + 1
        report.update(last_render_stage='renderer', last_render_source_hash=source_hash)
        # 请求前落盘计数；意外中断也不能重置请求预算。
        write_json(report_path, report)
        result = request('/render', {'xml': model})
        svg = result['svg']
        png = base64.b64decode(result['png'], validate=True)
        report['stage'] = 'artifacts'
        report['dimensions'] = validate_images(svg, png)
        render = {'source_sha256': source_hash, 'geometry': result['geometry'], 'renderer': result['renderer']}
        write_json(out / 'render.json', render)
        (out / 'diagram.svg').write_text(svg, encoding='utf-8')
        (out / 'diagram.png').write_bytes(png)
        report['stage'] = 'layout'
        report['last_render_stage'] = 'layout'
        issues = layout_issues(brief, result['geometry'])
        report['issues'] = issues
        require(not issues, '真实渲染布局检查失败')
        report['status'] = 'passed'
        report['stage'] = 'complete'
        report['sha256'] = {name: digest(out / name) for name in
                            ('brief.json', 'diagram.drawio', 'diagram.svg', 'diagram.png', 'render.json')}
        write_json(report_path, report)
        verify_package(out)
        code = 0
    except Exception as exc:
        report['status'] = 'blocked' if report['stage'] == 'renderer' else 'failed'
        report['issues'].append(str(exc))
        if report['status'] == 'blocked':
            report['renderer_error'] = failure(exc)
        code = 2 if report['status'] == 'blocked' else 1
        if old.get('status') == 'passed':
            # 无效的新请求不能破坏既有成功包；终端报告仍明确本次失败。
            report['existing_package_preserved'] = True
            return code, report
    report['elapsed_seconds'] = round(time.monotonic() - started, 3)
    write_json(report_path, report)
    return code, report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--brief', type=Path, required=True)
    parser.add_argument('--out-dir', type=Path, required=True)
    parser.add_argument('--diagram', type=Path, help='验证已有源文件；省略则根据 brief 生成')
    parser.add_argument('--existing-only', action='store_true')
    parser.add_argument('--reuse-valid-package', action='store_true')
    args = parser.parse_args()
    try:
        code, report = run(args)
    except Exception as exc:
        code, report = 1, {'status': 'failed', 'issues': [str(exc)]}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    sys.exit(code)
