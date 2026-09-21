#!/usr/bin/env python3
"""Validate source-only skill development layout and filtered installation."""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY = REPO_ROOT / "skills/registry.yaml"
INSTALLER = REPO_ROOT / "scripts/install_skills.sh"
CREATOR_NAME = "feipi-skill-govern"
DEVELOPMENT_REF = re.compile(r"(^|[\s'\"`(])(tests|evals)/|scripts/test\.sh", re.MULTILINE)


def fail(message: str) -> None:
    raise AssertionError(message)


def registry_paths() -> list[Path]:
    paths: list[Path] = []
    for line in REGISTRY.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^\s+path:\s*(.+?)\s*$", line)
        if match:
            paths.append(REPO_ROOT / match.group(1).strip("'\""))
    if not paths:
        fail("registry.yaml 未解析到 skill 路径")
    return paths


def validate_eval_cases(skill: Path) -> None:
    cases_path = skill / "evals/cases.json"
    if not cases_path.is_file():
        fail(f"缺少行为评估用例：{cases_path.relative_to(REPO_ROOT)}")
    data = json.loads(cases_path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or data.get("skill") != skill.name:
        fail(f"行为评估元数据不匹配：{cases_path.relative_to(REPO_ROOT)}")
    cases = data.get("cases")
    if not isinstance(cases, list) or not cases:
        fail(f"行为评估用例不能为空：{cases_path.relative_to(REPO_ROOT)}")
    seen: set[str] = set()
    for case in cases:
        case_id = case.get("id")
        if not isinstance(case_id, str) or not case_id or case_id in seen:
            fail(f"行为评估 id 缺失或重复：{cases_path.relative_to(REPO_ROOT)}")
        seen.add(case_id)
        for field in ("prompt", "expected", "forbidden"):
            value = case.get(field)
            if field == "prompt" and (not isinstance(value, str) or not value.strip()):
                fail(f"{case_id} 缺少 prompt")
            if field != "prompt" and (not isinstance(value, list) or not value):
                fail(f"{case_id} 缺少 {field}")


def validate_source_layout(skills: list[Path]) -> None:
    for skill in skills:
        test_entry = skill / "tests/run.sh"
        if not test_entry.is_file() or not os.access(test_entry, os.X_OK):
            fail(f"缺少可执行测试入口：{test_entry.relative_to(REPO_ROOT)}")
        validate_eval_cases(skill)

        for directory in skill.rglob("*"):
            if "node_modules" in directory.parts or "__pycache__" in directory.parts:
                continue
            if directory.is_dir() and directory.name in {"tests", "evals"} and directory.parent != skill:
                fail(f"开发目录必须位于 skill 根：{directory.relative_to(REPO_ROOT)}")

        if skill.name != CREATOR_NAME:
            for runtime_file in skill.rglob("*"):
                if not runtime_file.is_file():
                    continue
                relative_parts = runtime_file.relative_to(skill).parts
                if relative_parts[0] in {"tests", "evals", "node_modules", ".git"} \
                        or "__pycache__" in relative_parts:
                    continue
                text = runtime_file.read_text(encoding="utf-8", errors="replace")
                if DEVELOPMENT_REF.search(text):
                    fail(f"普通 skill 的运行内容引用开发目录：{runtime_file.relative_to(REPO_ROOT)}")


def assert_installed_tree(root: Path, skills: list[Path], link_mode: bool) -> None:
    for source in skills:
        installed = root / source.name
        if not (installed / "SKILL.md").is_file():
            fail(f"安装后缺少 SKILL.md：{installed}")
        for excluded in ("tests", "evals"):
            if (installed / excluded).exists() or (installed / excluded).is_symlink():
                fail(f"安装内容泄漏 {excluded}/：{installed}")
        if link_mode and (installed / "SKILL.md").is_symlink():
            fail(f"链接模式的入口文件必须实拷：{installed / 'SKILL.md'}")
        if not link_mode and (installed / "SKILL.md").is_symlink():
            fail(f"拷贝模式产生了意外软链接：{installed / 'SKILL.md'}")
        if link_mode:
            runtime_dirs = [
                entry for entry in source.iterdir()
                if entry.is_dir() and entry.name not in {"tests", "evals"}
            ]
            if runtime_dirs and not any((installed / entry.name).is_symlink() for entry in runtime_dirs):
                fail(f"链接模式未保留运行目录源码联动：{installed}")


def run_installer(args: list[str], env: dict[str, str]) -> None:
    result = subprocess.run(
        ["bash", str(INSTALLER), *args],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        errors="replace",
        capture_output=True,
    )
    if result.returncode:
        fail(f"安装器验证失败：{' '.join(args)}\n{result.stdout[-1200:]}\n{result.stderr[-1200:]}")


def validate_installation(skills: list[Path]) -> None:
    with tempfile.TemporaryDirectory(prefix="feipi-skill-layout-") as temporary:
        root = Path(temporary)
        project = root / "project"
        project.mkdir()
        env = dict(os.environ)

        run_installer(["--dir", str(project)], env)
        assert_installed_tree(project / ".agents/skills", skills, link_mode=False)

        codex_home = root / "codex-home"
        env["CODEX_HOME"] = str(codex_home)
        run_installer(["--agent", "codex"], env)
        assert_installed_tree(codex_home / "skills", skills, link_mode=True)


def main() -> None:
    skills = registry_paths()
    validate_source_layout(skills)
    validate_installation(skills)
    print(f"Skill layout validation passed: {len(skills)} skills; tests/evals excluded from copy and link installs")


if __name__ == "__main__":
    main()
