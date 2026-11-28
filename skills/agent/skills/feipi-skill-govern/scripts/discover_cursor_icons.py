#!/usr/bin/env python3
"""对比 Cursor 安装包中的 Custom Mode 图标名，检索新增候选。"""

import argparse
import json
from pathlib import Path
import re
from zipfile import BadZipFile, ZipFile

from skill_icon_catalog import CURSOR_NAMES, cursor_names, search_cursor


WORKBENCH = "out/vs/workbench/workbench.desktop.main.js"
ICON_MODULE = "out/vs/workbench/workbench.anysphere-ui.js"
IDENTIFIER = r"[a-zA-Z0-9_$]+"
NAME_MARKERS = {"code", "terminal", "shield", "lightning", "heart", "rocket"}


def read_bundle(path):
    if path.is_dir():
        for app in (path / "Contents/Resources/app", path / "resources/app", path):
            if (app / WORKBENCH).is_file():
                module = app / ICON_MODULE
                return ((app / "product.json").read_bytes(), (app / WORKBENCH).read_bytes(),
                        module.read_bytes() if module.is_file() else None)
        raise ValueError("找不到 Cursor 应用内的 product.json 和 workbench.desktop.main.js")
    with ZipFile(path) as archive:
        workbench = [name for name in archive.namelist() if name.endswith("/" + WORKBENCH)]
        if len(workbench) != 1:
            raise ValueError("ZIP 须包含一个 Cursor 应用的 workbench.desktop.main.js")
        prefix = workbench[0].removesuffix(WORKBENCH)
        module = prefix + ICON_MODULE
        return (archive.read(prefix + "product.json"), archive.read(workbench[0]),
                archive.read(module) if module in archive.namelist() else None)


def decode_names(packed):
    previous = ""
    names = []
    for token in packed.split():
        prefix = int(token[0], 36)
        if prefix > len(previous):
            return []
        previous = previous[:prefix] + token[1:]
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", previous):
            return []
        names.append(previous)
    if len(set(names)) != len(names) or not NAME_MARKERS.issubset(names):
        return []
    return names


def discover(source, icon_module=None):
    """找实际传给徽章校验的展开名单，忽略压缩变量名与入口拆包差异。"""
    workbench = source.decode("utf-8")
    icon_source = icon_module.decode("utf-8") if icon_module else workbench
    start = icon_source.find('"cursor-icons.ts"')
    if start < 0:
        raise ValueError("此版本的 Cursor 图标模块布局已变化，请检查实际客户端资源")
    module = icon_source[start:start + 20000]
    matches = []
    for packed in re.finditer(rf'\b({IDENTIFIER})="(0[\w-]+(?: [\w-]+){{30,}})"', module):
        names = decode_names(packed[2])
        if not names:
            continue
        consumer = re.search(rf'({IDENTIFIER})={IDENTIFIER}\({re.escape(packed[1])}\)', module[packed.end():])
        if consumer is None:
            continue
        if accepted_by_badge(consumer[1], workbench, icon_source):
            matches.append(names)
    if len(matches) != 1:
        raise ValueError("无法确认此版本 Custom Mode 徽章的名称校验表，保留现有快照")
    return matches[0]


def accepted_by_badge(variable, workbench, icon_source):
    escaped = re.escape(variable)
    if workbench is icon_source:
        aliases = [variable, *re.findall(rf'\b({IDENTIFIER})={escaped}(?=[,;])', workbench)]
        return any(re.search(rf'(?<![\w$]){re.escape(alias)}\.includes\(', workbench) for alias in aliases)

    exports = re.findall(rf'(?<![\w$]){escaped} as (CURSOR_ICON_NAMES(?:\${IDENTIFIER})?)\b', icon_source)
    for exported in exports:
        imported = re.search(rf'\b{re.escape(exported)} as ({IDENTIFIER})\b[^}}]*}}from"\./workbench\.anysphere-ui\.js"',
                             workbench)
        if imported is not None:
            sets = re.findall(rf'\b({IDENTIFIER})=new Set\({re.escape(imported[1])}\)', workbench)
            if any(re.search(rf'(?<![\w$]){re.escape(name)}\.has\(', workbench) for name in sets):
                return True
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path, help="Cursor.app、解包后的资源目录，或原始安装 ZIP")
    parser.add_argument("--query", help="用途关键词，用于筛选新增名字")
    parser.add_argument("--snapshot", type=Path, help="保存提取的候选快照供比较")
    args = parser.parse_args()
    try:
        metadata, source, module = read_bundle(args.bundle)
        product = json.loads(metadata)
        version, commit = product["version"], product["commit"]
        if not re.fullmatch(r"[\w.+-]+", version) or not re.fullmatch(r"[a-f0-9]{7,64}", commit):
            raise ValueError("Cursor 构建来源缺少可识别的版本或提交")
        current = discover(source, module)
        baseline = set(cursor_names())
        added, removed = sorted(set(current) - baseline), sorted(baseline - set(current))
        summary = {"baseline": CURSOR_NAMES.read_text(encoding="utf-8").splitlines()[0],
                   "version": version, "commit": commit, "count": len(current), "added": added, "removed": removed}
        if args.query:
            summary["added_matches"] = search_cursor(added, [args.query])
        if args.snapshot is not None:
            with args.snapshot.open("x", encoding="utf-8") as snapshot:
                snapshot.write(f"# Cursor {version} · {commit}\n# Custom Mode 徽章接受的图标标识符，含该版本的别名及样式变体。\n")
                snapshot.write("\n".join(current) + "\n")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    except (OSError, ValueError, TypeError, KeyError, BadZipFile) as error:
        parser.exit(1, f"[FAIL] {error}\n")


if __name__ == "__main__":
    main()
