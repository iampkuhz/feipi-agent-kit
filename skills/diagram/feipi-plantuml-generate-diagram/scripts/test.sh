#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$SKILL_DIR/../../.." && pwd)"
TEST_DIR="$SCRIPT_DIR/tests"

PASS=0
FAIL=0

pass() {
  echo "[PASS] $1"
  PASS=$((PASS + 1))
}

fail() {
  echo "[FAIL] $1" >&2
  FAIL=$((FAIL + 1))
}

check_json_field() {
  local json_file="$1"
  local field="$2"
  local expected="$3"
  local label="$4"
  local actual
  actual="$(python3 -c "import json; print(json.load(open('${json_file}'))['${field}'])")"
  if [[ "$actual" == "$expected" ]]; then
    pass "${label}"
  else
    fail "${label}：期望 '${expected}'，实际 '${actual}'"
  fi
}

check_json_field_in() {
  local json_file="$1"
  local field="$2"
  local label="$3"
  shift 3
  local values=("$@")
  local actual
  actual="$(python3 -c "import json; print(json.load(open('${json_file}'))['${field}'])")"
  local found=false
  for v in "${values[@]}"; do
    if [[ "$actual" == "$v" ]]; then
      found=true
      break
    fi
  done
  if [[ "$found" == "true" ]]; then
    pass "${label}：${actual}"
  else
    fail "${label}：期望 ${values[*]}，实际 '${actual}'"
  fi
}

run_validate() {
  local out_dir="$1"; shift
  rm -rf "$out_dir"
  bash "$SCRIPT_DIR/validate_package.sh" "$@" --out-dir "$out_dir" 2>/dev/null || true
}

# =============================================================================
# Step 1: 结构校验
# =============================================================================
echo "=== Step 1: 结构校验 ==="
bash "$SCRIPT_DIR/validate.sh" "$SKILL_DIR" >/dev/null && pass "结构校验" || fail "结构校验"

# =============================================================================
# Step 2: 样例文件存在
# =============================================================================
echo "=== Step 2: 样例文件 ==="
FALLBACK_DIAGRAM="$SKILL_DIR/assets/examples/fallback/fallback-diagram.example.puml"
ARCH_BRIEF="$SKILL_DIR/assets/examples/architecture/architecture-brief.example.yaml"
ARCH_DIAGRAM="$SKILL_DIR/assets/examples/architecture/architecture-diagram.example.puml"
SEQ_BRIEF="$SKILL_DIR/assets/examples/sequence/sequence-brief.example.yaml"
SEQ_DIAGRAM="$SKILL_DIR/assets/examples/sequence/sequence-diagram.example.puml"
SEQ_S_BRIEF="$SKILL_DIR/assets/examples/sequence/sequence-process-s-brief.example.yaml"
SEQ_S_DIAGRAM="$SKILL_DIR/assets/examples/sequence/sequence-process-s-diagram.example.puml"
COMPONENT_BRIEF="$SKILL_DIR/assets/examples/component/component-brief.example.yaml"
COMPONENT_DIAGRAM="$SKILL_DIR/assets/examples/component/component-diagram.example.puml"
ACTIVITY_BRIEF="$SKILL_DIR/assets/examples/activity/activity-brief.example.yaml"
ACTIVITY_DIAGRAM="$SKILL_DIR/assets/examples/activity/activity-diagram.example.puml"
DEPLOYMENT_BRIEF="$SKILL_DIR/assets/examples/deployment/deployment-brief.example.yaml"
DEPLOYMENT_DIAGRAM="$SKILL_DIR/assets/examples/deployment/deployment-diagram.example.puml"
SERVER_CANDIDATES="$SKILL_DIR/assets/server_candidates.txt"
for f in "$FALLBACK_DIAGRAM" "$ARCH_BRIEF" "$ARCH_DIAGRAM" "$SEQ_BRIEF" "$SEQ_DIAGRAM" \
  "$SEQ_S_BRIEF" "$SEQ_S_DIAGRAM" "$COMPONENT_BRIEF" "$COMPONENT_DIAGRAM" \
  "$ACTIVITY_BRIEF" "$ACTIVITY_DIAGRAM" "$DEPLOYMENT_BRIEF" "$DEPLOYMENT_DIAGRAM" "$SERVER_CANDIDATES"; do
  if [[ -f "$f" ]]; then
    pass "文件存在：$(basename "$f")"
  else
    fail "缺少文件：$f"
  fi
