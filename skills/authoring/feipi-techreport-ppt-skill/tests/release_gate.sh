#!/usr/bin/env bash
#
# release_gate.sh — 端到端发布门禁
#
# 运行完整的 release gate 检查，验证所有第二阶段能力就绪。
#
# 用法:
#   bash tests/release_gate.sh [--strict]
#
# 模式:
#   默认: 跑 full benchmark，允许 static-only pipeline
#   --strict: 要求 pptxgenjs 可用、能生成 PPTX、渲染环境可用才允许完整视觉验收
#
# 退出码:
#   0: Gate 通过（default 模式下 static-only 也算通过）
#   1: Gate 有 FAIL 项（strict 模式下缺少依赖必定 exit 1）
#
# 输出（按模式隔离，防止并发覆盖）:
#   tmp/ppt-skill-v2-run/release/default/release-report.md
#   tmp/ppt-skill-v2-run/release/default/release-report.json
#   或
#   tmp/ppt-skill-v2-run/release/strict/release-report.md
#   tmp/ppt-skill-v2-run/release/strict/release-report.json

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"

STRICT_MODE=0
MODE_LABEL="default"
if [[ "${1:-}" == "--strict" ]]; then
  STRICT_MODE=1
  MODE_LABEL="strict"
fi

# Mode-specific report directories to prevent concurrent overwrite
RELEASE_DIR="$REPO_ROOT/tmp/ppt-skill-v2-run/release/$MODE_LABEL"
ARTIFACTS_DIR="$RELEASE_DIR/artifacts"
mkdir -p "$RELEASE_DIR" "$ARTIFACTS_DIR"

REPORT_MD="$RELEASE_DIR/release-report.md"
REPORT_JSON="$RELEASE_DIR/release-report.json"

echo "# Release Gate Report" > "$REPORT_MD"
echo "" >> "$REPORT_MD"
echo "Date: $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$REPORT_MD"
echo "Mode: $MODE_LABEL" >> "$REPORT_MD"
echo "" >> "$REPORT_MD"

PASS_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0

# Helper functions
pass() { echo "**[PASS]** $1" >> "$REPORT_MD"; PASS_COUNT=$((PASS_COUNT + 1)); }
fail() { echo "**[FAIL]** $1" >> "$REPORT_MD"; FAIL_COUNT=$((FAIL_COUNT + 1)); }
skip() { echo "**[SKIP]** $1" >> "$REPORT_MD"; SKIP_COUNT=$((SKIP_COUNT + 1)); }

echo "Running release gate ($MODE_LABEL)..."
echo ""

# --- 0. Doctor (determine pipeline level) ---
echo "  0/9: Doctor..."
echo "## 0. Runtime Doctor & Pipeline Level" >> "$REPORT_MD"
DOCTOR_JSON=$(/usr/bin/env node "$SKILL_DIR/scripts/doctor.js" --json 2>/dev/null) || DOCTOR_JSON='{"pipeline_level":"unknown"}'
PIPELINE_LEVEL=$(echo "$DOCTOR_JSON" | /usr/bin/env node -e "const d=JSON.parse(require('fs').readFileSync('/dev/stdin','utf8')); process.stdout.write(d.pipeline_level || 'unknown')" 2>/dev/null || echo "unknown")
echo "$DOCTOR_JSON" > "$RELEASE_DIR/doctor.json"

echo "- **Pipeline Level: \`${PIPELINE_LEVEL}\`**" >> "$REPORT_MD"
echo "" >> "$REPORT_MD"

if [[ "$PIPELINE_LEVEL" == "static-only" ]]; then
  echo "> ⚠ **当前为 static-only 验收。** 缺少 pptxgenjs 和渲染引擎，无法生成 PPTX 或进行视觉验收。" >> "$REPORT_MD"
  echo "> 此门禁仅验证静态 IR 质量和 benchmark 逻辑正确性，**不代表已完成 full visual release**。" >> "$REPORT_MD"
  echo "" >> "$REPORT_MD"
elif [[ "$PIPELINE_LEVEL" == "pptx-build" ]]; then
  echo "> ℹ 当前可生成 PPTX，但缺少渲染引擎，无法进行 Render QA 视觉对比。" >> "$REPORT_MD"
  echo "" >> "$REPORT_MD"
fi

