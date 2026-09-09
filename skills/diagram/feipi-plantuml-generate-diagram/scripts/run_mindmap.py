#!/usr/bin/env python3
"""Mindmap 单图首次生成入口：固定编排，stdout 只输出一份结果 JSON。"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys

from generate_mindmap import generate
from lib.brief_loader import validate_brief_file
from lib.mindmap import validate_mindmap
from lib.profile_registry import get_profile

SCRIPTS = Path(__file__).resolve().parent
ARTIFACTS = {
    "brief": "brief.normalized.yaml",
    "diagram": "diagram.puml",
    "svg": "diagram.svg",
    "preview": "diagram.png",
    "validation": "validation.json",
    "preflight": "renderer-preflight.json",
    "log": "run.log",
}


class RunError(Exception):
    def __init__(self, stage: str, reason: str, issues: list[str]):
        super().__init__(issues[0])
        self.stage, self.reason, self.issues = stage, reason, issues[:3]


def missing_dependencies() -> list[str]:
    # Bash 与 curl 沿用既有渲染链，rsvg-convert 是本入口唯一的 PNG 预览实现。
    missing = [name for name in ("bash", "python3", "curl", "rsvg-convert") if not shutil.which(name)]
    if importlib.util.find_spec("yaml") is None and not shutil.which("ruby"):
        missing.append("PyYAML 或 Ruby（读取 YAML）")
    return missing


def invoke(command: list[str], stage: str, log: Path, *, timeout: int | None = None) -> int:
    with log.open("a", encoding="utf-8") as stream:
        stream.write(f"\n[{stage}]\n")
        stream.flush()
        return subprocess.run(command, stdout=stream, stderr=stream, timeout=timeout, check=False).returncode


def read_receipt(path: Path, stage: str) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except (OSError, ValueError):
        pass
    raise RunError(stage, "invalid_receipt", [f"缺少有效回执：{path.name}"])


def make_preview(svg: Path, png: Path, log: Path) -> None:
    # 仅将本次已验证 SVG 转成白底 PNG，不调用 renderer，不声称完成视觉审阅。
    temporary = png.with_suffix(".pending.png")
    try:
        code = invoke([
            "rsvg-convert", "--format", "png", "--background-color", "white",
            "--width", "1600", "--height", "1600", "--keep-aspect-ratio",
            "--output", str(temporary), str(svg),
        ], "preview", log, timeout=30)
        header = b""
        if temporary.is_file():
            with temporary.open("rb") as stream:
                header = stream.read(24)
        valid = len(header) == 24 and header[:8] == b"\x89PNG\r\n\x1a\n" and header[12:16] == b"IHDR"
        if code or not valid or not all(0 < size <= 1600 for size in struct.unpack(">II", header[16:24])):
            raise RunError("preview", "preview_failed", ["rsvg-convert 未生成有效 PNG；保留已验证 SVG，详情见 run.log"])
        temporary.replace(png)
    finally:
        temporary.unlink(missing_ok=True)


def run(brief: Path, out: Path, server_url: str = "auto") -> dict:
    brief, out = brief.expanduser().resolve(), out.expanduser().resolve()
    paths = {key: out / filename for key, filename in ARTIFACTS.items()}
    stage = "prepare"
    result = {"status": "blocked", "stage": stage, "reason": "", "issues": [], "visual_review": "not_ready", "paths": {}}
    may_write_result = False
    try:
        # 不覆盖上一个批次或用户已编辑源码，不以换路径重置修复计数。
        occupied = [paths[key].name for key in ("validation", "preflight", "diagram", "svg", "preview") if paths[key].exists()]
        if occupied:
            raise RunError(stage, "existing_package", ["输出目录已有图包/预检产物；修复或复用请使用 validate_package.sh，统一入口仅负责首次生成"])
        reserved = [p for key, p in paths.items() if key != "brief"] + [out / "run-result.json", out / "diagram.pending.png"]
        if brief in reserved or any(p.exists() and brief.is_file() and brief.samefile(p) for p in reserved):
            raise RunError(stage, "input_output_collision", ["brief 路径与输出产物冲突，请使用独立的 brief.yaml"])
        if not brief.is_file():
            raise RunError("brief", "brief_missing", [f"brief 文件不存在：{brief}"])
        missing = missing_dependencies()
        if missing:
            raise RunError("dependencies", "missing_dependencies", ["缺少依赖：" + "、".join(missing)])
        out.mkdir(parents=True, exist_ok=True)
        may_write_result = True
        paths["log"].write_text("", encoding="utf-8")
        if not paths["brief"].exists() or not brief.samefile(paths["brief"]):
            shutil.copyfile(brief, paths["brief"])

        stage = "brief"
        ok, errors, _, data = validate_brief_file(str(paths["brief"]), get_profile("mindmap")["brief_schema"])
        if ok:
            errors.extend(validate_mindmap(data))
        if errors:
            raise RunError(stage, "brief_validation_failed", errors)

        stage = "preflight"
        code = invoke([
            "bash", str(SCRIPTS / "preflight_renderer.sh"), "--out", str(paths["preflight"]),
            "--server-url", server_url,
        ], stage, paths["log"])
        receipt = read_receipt(paths["preflight"], stage)
        if code or receipt.get("final_status") != "success" or not receipt.get("renderer_url"):
            raise RunError(stage, str(receipt.get("blocked_reason") or "preflight_failed"), [str(receipt.get("issue") or "本地 renderer 不可用")])

        stage = "generate"
        paths["diagram"].write_text(generate(data), encoding="utf-8")
        stage = "validate"
        code = invoke([
            "bash", str(SCRIPTS / "validate_package.sh"), "--diagram-type", "mindmap",
            "--brief", str(paths["brief"]), "--diagram", str(paths["diagram"]),
            "--out-dir", str(out), "--server-url", receipt["renderer_url"],
        ], stage, paths["log"])
        validation = read_receipt(paths["validation"], stage)
        if code or validation.get("final_status") != "success" or validation.get("render_result") != "ok":
            raise RunError(stage, str(validation.get("blocked_reason") or "package_failed"), ["图包校验未通过，按 validation.json 定点处理；本入口不自动重试"])

        stage = "preview"
        make_preview(paths["svg"], paths["preview"], paths["log"])
        result.update(status="success", stage="complete", visual_review="pending")
    except RunError as exc:
        result.update(stage=exc.stage, reason=exc.reason, issues=exc.issues)
    except subprocess.TimeoutExpired:
        result.update(stage=stage, reason="preview_timeout", issues=["预览转换超过 30 秒；保留 SVG，未重试"])
    except (OSError, ValueError) as exc:
        result.update(stage=stage, reason="execution_failed", issues=[f"执行失败：{exc}"])
    result["paths"] = {key: str(path) for key, path in paths.items() if path.is_file()}
    if may_write_result:
        (out / "run-result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="一次完成 mindmap 首次生成、图包验证与 PNG 预览")
    parser.add_argument("--brief", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--server-url", default="auto", help="沿用预检的 loopback 地址覆盖；默认读取既有端口配置")
    args = parser.parse_args()
    result = run(Path(args.brief), Path(args.out_dir), args.server_url)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
