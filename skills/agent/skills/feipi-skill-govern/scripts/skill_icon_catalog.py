#!/usr/bin/env python3
"""从用途检索 Cursor 与 Codex 图标，并把选定图标应用到仓库 Skill。"""

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import tempfile


REFERENCES = Path(__file__).resolve().parents[1] / "references"
CURSOR_NAMES = REFERENCES / "cursor-icon-names.txt"
CURSOR_HINTS = REFERENCES / "cursor-icon-keywords.json"


def cursor_names(path=CURSOR_NAMES):
    return [name for name in path.read_text(encoding="utf-8").splitlines()
            if name and not name.startswith("#")]


def catalog_records(path):
    records = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(records, dict) or not records:
        raise ValueError(f"缺少图标描述：{path}")
    for key, record in records.items():
        if (not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]*", key) or not isinstance(record, dict)
                or not all(isinstance(record.get(field), str) and record[field].strip()
                           for field in ("name", "description"))
                or not isinstance(record.get("aliases"), list) or not record["aliases"]
                or not all(isinstance(alias, str) and alias.strip() for alias in record["aliases"])):
            raise ValueError(f"图标须有稳定 ID、名称、用途和同义词：{path} → {key}")
    return records


def load_codex_catalog(library):
    records = catalog_records(library / "catalog.json")
    files = {path.stem for path in library.glob("*.png") if path.is_file() and not path.is_symlink()}
    if files != records.keys():
        raise ValueError(f"Codex 图库和目录须逐项对应。缺图：{sorted(records.keys() - files)}。"
                         f"缺描述：{sorted(files - records.keys())}")
    return records


def search_text(value):
    value = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", value)
    return " ".join(re.findall(r"[a-z0-9]+|[\u3400-\u9fff]+", value.lower()))


def rank(records, queries, limit=5):
    """用词项重合提供候选与命中理由，最终选图由执行治理的 Agent 判断。"""
    normalized = [search_text(value) for value in queries]
    results = []
    for key, record in records.items():
        name = record.get("name", key)
        aliases = record.get("aliases", [])
        terms = dict.fromkeys([name, *aliases, key])
        scores = []
        for term in terms:
            phrase = search_text(term)
            if not phrase:
                continue
            words = re.findall(r"[a-z0-9]+", phrase)
            for query in normalized:
                if phrase == query:
                    scores.append((12, term))
                elif re.search(r"[\u3400-\u9fff]", phrase) and phrase in query:
                    scores.append((8, term))
                elif f" {phrase} " in f" {query} ":
                    scores.append((8, term))
                elif len(words) > 1 and set(words).issubset(query.split()):
                    scores.append((5, term))
        if scores:
            strongest = sorted(scores, reverse=True)
            matches = list(dict.fromkeys(term for _, term in strongest))
            exact = len({term for score, term in scores if score == 12})
            results.append((strongest[0][0], exact, len(matches), key, dict(
                id=key, name=name, description=record.get("description", ""), matched=matches[:5],
            )))
    results.sort(key=lambda item: (-item[0], -item[1], -item[2], item[3]))
    return [item[4] for item in results[:limit]]


def search_cursor(names, queries, limit=5):
    hints = catalog_records(CURSOR_HINTS)
    candidates = {}
    for name in names:
        meta = hints.get(name, {})
        # 原生名称始终可查。拆词使新版本尚未有手工同义词的名称仍可发现。
        parts = [part for part in search_text(name).split() if len(part) >= 3]
        candidates[name] = {**meta, "aliases": [*meta.get("aliases", []), *parts]}
    return rank(candidates, queries, limit)


def find_library(location):
    current = location.resolve()
    for parent in (current, *current.parents):
        library = parent / "assets/skill-icons"
        if (library / "catalog.json").is_file():
            return library
    raise ValueError("找不到 Codex 图库，请从目标仓库执行或提供 --skill 路径")


def find_candidates(skill, queries):
    if skill is not None:
        from validate_host_metadata import field_value, scalar_field, skill_frontmatter

        _, frontmatter, _ = skill_frontmatter(skill / "SKILL.md")
        description, continuation = field_value(frontmatter, 0, "description", "SKILL.md")
        queries = [*queries, scalar_field(frontmatter, 0, "name", "SKILL.md"),
                   " ".join([description, *continuation])]
    if not any(query.strip() for query in queries):
        raise ValueError("请提供用途关键词或 --skill")
    library = find_library(skill or Path.cwd())
    codex = rank(load_codex_catalog(library), queries)
    for candidate in codex:
        candidate["file"] = str(library / f"{candidate['id']}.png")
    return {"cursor": search_cursor(cursor_names(), queries),
            "codex": codex}


