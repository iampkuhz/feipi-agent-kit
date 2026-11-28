#!/usr/bin/env python3
"""Read and validate the repository's path-only Skill registry."""

import argparse
import os
from pathlib import Path
import re
import sys


SEGMENT = r"[a-z0-9]+(?:-[a-z0-9]+)*"
SKILL_PATH = re.compile(rf"skills/({SEGMENT})(?:/({SEGMENT}))?/(feipi-{SEGMENT})")
REGISTRY_ITEM = re.compile(r"""  - (['"]?)([^ '"\t#]+)\1(?:[ \t]+#.*)?""")
DEVELOPMENT_DIRS = {"maintenance", "tests", "evals", "node_modules", "__pycache__"}
ROLE_DIRS = {"workflow", "workflows", "verification"}


def registry_paths(path):
    """Accept the single mapping and block list used by the repository."""
    lines = [
        (number, line.rstrip()) for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if not lines or lines[0][1] != "skills:":
        raise ValueError("skills/registry.yaml 必须以 skills: 开始")
    paths = []
    for number, line in lines[1:]:
        entry = REGISTRY_ITEM.fullmatch(line)
        if entry is None:
            raise ValueError(f"skills/registry.yaml:{number} 只接受仓库相对路径")
        paths.append(entry[2])
    if not paths:
        raise ValueError("skills/registry.yaml 未列出 Skill")
    if len(set(paths)) != len(paths):
        raise ValueError("skills/registry.yaml 含重复路径")
    return paths


def read_metadata(entry):
    with entry.open(encoding="utf-8") as stream:
        if stream.readline().strip() != "---":
            raise ValueError(f"入口缺少 frontmatter：{entry}")
        fields = {}
        for line in stream:
            if line.rstrip() == "---":
                break
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            # Only name and description are consumed by the index. Leave extension
            # fields and nested YAML to the Skill package and its actual consumers.
            key, _, value = line.rstrip().partition(":")
            if key not in {"name", "description"}:
                continue
            if key in fields:
                raise ValueError(f"入口 frontmatter 字段重复：{key} → {entry}")
            value = value.strip()
            if len(value) > 1 and value[0] in ("'", '"') and value[-1] == value[0]:
                value = value[1:-1]
            fields[key] = value
        else:
            raise ValueError(f"入口 frontmatter 缺少结束符：{entry}")
    if not fields.get("name") or not fields.get("description"):
        raise ValueError(f"入口缺少 name 或 description：{entry}")
    return fields


def discover_skill_paths(root):
    def raise_error(error):
        raise error

    found = set()
    for current, directories, files in os.walk(root / "skills", onerror=raise_error):
        directories[:] = [
            name for name in directories if not name.startswith(".") and name not in DEVELOPMENT_DIRS
        ]
        if {"SKILL.md", ".smile"}.intersection(files) or "agents" in directories:
            found.add(Path(current).relative_to(root).as_posix())
    return found


def parse_registry(root):
    root = Path(root).resolve()
    indexed = registry_paths(root / "skills/registry.yaml")
    entries = []
    names = set()
    for value in indexed:
        match = SKILL_PATH.fullmatch(value)
        if match is None:
            raise ValueError(f"Skill 路径须为 skills/<领域>/[<子领域>/]<Skill ID>：{value}")
        domain, subdomain, name = match.groups()
        if any(part in ROLE_DIRS or part in DEVELOPMENT_DIRS for part in (domain, subdomain)):
            raise ValueError(f"Skill 分类须为领域和可选子领域：{value}")
        directory = root / value
        entry = directory / "SKILL.md"
        if not entry.resolve().is_relative_to((root / "skills").resolve()) or any(
            part.is_symlink() for part in (entry, directory, *directory.parents) if part != root and part.is_relative_to(root)
        ):
            raise ValueError(f"Skill 入口越界或经过符号链接：{value}")
        if not entry.is_file():
            raise ValueError(f"登记的 Skill 或入口不存在：{value}/SKILL.md")
        metadata = read_metadata(entry)
        if metadata["name"] != name:
            raise ValueError(f"入口 name 与目录不一致：{value}/SKILL.md")
        if name in names:
            raise ValueError(f"Skill ID 重复：{name}")
        names.add(name)
        entries.append(dict(metadata, path=value, domain=domain, subdomain=subdomain))
    extra = discover_skill_paths(root) - set(indexed)
    if extra:
        raise ValueError("以下 Skill 未注册：\n  - " + "\n  - ".join(sorted(extra)))
    return entries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paths", action="store_true", help="输出供安装器使用的绝对 Skill 路径")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    try:
        entries = parse_registry(root)
    except (OSError, ValueError) as error:
        print(f"[FAIL] {error}", file=sys.stderr)
        return 1
    if args.paths:
        for entry in entries:
            print(root / entry["path"])
    else:
        print(f"Registry validation: PASS ({len(entries)} skills)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