done

# =============================================================================
# Step 3: Fallback 正向验证
# =============================================================================
echo "=== Step 3: Fallback 正向验证 ==="
FALLBACK_OUT="/tmp/plantuml-fallback-smoke-test"
run_validate "$FALLBACK_OUT" --diagram "$FALLBACK_DIAGRAM" --diagram-type fallback

if [[ -f "$FALLBACK_OUT/validation.json" ]]; then
  pass "validation.json 已生成"
  check_json_field "$FALLBACK_OUT/validation.json" skill_name "feipi-plantuml-generate-diagram" "skill_name"
  check_json_field "$FALLBACK_OUT/validation.json" diagram_type "fallback" "diagram_type"
  check_json_field "$FALLBACK_OUT/validation.json" profile "fallback" "profile"
  check_json_field "$FALLBACK_OUT/validation.json" schema_version "1.1" "schema_version"
  check_json_field_in "$FALLBACK_OUT/validation.json" final_status "final_status" "success" "blocked"
else
  fail "validation.json 未生成"
fi

# =============================================================================
# Step 4: Fallback 负向验证（缺 @enduml）
# =============================================================================
echo "=== Step 4: Fallback 负向验证 ==="
INVALID_DIAGRAM="$TEST_DIR/invalid-missing-enduml.puml"
INVALID_OUT="/tmp/plantuml-fallback-invalid-test"
rm -rf "$INVALID_OUT"

if bash "$SCRIPT_DIR/validate_package.sh" \
  --diagram "$INVALID_DIAGRAM" \
  --diagram-type fallback \
  --out-dir "$INVALID_OUT" 2>/dev/null; then
  fail "负向用例应该被拦截"
else
  if [[ -f "$INVALID_OUT/validation.json" ]]; then
    check_json_field "$INVALID_OUT/validation.json" final_status "blocked" "负向用例正确拦截"
  else
    fail "负向用例未生成 validation.json"
  fi
fi

# =============================================================================
# Step 5: Architecture 正向验证
# =============================================================================
echo "=== Step 5: Architecture 正向验证 ==="
ARCH_OUT="/tmp/plantuml-arch-smoke-test"
run_validate "$ARCH_OUT" \
  --diagram-type architecture \
  --brief "$ARCH_BRIEF" \
  --diagram "$ARCH_DIAGRAM"

if [[ -f "$ARCH_OUT/validation.json" ]]; then
  pass "architecture validation.json 已生成"
  check_json_field "$ARCH_OUT/validation.json" diagram_type "architecture" "diagram_type"
  check_json_field "$ARCH_OUT/validation.json" profile "architecture" "profile"
  check_json_field "$ARCH_OUT/validation.json" brief_check "ok" "brief_check"
  check_json_field "$ARCH_OUT/validation.json" coverage_check "ok" "coverage_check"
  check_json_field "$ARCH_OUT/validation.json" layout_check "ok" "layout_check"
  check_json_field_in "$ARCH_OUT/validation.json" final_status "final_status" "success" "blocked"
else
  fail "architecture validation.json 未生成"
fi

# =============================================================================
# Step 6: Architecture 负向验证（缺组件/缺流程）
# =============================================================================
echo "=== Step 6: Architecture 负向验证 ==="
ARCH_NEG_OUT="/tmp/plantuml-arch-neg-test"
rm -rf "$ARCH_NEG_OUT"

if bash "$SCRIPT_DIR/validate_package.sh" \
  --diagram-type architecture \
  --brief "$ARCH_BRIEF" \
  --diagram "$TEST_DIR/architecture-invalid-diagram.puml" \
  --out-dir "$ARCH_NEG_OUT" 2>/dev/null; then
  fail "architecture 负向用例应该被拦截"
else
  if [[ -f "$ARCH_NEG_OUT/validation.json" ]]; then
    STATUS="$(python3 -c "import json; print(json.load(open('$ARCH_NEG_OUT/validation.json'))['final_status'])")"
    if [[ "$STATUS" == "blocked" ]]; then
      pass "architecture 负向用例正确拦截"
    else
      fail "architecture 负向用例 final_status 不是 blocked：$STATUS"
    fi
  else
    fail "architecture 负向用例未生成 validation.json"
  fi
