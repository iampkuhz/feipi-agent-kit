#!/usr/bin/env bash
set -euo pipefail

# 统一测试入口（供 make test 调用）
# 测试目标：从需求文本生成 PlantUML，再做真实渲染语法校验。

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
GEN_SCRIPT="$SCRIPT_DIR/generate_plantuml.sh"
CHECK_SCRIPT="$SCRIPT_DIR/check_plantuml.sh"
DEFAULT_CONFIG="$SKILL_DIR/references/test_cases.txt"

CONFIG=""
OUTPUT=""
SERVERS_CONFIG=""
APPEND_SERVER=""
TIMEOUT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --config)
      CONFIG="$2"
      shift 2
      ;;
    --output)
      OUTPUT="$2"
      shift 2
      ;;
    --servers-config)
      SERVERS_CONFIG="$2"
      shift 2
      ;;
    --append-server)
      APPEND_SERVER="$2"
      shift 2
      ;;
    # 兼容旧参数：统一并入候选列表语义
    --public-server)
      APPEND_SERVER="$2"
      shift 2
      ;;
    --local-config)
      SERVERS_CONFIG="$2"
      shift 2
      ;;
    --timeout)
      TIMEOUT="$2"
      shift 2
      ;;
    *)
      echo "未知参数: $1" >&2
      exit 1
      ;;
  esac
done

if [[ -z "$CONFIG" ]]; then
  CONFIG="$DEFAULT_CONFIG"
fi

if [[ ! -f "$CONFIG" ]]; then
  echo "测试配置不存在: $CONFIG" >&2
  exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "缺少依赖: curl" >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "缺少依赖: python3" >&2
  exit 1
fi

if [[ -n "$OUTPUT" ]]; then
  ROOT_DIR="$OUTPUT"
else
  stamp="$(date +%Y%m%d-%H%M%S)"
  ROOT_DIR="$HOME/Downloads/feipi-gen-plantuml-code-test-$stamp"
  if ! mkdir -p "$ROOT_DIR" 2>/dev/null; then
    ROOT_DIR="/tmp/feipi-gen-plantuml-code-test-$stamp"
  fi
fi
mkdir -p "$ROOT_DIR"
LOG_DIR="$ROOT_DIR/logs"
OUT_DIR="$ROOT_DIR/out"
mkdir -p "$LOG_DIR" "$OUT_DIR"

echo "测试配置: $CONFIG"
echo "测试输出: $ROOT_DIR"

trim() {
  printf '%s' "$1" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//'
}

assert_contains_all() {
  local file="$1"
  local assertions_raw="$2"

  IFS=';' read -r -a arr <<< "$assertions_raw"
  local item trimmed
  for item in "${arr[@]}"; do
    trimmed="$(trim "$item")"
    [[ -z "$trimmed" ]] && continue
    if ! grep -Fq "$trimmed" "$file"; then
      echo "断言失败: 未找到关键字 [$trimmed]" >&2
      return 1
    fi
  done
  return 0
}

TOTAL=0
PASSED=0
FAILED=0