if [[ $STRICT_MODE -eq 1 ]]; then
  echo "## 0b. Strict Mode Prerequisites" >> "$REPORT_MD"
  PPTX_AVAILABLE=$(echo "$DOCTOR_JSON" | /usr/bin/env node -e "const d=JSON.parse(require('fs').readFileSync('/dev/stdin','utf8')); process.stdout.write(d.pptxgenjs?.available ? 'yes' : 'no')" 2>/dev/null || echo "no")
  RENDER_AVAILABLE=$(echo "$DOCTOR_JSON" | /usr/bin/env node -e "const d=JSON.parse(require('fs').readFileSync('/dev/stdin','utf8')); process.stdout.write(d.render?.status === 'available' ? 'yes' : 'no')" 2>/dev/null || echo "no")

  if [[ "$PPTX_AVAILABLE" != "yes" ]]; then
    fail "[Strict] pptxgenjs 不可用，无法生成 PPTX。请运行: cd skills/authoring/feipi-techreport-ppt-skill && npm ci"
  else
    pass "[Strict] pptxgenjs 可用"
  fi

  if [[ "$RENDER_AVAILABLE" != "yes" ]]; then
    fail "[Strict] 渲染引擎 (soffice/libreoffice) 不可用，无法进行完整视觉验收。请安装 LibreOffice。"
  else
    pass "[Strict] 渲染引擎可用"
  fi
  echo "" >> "$REPORT_MD"
fi

# --- 1. Test ---
echo "  1/9: Test suite..."
echo "## 1. Test Suite" >> "$REPORT_MD"
if bash "$SCRIPT_DIR/run.sh" > "$RELEASE_DIR/test-output.txt" 2>&1; then
  pass "tests/run.sh 全部通过"
else
  fail "tests/run.sh 有失败项"
fi
echo "" >> "$REPORT_MD"

# --- 2. Full Benchmark dry-run (default mode) ---
echo "  2/9: Full benchmark dry-run..."
echo "## 2. Full Benchmark Dry-Run" >> "$REPORT_MD"
BENCH_EXIT=0
/usr/bin/env node "$SCRIPT_DIR/run_benchmarks.js" --dry-run --full --json > "$RELEASE_DIR/benchmark-dryrun.json" 2>/dev/null || BENCH_EXIT=$?
if [[ $BENCH_EXIT -eq 0 ]]; then
  pass "full benchmark dry-run 全部通过（无 skip，无 fail）"
else
  SKIPPED_COUNT=$(cat "$RELEASE_DIR/benchmark-dryrun.json" 2>/dev/null | /usr/bin/env node -e "const d=JSON.parse(require('fs').readFileSync('/dev/stdin','utf8')); process.stdout.write(String(d.skipped))" 2>/dev/null || echo "?")
  if [[ "$SKIPPED_COUNT" != "0" && "$SKIPPED_COUNT" != "?" ]]; then
    fail "full benchmark dry-run 有 ${SKIPPED_COUNT} 个 skip（缺失 slide-ir.json）"
  else
    fail "full benchmark dry-run 有失败项"
  fi
fi
echo "- benchmark-dryrun.json 已生成" >> "$REPORT_MD"
echo "" >> "$REPORT_MD"

# --- 3. Benchmark scoring ---
echo "  3/9: Benchmark scoring..."
echo "## 3. Quality Scoring" >> "$REPORT_MD"
SCORING_EXIT=0
/usr/bin/env node "$SCRIPT_DIR/run_benchmarks.js" --no-render --full --json > "$RELEASE_DIR/benchmark-scores.json" 2>/dev/null || SCORING_EXIT=$?
if [[ $SCORING_EXIT -eq 0 ]]; then
  pass "full benchmark scoring 完成"
else
  fail "full benchmark scoring 有失败项"
fi
echo "" >> "$REPORT_MD"

# --- 4. PPTX Post-Check (real artifact generation and inspection) ---
echo "  4/9: PPTX Post-Check..."
echo "## 4. PPTX Post-Check" >> "$REPORT_MD"

PPTX_ARTIFACT="$ARTIFACTS_DIR/architecture-map.pptx"
POSTCHECK_JSON="$RELEASE_DIR/postcheck-architecture-map.json"

if [[ "$PIPELINE_LEVEL" == "static-only" ]]; then
  skip "PPTX 检查跳过：当前 pipeline_level=static-only，无 PPTX 产物可验证"
  echo "- 当前为 static-only 验收，未生成 PPTX 产物，未进行 postcheck" >> "$REPORT_MD"