fi

# =============================================================================
# Step 7: Sequence 正向验证
# =============================================================================
echo "=== Step 7: Sequence 正向验证 ==="
SEQ_OUT="/tmp/plantuml-seq-smoke-test"
run_validate "$SEQ_OUT" \
  --diagram-type sequence \
  --brief "$SEQ_BRIEF" \
  --diagram "$SEQ_DIAGRAM"

if [[ -f "$SEQ_OUT/validation.json" ]]; then
  pass "sequence validation.json 已生成"
  check_json_field "$SEQ_OUT/validation.json" diagram_type "sequence" "diagram_type"
  check_json_field "$SEQ_OUT/validation.json" profile "sequence" "profile"
  check_json_field "$SEQ_OUT/validation.json" brief_check "ok" "brief_check"
  check_json_field "$SEQ_OUT/validation.json" coverage_check "ok" "coverage_check"
  check_json_field "$SEQ_OUT/validation.json" layout_check "ok" "layout_check"
  check_json_field_in "$SEQ_OUT/validation.json" final_status "final_status" "success" "blocked"
else
  fail "sequence validation.json 未生成"
fi

# =============================================================================
# Step 8: Sequence 负向验证（额外消息/缺 separator）
# =============================================================================
echo "=== Step 8: Sequence 负向验证 ==="
SEQ_NEG_EXTRA="/tmp/plantuml-seq-neg-extra-test"
rm -rf "$SEQ_NEG_EXTRA"

if bash "$SCRIPT_DIR/validate_package.sh" \
  --diagram-type sequence \
  --brief "$SEQ_BRIEF" \
  --diagram "$TEST_DIR/sequence-extra-message-diagram.puml" \
  --out-dir "$SEQ_NEG_EXTRA" 2>/dev/null; then
  fail "sequence 额外消息用例应该被拦截"
else
  if [[ -f "$SEQ_NEG_EXTRA/validation.json" ]]; then
    check_json_field "$SEQ_NEG_EXTRA/validation.json" final_status "blocked" "sequence 额外消息正确拦截"
  else
    fail "sequence 额外消息用例未生成 validation.json"
  fi
fi

SEQ_NEG_SEP="/tmp/plantuml-seq-neg-sep-test"
rm -rf "$SEQ_NEG_SEP"

if bash "$SCRIPT_DIR/validate_package.sh" \
  --diagram-type sequence \
  --brief "$SEQ_BRIEF" \
  --diagram "$TEST_DIR/sequence-missing-separator-diagram.puml" \
  --out-dir "$SEQ_NEG_SEP" 2>/dev/null; then
  fail "sequence 缺 separator 用例应该被拦截"
else
  if [[ -f "$SEQ_NEG_SEP/validation.json" ]]; then
    check_json_field "$SEQ_NEG_SEP/validation.json" final_status "blocked" "sequence 缺 separator 正确拦截"
  else
    fail "sequence 缺 separator 用例未生成 validation.json"
  fi
fi

# =============================================================================
# Step 9: 新 typed profiles 与 process_s
# =============================================================================
echo "=== Step 9: 新 typed profiles 与 process_s ==="
for spec in \
  "component|$COMPONENT_BRIEF|$COMPONENT_DIAGRAM" \
  "activity|$ACTIVITY_BRIEF|$ACTIVITY_DIAGRAM" \
  "deployment|$DEPLOYMENT_BRIEF|$DEPLOYMENT_DIAGRAM" \
  "sequence|$SEQ_S_BRIEF|$SEQ_S_DIAGRAM"; do
  IFS='|' read -r profile brief diagram <<< "$spec"
  out_dir="/tmp/plantuml-${profile}-v2-smoke-test"
  [[ "$brief" == "$SEQ_S_BRIEF" ]] && out_dir="/tmp/plantuml-sequence-process-s-smoke-test"
  run_validate "$out_dir" --diagram-type "$profile" --brief "$brief" --diagram "$diagram"
  if [[ -f "$out_dir/validation.json" ]]; then
    check_json_field "$out_dir/validation.json" schema_version "1.1" "$profile schema_version"
    check_json_field "$out_dir/validation.json" profile "$profile" "$profile profile"
    check_json_field "$out_dir/validation.json" brief_check "ok" "$profile brief_check"
    check_json_field "$out_dir/validation.json" coverage_check "ok" "$profile coverage_check"
    check_json_field "$out_dir/validation.json" layout_check "ok" "$profile layout_check"
    check_json_field_in "$out_dir/validation.json" final_status "$profile final_status" "success" "blocked"
  else
    fail "$profile validation.json 未生成"
  fi
