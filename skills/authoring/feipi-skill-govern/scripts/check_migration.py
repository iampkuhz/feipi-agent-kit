#!/usr/bin/env python3
"""核对迁移清单中的来源、显式依赖和候选安装包。"""

import argparse
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess

from check_delivery import indexed, nonempty, objects, require
from check_portability import fixed_machine_paths


SKILL_ID = re.compile(r"feipi-[a-z0-9-]+")
PROJECT_ENTRIES = {"instructions", "workflow", "verification", "evidence"}
TYPES = {"bundled", "skill", "project", "host", "sibling"}
DISPOSITIONS = {"reuse", "port", "adapt", "blocked"}
DEVELOPMENT = {"maintenance", "tests", "evals", ".git", "node_modules", "__pycache__"}
HOST_PRIVATE_PATH = re.compile(
    r"(?<![\w.-])\.(?:cursor(?:-server)?|vscode(?:-server|-insiders)?|idea|"
    r"windsurf|codex|claude)(?![\w.-])"
    r"|(?<![\w.-])(?:Cursor|Windsurf|Visual Studio Code|IntelliJ IDEA)\.app\b"
    r"|(?:Application Support|AppData[\\/]+(?:Local|Roaming)|\.config)[\\/]+"
    r"(?:Cursor|Code(?: - Insiders)?|JetBrains|Windsurf)(?=[\\/]|\s|$)"
    r"|(?<![\w.-])Downloads[\\/]+plugins(?![\w.-])"
    r"|(?<![\w.-])[\w.-]+\.code-workspace\b",
    re.IGNORECASE,
)
MACHINE_URI_OR_SHARE = re.compile(r"\bfile://|(?<![\\:\w])\\{2,4}[\w.-]+\\", re.IGNORECASE)


def relative(value, label):
    require(nonempty(value), f"{label} 缺少路径")
    path = PurePosixPath(value)
    require(not path.is_absolute() and ".." not in path.parts and "\\" not in value
            and bool(path.parts), f"{label} 需要相对路径：{value}")
    return path


def file_under(root, value, label):
    path = root / relative(value, label)
    require(path.resolve().is_relative_to(root.resolve()) and path.is_file(),
            f"{label} 不存在或超出目录：{value}")
    return path


def check_cycles(graph):
    done = set()

    def visit(node, stack):
        require(node not in stack, "Skill 调用有循环：" + " → ".join((*stack, node)))
        if node not in done:
            for child in sorted(graph[node]):
                visit(child, (*stack, node))
            done.add(node)

    for node in graph:
        visit(node, ())


def check_entry(path, name):
    text = path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    meta = parts[1] if len(parts) == 3 and not parts[0].strip() else ""
    match = re.search(r"(?m)^name:[ \t]*([^\r\n]+)$", meta)
    require(match and match[1].strip().strip('"').strip("'") == name,
            f"入口 Skill ID 不符：{name} → {path}")


def check_runtime_path(line, location):
    local_text = re.sub(r"https?://[^\s\"'\x60]+", "", line)
    private_path = HOST_PRIVATE_PATH.search(local_text)
    require(private_path is None,
            f"运行路径依赖 IDE、Agent 宿主或个人上游目录：{location}"
            + (f"（{private_path[0]}）" if private_path else ""))
    require(not MACHINE_URI_OR_SHARE.search(local_text), f"运行路径包含本机 URI 或固定网络共享：{location}")
    fixed_path = next(fixed_machine_paths(line, serialized_windows=True), None)
    require(fixed_path is None, f"{location}：{fixed_path}")


def runtime_tree(directory, installed=False):
    root = directory.resolve()

    def raise_walk_error(error):
        raise error

    for current, directories, files in os.walk(directory, onerror=raise_walk_error):
        for name in sorted(directories + files):
            path = Path(current) / name
            if name in DEVELOPMENT or path.suffix == ".pyc":
                require(not installed, f"安装包包含开发资料或缓存：{path}")
                if name in directories:
                    directories.remove(name)
                continue
            if installed or path.is_symlink():
                require(path.resolve().is_relative_to(root) and path.exists(),
                        f"运行文件路径失效或超出 Skill 根目录：{path}")
            if path.is_symlink():
                require(not Path(os.readlink(path)).is_absolute(), f"运行文件使用绝对符号链接：{path}")
            check_runtime_path(name, path)
            # The installer writes this provenance file. It is not a runtime dependency.
            if not path.is_file() or (installed and path == directory / ".feipi-agent-kit-source"):
                continue
            with path.open(encoding="utf-8", errors="replace") as stream:
                if "\x00" in stream.read(4096):
                    continue  # Binary asset. Its filename and location have still been checked.
                stream.seek(0)
                for number, line in enumerate(stream, 1):
                    check_runtime_path(line, f"{path}:{number}")


