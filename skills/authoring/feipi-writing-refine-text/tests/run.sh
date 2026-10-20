#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

[[ -f "$SKILL_DIR/SKILL.md" ]]
[[ -f "$SKILL_DIR/agents/openai.yaml" ]]
[[ -x "$SCRIPT_DIR/run.sh" ]]

! rg -Fq '{{' "$SKILL_DIR/SKILL.md" "$SKILL_DIR/agents/openai.yaml" "$SCRIPT_DIR/run.sh"
! rg -n 'make[[:space:]]+(new|test|validate)|^##[[:space:]]*维护与回归' "$SKILL_DIR/SKILL.md"
! rg -n '(^|[^A-Za-z])(tests|evals)/|scripts/test\.sh' "$SKILL_DIR/SKILL.md"

bash -n "$SCRIPT_DIR/run.sh"

# 只检查包与行为用例的完整性；文本改写质量另做原文对照评估。
python3 - "$SKILL_DIR" <<'PY'
import json
import hashlib
from pathlib import Path
import re
import sys

root = Path(sys.argv[1]).resolve()
runtime_files = [root / "SKILL.md", *sorted((root / "references").rglob("*.md"))]
entry_targets = set()
for path in runtime_files:
    text = path.read_text(encoding="utf-8")
    for target in re.findall(r"\]\(([^\s)]+)\)", text):
        if "://" in target or target.startswith("#"):
            continue
        resolved = (path.parent / target.split("#", 1)[0]).resolve()
        assert resolved.is_relative_to(root), f"资源链接越界：{target}"
        assert resolved.is_file(), f"缺少资源：{target}"
        if path == root / "SKILL.md":
            entry_targets.add(resolved)
        elif resolved.parent == root / "references/scenes":
            raise AssertionError(f"参考文件不得跨载场景，应由入口选择：{path.name} -> {target}")
    assert not re.search(r"(^|[\s'\"`(])(tests|evals)/", text), f"运行内容依赖开发目录：{path.name}"
for resource in runtime_files[1:]:
    assert resource in entry_targets, f"资源没有入口直达链接：{resource.relative_to(root)}"

data = json.loads((root / "evals/cases.json").read_text(encoding="utf-8"))
assert data["schema_version"] == 1 and data["skill"] == root.name
cases = data["cases"]
assert isinstance(cases, list) and cases, "行为用例不能为空"
ids = set()
document_count = 0
criterion_ids = set()
eval_root = root / "evals"

def eval_file(relative):
    assert isinstance(relative, str) and relative, "样例路径不能为空"
    resolved = (eval_root / relative).resolve()
    assert resolved.is_relative_to(eval_root), f"样例路径越界：{relative}"
    assert resolved.is_file(), f"样例文件缺失：{relative}"
    return resolved

for case in cases:
    case_id = case["id"]
    assert isinstance(case_id, str) and case_id and case_id not in ids
    ids.add(case_id)
    assert isinstance(case["prompt"], str) and case["prompt"].strip()
    for field in ("expected", "forbidden"):
        assert isinstance(case[field], list) and case[field]
        assert all(isinstance(item, str) and item.strip() for item in case[field])
    file_fields = ("input_file", "reference_file", "expectations_file", "provenance_file")
    if not any(field in case for field in file_fields):
        continue
    paths = {field: eval_file(case[field]) for field in file_fields}
    assert len(set(paths.values())) == len(file_fields), f"输入与评估资料必须分离：{case_id}"
    raw = paths["input_file"].read_bytes()
    original = raw.decode("utf-8")
    assert original.strip() and paths["reference_file"].read_text(encoding="utf-8").strip()
    provenance = json.loads(paths["provenance_file"].read_text(encoding="utf-8"))
    assert provenance["schema_version"] == 1 and provenance["source_kind"] == "local_document"
    for field in ("source_project", "source_path", "document_date", "captured_at"):
        assert isinstance(provenance[field], str) and provenance[field].strip()
    assert re.fullmatch(r"[0-9a-f]{64}", provenance["source_sha256"])
    assert hashlib.sha256(raw).hexdigest() == provenance["input_sha256"], f"原文快照哈希不符：{case_id}"
    assert isinstance(provenance["source_tracked"], bool)
    if provenance["source_tracked"]:
        assert re.fullmatch(r"[0-9a-f]{40,64}", provenance["source_commit"] or "")
    else:
        assert provenance["source_commit"] is None, f"未跟踪文件不得填造提交：{case_id}"
    for field in ("input_file", "reference_file"):
        assert (paths["provenance_file"].parent / provenance[field]).resolve() == paths[field]
    selection = provenance["selection"]
    assert selection["method"] == "verbatim_lines"
    assert 1 <= selection["start_line"] <= selection["end_line"]
    assert selection["end_line"] - selection["start_line"] + 1 == len(original.splitlines())
    status = provenance["reference_status"]
    assert status in ("proposed", "user_confirmed")
    if status == "user_confirmed":
        evidence = provenance["confirmation_evidence"]
        assert isinstance(evidence, str) and evidence.strip(), f"用户确认缺少依据：{case_id}"
    else:
        assert provenance["confirmation_evidence"] is None
    checks = json.loads(paths["expectations_file"].read_text(encoding="utf-8"))
    assert checks["schema_version"] == 1 and checks["case_id"] == case_id
    assert checks["status"] == status
    for field in ("must_include", "must_exclude"):
        assert isinstance(checks[field], list) and checks[field]
        for check in checks[field]:
            assert check.get("scope", "body") in ("body", "issue_list"), f"未知评估范围：{check['id']}"
            assert check["id"] and check["id"] not in criterion_ids
            criterion_ids.add(check["id"])
            assert check["criterion"].strip() and check["reason"].strip()
            assert isinstance(check["source_quotes"], list) and check["source_quotes"]
            for quote in check["source_quotes"]:
                assert quote and quote in original, f"验收项原文锚点缺失：{check['id']}"
    document_count += 1
print(f"包结构与 {len(cases)} 条用例完整性通过，含 {document_count} 组真实文档、{len(criterion_ids)} 项来源锚点；不代表改写质量或用户验收通过。")
PY