done

if python3 "$SCRIPT_DIR/check_coverage.py" --type sequence --brief "$SEQ_S_BRIEF" \
  --diagram "$TEST_DIR/sequence-process-s-mixed-diagram.puml" >/dev/null 2>&1; then
  fail "process_s 混用 M/R 应被拦截"
else
  pass "process_s 混用 M/R 正确拦截"
fi

UNLABELED_COMPONENT="/tmp/plantuml-component-unlabeled.puml"
sed -E 's/[[:space:]]*:[[:space:]]*E[1-9][0-9]*[[:space:]]*$//' "$COMPONENT_DIAGRAM" > "$UNLABELED_COMPONENT"
if python3 "$SCRIPT_DIR/check_coverage.py" --type component --brief "$COMPONENT_BRIEF" \
  --diagram "$UNLABELED_COMPONENT" >/dev/null 2>&1; then
  pass "component 关系允许无文字标签"
else
  fail "component 无文字关系应被允许"
fi

PROCESS_S_AUTONUMBER="/tmp/plantuml-process-s-autonumber.puml"
awk '{print} /skinparam ranksep/ {print "autonumber"}' "$SEQ_S_DIAGRAM" > "$PROCESS_S_AUTONUMBER"
if bash "$SCRIPT_DIR/lint_layout.sh" --type sequence "$PROCESS_S_AUTONUMBER" "$SEQ_S_BRIEF" >/dev/null 2>&1; then
  fail "process_s autonumber 应被拦截"
else
  pass "process_s autonumber 正确拦截"
fi

if python3 "$TEST_DIR/test_profile_validators.py" >/dev/null 2>&1; then
  pass "profile 边界与编号单元测试"
else
  fail "profile 边界与编号单元测试"
fi

if python3 "$TEST_DIR/test_package_verifier.py" >/dev/null 2>&1; then
  pass "v1.1 package 安全与双向合同单元测试"
else
  fail "v1.1 package 安全与双向合同单元测试"
fi

# 未注册图型只能进入 fallback，不得跳过 typed schema 后伪装成 typed profile。
UNKNOWN_OUT="/tmp/plantuml-unknown-fallback-test"
run_validate "$UNKNOWN_OUT" --diagram-type class --diagram "$FALLBACK_DIAGRAM"
if [[ -f "$UNKNOWN_OUT/validation.json" ]]; then
  check_json_field "$UNKNOWN_OUT/validation.json" diagram_type "class" "保留请求图型"
  check_json_field "$UNKNOWN_OUT/validation.json" profile "fallback" "未注册图型路由 fallback"
else
  fail "未知图型 fallback 未生成 validation.json"
fi

# v1.1 hash 合同必须可复核，任一 artifact 被篡改都失败。
HASH_OUT="/tmp/plantuml-component-v2-smoke-test"
if python3 - "$HASH_OUT/validation.json" <<'PY' >/dev/null 2>&1
import json
import sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
required = {
    "diagram_id", "profile_version", "brief_sha256", "puml_sha256",
    "normalized_puml_sha256", "artifacts", "metrics",
}
assert required.issubset(data)
assert data["diagram_id"] == "D1"
assert data["brief_path"] == "brief.normalized.yaml"
assert data["diagram_path"] == "diagram.puml"
assert data["brief_sha256"] == data["artifacts"]["brief"]["sha256"]
assert data["puml_sha256"] == data["artifacts"]["diagram"]["sha256"]
assert data["metrics"] == {"node_count": 3, "edge_count": 2, "max_degree": 2}
PY
then
  pass "v1.1 字段、相对路径与 metrics 合同"