def validate_registry(skills, source_root):
    # Repository-only lookup. An installed copy can validate a draft without repo tooling.
    from runpy import run_path

    validator = file_under(source_root, "scripts/harness/validate_registry.py", "注册表校验器")
    entries = run_path(str(validator))["parse_registry"](source_root)
    require(isinstance(entries, list), "现有 Skill 注册表无法解析")
    registered = indexed(entries, "name")
    for name, skill in skills.items():
        require(name in registered and registered[name].get("path") == skill["path"]
                and registered[name].get("entry") == "SKILL.md",
                f"迁移清单与注册表路径不一致：{name}")


def validate(data, source_root, installed_root=None, upstream_root=None, registered=False):
    require(isinstance(data, dict) and data.get("schema_version") == 1, "迁移清单版本应为 1")
    revision = data.get("upstream_revision")
    require(isinstance(revision, str) and re.fullmatch(r"[0-9a-f]{40}", revision),
            "上游需要固定到完整 Git SHA")
    skills = indexed(objects(data, "skills"), "name")
    require(bool(skills), "清单缺少目标 Skill")
    if upstream_root is not None and (upstream_root / ".git").exists():
        head = subprocess.run(["git", "-C", str(upstream_root), "rev-parse", "HEAD"],
                              check=True, capture_output=True, text=True).stdout.strip()
        require(head == revision, "上游工作区与固定 Git SHA 不一致")
    if registered:
        validate_registry(skills, source_root)
    graph = {name: set() for name in skills}
    for name, entry in skills.items():
        require(SKILL_ID.fullmatch(name), f"Skill ID 无效：{name}")
        directory = relative(entry.get("path"), name)
        require(directory.parts[0] == "skills" and directory.name == name,
                f"源码目录与 Skill ID 不匹配：{directory}")
        check_entry(file_under(source_root, str(directory / "SKILL.md"), name), name)
        runtime_tree(source_root / directory)
        if installed_root is not None:
            check_entry(file_under(installed_root, f"{name}/SKILL.md", "安装入口"), name)
            runtime_tree(installed_root / name, installed=True)

    dependencies = indexed(objects(data, "dependencies"), "id")
    require(bool(dependencies), "迁移清单缺少依赖记录")
    for identity, dep in dependencies.items():
        caller, kind, action = (dep.get(key) for key in ("caller", "kind", "disposition"))
        require(caller in skills and kind in TYPES and action in DISPOSITIONS,
                f"{identity} 的调用者、类别或处理方式无效")
        for key in ("source", "behavior", "target", "missing", "verification"):
            require(nonempty(dep.get(key)), f"{identity} 缺少 {key}")
        upstream, separator, line = dep["source"].rpartition("#L")
        require(bool(separator) and line.isdecimal() and int(line) > 0,
                f"{identity} 的上游定位应为相对路径#L行号")
        relative(upstream, "上游来源")
        if upstream_root is not None:
            source = file_under(upstream_root, upstream, "上游来源")
            require(int(line) <= len(source.read_text(encoding="utf-8").splitlines()),
                    f"{identity} 的上游行号超出文件")
        target = dep["target"]
        check_runtime_path(target, f"{identity} 的目标入口")
        if action == "blocked":
            continue
        if kind == "skill":
            require(target in skills, f"{identity} 引用未知 Skill：{target}")
            graph[caller].add(target)
        elif kind == "project":
            require(target in PROJECT_ENTRIES, f"{identity} 引用未知项目入口：{target}")
        elif kind == "bundled":
            resource = relative(target, identity)
            require(not DEVELOPMENT.intersection(resource.parts), f"{identity} 依赖开发资料")
            file_under(source_root, str(PurePosixPath(skills[caller]["path"]) / resource), identity)
            if installed_root is not None:
                file_under(installed_root, str(PurePosixPath(caller) / resource), identity)
    check_cycles(graph)
    return dependencies


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--installed-root", type=Path, help="隔离的平铺 Skill 安装目录")
    parser.add_argument("--upstream-root", type=Path, help="核对记录的原文路径和行号")
    parser.add_argument("--registered", action="store_true", help="正式入库时核对现有 Skill Registry")
    args = parser.parse_args()
    try:
        data = json.loads(args.manifest.read_text(encoding="utf-8"))
        dependencies = validate(data, args.source_root, args.installed_root, args.upstream_root, args.registered)
    except (OSError, ValueError, TypeError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"[FAIL] {error}\n")
    print(f"[PASS] 核对 {len(dependencies)} 条声明依赖")
    for identity, dep in dependencies.items():
        if dep["disposition"] == "blocked":
            print(f"[BLOCKED] {identity}：{dep['missing']}")
    print("此检查覆盖声明、路径和调用关系。宿主替代行为及实际验证另需运行证据。")


if __name__ == "__main__":
    main()
