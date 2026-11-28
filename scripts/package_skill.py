#!/usr/bin/env python3
"""构建或比较过滤后的 Skill 安装树；链接与拷贝共用排除规则。"""

import filecmp
from functools import lru_cache
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys


EXCLUDED = {"maintenance", "tests", "evals", "node_modules", "__pycache__"}
MARKER = ".feipi-agent-kit-source"
REPO_ROOT = Path(__file__).resolve().parents[1]
ICON_LIBRARY = REPO_ROOT / "assets/skill-icons"


def shared_icons(skill):
    """只将约定的图库链接物化为安装包内的文件。"""
    metadata = skill / "agents/openai.yaml"
    config = metadata.read_text(encoding="utf-8") if metadata.is_file() else ""
    declares_icon = re.search(r"(?m)^ +['\"]?icon_(small|large)['\"]?\s*:", config)
    in_repository = (REPO_ROOT / "skills") in skill.resolve().parents
    expects_icon = in_repository and (ICON_LIBRARY / "catalog.json").is_file()
    if not declares_icon and not expects_icon and skill.name != "feipi-skill-govern":
        return {}
    sys.path.insert(0, str(REPO_ROOT / "skills/agent/skills/feipi-skill-govern/scripts"))
    from validate_host_metadata import codex_icon_path, validate_icon_file

    paths = [skill / codex_icon_path(config)]
    if skill.name == "feipi-skill-govern":
        paths.append(skill / "templates/code.png")
    icons = {}
    for path in paths:
        relative = path.relative_to(skill)
        validate_icon_file(skill.resolve() / relative, ICON_LIBRARY if in_repository else None, "Codex 图标")
        icons[path] = path.resolve()
    return icons


def excluded(path):
    if path.name in EXCLUDED or path.suffix == ".pyc":
        return True
    if path.is_symlink():
        target = path.resolve()
        return target.suffix == ".pyc" or bool(EXCLUDED.intersection(target.parts))
    return False


def entries(directory, icons):
    return [p for p in directory.iterdir() if p in icons or not excluded(p)]


@lru_cache(maxsize=None)
def needs_filter(directory):
    for child in directory.iterdir():
        if excluded(child) or child.is_symlink():
            return True
        if child.is_dir() and needs_filter(child):
            return True
    return False


def equal(left, right):
    if not os.path.lexists(right):
        return False
    left_mode, right_mode = left.lstat().st_mode, right.lstat().st_mode
    if stat.S_IFMT(left_mode) != stat.S_IFMT(right_mode):
        return False
    if stat.S_ISLNK(left_mode):
        return os.readlink(left) == os.readlink(right)
    if stat.S_IMODE(left_mode) != stat.S_IMODE(right_mode):
        return False
    if stat.S_ISDIR(left_mode):
        names = {p.name for p in left.iterdir()}
        return names == {p.name for p in right.iterdir()} and all(
            equal(left / name, right / name) for name in names
        )
    return stat.S_ISREG(left_mode) and filecmp.cmp(left, right, shallow=False)


def runtime_equal(source, destination, mode, icons, ancestors=frozenset()):
    if source in icons:
        return equal(icons[source], destination)
    if source.is_symlink() and source.is_dir():
        source = source.resolve()
    if source.is_symlink() or not source.is_dir():
        return equal(source, destination)
    resolved = source.resolve()
    if resolved in ancestors:
        return False
    ancestors = ancestors | {resolved}
    if mode == "link" and not needs_filter(source):
        return destination.is_symlink() and os.readlink(destination) == str(source)
    return (destination.is_dir() and not destination.is_symlink()
            and stat.S_IMODE(source.stat().st_mode) == stat.S_IMODE(destination.stat().st_mode)
            and {p.name for p in entries(source, icons)} == {p.name for p in destination.iterdir()}
            and all(runtime_equal(p, destination / p.name, mode, icons, ancestors) for p in entries(source, icons)))


def installed_equal(source, destination, mode, icons):
    marker = destination / MARKER
    return (destination.is_dir() and not destination.is_symlink()
            and stat.S_IMODE(destination.stat().st_mode) == 0o700
            and {p.name for p in destination.iterdir()} == {p.name for p in entries(source, icons)} | {MARKER}
            and marker.is_file() and not marker.is_symlink()
            and stat.S_IMODE(marker.stat().st_mode) == 0o600
            and marker.read_bytes() == (str(source) + "\n").encode()
            and all(runtime_equal(p, destination / p.name, mode, icons) for p in entries(source, icons)))


def stage_entry(source, destination, mode, icons, ancestors=frozenset()):
    source = icons.get(source, source)
    if source.is_symlink() and source.is_dir():
        source = source.resolve()
    if source.is_symlink():
        destination.symlink_to(os.readlink(source))
    elif source.is_dir():
        resolved = source.resolve()
        if resolved in ancestors:
            raise ValueError(f"运行目录存在循环链接：{source}")
        ancestors = ancestors | {resolved}
        if mode == "link" and not needs_filter(source):
            destination.symlink_to(source)
        elif not needs_filter(source):
            subprocess.run(["cp", "-R", "-p", str(source), str(destination)], check=True)
        else:
            destination.mkdir()
            for child in entries(source, icons):
                stage_entry(child, destination / child.name, mode, icons, ancestors)
            shutil.copystat(source, destination)
    else:
        subprocess.run(["cp", "-p", str(source), str(destination)], check=True)


def main():
    operation, source_arg, destination_arg, mode = sys.argv[1:]
    source, destination = Path(source_arg), Path(destination_arg)
    if mode == "staged":
        return 0 if equal(source, destination) else 1
    icons = shared_icons(source)
    if operation == "stage":
        for child in entries(source, icons):
            stage_entry(child, destination / child.name, mode, icons)
        return 0
    return 0 if installed_equal(source, destination, mode, icons) else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"[ERROR] 无法构建或比较安装内容：{error}", file=sys.stderr)
        sys.exit(2)