else
  fail "v1.1 字段、相对路径与 metrics 合同"
fi
HASH_STATUS="$(python3 -c "import json; print(json.load(open('$HASH_OUT/validation.json'))['final_status'])")"
if [[ "$HASH_STATUS" == "success" ]]; then
  if python3 "$SCRIPT_DIR/verify_package.py" "$HASH_OUT" >/dev/null 2>&1; then
    pass "v1.1 package hash 复核"
  else
    fail "v1.1 package hash 复核"
  fi
  printf '\n' >> "$HASH_OUT/diagram.puml"
  if python3 "$SCRIPT_DIR/verify_package.py" "$HASH_OUT" >/dev/null 2>&1; then
    fail "篡改 diagram.puml 应导致 hash 复核失败"
  else
    pass "篡改 diagram.puml 正确拦截"
  fi
else
  check_json_field "$HASH_OUT/validation.json" blocked_reason "render_server_unavailable" "离线渲染如实阻塞"
fi

# renderer 缺失时不得复用旧 SVG 或写出 success。
MISSING_RENDER_ROOT="$(mktemp -d /tmp/plantuml-missing-render.XXXXXX)"
mkdir -p "$MISSING_RENDER_ROOT/scripts" "$MISSING_RENDER_ROOT/out"
cp "$SCRIPT_DIR/validate_package.sh" "$MISSING_RENDER_ROOT/scripts/validate_package.sh"
cp -R "$SCRIPT_DIR/lib" "$MISSING_RENDER_ROOT/scripts/lib"
printf '<svg>stale</svg>\n' > "$MISSING_RENDER_ROOT/out/diagram.svg"
if bash "$MISSING_RENDER_ROOT/scripts/validate_package.sh" \
  --diagram "$FALLBACK_DIAGRAM" --diagram-type fallback --out-dir "$MISSING_RENDER_ROOT/out" >/dev/null 2>&1; then
  fail "renderer 缺失不应返回 success"
elif [[ -f "$MISSING_RENDER_ROOT/out/diagram.svg" ]]; then
  fail "renderer 缺失时旧 SVG 未失效"
else
  check_json_field "$MISSING_RENDER_ROOT/out/validation.json" final_status "blocked" "renderer 缺失正确阻塞"
  check_json_field "$MISSING_RENDER_ROOT/out/validation.json" blocked_reason "renderer_missing" "旧 SVG 不进入合同"
fi

# =============================================================================
# Step 10: Python 语法与 Shell 语法检查
# =============================================================================
echo "=== Step 10: 脚本语法检查 ==="
if python3 -m py_compile $(find "$SCRIPT_DIR" -type f -name '*.py' | sort) 2>/dev/null; then
  pass "Python 语法检查"
else
  fail "Python 语法检查"
fi
if find "$SCRIPT_DIR" -type f -name '*.sh' -print0 | xargs -0 -n1 bash -n 2>/dev/null; then
  pass "Shell 语法检查"
else
  fail "Shell 语法检查"
fi

# =============================================================================
# Step 11: 触发边界一致 & 旧 skill 保护
# =============================================================================
echo "=== Step 11: 触发边界 & 旧 skill 保护 ==="
if rg -q 'fallback' "$SKILL_DIR/SKILL.md"; then
  pass "SKILL.md 包含 fallback"
else
  fail "SKILL.md 缺少 fallback"
fi
ARCH_OLD_SKILL="$REPO_ROOT/skills/diagram/feipi-plantuml-generate-architecture-diagram/SKILL.md"
SEQ_OLD_SKILL="$REPO_ROOT/skills/diagram/feipi-plantuml-generate-sequence-diagram/SKILL.md"
if [[ -f "$ARCH_OLD_SKILL" && -f "$SEQ_OLD_SKILL" ]]; then
  pass "旧 skill 未被删除"
else
  fail "旧 skill 已被删除"
fi

# =============================================================================
# 总结
# =============================================================================
echo ""
echo "=== 测试总结 ==="
echo "PASS: $PASS"
echo "FAIL: $FAIL"

if [[ "$FAIL" -gt 0 ]]; then
  echo "测试失败" >&2
  exit 1
fi

echo "测试通过：feipi-plantuml-generate-diagram"
