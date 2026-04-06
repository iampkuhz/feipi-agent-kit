#!/usr/bin/env bash
set -euo pipefail

# 使用当前 skill 本地模板初始化一个新 skill。
# 脚本会执行 v2 命名规则与 layer 校验，并创建：
# - SKILL.md
# - agents/openai.yaml
# - scripts/test.sh
# - 可选资源目录（references/assets）

usage() {
  cat <<'USAGE'
用法:
  bash scripts/init_skill_internal.sh <skill-name> [--resources scripts,references,assets] [--layer <layer>] [--target auto|skills|repo|<path>]

示例:
  bash scripts/init_skill_internal.sh video-read-youtube --layer integration
  bash scripts/init_skill_internal.sh feipi-video-read-youtube --resources scripts,references,assets --layer integration
  bash scripts/init_skill_internal.sh patent-generate-innovation-disclosure --layer authoring --target /tmp/skills
USAGE
}

if [[ $# -lt 1 ]]; then
  usage
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$SKILL_DIR/../../.." && pwd)"
TEMPLATES_ROOT="$SKILL_DIR/templates"

SKILL_NAME_INPUT="$1"
shift

RESOURCES="scripts,references"
TARGET="auto"
LAYER=""
ALLOWED_LAYERS="authoring diagram integration platform"
DISCOURAGED_ACTIONS="web ops automate misc helper utils tools temp tmp skill"
LEGACY_ACTION_HINTS="read write summarize review analyze test debug refactor generate gen configure send plan planning design build deploy migrate translate govern code coding docs"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --resources)
      RESOURCES="$2"
      shift 2
      ;;
    --layer)
      LAYER="$2"
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

normalize_skill_name() {
  local name="$1"
  if [[ "$name" == feipi-* ]]; then
    printf "%s" "$name"
  else
    printf "feipi-%s" "$name"
  fi
}

validate_skill_name() {
  local name="$1"
  local domain=""
  local action=""

  if [[ ! "$name" =~ ^[a-z0-9-]{1,64}$ ]]; then
    echo "Skill 名称必须匹配 ^[a-z0-9-]{1,64}$" >&2
    exit 1
  fi

  if [[ "$name" != feipi-* ]]; then
    echo "Skill 名称必须以 feipi- 开头：$name" >&2
    exit 1
  fi

  if printf "%s" "$name" | rg -qi '(anthropic|claude)'; then
    echo "Skill 名称不能包含保留词 anthropic 或 claude" >&2
    exit 1
  fi

  if [[ "$name" == "feipi-skill-govern" ]]; then
    return 0
  fi

  IFS='-' read -r -a tokens <<< "$name"
  if [[ ${#tokens[@]} -lt 4 ]]; then
    echo "Skill 名称必须符合 feipi-<domain>-<action>-<object...>，例如 feipi-video-read-youtube" >&2
    exit 1
  fi

  domain="${tokens[1]}"
  action="${tokens[2]}"
  if printf "%s\n" "$LEGACY_ACTION_HINTS" | tr ' ' '\n' | rg -qx "$domain"; then
    echo "检测到旧 action-first 命名痕迹：第二段像 action，请先确定 domain 再命名" >&2
    exit 1
  fi
  if printf "%s\n" "$DISCOURAGED_ACTIONS" | tr ' ' '\n' | rg -qx "$action"; then
    echo "action 不能使用低语义词：$action" >&2
    echo "请使用真正的动词原形，例如 read、generate、summarize、configure、send" >&2
    exit 1
  fi
}

validate_layer() {
  local layer="$1"
  if [[ -z "$layer" ]]; then
    return 0
  fi
  if ! printf "%s\n" "$ALLOWED_LAYERS" | tr ' ' '\n' | rg -qx "$layer"; then
    echo "不支持的 layer: $layer" >&2
    echo "允许的 layer: $ALLOWED_LAYERS" >&2
    exit 1
  fi
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

target_requires_layer() {
  local target_root="$1"
  if [[ "$target_root" == "$REPO_ROOT/skills" || "$target_root" == */skills ]]; then
    return 0
  fi
  return 1
}

relative_display_path() {
  local abs_path="$1"
  if [[ "$abs_path" == "$REPO_ROOT" ]]; then
    printf "."
  elif [[ "$abs_path" == "$REPO_ROOT/"* ]]; then
    printf "%s" "${abs_path#$REPO_ROOT/}"
  else
    printf "%s" "$abs_path"
  fi
}

SKILL_NAME="$(normalize_skill_name "$SKILL_NAME_INPUT")"
validate_skill_name "$SKILL_NAME"
validate_layer "$LAYER"

SKILLS_ROOT="$(resolve_target_root "$TARGET")"
if target_requires_layer "$SKILLS_ROOT" && [[ -z "$LAYER" ]]; then
  echo "目标根目录要求提供 --layer，路径需落到 skills/<layer>/<skill-name>/" >&2
  exit 1
fi

if [[ -n "$LAYER" ]]; then
  ROOT_DIR="$SKILLS_ROOT/$LAYER/$SKILL_NAME"
else
  ROOT_DIR="$SKILLS_ROOT/$SKILL_NAME"
fi

if [[ -e "$ROOT_DIR" ]]; then
  echo "目标目录已存在: $ROOT_DIR" >&2
  exit 1
fi

RESOURCES="$(normalize_resources "$RESOURCES")"

mkdir -p "$ROOT_DIR/agents" "$ROOT_DIR/scripts"

TITLE="${SKILL_NAME}（待补中文名）"
DESCRIPTION="用于处理对应领域任务并输出可验证结果；在用户提出匹配场景需求时使用。"

sed \
  -e "s/{{SKILL_NAME}}/$SKILL_NAME/g" \
  -e "s/{{SKILL_DESCRIPTION}}/$DESCRIPTION/g" \
  -e "s/{{TITLE}}/$TITLE/g" \
  "$TEMPLATES_ROOT/SKILL.template.md" > "$ROOT_DIR/SKILL.md"

DISPLAY_NAME="$TITLE"
SHORT_DESCRIPTION="使用中文完成目标任务，并输出可核验交付结果。"
DEFAULT_PROMPT="请先确认用户目标、输入、边界和成功标准，再按 Explore -> Plan -> Implement -> Verify 执行；默认只读取必要上下文，优先复用本 skill 本地 scripts、references、assets，输出需包含验证步骤、验证结果和剩余风险。"

sed \
  -e "s/{{DISPLAY_NAME}}/$DISPLAY_NAME/g" \
  -e "s/{{SHORT_DESCRIPTION}}/$SHORT_DESCRIPTION/g" \
  -e "s/{{DEFAULT_PROMPT}}/$DEFAULT_PROMPT/g" \
  "$TEMPLATES_ROOT/openai.template.yaml" > "$ROOT_DIR/agents/openai.yaml"

IFS=',' read -r -a ARR <<< "$RESOURCES"
for r in "${ARR[@]}"; do
  mkdir -p "$ROOT_DIR/$r"
done

sed \
  -e "s/{{SKILL_NAME}}/$SKILL_NAME/g" \
  "$TEMPLATES_ROOT/test.template.sh" > "$ROOT_DIR/scripts/test.sh"
chmod +x "$ROOT_DIR/scripts/test.sh"

echo "已初始化: $(relative_display_path "$ROOT_DIR")"
