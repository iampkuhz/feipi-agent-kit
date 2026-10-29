"""安装输出回归：真实 make 入口、隔离目录、实际变更及 TTY/管道行为。"""

import errno
import os
from pathlib import Path
import pty
import select
import shutil
import subprocess
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]


class InstallOutputTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="feipi output ")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.repo = self.base / "source repo"
        (self.repo / "scripts/harness").mkdir(parents=True)
        for relative in ("Makefile", "scripts/install_skills.sh", "scripts/harness/validate_registry.py"):
            shutil.copy2(ROOT / relative, self.repo / relative)
        self.home = self.base / "home"
        self.home.mkdir()
        self.project = self.base / "project"
        self.project.mkdir()
        self.codex = self.home / ".codex"
        self.openclaw = self.home / ".openclaw"
        self.env = dict(os.environ, HOME=str(self.home), CODEX_HOME=str(self.codex),
                        OPENCLAW_HOME=str(self.openclaw), TERM="xterm-256color")
        for key in ("NO_COLOR", "COLOR", "VERBOSE", "MAKEFLAGS", "MFLAGS"):
            self.env.pop(key, None)
        records = ["skills:"]
        for name in ("feipi-one", "feipi-two"):
            skill = self.repo / "skills/integration" / name
            (skill / "scripts").mkdir(parents=True)
            (skill / "SKILL.md").write_text(f"---\nname: {name}\n---\nfixture\n")
            (skill / "scripts/run.sh").write_text("# $REPO_ROOT/shared/resource.txt\n")
            records.append(
                f"  - name: {name}\n    path: skills/integration/{name}\n"
                "    layer: integration\n    description: fixture\n    clients: [codex]\n"
                "    entry: SKILL.md\n    validation: null\n    status: stable"
            )
        (self.repo / "skills/registry.yaml").write_text("\n".join(records) + "\n")
        (self.repo / "shared").mkdir()
        (self.repo / "shared/resource.txt").write_text("shared fixture\n")

    def run_make(self, *args, env=None, success=True):
        result = subprocess.run(["make", *args], cwd=self.repo, env=env or self.env,
                                text=True, capture_output=True, timeout=30)
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        return result

    def assert_counts(self, output, added=0, updated=0, skipped=0, warnings=0):
        self.assertIn(f"总计：新增 {added} · 更新 {updated} · 跳过 {skipped} · 警告 {warnings}", output)

    def test_new_repeat_and_updated_entries(self):
        first = self.run_make("install-links", "AGENT=codex")
        self.assert_counts(first.stdout, added=3)
        self.assertEqual(first.stdout.count("[新增]"), 3)
        self.assertNotIn("[PASS]", first.stdout)
        self.assertNotIn("\033[", first.stdout + first.stderr)
        dest = self.codex / "skills/feipi-one/SKILL.md"
        before = dest.stat()
        repeat = self.run_make("install-links", "AGENT=codex")
        self.assert_counts(repeat.stdout, skipped=3)
        self.assertNotIn("[跳过]", repeat.stdout)
        self.assertNotIn("feipi-one", repeat.stdout)
        self.assertEqual((before.st_ino, before.st_mtime_ns), (dest.stat().st_ino, dest.stat().st_mtime_ns))
        source = self.repo / "skills/integration/feipi-one/SKILL.md"
        source.write_text(source.read_text() + "changed\n")
        changed = self.run_make("install-links", "AGENT=codex")
        self.assert_counts(changed.stdout, updated=1, skipped=2)
        self.assertIn("[更新] feipi-one", changed.stdout)
        self.assertEqual(dest.read_bytes(), source.read_bytes())

    def test_verbose_shows_skip_and_preservation_reasons(self):
        self.run_make("install-links", "AGENT=codex")
        foreign = self.codex / "skills/foreign-skill"
        foreign.mkdir()
        concise = self.run_make("install-links", "AGENT=codex")
        self.assertIn("移除 0 · 保留 1", concise.stdout)
        self.assertNotIn("[保留]", concise.stdout)
        verbose = self.run_make("install-links", "AGENT=codex", "VERBOSE=1")
        self.assertIn("[跳过] feipi-one（内容未变）", verbose.stdout)
        self.assertIn("[跳过] 共享/shared（链接未变）", verbose.stdout)
        self.assertIn(f"[保留] {foreign}（无来源标记", verbose.stdout)
        self.assertIn("[PASS]", verbose.stdout)
        self.assert_counts(verbose.stdout, skipped=3)
        self.assertTrue(foreign.is_dir())

    def test_cleanup_remains_visible_in_concise_mode(self):
        self.run_make("install-links", "AGENT=codex")
        retired = self.codex / "skills/feipi-old"
        retired.symlink_to(self.repo / "skills/integration/feipi-old", target_is_directory=True)
        result = self.run_make("install-links", "AGENT=codex")
        self.assertIn(f"[清理] 已移除本仓库旧入口：{retired}", result.stdout)
        self.assertIn("移除 1 · 保留 0", result.stdout)
        self.assert_counts(result.stdout, skipped=3)
        self.assertFalse(retired.is_symlink())

    def test_shared_link_repair_and_conflict_are_not_new_installs(self):
        self.run_make("install-links", "AGENT=codex")
        shared = self.codex / "shared"
        shared.unlink()
        shared.symlink_to(self.base / "missing", target_is_directory=True)
        repaired = self.run_make("install-links", "AGENT=codex")
        self.assertIn("[更新] 共享/shared（修复失效链接）", repaired.stdout)
        self.assert_counts(repaired.stdout, updated=1, skipped=2)
        self.assertEqual(shared.resolve(), (self.repo / "shared").resolve())
        shared.unlink()
        shared.mkdir()
        conflict = self.run_make("install-links", "AGENT=codex")
        self.assertIn("[警告] 共享/shared（目标已存在且非软链接，跳过：", conflict.stderr)
        self.assert_counts(conflict.stdout, skipped=3, warnings=1)
        self.assertFalse(shared.is_symlink())

    def test_project_openclaw_and_compatibility_entrypoints(self):
        for args, destination in (
            (("install-project", f"PROJECT={self.project}"), self.project / ".agents"),
            (("install-links", "AGENT=openclaw"), self.openclaw),
        ):
            with self.subTest(args=args):
                first = self.run_make(*args)
                self.assert_counts(first.stdout, added=3)
                self.assertIn("模式：实拷", first.stdout)
                self.assertFalse((destination / "skills/feipi-one/scripts").is_symlink())
                self.assert_counts(self.run_make(*args).stdout, skipped=3)
                resource = self.repo / "shared/resource.txt"
                resource.write_text(resource.read_text() + "changed\n")
                self.assert_counts(self.run_make(*args).stdout, updated=1, skipped=2)
                self.assertEqual((destination / "shared/resource.txt").read_bytes(), resource.read_bytes())
        alias = self.run_make("install", f"DIR={self.project}", "VERBOSE=1", "COLOR=never")
        self.assertIn("[跳过] feipi-one", alias.stdout)
        self.assertNotIn("Entering directory", alias.stdout)
        self.assertNotIn("\033[", alias.stdout)
        self.assert_counts(self.run_make("install", "AGENT=codex").stdout, added=3)

    def test_multi_agent_totals(self):
        self.codex.mkdir()
        self.openclaw.mkdir()
        result = self.run_make("install-links")
        self.assertEqual(result.stdout.count("小计：新增 3"), 2)
        self.assert_counts(result.stdout, added=6)
        self.assert_counts(self.run_make("install-links").stdout, skipped=6)

    def test_no_shared_dependencies_is_a_successful_install(self):
        for name in ("feipi-one", "feipi-two"):
            (self.repo / "skills/integration" / name / "scripts/run.sh").write_text("# no shared dependencies\n")
        first = self.run_make("install-links", "AGENT=codex")
        self.assert_counts(first.stdout, added=2)
        self.assert_counts(self.run_make("install-links", "AGENT=codex").stdout, skipped=2)

    def test_color_controls_for_pipes(self):
        forced = self.run_make("install-links", "AGENT=codex", "COLOR=always")
        self.assertIn("\033[1;32m[新增]\033[0m", forced.stdout)
        self.assertIn("\033[1;36mcodex\033[0m", forced.stdout)
        repeat = self.run_make("install-links", "AGENT=codex", "COLOR=always", "VERBOSE=1")
        self.assertIn("\033[2m[跳过]\033[0m", repeat.stdout)
        for options, env in (
            (("COLOR=never",), self.env),
            (("COLOR=always",), dict(self.env, NO_COLOR="1")),
            (("COLOR=auto",), dict(self.env, TERM="dumb")),
        ):
            with self.subTest(options=options, env=env.get("NO_COLOR")):
                output = self.run_make("install-links", "AGENT=codex", *options, env=env)
                self.assertNotIn("\033[", output.stdout + output.stderr)

    def test_auto_color_on_terminal_and_plain_redirected_stderr(self):
        self.codex.mkdir()
        (self.codex / "shared").mkdir()  # 警告写入单独重定向的 stderr。
        master, slave = pty.openpty()
        try:
            process = subprocess.Popen(["make", "install-links", "AGENT=codex"], cwd=self.repo,
                                       env=self.env, stdout=slave, stderr=subprocess.PIPE)
            # 持续读取，避免 PTY 缓冲阻塞；保留 slave 到读取完毕，兼容 macOS。
            chunks = []
            deadline = time.monotonic() + 30
            try:
                while True:
                    ready, _, _ = select.select([master], [], [], 0.1)
                    if ready:
                        try:
                            chunk = os.read(master, 65536)
                        except OSError as error:
                            if error.errno != errno.EIO:
                                raise
                            break
                        if not chunk:
                            break
                        chunks.append(chunk)
                    elif process.poll() is not None:
                        break
                    if time.monotonic() > deadline:
                        self.fail("终端输出超时")
                _, stderr = process.communicate(timeout=5)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.communicate()
            self.assertEqual(process.returncode, 0, stderr)
            self.assertIn(b"\033[1;32m", b"".join(chunks))
            self.assertNotIn(b"\033[", stderr)
            self.assertIn("[警告]", stderr.decode())
        finally:
            os.close(master)
            if slave is not None:
                os.close(slave)

    def test_failure_keeps_prior_progress_without_success_summary(self):
        fakebin = self.base / "bin"
        fakebin.mkdir()
        command = fakebin / "cp"
        command.write_text('#!/bin/sh\ncase "$*" in *feipi-two*) exit 77;; esac\nexec /bin/cp "$@"\n')
        command.chmod(0o755)
        result = self.run_make("install-links", "AGENT=codex", success=False,
                               env=dict(self.env, PATH=f"{fakebin}{os.pathsep}{self.env['PATH']}"))
        self.assertIn("[新增] feipi-one", result.stdout)
        self.assertIn("[失败] 安装失败：", result.stderr)
        self.assertIn("feipi-two", result.stderr)
        self.assertNotIn("总计：", result.stdout)
        self.assertNotIn("小计：", result.stdout)
        self.assertTrue((self.codex / "skills/feipi-one/SKILL.md").is_file())
        self.assertFalse((self.codex / "skills/feipi-two").exists())

    def test_validation_failure_and_invalid_options_stop_before_install(self):
        bad_color = self.run_make("install-links", "AGENT=codex", "COLOR=bad", success=False)
        self.assertIn("无效颜色模式", bad_color.stderr)
        missing = subprocess.run(["bash", "scripts/install_skills.sh", "--color"], cwd=self.repo,
                                 env=self.env, capture_output=True, text=True, timeout=10)
        self.assertNotEqual(missing.returncode, 0)
        self.assertIn("--color 缺少参数", missing.stderr)
        (self.repo / "skills/integration/feipi-one/SKILL.md").unlink()
        failed = self.run_make("install-links", "AGENT=codex", success=False)
        self.assertIn("[FAIL]", failed.stderr)
        self.assertIn("[失败] 注册表验证失败", failed.stderr)
        self.assertNotIn("[清理]", failed.stdout)
        self.assertNotIn("总计：", failed.stdout)
        self.assertFalse(self.codex.exists())


if __name__ == "__main__":
    unittest.main()
