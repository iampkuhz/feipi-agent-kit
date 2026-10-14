#!/usr/bin/env python3
"""真实组件图包：拦截穿字、同包修复一次、复用与最终文件复核。"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FIXTURES = ROOT / "fixtures/rendered-layout"
SCRIPTS = ROOT.parent / "scripts"


def main():
    with tempfile.TemporaryDirectory(prefix="plantuml-component-occlusion-") as directory:
        base = Path(directory)
        source = base / "source.puml"
        source.write_bytes((FIXTURES / "component-complex-ortho.puml").read_bytes())
        package = base / "package"
        command = [sys.executable, str(SCRIPTS / "validate_package.py"), "--diagram-type", "component",
                   "--brief", str(FIXTURES / "component-complex-brief.yaml"), "--diagram", str(source),
                   "--out-dir", str(package), "--server-url", sys.argv[1]]
        def run(expected):
            result = subprocess.run(command, capture_output=True, text=True)
            assert result.returncode == expected, result.stdout+result.stderr
            return json.loads((package / "validation.json").read_text())
        data = run(1)
        assert data["blocked_reason"] == "rendered_layout_failed", data
        assert data["render_result"] == "ok" and data["failure_class"] == "layout" and data["repairable"]
        assert data["attempt_index"] == 1 and any("E2" in issue for issue in data["issues"])
        source.write_bytes((FIXTURES / "component-complex-fixed.puml").read_bytes())
        data = run(0)
        assert data["final_status"] == "success" and data["rendered_layout"]["status"] == "ok"
        assert data["attempt_index"] == 2 and data["attempts_remaining"] == 0
        command.append("--reuse-valid-package")
        cached = run(0)
        assert cached["last_run_counters"]["cache_hits"] == 1
        assert cached["last_run_counters"]["render_http_requests"] == 0
        assert cached["last_run_counters"]["package_verifier_runs"] == 2
        print("组件复杂图：穿字拦截、一次修复、零渲染缓存复核通过")


if __name__ == "__main__":
    main()
