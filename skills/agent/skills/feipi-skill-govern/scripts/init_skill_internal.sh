#!/usr/bin/env bash
set -euo pipefail

# 使用当前 skill 本地模板初始化一个新 skill。
# 脚本会执行 v2 命名规则与领域校验，并创建：
# - SKILL.md
# - agents/openai.yaml
# - tests/run.sh
# - <target_skill>/maintenance/README.md 与术语表
# - assets/ 下的初始图稿，以及用户明确选择的资源目录

usage() {
  cat <<'USAGE'
用法:
  bash scripts/init_skill_internal.sh <skill-name> [--resources scripts,references,assets] [--domain <领域>] [--subdomain <子领域>] [--target auto|skills|repo|<path>]

示例:
  bash scripts/init_skill_internal.sh video-read-youtube --domain media --subdomain video
  bash scripts/init_skill_internal.sh feipi-video-read-youtube --resources scripts,references,assets --domain media --subdomain video
  temp_dir="$(mktemp -d)"
  bash scripts/init_skill_internal.sh report-generate-brief --domain content --target "$temp_dir/skills"
USAGE
}

if [[ $# -lt 1 ]]; then
  usage
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
source "$SCRIPT_DIR/skill_identity.sh"
REPO_ROOT="$(skill_repo_root "$SKILL_DIR")"
TEMPLATES_ROOT="$SKILL_DIR/templates"

SKILL_NAME_INPUT="$1"
shift

RESOURCES=""
TARGET="auto"
DOMAIN=""
SUBDOMAIN=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --resources)
      if [[ $# -lt 2 ]]; then echo "--resources 缺少参数值" >&2; exit 1; fi
      RESOURCES="$2"
      shift 2
      ;;
    --domain)
      if [[ $# -lt 2 || "$2" == --* ]]; then echo "--domain 缺少参数值" >&2; exit 1; fi
      DOMAIN="$2"
      shift 2
      ;;
    --subdomain)
      if [[ $# -lt 2 || "$2" == --* ]]; then echo "--subdomain 缺少参数值" >&2; exit 1; fi
      SUBDOMAIN="$2"
      shift 2
      ;;
    --target)
      if [[ $# -lt 2 ]]; then echo "--target 缺少参数值" >&2; exit 1; fi
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
  local normalized=""
  local seen="|"
  local IFS=','

  for item in $raw; do
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
      if [[ -n "$normalized" ]]; then
        normalized+=","
      fi
      normalized+="$item"
      seen="${seen}${item}|"
    fi
  done

  printf "%s" "$normalized"
}

normalize_skill_name() {
  local name="$1"
  if [[ "$name" == feipi-* ]]; then
    printf "%s" "$name"
  else
    printf "feipi-%s" "$name"
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

target_requires_domain() {
  local target_root="$1"
  if [[ "$target_root" == */skills && "$target_root" != */.agents/skills ]]; then
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


SKILLS_ROOT="$(resolve_target_root "$TARGET")"
if target_requires_domain "$SKILLS_ROOT" && [[ -z "$DOMAIN" ]]; then
  echo "目标根目录要求提供 --domain，路径需落到 skills/<领域>/[<子领域>/]<Skill ID>/" >&2
  exit 1
fi

if [[ -n "$SUBDOMAIN" && -z "$DOMAIN" ]]; then
  echo "--subdomain 需要同时提供 --domain" >&2
  exit 1
fi
ROOT_DIR="$SKILLS_ROOT"
if [[ -n "$DOMAIN" ]]; then
  validate_skill_classification "$DOMAIN"
  ROOT_DIR="$ROOT_DIR/$DOMAIN"
fi
if [[ -n "$SUBDOMAIN" ]]; then
  validate_skill_classification "$SUBDOMAIN"
  ROOT_DIR="$ROOT_DIR/$SUBDOMAIN"
fi
ROOT_DIR="$ROOT_DIR/$SKILL_NAME"

if [[ -e "$ROOT_DIR" ]]; then
  echo "目标目录已存在: $ROOT_DIR" >&2
  exit 1
fi

RESOURCES="$(normalize_resources "$RESOURCES")"

if ! command -v python3 >/dev/null 2>&1; then
  echo "缺少依赖：python3（用于解析 Skill 图标路径）" >&2
  exit 1
fi
ICON_LINK="$(python3 - "$SCRIPT_DIR" "$ROOT_DIR" <<'PYTHON'
import os
from pathlib import Path
import sys

sys.path.insert(0, sys.argv[1])
from validate_host_metadata import source_library

skill = Path(sys.argv[2]).resolve()
library = source_library(skill)
if library is not None:
    icon = library / "code.png"
    if not icon.is_file():
        sys.exit(f"图库缺少初始化图标：{icon}")
    print(os.path.relpath(icon, skill / "assets"))
PYTHON
)"

mkdir -p "$ROOT_DIR/agents" "$ROOT_DIR/assets" "$ROOT_DIR/tests" "$ROOT_DIR/maintenance"
if [[ -n "$ICON_LINK" ]]; then
  ln -s "$ICON_LINK" "$ROOT_DIR/assets/code.png"
else
  cp -L "$TEMPLATES_ROOT/code.png" "$ROOT_DIR/assets/"
fi

for name in README terminology; do
  sed -e "s/{{SKILL_NAME}}/$SKILL_NAME/g" \
    "$TEMPLATES_ROOT/maintenance-${name}.template.md" > "$ROOT_DIR/maintenance/${name}.md"
done

TITLE="${SKILL_NAME}（待补中文名）"
DESCRIPTION="用于处理对应领域任务并输出可验证结果；在用户提出匹配场景需求时使用。"
DISABLE_MODEL_INVOCATION=false
ALLOW_IMPLICIT_INVOCATION=true
if [[ "$SKILL_NAME" == *-mode ]]; then
  DISABLE_MODEL_INVOCATION=true
  ALLOW_IMPLICIT_INVOCATION=false
fi

sed \
  -e "s/{{SKILL_NAME}}/$SKILL_NAME/g" \
  -e "s/{{SKILL_DESCRIPTION}}/$DESCRIPTION/g" \
  -e "s/{{DISABLE_MODEL_INVOCATION}}/$DISABLE_MODEL_INVOCATION/g" \
  -e "s/{{TITLE}}/$TITLE/g" \
  "$TEMPLATES_ROOT/SKILL.template.md" > "$ROOT_DIR/SKILL.md"

DISPLAY_NAME="$TITLE"
SHORT_DESCRIPTION="使用中文完成目标任务，并输出可核验交付结果。"
DEFAULT_PROMPT="请使用 \$$SKILL_NAME 完成目标任务；按入口的功能规约交付可核对的业务结果，输入不足时说明具体缺口，并如实区分已验证结果和未验证项。"

sed \
  -e "s/{{DISPLAY_NAME}}/$DISPLAY_NAME/g" \
  -e "s/{{SHORT_DESCRIPTION}}/$SHORT_DESCRIPTION/g" \
  -e "s/{{DEFAULT_PROMPT}}/$DEFAULT_PROMPT/g" \
  -e "s/{{ALLOW_IMPLICIT_INVOCATION}}/$ALLOW_IMPLICIT_INVOCATION/g" \
  "$TEMPLATES_ROOT/openai.template.yaml" > "$ROOT_DIR/agents/openai.yaml"

for r in scripts references assets; do
  case ",$RESOURCES," in
    *",$r,"*) mkdir -p "$ROOT_DIR/$r" ;;
  esac
done

sed \
  -e "s/{{SKILL_NAME}}/$SKILL_NAME/g" \
  "$TEMPLATES_ROOT/tests-run.template.sh" > "$ROOT_DIR/tests/run.sh"
chmod +x "$ROOT_DIR/tests/run.sh"

echo "已初始化: $(relative_display_path "$ROOT_DIR")"
echo "这是待完善的脚手架；请核对调用策略、颜色与图标，并补齐功能规约、业务案例与实际验证。"