def set_scalar(text, indent, field, value, source, quoted=False):
    from validate_host_metadata import scalar_field

    current = scalar_field(text, indent, field, source, required=False)
    token = json.dumps(value) if quoted else value
    if current is None:
        return text.rstrip("\n") + f"\n{' ' * indent}{field}: {token}\n"
    if current == value:
        return text
    pattern = rf"(?m)^(?P<key>{' ' * indent}(['\"]?){field}\2[ \t]*:[ \t]+)(?:\"[^\"\n]*\"|'[^'\n]*'|[^\s#]+)"
    updated, count = re.subn(pattern, lambda match: match["key"] + token, text)
    if count != 1:
        raise ValueError(f"无法修改 {source}.{field}")
    return updated


def set_codex_icon(config, relative):
    from validate_host_metadata import mapping_field

    source = "agents/openai.yaml"
    _, indent = mapping_field(config, "interface", source)
    header = re.search(r"(?m)^(['\"]?)interface\1[ \t]*:[^\n]*\n", config)
    start = header.end()
    remainder = config[start:]
    following = re.search(r"(?m)^[^ \t\n#]", remainder)
    end = start + following.start() if following else len(config)
    interface = config[start:end]
    for field in ("icon_small", "icon_large"):
        interface = set_scalar(interface, indent, field, f"./{relative}", source, quoted=True)
    return config[:start] + interface + config[end:]


def bind(skill, cursor, codex, color):
    from validate_host_metadata import (CURSOR_COLORS, codex_icon_path, skill_frontmatter,
                                        source_library, validate_host_metadata)

    skill = skill.resolve()
    library = source_library(skill)
    if library is None:
        raise ValueError("绑定命令用于仓库 skills/ 内的源码 Skill")
    if cursor not in cursor_names() or codex not in load_codex_catalog(library):
        raise ValueError("Cursor 或 Codex 图标 ID 未收录，使用 search 查找候选")
    if color is not None and color not in CURSOR_COLORS:
        raise ValueError(f"Cursor 颜色无效：{color!r}")

    entry = skill / "SKILL.md"
    opening, frontmatter, body = skill_frontmatter(entry)
    original = opening + frontmatter + body
    frontmatter = set_scalar(frontmatter, 0, "icon", cursor, "SKILL.md")
    if color is not None:
        frontmatter = set_scalar(frontmatter, 0, "color", color, "SKILL.md")
    updated = opening + frontmatter + body

    metadata = skill / "agents/openai.yaml"
    config = metadata.read_text(encoding="utf-8")
    relative = Path("assets") / f"{codex}.png"
    updated_config = set_codex_icon(config, relative)
    icon = skill / relative
    if icon.exists() and not icon.is_symlink():
        raise ValueError(f"请先迁移仓库 Skill 的本地图像：{icon}")
    target = os.path.relpath(library / icon.name, icon.parent)
    previous = os.readlink(icon) if icon.is_symlink() else None
    if target == previous and updated == original and config == updated_config:
        validate_host_metadata(skill)
        return

    old_icon = None
    try:
        old_icon = skill / codex_icon_path(config)
    except ValueError:
        pass  # 缺失或不一致的旧字段没有可安全清理的唯一绑定。
    icon.parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".skill-icons-", dir=skill) as directory:
        staging = Path(directory)
        backups = []
        for path, content in ((entry, updated), (metadata, updated_config)):
            backup = staging / f"old-{path.name}"
            replacement = staging / path.name
            shutil.copy2(path, backup)
            replacement.write_text(content, encoding="utf-8")
            shutil.copymode(path, replacement)
            backups.append((path, backup, replacement))
        icon_copy = staging / icon.name
        icon_copy.symlink_to(target)
        os.replace(icon_copy, icon)
        try:
            for path, _, replacement in backups:
                os.replace(replacement, path)
            validate_host_metadata(skill)
            if (old_icon is not None and old_icon != icon and old_icon.is_symlink()
                    and old_icon.resolve().parent == library):
                old_icon.unlink()
        except (OSError, ValueError):
            for path, backup, _ in backups:
                os.replace(backup, path)
            if previous is None:
                icon.unlink()
            else:
                icon_copy.symlink_to(previous)
                os.replace(icon_copy, icon)
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    search = actions.add_parser("search", help="按 Skill 用途或关键词展示两端候选与命中词")
    search.add_argument("query", nargs="*")
    search.add_argument("--skill", type=Path)
    apply = actions.add_parser("bind", help="应用已选定的两端图标")
    apply.add_argument("skill", type=Path)
    apply.add_argument("--cursor", required=True)
    apply.add_argument("--codex", required=True)
    apply.add_argument("--color")
    args = parser.parse_args()
    try:
        if args.action == "search":
            print(json.dumps(find_candidates(args.skill, args.query), ensure_ascii=False, indent=2))
        else:
            bind(args.skill, args.cursor, args.codex, args.color)
            print(f"已绑定 {args.skill.name} · Cursor {args.cursor} · Codex {args.codex}")
    except (OSError, ValueError) as error:
        parser.exit(1, f"[FAIL] {error}\n")


if __name__ == "__main__":
    main()
