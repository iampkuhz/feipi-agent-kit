"""新机启动契约：隔离 HOME、伪 Podman 与真实 Compose 静态展开，不启停服务。"""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ServiceBootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="feipi service audit ")
        self.base = Path(self.temp.name)
        self.home = self.base / "new Mac home"
        self.home.mkdir()
        self.bin = self.base / "bin"
        self.bin.mkdir()
        self.log = self.base / "calls.jsonl"
        self.data = self.base / "service data"
        self.env = {"PATH": f"{self.bin}:/usr/bin:/bin", "HOME": str(self.home),
                    "CALL_LOG": str(self.log), "AGENT_SERVICE_DATA_DIR": str(self.data)}
        # 测试只记录命令和非敏感路径；绝不会调用真实 Podman、Docker 或网络。
        stub = f"""#!{sys.executable}
import json, os, pathlib, sys
args = sys.argv[1:]
name = pathlib.Path(sys.argv[0]).name
with open(os.environ['CALL_LOG'], 'a') as stream:
    stream.write(json.dumps({{'name': name, 'args': args, 'crawl_env': os.environ.get('CRAWL4AI_ENV_FILE')}})+'\\n')
if name == 'curl':
    raise SystemExit(22)
if name == 'podman' and args[:3] == ['system', 'connection', 'list']:
    print(json.dumps([{{'Default': True, 'URI': os.environ.get('TEST_CONNECTION', 'unix:///tmp/podman.sock')}}]))
elif name == 'podman' and args == ['info']:
    raise SystemExit(int(os.environ.get('TEST_ENGINE_FAIL', '0')))
elif args == ['--version']:
    print('test provider 1.0')
"""
        for name in ["podman", "podman-compose", "curl"]:
            p = self.bin / name
            p.write_text(stub)
            p.chmod(0o755)
        (self.bin / "python3").symlink_to(sys.executable)

    def tearDown(self):
        self.temp.cleanup()

    def run_script(self, relative, *args, env=None, root=ROOT):
        return subprocess.run(["/bin/bash", str(root / relative), *args],
                              env=env or self.env, text=True, capture_output=True, timeout=20)

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def test_setup_supports_podman_without_docker_and_is_read_only(self):
        p = self.run_script("scripts/bootstrap/setup.sh")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertFalse(self.data.exists())
        self.assertFalse((self.home / ".env").exists())
        self.assertFalse(any("machine" in row["args"] for row in self.calls()))

    def test_make_setup_preserves_engine_failure(self):
        env = dict(self.env, TEST_ENGINE_FAIL="1")
        p = subprocess.run(["/usr/bin/make", "setup"], cwd=ROOT, env=env,
                           capture_output=True, text=True, timeout=20)
        self.assertNotEqual(p.returncode, 0)
        self.assertNotIn("检查通过", p.stdout)

    def test_make_searxng_uses_podman_wrapper(self):
        p = subprocess.run(["/usr/bin/make", "searxng-up"], cwd=ROOT, env=self.env,
                           capture_output=True, text=True, timeout=20)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertTrue(any(row["args"][:1] == ["compose"] and row["args"][-2:] == ["up", "-d"]
                            for row in self.calls()))

    def test_crawl_clean_copy_uses_template_and_real_up_action(self):
        # 模拟克隆后没有本机环境文件、且仓库路径带空格的情况。
        clone = self.base / "clone with spaces"
        for rel in ["tools/crawl/crawl4ai/scripts/crawl4ai.sh",
                    "tools/crawl/crawl4ai/compose/docker-compose.yml",
                    "tools/crawl/crawl4ai/env/.env.example", "tools/lib/podman.sh"]:
            target = clone / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / rel, target)
        p = self.run_script("tools/crawl/crawl4ai/scripts/crawl4ai.sh", "up", root=clone)
        self.assertEqual(p.returncode, 0, p.stderr)
        compose = next(row for row in self.calls() if row["args"][:1] == ["compose"])
        self.assertTrue(compose["crawl_env"].endswith("env/.env.example"))
        self.assertEqual(compose["args"][-2:], ["up", "-d"])

    def test_remote_connection_does_not_start_or_create_data(self):
        env = dict(self.env, TEST_CONNECTION="ssh://user@another-machine/run/podman.sock")
        p = self.run_script("tools/gateway/otel/scripts/otel.sh", "up", env=env)
        self.assertNotEqual(p.returncode, 0)
        self.assertFalse(self.data.exists())
        self.assertFalse(any(row["args"][:1] == ["compose"] for row in self.calls()))

    def test_otel_status_does_not_create_data(self):
        p = self.run_script("tools/gateway/otel/scripts/otel.sh", "status")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertFalse(self.data.exists())

    def test_otel_up_creates_only_selected_data_directory(self):
        p = self.run_script("tools/gateway/otel/scripts/otel.sh", "up")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual([p.name for p in self.data.iterdir()], ["otel"])

    def test_otel_restart_applies_changed_configuration(self):
        p = self.run_script("tools/gateway/otel/scripts/otel.sh", "restart")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertTrue(any("--force-recreate" in row["args"] for row in self.calls()))

    def test_relative_data_root_is_rejected_before_creating_files(self):
        env = dict(self.env, AGENT_SERVICE_DATA_DIR="relative-data")
        p = self.run_script("tools/gateway/otel/scripts/otel.sh", "up", env=env)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("绝对路径", p.stderr)
        self.assertFalse(self.data.exists())

    def test_litellm_up_uses_current_home_and_custom_data_root(self):
        p = self.run_script("tools/gateway/litellm/scripts/litellm.sh", "up")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertTrue((self.data / "postgres").is_dir())
        self.assertTrue((self.data / "litellm/chatgpt-tokens").is_dir())
        self.assertNotIn("/Users/zhehan", p.stdout)

    def test_litellm_status_is_read_only(self):
        p = self.run_script("tools/gateway/litellm/scripts/litellm.sh", "status")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertFalse(self.data.exists())
        self.assertTrue(any(row["args"][-1:] == ["ps"] for row in self.calls()))

    def test_litellm_stop_logs_and_status_reject_remote_connection(self):
        env = dict(self.env, TEST_CONNECTION="ssh://user@another-machine/run/podman.sock")
        for command in ["down", "logs", "status"]:
            with self.subTest(command=command):
                p = self.run_script("tools/gateway/litellm/scripts/litellm.sh", command, env=env)
                self.assertNotEqual(p.returncode, 0)
                self.assertFalse(self.data.exists())
                self.assertFalse(any(row["args"][:1] == ["compose"] for row in self.calls()))

    def test_doctor_reaches_summary_and_reports_http_error(self):
        p = self.run_script("scripts/doctor/check.sh")
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("检查结果", p.stdout)
        self.assertIn("LiteLLM", p.stdout)
        calls = [row for row in self.calls() if row["name"] == "curl"]
        self.assertEqual(len(calls), 2)
        self.assertTrue(any("/health/readiness" in " ".join(row["args"]) for row in calls))


class ComposePortabilityTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("podman-compose"), "静态展开校验需要 podman-compose")
    def test_podman_provider_accepts_all_four_definitions_on_new_home(self):
        with tempfile.TemporaryDirectory(prefix="feipi podman config ") as folder:
            env = {"PATH": os.environ["PATH"], "HOME": folder}
            for rel in ["tools/search/searxng/compose/docker-compose.yml",
                        "tools/crawl/crawl4ai/compose/docker-compose.yml",
                        "tools/gateway/litellm/compose/docker-compose.yml",
                        "tools/gateway/otel/compose/docker-compose.yml"]:
                with self.subTest(file=rel):
                    p = subprocess.run(["podman-compose", "--env-file", "/dev/null", "-f", str(ROOT/rel),
                                        "config", "-q"], env=env, capture_output=True, text=True, timeout=20)
                    self.assertEqual(p.returncode, 0, p.stderr)

    @unittest.skipUnless(shutil.which("docker-compose"), "独立 JSON 展开校验需要 docker-compose 客户端")
    def test_compose_paths_and_clean_crawl_template(self):
        # Compose config 不创建容器；独立实现校验嵌套变量与带空格的主机路径。
        with tempfile.TemporaryDirectory(prefix="feipi compose ") as folder:
            home = Path(folder) / "new Mac home"
            home.mkdir()
            env = {"PATH": os.environ["PATH"], "HOME": str(home)}
            files = ["tools/gateway/litellm/compose/docker-compose.yml",
                     "tools/gateway/otel/compose/docker-compose.yml",
                     "tools/crawl/crawl4ai/compose/docker-compose.yml"]
            for override in [None, str(Path(folder) / "custom data")]:
                with self.subTest(override=override):
                    current = dict(env)
                    if override:
                        current["AGENT_SERVICE_DATA_DIR"] = override
                    expected = Path(override) if override else home / "Documents/service-data"
                    for rel in files:
                        p = subprocess.run(["docker-compose", "--env-file", "/dev/null", "-f", str(ROOT/rel),
                                            "config", "--format", "json"], env=current,
                                           capture_output=True, text=True, timeout=20)
                        self.assertEqual(p.returncode, 0, p.stderr)
                        services = json.loads(p.stdout)["services"]
                        if "postgres" in services:
                            self.assertEqual(services["postgres"]["volumes"][0]["source"], str(expected/"postgres"))
                            self.assertEqual(services["litellm"]["volumes"][1]["source"], str(expected/"litellm/chatgpt-tokens"))
                        if "otel-collector" in services:
                            self.assertEqual(services["otel-collector"]["volumes"][1]["source"], str(expected/"otel"))
                        if "crawl4ai" in services:
                            self.assertNotIn("HTTP_PROXY", services["crawl4ai"]["environment"])
                            self.assertEqual(services["crawl4ai"]["shm_size"], "1073741824")


if __name__ == "__main__":
    unittest.main()
