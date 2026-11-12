#!/usr/bin/env python3
"""在调用者给出的空目录内准备独立治理任务，不包含评分答案。"""

import argparse
import hashlib
import json
from pathlib import Path
import shutil


def prepare(root, case="report-loss-forward-test"):
    if case not in {"report-loss-forward-test", "analyze-only", "stale-handoff"}:
        raise ValueError("未知评估案例")
    root.mkdir(parents=True, exist_ok=True)
    if any(root.iterdir()):
        raise ValueError("评估工作区必须为空，避免覆盖已有资料")
    source = Path(__file__).resolve().parent / "fixtures/report-loss"
    skill = root / "skills/integration/feipi-issues-build-report"
    skill.mkdir(parents=True)
    for directory in ("scripts", "agents", "maintenance", "references", "tests"):
        (skill / directory).mkdir()
    mapping = {
        "skill.md": "SKILL.md", "openai.yaml": "agents/openai.yaml",
        "report.py": "scripts/report.py", "smoke.py": "tests/smoke.py",
        "policy.md": "references/report-policy.md",
    }
    for original, relative in mapping.items():
        shutil.copyfile(source / original, skill / relative)
    (skill / "maintenance/README.md").write_text(
        "# 维护入口\n先读 terminology.md。运行规约在 ../references/report-policy.md；"
        "实现为 ../scripts/report.py，消费者是本地报告和通知文件。测试在 ../tests/。\n", encoding="utf-8")
    (skill / "maintenance/terminology.md").write_text(
        "# 术语\n问题是一条独立发现，同一 Skill 可有多条问题；通知是本地给用户的文本，没有外部发送。\n", encoding="utf-8")
    entry = skill / "tests/run.sh"
    entry.write_text('#!/usr/bin/env bash\nset -euo pipefail\nSCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"\npython3 "$SCRIPT_DIR/smoke.py"\n', encoding="utf-8")
    entry.chmod(0o755)
    for name in ("request.txt", "input.json"):
        shutil.copyfile(source / name, root / name)
    if case == "analyze-only":
        (root / "request.txt").write_text(
            "先分析 skills/integration/feipi-issues-build-report 当前有哪些问题、依据是什么、建议怎么改和预期效果。"
            "本轮仅分析，不要修改、创建或删除任何文件，也不要执行外部操作。input.json 是原始材料。", encoding="utf-8")
    elif case == "stale-handoff":
        prepare_resume(root)
    return skill


def prepare_resume(root):
    def digest(name):
        return hashlib.sha256((root / name).read_bytes()).hexdigest()

    (root / "prior-report.md").write_text(
        "# 上轮报告\n仅记录了原始清单的三个目标项，仍需继续修复并核对最终交付。\n", encoding="utf-8")
    record = {
        "schema_version": 1, "target_skill": "feipi-issues-build-report",
        "request_sha256": digest("request.txt"),
        "inputs": [{"id": "source", "path": "input.json", "sha256": digest("input.json")}],
        "problems": [{
            "id": "P1", "source_ids": ["request", "source"],
            "observation": "上轮报告丢失具体问题内容，影响后续处理。",
            "expected": "报告和通知保留来源问题、影响和状态。",
            "failure_case": "同一 Skill 多条问题均需保留。", "owner": "脚本处理",
            "status": "open", "outcome": "仅完成初步分析，尚未修改源码。", "check_ids": [],
        }],
        "checks": [], "artifacts": [{"path": "prior-report.md", "sha256": digest("prior-report.md")}],
        "report": None, "notification": None,
    }
    (root / "governance-record.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    issues = json.loads((root / "input.json").read_text(encoding="utf-8"))
    issues[0]["impact"] = "第二页的五条笔记未进入归档"
    issues.append({
        "skill": "feipi-notes-collect-pages", "problem": "归档的时间字段时区错误，凌晨记录被归到前一天",
        "impact": "当日两条记录落到错误日期", "status": "open", "reason": "需要修复时区转换后复验",
    })
    (root / "input.json").write_text(json.dumps(issues, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (root / "request.txt").write_text(
        "请基于 governance-record.json 接着完成 skills/integration/feipi-issues-build-report 的治理。"
        "input.json 是业务方现在提供的最新清单。请完成修复、验证和用户报告，并把答复保存为 reply.txt。"
        "只在本工作区内修改，不外发、不操作 Git。", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--case", choices=["report-loss-forward-test", "analyze-only", "stale-handoff"], default="report-loss-forward-test")
    args = parser.parse_args()
    try:
        skill = prepare(args.workspace, args.case)
    except (ValueError, OSError) as error:
        parser.exit(1, f"准备失败：{error}\n")
    print(f"评估目标：{skill}")


if __name__ == "__main__":
    main()
