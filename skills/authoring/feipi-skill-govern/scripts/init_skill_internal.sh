#!/usr/bin/env bash
set -euo pipefail

# 使用仓库模板初始化一个新 skill。
# 脚本会执行命名规则校验，并创建：
# - SKILL.md
# - agents/openai.yaml
# - scripts/test.sh
# - 可选资源目录（references/assets）

usage() {
  cat <<'USAGE'
用法:
  bash scripts/init_skill_internal.sh <skill-name> [--resources scripts,references,assets] [--target auto|skills|repo|<path>]

示例:
  bash scripts/init_skill_internal.sh feipi-coding-react
  bash scripts/init_skill_internal.sh gen-api-tests --resources scripts,references
  bash scripts/init_skill_internal.sh gen-api-tests --target repo
USAGE
}

if [[ $# -lt 1 ]]; then
  usage
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$SKILL_DIR/../.." && pwd)"
TEMPLATES_ROOT="$SKILL_DIR/templates"

SKILL_NAME="$1"
shift

RESOURCES="scripts,references"
TARGET="auto"
# `feipi-<action>-<target...>` 命名里的 action 白名单。
ALLOWED_ACTIONS="coding gen read write analyze review test debug refactor docs data git web ops build deploy migrate automate monitor summarize translate design planning govern skill"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --resources)
      RESOURCES="$2"
      shift 2
      ;;
    --target)
      TARGET="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "未知参数: $1" >&2
      usage
      exit 1
      ;;
  esac
done

normalize_resources() {
  local raw="$1"
  local item=""
  local normalized=()
  local seen="|"

  if [[ -z "$raw" ]]; then
    raw="scripts,references"
  fi

  IFS=',' read -r -a items <<< "$raw"
  for item in "${items[@]}"; do
    item="$(printf "%s" "$item" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')"
    [[ -z "$item" ]] && continue
    case "$item" in
      scripts|references|assets) ;;
      *)
        echo "未知资源类型: $item (仅支持 scripts,references,assets)" >&2
        exit 1
        ;;
    esac
    if [[ "$seen" != *"|$item|"* ]]; then
      normalized+=("$item")
      seen="${seen}${item}|"
    fi
  done

  if [[ "$seen" != *"|scripts|"* ]]; then
    normalized=("scripts" "${normalized[@]}")
  fi

  local joined=""
  for item in "${normalized[@]}"; do
    if [[ -n "$joined" ]]; then
      joined+=","
    fi
    joined+="$item"
  done
  printf "%s" "$joined"
}

resolve_target_root() {
  local target="$1"
  case "$target" in
    auto)
      if [[ -d "$REPO_ROOT/skills" ]]; then
        echo "$REPO_ROOT/skills"
      else
        echo "$REPO_ROOT/.agents/skills"
      fi
      ;;
    skills)
      echo "$REPO_ROOT/skills"
      ;;
    repo)
      echo "$REPO_ROOT/.agents/skills"
      ;;
    /*)
      echo "$target"
      ;;
    *)
      echo "$REPO_ROOT/$target"
      ;;
  esac
}

SKILLS_ROOT="$(resolve_target_root "$TARGET")"

if [[ ! "$SKILL_NAME" =~ ^[a-z0-9-]{1,64}$ ]]; then
  echo "Skill 名称必须匹配 ^[a-z0-9-]{1,64}$" >&2
  exit 1
fi

if [[ "$SKILL_NAME" != feipi-* ]]; then
  # 自动补全前缀，兼容 `make new SKILL=gen-api-tests` 这种输入。
  SKILL_NAME="feipi-$SKILL_NAME"
fi

if [[ ${#SKILL_NAME} -gt 64 ]]; then
  echo "补全前缀后名称超过 64 字符: $SKILL_NAME" >&2
  exit 1
fi

if [[ "$SKILL_NAME" =~ (anthropic|claude) ]]; then
  echo "Skill 名称不能包含保留词 anthropic 或 claude" >&2
  exit 1
fi

IFS='-' read -r -a TOKENS <<< "$SKILL_NAME"
if [[ ${#TOKENS[@]} -lt 3 ]]; then
  echo "Skill 名称必须符合 feipi-<action>-<target...>，例如 feipi-coding-react" >&2
  exit 1
fi

# 第二段是 action，必须在白名单里。
ACTION="${TOKENS[1]}"
if ! printf "%s\n" "$ALLOWED_ACTIONS" | tr ' ' '\n' | rg -qx "$ACTION"; then
  echo "不支持的 action: $ACTION" >&2
  echo "允许的 action: $ALLOWED_ACTIONS" >&2
  exit 1
fi

ROOT_DIR="$SKILLS_ROOT/$SKILL_NAME"
if [[ -e "$ROOT_DIR" ]]; then
  echo "目标目录已存在: $ROOT_DIR" >&2
  exit 1
fi

RESOURCES="$(normalize_resources "$RESOURCES")"

mkdir -p "$ROOT_DIR/agents"

TITLE="${SKILL_NAME}（待补中文名）"
DESCRIPTION="处理相关任务并输出可验证结果。在用户提出对应场景需求时使用。"

sed \
  -e "s/{{SKILL_NAME}}/$SKILL_NAME/g" \
  -e "s/{{SKILL_DESCRIPTION}}/$DESCRIPTION/g" \
  -e "s/{{TITLE}}/$TITLE/g" \
  "$TEMPLATES_ROOT/SKILL.template.md" > "$ROOT_DIR/SKILL.md"

DISPLAY_NAME="$TITLE"
SHORT_DESCRIPTION="使用中文完成任务，并提供可验证交付结果。"
DEFAULT_PROMPT="请先确认用户目标、输入、边界和成功标准，再按 Explore -> Plan -> Implement -> Verify 执行；输出需包含验证步骤、验证结果和剩余风险。"

sed \
  -e "s/{{DISPLAY_NAME}}/$DISPLAY_NAME/g" \
  -e "s/{{SHORT_DESCRIPTION}}/$SHORT_DESCRIPTION/g" \
  -e "s/{{DEFAULT_PROMPT}}/$DEFAULT_PROMPT/g" \
  "$TEMPLATES_ROOT/openai.template.yaml" > "$ROOT_DIR/agents/openai.yaml"

if [[ -n "$RESOURCES" ]]; then
  # 根据参数创建可选资源目录。
  IFS=',' read -r -a ARR <<< "$RESOURCES"
  for r in "${ARR[@]}"; do
    mkdir -p "$ROOT_DIR/$r"
  done
fi

sed \
  -e "s/{{SKILL_NAME}}/$SKILL_NAME/g" \
  "$TEMPLATES_ROOT/test.template.sh" > "$ROOT_DIR/scripts/test.sh"
chmod +x "$ROOT_DIR/scripts/test.sh"

if [[ "$SKILLS_ROOT" == "$REPO_ROOT" ]]; then
  ROOT_DISPLAY="."
elif [[ "$SKILLS_ROOT" == "$REPO_ROOT/"* ]]; then
  ROOT_DISPLAY="${SKILLS_ROOT#$REPO_ROOT/}"
else
  ROOT_DISPLAY="$SKILLS_ROOT"
fi

echo "已初始化: $ROOT_DISPLAY/$SKILL_NAME"
