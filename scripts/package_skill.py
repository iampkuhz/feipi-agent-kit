#!/usr/bin/env python3
"""构建或比较过滤后的 Skill 安装树；链接与拷贝共用排除规则。"""

import filecmp
from functools import lru_cache
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys


EXCLUDED = {"maintenance", "tests", "evals", "node_modules"}
MARKER = ".feipi-agent-kit-source"


def excluded(path):
    return path.name in EXCLUDED or (path.is_symlink() and bool(EXCLUDED.intersection(path.resolve().parts)))


def entries(directory):
    return [p for p in directory.iterdir() if not excluded(p)]


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


def runtime_equal(source, destination, mode, ancestors=frozenset()):
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
            and {p.name for p in entries(source)} == {p.name for p in destination.iterdir()}
            and all(runtime_equal(p, destination / p.name, mode, ancestors) for p in entries(source)))


def installed_equal(source, destination, mode):
    marker = destination / MARKER
    return (destination.is_dir() and not destination.is_symlink()
            and stat.S_IMODE(destination.stat().st_mode) == 0o700
            and {p.name for p in destination.iterdir()} == {p.name for p in entries(source)} | {MARKER}
            and marker.is_file() and not marker.is_symlink()
            and stat.S_IMODE(marker.stat().st_mode) == 0o600
            and marker.read_bytes() == (str(source) + "\n").encode()
            and all(runtime_equal(p, destination / p.name, mode) for p in entries(source)))


def stage_entry(source, destination, mode, ancestors=frozenset()):
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
            for child in entries(source):
                stage_entry(child, destination / child.name, mode, ancestors)
            shutil.copystat(source, destination)
    else:
        subprocess.run(["cp", "-p", str(source), str(destination)], check=True)


def main():
    operation, source_arg, destination_arg, mode = sys.argv[1:]
    source, destination = Path(source_arg), Path(destination_arg)
    if operation == "stage":
        for child in entries(source):
            stage_entry(child, destination / child.name, mode)
        return 0
    same = equal(source, destination) if mode == "staged" else installed_equal(source, destination, mode)
    return 0 if same else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"[ERROR] 无法构建或比较安装内容：{error}", file=sys.stderr)
        sys.exit(2)
