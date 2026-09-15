#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
NODE_BIN="$(command -v node)"
TMP_ROOT="$(mktemp -d)"
trap 'rm -rf "$TMP_ROOT"' EXIT

required_files=(
  "$SKILL_DIR/SKILL.md"
  "$SKILL_DIR/agents/openai.yaml"
  "$SKILL_DIR/compiler/token-store.js"
  "$SKILL_DIR/compiler/render-plan-compiler.js"
  "$SKILL_DIR/compiler/overflow-evaluator.js"
  "$SKILL_DIR/adapters/pptx-backend.js"
  "$SKILL_DIR/adapters/pptxgenjs/backend.js"
  "$SKILL_DIR/schemas/slide-ir.v2.schema.json"
  "$SKILL_DIR/schemas/render-plan.schema.json"
  "$SKILL_DIR/design-system/layouts/layered-architecture.layout.json"
  "$SKILL_DIR/design-system/layouts/solution-comparison.layout.json"
  "$SKILL_DIR/design-system/layouts/multi-party-flow.layout.json"
)

for file in "${required_files[@]}"; do
  [[ -f "$file" ]] || { echo "缺少必需文件: $file" >&2; exit 1; }
done

bash -n "$SCRIPT_DIR/run.sh"

"$NODE_BIN" "$SKILL_DIR/scripts/validate_design_system.js" --json > "$TMP_ROOT/design-system.json"
"$NODE_BIN" "$SKILL_DIR/scripts/validate_workflow_modes.js" --json > "$TMP_ROOT/workflow-modes.json"
for style_lock in "$SKILL_DIR"/templates/style-locks/*.style-lock.json; do
  "$NODE_BIN" "$SKILL_DIR/scripts/validate_style_lock.js" "$style_lock" --json > /dev/null
done

v1_fixtures=(architecture-map comparison-matrix flow-diagram)
for fixture in "${v1_fixtures[@]}"; do
  "$NODE_BIN" "$SKILL_DIR/scripts/validate_slide_ir.js" "$SKILL_DIR/tests/fixtures/$fixture.slide-ir.json" --json > /dev/null
done

v2_fixtures=(layered-architecture solution-comparison multi-party-flow)
for fixture in "${v2_fixtures[@]}"; do
  "$NODE_BIN" "$SKILL_DIR/scripts/validate_slide_ir.js" "$SKILL_DIR/tests/fixtures/acceptance/$fixture.slide-ir.v2.json" --json > /dev/null
done

"$NODE_BIN" "$SKILL_DIR/tests/p0/run.js"

"$NODE_BIN" "$SCRIPT_DIR/run_benchmarks.js" --dry-run --full --json > "$TMP_ROOT/benchmarks.json"
"$NODE_BIN" - "$TMP_ROOT/benchmarks.json" <<'NODE'
const fs = require('fs');
const report = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const failures = report.results.filter(item => item.status !== 'pass');
if (failures.length > 0) throw new Error(`benchmark 未通过: ${failures.map(item => item.name).join(', ')}`);
const overload = report.results.find(item => item.name === 'overload-should-split');
if (overload?.actual_status !== 'needs_user_decision') throw new Error('overload benchmark 未返回 needs_user_decision');
NODE

"$NODE_BIN" "$SKILL_DIR/scripts/generate_pptx_pipeline.js" \
  "$SKILL_DIR/tests/fixtures/acceptance/layered-architecture.slide-ir.v2.json" \
  "$TMP_ROOT/pipeline" --mode fast --no-render --json > /dev/null
"$NODE_BIN" - "$TMP_ROOT/pipeline/pipeline-report.json" <<'NODE'
const fs = require('fs');
const report = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
if (report.final_status !== 'pass') throw new Error(`fast pipeline 未通过: ${report.final_status}`);
if (!fs.existsSync(process.argv[2].replace(/pipeline-report\.json$/, 'output.pptx'))) throw new Error('fast pipeline 未生成 PPTX');
NODE

DOCTOR_JSON=$("$NODE_BIN" "$SKILL_DIR/scripts/doctor.js" --json)
RUNTIME_JSON=$("$NODE_BIN" "$SKILL_DIR/scripts/runtime_capabilities.js")
"$NODE_BIN" - "$DOCTOR_JSON" "$RUNTIME_JSON" <<'NODE'
const doctor = JSON.parse(process.argv[2]);
const runtime = JSON.parse(process.argv[3]);
if (!doctor.pipeline_level || doctor.pipeline_level !== runtime.pipeline_level) {
  throw new Error('doctor 与 runtime_capabilities 的 pipeline_level 不一致');
}
NODE

if rg -n 'fontSize\s*:\s*[0-9]|fontSize\s*\|\||font_size_pt\s*\|\||fontScale|autoFit\s*:\s*true|shrink_font' \
  "$SKILL_DIR/helpers" "$SKILL_DIR/adapters" "$SKILL_DIR/compiler" "$SKILL_DIR/scripts" -g '*.js'; then
  echo '发现绕过 token 的字号 fallback 或自动缩放路径' >&2
  exit 1
fi

if rg -n '/Users/.*/Downloads/feipi-ppt-design-kit' "$SKILL_DIR/helpers" "$SKILL_DIR/compiler" "$SKILL_DIR/adapters"; then
  echo '发现外部 Downloads design-kit 路径' >&2
  exit 1
fi

echo 'feipi-techreport-ppt-skill: all tests passed'
