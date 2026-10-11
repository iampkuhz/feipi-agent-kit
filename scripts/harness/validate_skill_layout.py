#!/usr/bin/env python3
"""Validate source-only skill development layout and filtered installation."""

from __future__ import annotations

import json
import os
import re
import shutil
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


def entry_snapshot(path: Path):
    """不跟随链接，检查保留入口的全部内容。"""
    if path.is_symlink():
        return ("link", os.readlink(path))
    if path.is_dir():
        return ("directory", {child.name: entry_snapshot(child) for child in path.iterdir()})
    return ("file", path.read_bytes())


def validate_retired_entries(root: Path, link_root: Path, project: Path, env: dict[str, str]) -> None:
    """在最小仓库副本执行真实 make 入口，不修改源码或用户安装目录。"""
    repo = root / "source repo"
    scripts = repo / "scripts"
    (scripts / "harness").mkdir(parents=True)
    shutil.copy2(INSTALLER, scripts / INSTALLER.name)
    shutil.copy2(REPO_ROOT / "scripts/harness/validate_registry.py", scripts / "harness")
    shutil.copy2(REPO_ROOT / "Makefile", repo / "Makefile")
    source_root = repo / "skills"
    marker = ".feipi-agent-kit-source"

    def create_skill(name: str, resources: bool = True) -> Path:
        skill = source_root / "integration" / name
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(f"---\nname: {name}\n---\nfixture\n", encoding="utf-8")
        if resources:
            (skill / "scripts").mkdir()
            (skill / "scripts/run.sh").write_text("runtime\n", encoding="utf-8")
        for excluded in ("tests", "evals"):
            (skill / excluded).mkdir()
        return skill

    def write_registry(skills: list[Path]) -> None:
        records = ["skills:"]
        for skill in skills:
            records.append(
                f"  - name: {skill.name}\n    path: {skill.relative_to(repo)}\n"
                f"    layer: {skill.parent.name}\n    description: fixture\n"
                "    clients: [codex]\n    entry: SKILL.md\n    validation: null\n    status: stable"
            )
        (source_root / "registry.yaml").write_text("\n".join(records) + "\n", encoding="utf-8")

    commands = (
        (["make", "install-links", "AGENT=codex"], link_root, True),
        (["make", "install-project", f"PROJECT={project}"], project / ".agents/skills", False),
    )

    def install(expect_success: bool = True) -> dict[Path, str]:
        outputs = {}
        for command, destination, _ in commands:
            result = subprocess.run(command, cwd=repo, env=env, text=True, capture_output=True, timeout=60)
            if (result.returncode == 0) != expect_success:
                fail(f"同步清理验证失败：{command}\n{result.stdout[-1200:]}\n{result.stderr[-1200:]}")
            if expect_success:
                for message in ("目标目录：", "清理本仓库旧入口...", "清理结果：", "完成：安装"):
                    if message not in result.stdout:
                        fail(f"安装日志未输出到终端：{command}，缺少 {message}")
                if re.search(r"^\d+ \d+$", result.stdout, re.MULTILINE):
                    fail(f"内部安装计数泄漏到终端：{command}")
            elif "清理本仓库旧入口..." in result.stdout:
                fail(f"注册表无效时开始了清理：{command}")
            outputs[destination] = result.stdout
        return outputs

    current = create_skill("feipi-current")
    retired = create_skill("feipi-retired")
    marker_only = create_skill("feipi-marker-only", resources=False)
    write_registry([current, retired, marker_only])
    install()

    preserved = {}
    removed = []
    foreign_source = root / "other source/skills/feipi-foreign"
    (foreign_source / "scripts").mkdir(parents=True)
    for _, destination, link_mode in commands:
        assert_installed_tree(destination, [current, retired, marker_only], link_mode)
        for source in (current, retired, marker_only):
            if Path((destination / source.name / marker).read_text().strip()).resolve() != source.resolve():
                fail(f"缺少安装来源：{destination / source.name}")
        if link_mode:
            # 模拟已部署的旧版真实目录：入口实拷，只有内部链接证明归属。
            (destination / retired.name / marker).unlink()

        removed.extend([destination / retired.name, destination / marker_only.name])
        for name, target in (
            ("feipi-old-absolute", source_root / "integration/feipi-old-absolute"),
            ("feipi-old-relative", source_root / "integration/feipi-old-relative"),
            ("feipi-live-retired", source_root / "integration/feipi-live-retired"),
            ("foreign-absolute", foreign_source),
            ("foreign-relative", foreign_source),
            ("foreign-broken", foreign_source / "missing"),
            ("foreign-broken-relative", foreign_source / "missing-relative"),
            ("feipi-prefix-neighbor", repo / "skills-other/feipi-prefix-neighbor"),
        ):
            if name == "feipi-live-retired":
                target.mkdir(exist_ok=True)
                (target / "keep.txt").write_text("source must survive", encoding="utf-8")
            entry = destination / name
            entry.symlink_to(os.path.relpath(target, destination) if "relative" in name else target)
            if name.startswith("feipi-old-") or name == "feipi-live-retired":
                removed.append(entry)
            else:
                preserved[entry] = entry_snapshot(entry)

        legacy = destination / "feipi-legacy-relative"
        legacy.mkdir()
        (legacy / "SKILL.md").write_text("old copied entry", encoding="utf-8")
        (legacy / "scripts").symlink_to(os.path.relpath(
            source_root / "integration" / legacy.name / "scripts", legacy
        ))
        removed.append(legacy)

        for name in ("feipi-foreign", "feipi-unmarked-copy", "feipi-mixed", "feipi-foreign-marked"):
            entry = destination / name
            entry.mkdir()
            (entry / "SKILL.md").write_text("preserve me", encoding="utf-8")
            if name != "feipi-unmarked-copy":
                resource_source = source_root / "integration" / name if name == "feipi-foreign-marked" else foreign_source
                (entry / "scripts").symlink_to(resource_source / "scripts")
            if name in {"feipi-mixed", "feipi-foreign-marked"}:
                (entry / "assets").symlink_to(source_root / "integration" / name / "assets")
            if name == "feipi-foreign-marked":
                (entry / marker).write_text(str(foreign_source) + "\n", encoding="utf-8")
            preserved[entry] = entry_snapshot(entry)

        # 初次安装的真仓库内容，对 fixture 仓库来说也属于其他来源。
        original_entry = destination / "feipi-skill-govern/SKILL.md"
        preserved[original_entry] = entry_snapshot(original_entry)

    renamed = retired.with_name("feipi-renamed")
    retired.rename(renamed)
    shutil.rmtree(marker_only)
    marker_only.mkdir()  # 目录仍存在但已无 SKILL.md，也应退役。
    moved = source_root / "authoring" / current.name
    moved.parent.mkdir()
    current.rename(moved)
    (moved / "SKILL.md").write_text("updated current skill", encoding="utf-8")

    # 注册表未同步时，必须在任何清理或安装之前中止。
    before = {entry: entry_snapshot(entry) for entry in removed}
    install(expect_success=False)
    for entry, snapshot in before.items():
        if entry_snapshot(entry) != snapshot:
            fail(f"注册表无效时改动了入口：{entry}")

    write_registry([moved, renamed])
    for iteration in range(2):
        outputs = install()
        for destination, output in outputs.items():
            expected = [entry for entry in removed if entry.parent == destination] if iteration == 0 else []
            messages = [line for line in output.splitlines() if "已移除本仓库旧入口：" in line]
            if len(messages) != len(expected) or any(
                not any(line.endswith(f"/{entry.name}") for line in messages) for entry in expected
            ):
                fail(f"删除日志与实际清理不一致：{destination}")
            if f"清理结果：移除 {len(expected)} 个本仓库旧入口" not in output:
                fail(f"缺少清理结果日志：{destination}")
            if not any("保留入口：" in line and "/feipi-unmarked-copy" in line
                       and "无来源标记" in line for line in output.splitlines()):
                fail(f"未说明纯实拷旧入口的保留原因：{destination}")
        for entry in removed:
            if os.path.lexists(entry):
                fail(f"本仓库旧入口未清理：{entry}")
        for entry, snapshot in preserved.items():
            if entry_snapshot(entry) != snapshot:
                fail(f"其他来源入口被修改：{entry}")
        for _, destination, link_mode in commands:
            assert_installed_tree(destination, [moved, renamed], link_mode)
            for source in (moved, renamed):
                if Path((destination / source.name / marker).read_text().strip()).resolve() != source.resolve():
                    fail(f"改名或迁层后来源未同步：{destination / source.name}")
            if (destination / moved.name / "SKILL.md").read_text() != "updated current skill":
                fail(f"当前入口未更新：{destination / moved.name}")
        if not (source_root / "integration/feipi-live-retired/keep.txt").is_file():
            fail("清理旧入口误删了链接指向的源码")


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
        validate_retired_entries(root, codex_home / "skills", project, env)


def main() -> None:
    skills = registry_paths()
    validate_source_layout(skills)
    validate_installation(skills)
    print(f"Skill layout validation passed: {len(skills)} skills; install filtering and ownership cleanup verified")


if __name__ == "__main__":
    main()