else
  # Generate PPTX from architecture-map fixture
  FIXTURE_IR="$SKILL_DIR/tests/fixtures/architecture-map.slide-ir.json"
  if [[ -f "$FIXTURE_IR" ]]; then
    echo "  生成 PPTX 产物: $PPTX_ARTIFACT"
    /usr/bin/env node "$SKILL_DIR/scripts/build_pptx_from_ir.js" "$FIXTURE_IR" "$PPTX_ARTIFACT" --allow-warnings > "$RELEASE_DIR/build-pptx-output.txt" 2>&1
    BUILD_EXIT=$?

    if [[ $BUILD_EXIT -ne 0 ]] || [[ ! -s "$PPTX_ARTIFACT" ]]; then
      fail "PPTX 生成失败（build_pptx_from_ir.js exit=$BUILD_EXIT）"
      echo "- PPTX 生成失败，无法进行 postcheck" >> "$REPORT_MD"
    else
      # Run real postcheck on the generated PPTX
      /usr/bin/env node "$SKILL_DIR/scripts/inspect_pptx_artifact.js" "$PPTX_ARTIFACT" --json --expected-slides 1 > "$POSTCHECK_JSON" 2>/dev/null
      INSPECT_EXIT=$?

      if [[ -f "$POSTCHECK_JSON" ]]; then
        # Parse the postcheck result using a helper script to avoid shell variable issues
        PPTX_SIZE=$(stat -f%z "$PPTX_ARTIFACT" 2>/dev/null || stat -c%s "$PPTX_ARTIFACT" 2>/dev/null || echo "unknown")

        /usr/bin/env node -e "
const fs = require('fs');
const pc = JSON.parse(fs.readFileSync('$POSTCHECK_JSON', 'utf8'));
const md = fs.readFileSync('$REPORT_MD', 'utf-8');

const success = pc.postcheck?.success ?? false;
const slideCount = pc.slide_count ?? 0;
const textElems = pc.text_elements ?? 0;
const issues = pc.postcheck?.issues || [];

let report = md;
report += '- **PPTX 产物**: $PPTX_ARTIFACT ($PPTX_SIZE bytes)\n';
report += '- **幻灯片数**: ' + slideCount + '（期望 1）\n';
report += '- **文本元素**: ' + textElems + '\n';
report += '- **问题数**: ' + issues.length + '\n';

if (success) {
  report += '**[PASS]** PPTX postcheck 通过（slide_count=' + slideCount + ', texts=' + textElems + ', issues=' + issues.length + ')\n';
} else {
  issues.forEach(i => { report += '- [' + i.severity + '] ' + i.message + '\n'; });
  report += '**[FAIL]** PPTX postcheck 未通过\n';
}

fs.writeFileSync('$REPORT_MD', report);
// Output success/fail for shell to capture
process.stdout.write(success ? 'PASS' : 'FAIL');
" 2>/dev/null > "$RELEASE_DIR/postcheck-status.txt" || echo "FAIL" > "$RELEASE_DIR/postcheck-status.txt"

        PC_STATUS=$(cat "$RELEASE_DIR/postcheck-status.txt" 2>/dev/null || echo "FAIL")
        if [[ "$PC_STATUS" == "PASS" ]]; then
          pass "PPTX postcheck 通过"
        else
          fail "PPTX postcheck 未通过"
        fi
      else
        fail "PPTX 反检工具输出异常（postcheck JSON 未生成）"
      fi
    fi
  else
    fail "基准 fixture 不存在: $FIXTURE_IR"
  fi
fi
echo "" >> "$REPORT_MD"

# --- 5. Residue search ---
echo "  5/9: Residue search..."
echo "## 5. Residue Search" >> "$REPORT_MD"
PLACEHOLDER_FOUND=0
for f in $(find "$SKILL_DIR/tests/fixtures/benchmarks" -name "slide-ir.json" 2>/dev/null); do
  MATCHES=$(rg -c "xxxx|lorem|ipsum" "$f" 2>/dev/null | grep -v ':0$' || true)
  if [ -n "$MATCHES" ]; then
    PLACEHOLDER_FOUND=$((PLACEHOLDER_FOUND + 1))
  fi
done
if [ "$PLACEHOLDER_FOUND" -eq 0 ]; then
  pass "无 placeholder/lorem/xxxx 残留"
else
  fail "发现 $PLACEHOLDER_FOUND 处可能的 placeholder 残留"
  rg -n "placeholder|lorem|xxxx" "$SKILL_DIR" 2>/dev/null | head -20 >> "$REPORT_MD" || true
fi
echo "" >> "$REPORT_MD"

# Path leak search
PATH_LEAK_FOUND_ACTUAL=$(rg -c "/Users/|/home/oai|/mnt/data" "$SKILL_DIR/tests/fixtures" "$SKILL_DIR/templates" 2>/dev/null | grep -v ':0$' | wc -l || true)
if [ "$PATH_LEAK_FOUND_ACTUAL" -eq 0 ]; then
  pass "无绝对路径泄漏（fixtures/templates 范围）"
else
  fail "发现 $PATH_LEAK_FOUND_ACTUAL 处可能的绝对路径泄漏"
