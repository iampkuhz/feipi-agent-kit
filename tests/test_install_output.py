"""安装输出回归：真实 Skill 安装器、隔离目录、实际变更及 TTY/管道行为。"""

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
        for relative in ("scripts/install_skills.sh", "scripts/package_skill.py", "scripts/harness/validate_registry.py"):
            shutil.copy2(ROOT / relative, self.repo / relative)
        self.home = self.base / "home"
        self.home.mkdir()
        self.project = self.base / "project"
        self.project.mkdir()
        self.codex = self.home / ".codex"
        self.openclaw = self.home / ".openclaw"
        self.env = dict(os.environ, HOME=str(self.home), CODEX_HOME=str(self.codex),
                        OPENCLAW_HOME=str(self.openclaw), TERM="xterm-256color")
        for key in ("NO_COLOR",):
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

    def run_installer(self, *args, env=None, success=True):
        result = subprocess.run(["bash", "scripts/install_skills.sh", *args], cwd=self.repo, env=env or self.env,
                                text=True, capture_output=True, timeout=30)
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        return result

    def test_recursive_development_exclusion_and_repeat_install(self):
        source = self.repo / 'skills/integration/feipi-one'
        for parent in (source, source/'scripts/examples'):
            for name in ('maintenance', 'tests', 'evals', 'node_modules', '__pycache__'):
                directory = parent/name
                directory.mkdir(parents=True)
                (directory/'SKILL.md').write_text('source only')
                (directory/'dependency.sh').write_text('# $REPO_ROOT/development-only/resource.txt\n')
        (self.repo/'development-only').mkdir()
        (self.repo/'development-only/resource.txt').write_text('do not publish')
        clean = source/'scripts/examples/runtime'
        clean.mkdir()
        (clean/'data.txt').write_text('runtime data')
        (clean.parent/'old.pyc').write_bytes(b'cached python')
        (source/'scripts/source-notes').symlink_to(source/'maintenance')
        (source/'scripts/runtime-alias').symlink_to(source/'scripts/examples')
        commands = (
            (('--agent', 'codex'), self.codex/'skills', True),
            (('--copy', '--agent', 'openclaw'), self.openclaw/'skills', False),
            (('--dir', str(self.project)), self.project/'.agents/skills', False),
        )
        for command, destination, links in commands:
            with self.subTest(command=command):
                self.run_installer(*command)
                installed = destination/source.name
                for directory, dirs, files in os.walk(installed, followlinks=True):
                    self.assertFalse({'maintenance', 'tests', 'evals', 'node_modules', '__pycache__'}.intersection(dirs+files), directory)
                    self.assertFalse(any(name.endswith('.pyc') for name in files), directory)
                self.assertEqual((installed/'scripts/examples/runtime/data.txt').read_text(), 'runtime data')
                self.assertFalse((installed/'scripts').is_symlink())
                self.assertFalse((installed/'scripts/source-notes').exists())
                self.assertFalse((installed/'scripts/runtime-alias/maintenance').exists())
                self.assertEqual((installed/'scripts/examples/runtime').is_symlink(), links)
                self.assertFalse((destination.parent/'development-only').exists())
                before = (installed.stat().st_ino, (installed/'SKILL.md').stat().st_mtime_ns)
                (source/'scripts/examples/maintenance/SKILL.md').write_text('changed source only')
                result = self.run_installer(*command)
                self.assert_counts(result.stdout, skipped=3)
                self.assertEqual(before, (installed.stat().st_ino, (installed/'SKILL.md').stat().st_mtime_ns))

    def test_linked_directory_is_refiltered_when_maintenance_is_added(self):
        self.run_installer('--agent', 'codex')
        installed = self.codex/'skills/feipi-one/scripts'
        self.assertTrue(installed.is_symlink())
        source = self.repo/'skills/integration/feipi-one/scripts'
        (source/'maintenance').mkdir()
        (source/'maintenance/private.md').write_text('source only')
        result = self.run_installer('--agent', 'codex')
        self.assert_counts(result.stdout, updated=1, skipped=2)
        self.assertFalse(installed.is_symlink())
        self.assertFalse((installed/'maintenance').exists())
        self.assertEqual((installed/'run.sh').read_bytes(), (source/'run.sh').read_bytes())

    def test_cyclic_runtime_link_does_not_replace_existing_installation(self):
        self.run_installer('--copy', '--agent', 'codex')
        installed = self.codex/'skills/feipi-one'
        before = installed.stat().st_ino
        source = self.repo/'skills/integration/feipi-one/scripts'
        (source/'loop').symlink_to(source)
        result = self.run_installer('--copy', '--agent', 'codex', success=False)
        self.assertIn('循环链接', result.stderr)
        self.assertEqual(installed.stat().st_ino, before)
        self.assertFalse((installed/'scripts/loop').exists())

    def env_without_executable(self, executable):
        path_parts = []
        for index, path_entry in enumerate(self.env["PATH"].split(os.pathsep)):
            directory = Path(path_entry)
            candidate = directory / executable
            if candidate.is_file() and os.access(candidate, os.X_OK):
                shadow = self.base / f"path-without-{executable}-{index}"
                shadow.mkdir()
                for item in directory.iterdir():
                    if item.name == executable or not item.is_file() or not os.access(item, os.X_OK):
                        continue
                    (shadow / item.name).symlink_to(item)
                path_parts.append(str(shadow))
            else:
                path_parts.append(path_entry)
        env = dict(self.env, PATH=os.pathsep.join(path_parts))
        self.assertIsNone(shutil.which(executable, path=env["PATH"]))
        return env

    def assert_counts(self, output, added=0, updated=0, deleted=0, preserved=0, skipped=0, warnings=0):
        self.assertIn(f"总计：新增 {added} · 更新 {updated} · 删除 {deleted} · 保留 {preserved}"
                      f" · 跳过 {skipped} · 警告 {warnings}", output)

    def test_single_skill_preserves_other_entries_and_skips_unrelated_dependencies(self):
        self.run_installer('--copy', '--agent', 'codex')
        other = self.codex/'skills/feipi-two/SKILL.md'
        other.write_text('local unpublished content')
        stale = self.codex/'skills/feipi-retired'
        stale.mkdir()
        shutil.copy2(self.codex/'skills/feipi-one/.feipi-agent-kit-source', stale/'.feipi-agent-kit-source')
        shutil.rmtree(self.codex/'shared')
        (self.repo/'skills/integration/feipi-one/scripts/run.sh').write_text('# no shared dependency\n')
        result = subprocess.run(['bash', 'scripts/install_skills.sh', '--agent', 'codex', '--copy', '--skill', 'feipi-one'],
                                cwd=self.repo, env=self.env, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        self.assertEqual(other.read_text(), 'local unpublished content')
        self.assertTrue(stale.exists())
        self.assertFalse((self.codex/'shared').exists())
        self.assertFalse(self.openclaw.exists())
        self.assertNotIn('feipi-two', result.stdout)

    def test_unknown_selected_skill_fails_before_target_creation(self):
        result = subprocess.run(['bash', 'scripts/install_skills.sh', '--agent', 'codex', '--skill', 'missing'],
                                cwd=self.repo, env=self.env, text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('未注册', result.stderr)
        self.assertFalse(self.codex.exists())

    def test_install_succeeds_without_ripgrep(self):
        env = self.env_without_executable("rg")
        result = subprocess.run(
            ["bash", "scripts/install_skills.sh", '--agent', 'codex'],
            cwd=self.repo, env=env, text=True, capture_output=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((self.codex / "skills/feipi-one/SKILL.md").is_file())
        self.assertTrue((self.codex / "shared/resource.txt").is_file())

    def test_new_repeat_and_updated_entries(self):
        first = self.run_installer('--agent', 'codex')
        self.assert_counts(first.stdout, added=3)
        self.assertEqual(first.stdout.count("[新增]"), 3)
        self.assertNotIn("[PASS]", first.stdout)
        self.assertNotIn("\033[", first.stdout + first.stderr)
        dest = self.codex / "skills/feipi-one/SKILL.md"
        before = dest.stat()
        repeat = self.run_installer('--agent', 'codex')
        self.assert_counts(repeat.stdout, skipped=3)
        self.assertIn("[跳过] feipi-one（内容未变）", repeat.stdout)
        self.assertEqual((before.st_ino, before.st_mtime_ns), (dest.stat().st_ino, dest.stat().st_mtime_ns))
        source = self.repo / "skills/integration/feipi-one/SKILL.md"
        source.write_text(source.read_text() + "changed\n")
        changed = self.run_installer('--agent', 'codex')
        self.assert_counts(changed.stdout, updated=1, skipped=2)
        self.assertIn("[更新] feipi-one", changed.stdout)
        self.assertEqual(dest.read_bytes(), source.read_bytes())

    def test_copy_install_reports_skill_version_transition(self):
        metadata = self.repo / "skills/integration/feipi-one/agents/openai.yaml"
        metadata.parent.mkdir(parents=True)
        metadata.write_text("version: 1\n", encoding="utf-8")
        self.run_installer('--copy', '--agent', 'codex')

        metadata.write_text("version: 2\n", encoding="utf-8")
        updated = self.run_installer('--copy', '--agent', 'codex')

        self.assertIn("[更新] feipi-one（v1 → v2）", updated.stdout)
        self.assert_counts(updated.stdout, updated=1, skipped=2)
        installed_metadata = self.codex / "skills/feipi-one/agents/openai.yaml"
        self.assertEqual(installed_metadata.read_text(encoding="utf-8"), "version: 2\n")

    def test_unrelated_skills_are_silently_ignored(self):
        self.run_installer('--agent', 'codex')
        foreign = self.codex / "skills/foreign-skill"
        foreign.mkdir()
        entry = foreign / "SKILL.md"
        entry.write_text("third-party skill")
        result = self.run_installer('--agent', 'codex')
        self.assertIn("[跳过] feipi-one（内容未变）", result.stdout)
        self.assertIn("[跳过] 共享/shared（链接未变）", result.stdout)
        self.assertNotIn(foreign.name, result.stdout + result.stderr)
        self.assertIn("注册表及目录一致", result.stdout)
        self.assert_counts(result.stdout, skipped=3)
        self.assertEqual(entry.read_text(), "third-party skill")

    def test_source_marker_is_stable_across_umask_in_copy_and_link_modes(self):
        for options in (('--copy',), ()):
            with self.subTest(options=options):
                if self.codex.exists():
                    shutil.rmtree(self.codex)
                marker = self.codex / 'skills/feipi-one/.feipi-agent-kit-source'
                for mask in [0o077, 0o022]:
                    result = subprocess.run(['bash', 'scripts/install_skills.sh', *options, '--agent', 'codex'], cwd=self.repo,
                                            env=self.env, text=True, capture_output=True, timeout=30,
                                            umask=mask)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    if mask == 0o077:
                        previous = marker.stat()
                    else:
                        self.assert_counts(result.stdout, skipped=3)
                        self.assertEqual((previous.st_ino, previous.st_mtime_ns),
                                         (marker.stat().st_ino, marker.stat().st_mtime_ns))
                    self.assertEqual(marker.stat().st_mode & 0o777, 0o600)

    def test_deletion_is_visible_in_client_subtotal_and_total(self):
        self.run_installer('--agent', 'codex')
        retired = self.codex / "skills/feipi-old"
        retired.symlink_to(self.repo / "skills/integration/feipi-old", target_is_directory=True)
        result = self.run_installer('--agent', 'codex')
        self.assertIn(f"[删除] 已移除本仓库旧入口：{retired}", result.stdout)
        self.assertIn("小计：新增 0 · 更新 0 · 删除 1 · 保留 0 · 跳过 3 · 警告 0", result.stdout)
        self.assertNotIn("[清理]", result.stdout)
        self.assert_counts(result.stdout, deleted=1, skipped=3)
        self.assertFalse(retired.is_symlink())

    def test_dependencies_are_not_discovered_or_installed_in_any_mode(self):
        for name in ('feipi-one','feipi-two'):
            dep=self.repo/'skills/integration'/name/'node_modules/foreign-package'
            dep.mkdir(parents=True);(dep/'SKILL.md').write_text('not a skill')
        for args,dest in [
            (('--agent', 'codex'),self.codex/'skills'),
            (('--copy', '--agent', 'codex'),self.codex/'skills'),
            (('--agent', 'openclaw'),self.openclaw/'skills'),
            (('--dir', str(self.project)),self.project/'.agents/skills'),
        ]:
            with self.subTest(args=args):
                self.run_installer(*args)
                self.assertFalse((dest/'feipi-one/node_modules').exists())
                local=dest/'feipi-one/node_modules';local.mkdir();(local/'old').write_text('old copy')
                self.run_installer(*args)
                self.assertFalse(local.exists())

    def test_unchanged_skills_are_not_copied_to_staging(self):
        for name in ('feipi-one','feipi-two'):
            (self.repo/'skills/integration'/name/'scripts/run.sh').write_text('no shared dependencies\n')
        for mode, options in [('copy', ('--copy',)), ('link', ())]:
            with self.subTest(mode=mode):
                self.run_installer(*options, '--agent', 'codex')
                fake=self.base/('fail-cp-'+mode);fake.mkdir()
                cp=fake/'cp';cp.write_text('#!/bin/sh\nexit 77\n');cp.chmod(0o755)
                result=self.run_installer(*options, '--agent', 'codex', env=dict(self.env,PATH=f'{fake}{os.pathsep}'+self.env['PATH']))
                self.assert_counts(result.stdout,skipped=2)

    def test_same_size_and_mtime_corruption_and_permission_drift_are_repaired(self):
        self.run_installer('--copy', '--agent', 'codex')
        dest=self.codex/'skills/feipi-one/SKILL.md';before=dest.stat()
        content=dest.read_bytes();dest.write_bytes(content.replace(b'fixture',b'changed'))
        os.utime(dest,ns=(before.st_atime_ns,before.st_mtime_ns))
        result=self.run_installer('--copy', '--agent', 'codex')
        self.assert_counts(result.stdout,updated=1,skipped=2);self.assertEqual(dest.read_bytes(),content)
        dest.chmod(0o600 if dest.stat().st_mode&0o777!=0o600 else 0o644)
        self.assert_counts(self.run_installer('--copy', '--agent', 'codex').stdout,updated=1,skipped=2)

    def test_shared_link_repair_and_conflict_are_not_new_installs(self):
        self.run_installer('--agent', 'codex')
        shared = self.codex / "shared"
        shared.unlink()
        shared.symlink_to(self.base / "missing", target_is_directory=True)
        repaired = self.run_installer('--agent', 'codex')
        self.assertIn("[更新] 共享/shared（修复失效链接）", repaired.stdout)
        self.assert_counts(repaired.stdout, updated=1, skipped=2)
        self.assertEqual(shared.resolve(), (self.repo / "shared").resolve())
        shared.unlink()
        shared.mkdir()
        conflict = self.run_installer('--agent', 'codex')
        self.assertIn("[警告] 共享/shared（目标已存在且非软链接，跳过：", conflict.stderr)
        self.assert_counts(conflict.stdout, skipped=3, warnings=1)
        self.assertFalse(shared.is_symlink())

    def test_project_and_openclaw_copy(self):
        for args, destination in (
            (('--dir', str(self.project)), self.project / ".agents"),
            (('--agent', 'openclaw'), self.openclaw),
        ):
            with self.subTest(args=args):
                first = self.run_installer(*args)
                self.assert_counts(first.stdout, added=3)
                self.assertIn("模式：实拷", first.stdout)
                self.assertFalse((destination / "skills/feipi-one/scripts").is_symlink())
                self.assert_counts(self.run_installer(*args).stdout, skipped=3)
                resource = self.repo / "shared/resource.txt"
                resource.write_text(resource.read_text() + "changed\n")
                self.assert_counts(self.run_installer(*args).stdout, updated=1, skipped=2)
                self.assertEqual((destination / "shared/resource.txt").read_bytes(), resource.read_bytes())
        self.assert_counts(self.run_installer('--copy', '--agent', 'codex').stdout, added=3)

    def test_multi_agent_totals(self):
        self.codex.mkdir()
        self.openclaw.mkdir()
        result = self.run_installer()
        self.assertEqual(result.stdout.count("小计：新增 3"), 2)
        self.assert_counts(result.stdout, added=6)
        retired = self.codex / "skills/feipi-old"
        retired.symlink_to(self.repo / "skills/integration/feipi-old", target_is_directory=True)
        repeat = self.run_installer()
        self.assertIn("小计：新增 0 · 更新 0 · 删除 1 · 保留 0 · 跳过 3 · 警告 0", repeat.stdout)
        self.assertIn("小计：新增 0 · 更新 0 · 删除 0 · 保留 0 · 跳过 3 · 警告 0", repeat.stdout)
        self.assert_counts(repeat.stdout, deleted=1, skipped=6)

    def test_no_shared_dependencies_is_a_successful_install(self):
        for name in ("feipi-one", "feipi-two"):
            (self.repo / "skills/integration" / name / "scripts/run.sh").write_text("# no shared dependencies\n")
        first = self.run_installer('--agent', 'codex')
        self.assert_counts(first.stdout, added=2)
        self.assert_counts(self.run_installer('--agent', 'codex').stdout, skipped=2)

    def test_auto_color_on_terminal_and_plain_redirected_stderr(self):
        self.codex.mkdir()
        (self.codex / "shared").mkdir()  # 警告写入单独重定向的 stderr。
        master, slave = pty.openpty()
        try:
            process = subprocess.Popen(["bash", "scripts/install_skills.sh", '--agent', 'codex'], cwd=self.repo,
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
        result = self.run_installer('--agent', 'codex', success=False,
                               env=dict(self.env, PATH=f"{fakebin}{os.pathsep}{self.env['PATH']}"))
        self.assertIn("[新增] feipi-one", result.stdout)
        self.assertIn("[失败] 安装失败：", result.stderr)
        self.assertIn("feipi-two", result.stderr)
        self.assertNotIn("总计：", result.stdout)
        self.assertNotIn("小计：", result.stdout)
        self.assertTrue((self.codex / "skills/feipi-one/SKILL.md").is_file())
        self.assertFalse((self.codex / "skills/feipi-two").exists())

    def test_validation_failure_and_invalid_options_stop_before_install(self):
        invalid = self.run_installer('--unknown', success=False)
        self.assertIn("未知参数", invalid.stderr)
        (self.repo / "skills/integration/feipi-one/SKILL.md").unlink()
        failed = self.run_installer('--agent', 'codex', success=False)
        self.assertIn("[FAIL]", failed.stderr)
        self.assertIn("[失败] 注册表验证失败", failed.stderr)
        self.assertNotIn("[删除]", failed.stdout)
        self.assertNotIn("总计：", failed.stdout)
        self.assertFalse(self.codex.exists())


if __name__ == "__main__":
    unittest.main()