run_case() {
  local case_id="$1"
  local expect="$2"
  local diagram_type="$3"
  local requirement_text="$4"
  local assert_contains="$5"

  local puml_path="$OUT_DIR/${case_id}.puml"
  local svg_path="$OUT_DIR/${case_id}.svg"
  local log_path="$LOG_DIR/${case_id}.log"

  local gen_cmd=("bash" "$GEN_SCRIPT" "--type" "$diagram_type" "--requirement" "$requirement_text" "--output" "$puml_path")
  local gen_output=""
  local gen_code=0

  set +e
  gen_output="$("${gen_cmd[@]}" 2>&1)"
  gen_code=$?
  set -e

  {
    echo "case_id=$case_id"
    echo "expect=$expect"
    echo "diagram_type=$diagram_type"
    echo "requirement_text=$requirement_text"
    echo "gen_command=${gen_cmd[*]}"
    echo "gen_code=$gen_code"
    echo "gen_output_start"
    printf '%s\n' "$gen_output"
    echo "gen_output_end"
  } > "$log_path"

  case "$expect" in
    generate_error)
      if [[ "$gen_code" -ne 0 ]]; then
        if [[ -n "$assert_contains" ]] && ! printf '%s\n' "$gen_output" | grep -Fq "$assert_contains"; then
          echo "[FAIL] ${case_id}（生成失败信息不符合预期）" >&2
          echo "日志: $log_path" >&2
          FAILED=$((FAILED + 1))
          return
        fi
        echo "[PASS] ${case_id}（预期生成失败）"
        PASSED=$((PASSED + 1))
      else
        echo "[FAIL] ${case_id}（预期生成失败，实际成功）" >&2
        echo "日志: $log_path" >&2
        FAILED=$((FAILED + 1))
      fi
      return
      ;;
    ok)
      if [[ "$gen_code" -ne 0 || ! -f "$puml_path" ]]; then
        echo "[FAIL] ${case_id}（生成阶段失败）" >&2
        echo "日志: $log_path" >&2
        FAILED=$((FAILED + 1))
        return
      fi
      ;;
    *)
      echo "[FAIL] $case_id 未知 expect: $expect" >&2
      echo "日志: $log_path" >&2
      FAILED=$((FAILED + 1))
      return
      ;;
  esac

  if ! assert_contains_all "$puml_path" "$assert_contains"; then
    {
      echo "assert_contains=$assert_contains"
      echo "puml_snapshot_start"
      sed -n '1,260p' "$puml_path"
      echo "puml_snapshot_end"
    } >> "$log_path"
    echo "[FAIL] ${case_id}（生成内容断言失败）" >&2
    echo "日志: $log_path" >&2
    FAILED=$((FAILED + 1))
    return
  fi

  local check_cmd=("bash" "$CHECK_SCRIPT" "$puml_path" "--svg-output" "$svg_path")
  if [[ -n "$SERVERS_CONFIG" ]]; then
    check_cmd+=("--servers-config" "$SERVERS_CONFIG")
  fi
  if [[ -n "$APPEND_SERVER" ]]; then
    check_cmd+=("--append-server" "$APPEND_SERVER")
  fi
  if [[ -n "$TIMEOUT" ]]; then
    check_cmd+=("--timeout" "$TIMEOUT")
  fi

  local check_output=""
  local check_code=0
  set +e
  check_output="$("${check_cmd[@]}" 2>&1)"
  check_code=$?
  set -e

  {
    echo "check_command=${check_cmd[*]}"
    echo "check_code=$check_code"
    echo "check_output_start"
    printf '%s\n' "$check_output"
    echo "check_output_end"
  } >> "$log_path"

  if [[ "$check_code" -eq 0 ]] \
    && printf '%s\n' "$check_output" | grep -Fq 'syntax_result=ok' \
    && printf '%s\n' "$check_output" | grep -Eq 'server_mode=(ordered|custom)' \
    && [[ -f "$svg_path" ]]; then
    echo "[PASS] $case_id ($diagram_type)"
    PASSED=$((PASSED + 1))
  else
    echo "[FAIL] $case_id ($diagram_type)" >&2
    echo "日志: $log_path" >&2
    FAILED=$((FAILED + 1))
  fi
}

while IFS= read -r raw || [[ -n "$raw" ]]; do
  line="${raw%%#*}"
  line="$(trim "$line")"
  [[ -z "$line" ]] && continue

  IFS='|' read -r case_id expect diagram_type requirement_text assert_contains extra <<< "$line"
  case_id="$(trim "${case_id:-}")"
  expect="$(trim "${expect:-}")"
  diagram_type="$(trim "${diagram_type:-}")"
  requirement_text="$(trim "${requirement_text:-}")"
  assert_contains="$(trim "${assert_contains:-}")"
  extra="$(trim "${extra:-}")"

  TOTAL=$((TOTAL + 1))

  if [[ -n "$extra" || -z "$case_id" || -z "$expect" || -z "$diagram_type" || -z "$requirement_text" ]]; then
    echo "[FAIL] case-$TOTAL 用例格式错误: $line" >&2
    FAILED=$((FAILED + 1))
    continue
  fi

  run_case "$case_id" "$expect" "$diagram_type" "$requirement_text" "$assert_contains"
done < "$CONFIG"

if [[ "$TOTAL" -eq 0 ]]; then
  echo "未执行任何测试用例" >&2
  exit 1
fi

echo "测试汇总: total=$TOTAL pass=$PASSED fail=$FAILED"
if [[ "$FAILED" -ne 0 ]]; then
  exit 1
fi

echo "测试通过: feipi-gen-plantuml-code（需求文本生成 + 真实渲染校验通过）"
