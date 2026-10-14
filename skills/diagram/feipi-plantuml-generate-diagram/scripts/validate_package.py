#!/usr/bin/env python3
"""图包验证编排：同进程计时，冻结观测后复核最终文件。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import time

from lib.brief_loader import load_yaml
from lib.profile_registry import resolve_profile
from lib.runtime_observation import RunClock, atomic_json, receipt_fields
from lib.svg_validation import is_success_svg
from lib.rendered_layout import inspect_rendered_layout

SCRIPTS = Path(__file__).resolve().parent
LIB = SCRIPTS / "lib"
RENDER_CONTRACT = "5"
MAX_ATTEMPTS = 2


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def parent_brief(brief):
    if not brief:
        return None
    try:
        data = load_yaml(brief)
        ref = data.get("parent_component_ref", {}) if isinstance(data, dict) else {}
        value = ref.get("overview_brief_path") if isinstance(ref, dict) else None
        rel = PurePosixPath(value) if isinstance(value, str) and value and "\\" not in value else None
        if rel and not rel.is_absolute() and not any(p in {"", ".", ".."} for p in rel.parts):
            candidate = (brief.resolve().parent / Path(*rel.parts)).resolve()
            candidate.relative_to(brief.resolve().parent)
            if candidate.is_file():
                return rel, candidate
    except Exception:
        # 父引用提取失败由后续 brief 校验报告，不能抢先绕过失败图包合同。
        pass
    return None


def copy_snapshot(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists() or not source.samefile(destination):
        shutil.copyfile(source, destination)


class PackageRun:
    def __init__(self, args, clock):
        self.args, self.clock = args, clock
        self.config = resolve_profile(args.diagram_type)
        self.profile = self.config["profile"]
        self.typed = self.profile != "fallback"
        self.out = Path(args.out_dir)
        self.diagram = self.out / "diagram.puml"
        self.svg = self.out / "diagram.svg"
        self.validation = self.out / "validation.json"
        self.brief = self.out / "brief.normalized.yaml" if self.typed else None
        self.checks = dict(brief_check="skipped", coverage_check="skipped", layout_check="skipped")
        self.counters = dict(render_http_requests=0, render_rounds=0, package_validation_runs=1,
                             package_verifier_runs=0, cache_hits=0)
        self.previous_attempts = 0
        self.brief_reused = False
        self.render_result, self.render_server = "skipped", ""
        self.env = dict(os.environ, PLANTUML_PYTHON=sys.executable)

    def invoke(self, command):
        return subprocess.run(list(map(str, command)), stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True, env=self.env)

    def verifier(self):
        self.counters["package_verifier_runs"] += 1
        result = self.invoke([sys.executable, SCRIPTS / "verify_package.py", self.out])
        if result.returncode:
            print(result.stdout, file=sys.stderr, end="")
        return result

    def write(self, status, reason="", issue="", include_brief=True):
        # 截止点在报告物化前。写入和最终 verifier 不纳入被冻结的计时，避免自引用。
        timings = self.clock.timings()
        options = {
            "output": self.validation, "render-contract-version": RENDER_CONTRACT,
            "diagram-type": self.args.diagram_type, "profile": self.profile,
            "diagram-path": self.diagram, "svg-path": self.svg,
            "brief-path": self.brief if include_brief and self.brief else "",
            **{key.replace("_", "-"): value for key, value in self.checks.items()},
            "render-result": self.render_result, "render-server": self.render_server,
            "final-status": status, "blocked-reason": reason, "issue-text": issue or reason,
            "attempt-index": self.previous_attempts + self.counters["render_rounds"],
            "max-render-attempts": MAX_ATTEMPTS,
            "brief-validation-reused": str(self.brief_reused).lower(), "package-dir": self.out,
            "total-duration-ms": timings["total_ms"], "render-duration-ms": timings["render_ms"],
            "static-validation-duration-ms": timings["static_validation_ms"],
            **{key.replace("_", "-"): value for key, value in self.counters.items()},
        }
        command = [sys.executable, LIB / "write_validation.py"]
        for key, value in options.items():
            command.extend(["--" + key, str(value)])
        result = self.invoke(command)
        if result.returncode:
            raise RuntimeError(result.stdout)

    def blocked(self, reason, issue="", include_brief=True):
        self.write("blocked", reason, issue, include_brief)
        print("[FAIL] " + reason, file=sys.stderr)
        if issue:
            print(issue, file=sys.stderr)
        return 1

    def cache_identity_matches(self, data):
        expected = {
            "final_status": "success", "render_result": "ok", "diagram_type": self.args.diagram_type,
            "profile": self.profile, "profile_version": str(self.config["profile_version"]),
            "render_contract_version": RENDER_CONTRACT, "puml_sha256": sha256(self.args.diagram),
        }
        if any(data.get(key) != value for key, value in expected.items()):
            return False
        if self.typed:
            if data.get("brief_sha256") != sha256(self.args.brief):
                return False
            parent = parent_brief(Path(self.args.brief))
            if parent and data.get("parent_brief_sha256") != sha256(parent[1]):
                return False
        elif data.get("brief_sha256"):
            return False
        return True

    def try_cache(self):
        data = read_json(self.validation)
        if not self.args.reuse_valid_package or not self.svg.is_file() or not self.cache_identity_matches(data):
            return None
        # 原报告先按原样校验，禁止修正旧 timing/hash 使缓存伪成功。
        if self.verifier().returncode:
            return None
        self.counters["cache_hits"] = 1
        self.counters["package_verifier_runs"] += 1
        data["last_run_timings"] = {**self.clock.timings(), "cache_hit": True}
        data["last_run_counters"] = dict(self.counters)
        atomic_json(self.validation, data)
        return self.final_verify(cache_hit=True, count_reserved=True)

    def final_verify(self, cache_hit=False, count_reserved=False):
        if count_reserved:
            self.counters["package_verifier_runs"] -= 1
        result = self.verifier()
        if result.returncode:
            # 保留冻结的计时和全部具体错误；失败文件不再宣称 success。
            data = read_json(self.validation)
            data.update(final_status="blocked", blocked_reason="package_verification_failed",
                        failure_class="contract", repairable=False)
            data["issues"] = result.stdout.splitlines() or ["verifier 未返回诊断"]
            atomic_json(self.validation, data)
            print("[FAIL] package_verification_failed", file=sys.stderr)
            return 1
        # 从这里到 success 输出不再修改任何包文件。
        if read_json(self.validation).get("final_status") != "success":
            print("[FAIL] 最终报告未达到 success", file=sys.stderr)
            return 1
        if cache_hit:
            print("cache_hit=true")
        print("final_status=success")
        return 0

    def retry_guard(self):
        data = read_json(self.validation)
        brief_hash = sha256(self.args.brief) if self.args.brief else ""
        if (data.get("final_status") == "blocked" and data.get("profile") == self.profile
                and data.get("brief_sha256") == brief_hash):
            # 升级 profile/渲染合同也不能重置同一失败包的修复次数。
            if data.get("repairable") is not True:
                raise ValueError("上次失败不可自动修复；请处理 blocker，保留失败批次")
            if data.get("puml_sha256") == sha256(self.args.diagram):
                raise ValueError("失败图未发生变化，禁止重复校验和渲染")
            attempt = data.get("attempt_index", 0)
            if type(attempt) is not int or attempt < 0:
                raise ValueError("上次渲染次数无效，禁止重置计数")
            if attempt >= MAX_ATTEMPTS:
                raise ValueError("已达到每图最多 2 次 renderer 调用，禁止继续")
            self.previous_attempts = attempt

    def run(self):
        cached = self.try_cache()
        if cached is not None:
            return cached
        self.retry_guard()
        for path in (self.svg, self.validation):
            if path.exists():
                path.unlink()
        copy_snapshot(Path(self.args.diagram), self.diagram)
        snapshots = [self.diagram]
        if self.typed:
            copy_snapshot(Path(self.args.brief), self.brief)
            snapshots.append(self.brief)
            parent = parent_brief(Path(self.args.brief))
            if parent:
                destination = self.out / Path(*parent[0].parts)
                copy_snapshot(parent[1], destination)
                snapshots.append(destination)
        hashes = {path: sha256(path) for path in snapshots}

        def unchanged():
            return all(path.is_file() and sha256(path) == digest for path, digest in hashes.items())

        markers = ("startmindmap", "endmindmap") if self.args.diagram_type == "mindmap" else ("startuml", "enduml")
        text = self.diagram.read_text(encoding="utf-8")
        for marker in markers:
            if not re.search(r"^[ \t]*@" + marker + r"[ \t]*$", text, re.MULTILINE):
                return self.blocked("missing_" + marker, "diagram 缺少 @" + marker, include_brief=False)
        if self.typed:
            schema = Path(self.config["brief_schema"])
            if not schema.is_file():
                self.checks["brief_check"] = "failed"
                return self.blocked("profile_registry_incomplete", "已注册 profile 缺少 schema：" + str(schema))
            digest = hashlib.sha256()
            for path in [schema, *[LIB / name for name in (
                "profile_registry.py", "brief_loader.py", "validate_brief_cli.py", "profile_validators.py",
                "mindmap.py", "text_codec.py",
            )]]:
                digest.update(path.name.encode("utf-8") + b"\0" + path.read_bytes() + b"\n")
            lock = self.out / ".brief-lock.json"
            expected = dict(brief_sha256=hashes[self.brief], profile=self.profile,
                            profile_version=str(self.config["profile_version"]),
                            brief_ruleset_sha256=digest.hexdigest(), brief_check="ok")
            old_lock = read_json(lock)
            if all(old_lock.get(key) == value for key, value in expected.items()):
                self.brief_reused = True
            else:
                result = self.invoke([sys.executable, LIB / "validate_brief_cli.py", self.brief,
                                      "--schema", schema, "--type", self.profile])
                if result.returncode:
                    self.checks["brief_check"] = "failed"
                    return self.blocked("brief_validation_failed", result.stdout)
                atomic_json(lock, expected)
            self.checks["brief_check"] = "ok"
            for name, command in (
                ("coverage", [sys.executable, SCRIPTS / "check_coverage.py", "--type", self.config["coverage_mode"],
                              "--brief", self.brief, "--diagram", self.diagram]),
                ("layout", ["bash", SCRIPTS / "lint_layout.sh", "--type", self.config["layout_mode"], self.diagram, self.brief]),
            ):
                result = self.invoke(command)
                self.checks[name + "_check"] = "failed" if result.returncode else "ok"
                if result.returncode:
                    return self.blocked(name + "_validation_failed", result.stdout)
        if not unchanged():
            return self.blocked("package_snapshot_changed", "校验期间 package 副本发生变化")
        renderer = SCRIPTS / "check_render.sh"
        if not renderer.is_file():
            return self.blocked("renderer_missing")
        if self.previous_attempts + 1 > MAX_ATTEMPTS:
            return self.blocked("attempt_limit_exceeded")
        self.counters["render_rounds"] += 1
        start_ns = time.monotonic_ns()
        rendered = self.invoke(["bash", renderer, self.diagram, "--svg-output", self.svg,
                                "--server-url", self.args.server_url])
        self.clock.render_ns += time.monotonic_ns() - start_ns
        fields = receipt_fields(rendered.stdout)
        self.counters["render_http_requests"] = int(fields.get("render_http_requests", "0"))
        if rendered.returncode:
            self.render_result, reason = {
                2: ("syntax_error", "render_syntax_error"),
                4: ("skipped", "render_server_unavailable"),
                5: ("skipped", "render_access_denied"),
            }.get(rendered.returncode, ("failed", "render_failed"))
            return self.blocked(reason, rendered.stdout)
        self.render_result = fields.get("render_result", "failed")
        self.render_server = fields.get("render_server", "")
        if self.render_result != "ok":
            return self.blocked("render_failed", rendered.stdout)
        if not self.render_server or not self.svg.is_file() or not is_success_svg(self.svg):
            self.render_result = "failed"
            return self.blocked("render_evidence_missing", rendered.stdout)
        if not unchanged():
            return self.blocked("package_snapshot_changed", "渲染期间 package 副本发生变化")
        layout = inspect_rendered_layout(self.svg)
        if layout["status"] != "ok":
            reason = "rendered_layout_failed" if layout["status"] == "failed" else "rendered_layout_review_required"
            return self.blocked(reason, "\n".join(layout["issues"]))
        self.counters["package_verifier_runs"] += 1
        self.write("success")
        return self.final_verify(count_reserved=True)


def main():
    clock = RunClock()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--diagram-type", default="fallback")
    parser.add_argument("--brief", default="")
    parser.add_argument("--diagram", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--server-url", default="auto")
    parser.add_argument("--reuse-valid-package", action="store_true")
    args = parser.parse_args()
    try:
        if not Path(args.diagram).is_file():
            raise ValueError("diagram 文件不存在：" + args.diagram)
        if resolve_profile(args.diagram_type)["profile"] != "fallback" and not Path(args.brief).is_file():
            raise ValueError("typed profile 缺少有效 --brief")
        Path(args.out_dir).mkdir(parents=True, exist_ok=True)
        return PackageRun(args, clock).run()
    except (OSError, ValueError, RuntimeError) as exc:
        print("[FAIL] " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