fi
echo "" >> "$REPORT_MD"

# --- 6. Cache ---
echo "  6/9: Cache system..."
echo "## 6. Cache System" >> "$REPORT_MD"
if /usr/bin/env node "$SKILL_DIR/scripts/clean_pipeline_cache.js" --stats > "$RELEASE_DIR/cache-stats.txt" 2>&1; then
  pass "cache 系统可用"
else
  fail "cache 系统异常"
fi
echo "" >> "$REPORT_MD"

# --- 7. Script inventory ---
echo "  7/9: Script inventory..."
echo "## 7. Script Inventory" >> "$REPORT_MD"
SCRIPT_COUNT=$(find "$SKILL_DIR/scripts" -name "*.js" -o -name "*.sh" | wc -l | tr -d ' ')
pass "共 $SCRIPT_COUNT 个脚本文件"
echo "" >> "$REPORT_MD"

# --- 8. Pipeline level verification ---
echo "  8/9: Pipeline level check..."
echo "## 8. Pipeline Level" >> "$REPORT_MD"
echo "- 当前级别: \`${PIPELINE_LEVEL}\`" >> "$REPORT_MD"
case "$PIPELINE_LEVEL" in
  full)
    pass "Pipeline 级别: full（PPTX + Render QA 均可用）"
    ;;
  pptx-build)
    pass "Pipeline 级别: pptx-build（可生成 PPTX，已运行 postcheck）"
    ;;
  static-only)
    if [[ $STRICT_MODE -eq 1 ]]; then
      fail "[Strict] Pipeline 级别 static-only，不满足 strict 要求"
    else
      pass "Pipeline 级别: static-only（仅静态 IR 验收）"
    fi
    ;;
  *)
    fail "Pipeline 级别未知: $PIPELINE_LEVEL"
    ;;
esac
echo "" >> "$REPORT_MD"

# --- Summary ---
echo "" >> "$REPORT_MD"
echo "---" >> "$REPORT_MD"
echo "" >> "$REPORT_MD"
echo "## Summary" >> "$REPORT_MD"
echo "- Pipeline Level: \`${PIPELINE_LEVEL}\`" >> "$REPORT_MD"
echo "- Mode: $MODE_LABEL" >> "$REPORT_MD"
echo "- PASS: $PASS_COUNT" >> "$REPORT_MD"
echo "- FAIL: $FAIL_COUNT" >> "$REPORT_MD"
echo "- SKIP: $SKIP_COUNT" >> "$REPORT_MD"
echo "" >> "$REPORT_MD"

if [ "$FAIL_COUNT" -eq 0 ]; then
  if [[ "$PIPELINE_LEVEL" == "full" ]]; then
    echo "**结论: Full Visual Release Gate 通过**" >> "$REPORT_MD"
  elif [[ "$PIPELINE_LEVEL" == "pptx-build" ]]; then
    echo "**结论: PPTX-Build Release Gate 通过**（无 Render QA）" >> "$REPORT_MD"
  else
    echo "**结论: Static-Only Release Gate 通过**（未生成 PPTX，未进行视觉验收）" >> "$REPORT_MD"
  fi
else
  echo "**结论: Release Gate 未通过，有 $FAIL_COUNT 项失败**" >> "$REPORT_MD"
fi

# Generate JSON report — conclusion/exit_code consistent with shell exit
CONCLUSION="pass"
EXIT_CODE=0
if [ "$FAIL_COUNT" -gt 0 ]; then
  CONCLUSION="fail"
  EXIT_CODE=1
fi

/usr/bin/env node -e "
const fs = require('fs');
const md = fs.readFileSync('$REPORT_MD', 'utf-8');
const report = {
  date: new Date().toISOString(),
  pipeline_level: '$PIPELINE_LEVEL',
  strict_mode: $([[ ${STRICT_MODE} -eq 1 ]] && echo "true" || echo "false"),
  pass: $PASS_COUNT,
  fail: $FAIL_COUNT,
  skip: $SKIP_COUNT,
  conclusion: '$CONCLUSION',
  exit_code: $EXIT_CODE,
  report_md: md
};
fs.writeFileSync('$REPORT_JSON', JSON.stringify(report, null, 2));
" 2>/dev/null || true

echo ""
echo "Release gate ($MODE_LABEL) complete:"
echo "  Markdown: $REPORT_MD"
echo "  JSON:     $REPORT_JSON"
echo "  Pipeline: $PIPELINE_LEVEL"
echo "  PASS: $PASS_COUNT  FAIL: $FAIL_COUNT  SKIP: $SKIP_COUNT"
echo ""
cat "$REPORT_MD"

exit $EXIT_CODE
