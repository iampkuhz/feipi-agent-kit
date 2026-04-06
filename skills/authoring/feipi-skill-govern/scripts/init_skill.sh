#!/usr/bin/env bash
set -euo pipefail

# feipi-skill-govern 的本地初始化封装（标准入口）。
# 目标：使用当前 skill 本地模板和脚本初始化新 skill，不依赖仓库级共享实现。

usage() {
  cat <<'USAGE'
用法:
  bash scripts/init_skill.sh <skill-name> [--resources scripts,references,assets] [--layer <layer>] [--target auto|skills|repo|<path>]

兼容旧位置参数:
  bash scripts/init_skill.sh <skill-name> [resources] [target]

示例:
  bash scripts/init_skill.sh video-read-youtube --layer integration
  bash scripts/init_skill.sh patent-generate-innovation-disclosure --resources scripts,references,assets --layer authoring
  bash scripts/init_skill.sh video-read-youtube scripts,references /tmp/skills
USAGE
}

if [[ $# -lt 1 ]]; then
  usage
  exit 1
fi

if [[ "$1" == "-h" || "$1" == "--help" ]]; then
  usage
  exit 0
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$SKILL_DIR/../../.." && pwd)"
INIT_INTERNAL="$SCRIPT_DIR/init_skill_internal.sh"
VALIDATE_SCRIPT="$SCRIPT_DIR/validate.sh"

if [[ ! -x "$INIT_INTERNAL" ]]; then
  echo "缺少内部初始化脚本：$INIT_INTERNAL" >&2
  exit 1
fi

if [[ ! -x "$VALIDATE_SCRIPT" ]]; then
  echo "缺少本地校验脚本：$VALIDATE_SCRIPT" >&2
  exit 1
fi

SKILL_INPUT="$1"
shift

RESOURCES_INPUT="scripts,references"
TARGET_INPUT="auto"
LAYER_INPUT=""
POSITIONAL_RESOURCES_USED=0
POSITIONAL_TARGET_USED=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --resources)
      RESOURCES_INPUT="$2"
      shift 2
      ;;
    --layer)
      LAYER_INPUT="$2"
      shift 2
      ;;
    --target)
      TARGET_INPUT="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      if [[ "$POSITIONAL_RESOURCES_USED" -eq 0 ]]; then
        RESOURCES_INPUT="$1"
        POSITIONAL_RESOURCES_USED=1
        shift
      elif [[ "$POSITIONAL_TARGET_USED" -eq 0 ]]; then
        TARGET_INPUT="$1"
        POSITIONAL_TARGET_USED=1
        shift
      else
        echo "未知参数: $1" >&2
        usage
        exit 1
      fi
      ;;
  esac
done

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

target_requires_layer() {
  local target_root="$1"
  if [[ "$target_root" == "$REPO_ROOT/skills" || "$target_root" == */skills ]]; then
    return 0
  fi
  return 1
}

SKILL_NAME="$(normalize_skill_name "$SKILL_INPUT")"
TARGET_ROOT="$(resolve_target_root "$TARGET_INPUT")"

if target_requires_layer "$TARGET_ROOT" && [[ -z "$LAYER_INPUT" ]]; then
  echo "目标根目录要求提供 --layer，路径需落到 skills/<layer>/<skill-name>/" >&2
  exit 1
fi

if [[ -n "$LAYER_INPUT" ]]; then
  TARGET_SKILL_DIR="$TARGET_ROOT/$LAYER_INPUT/$SKILL_NAME"
else
  TARGET_SKILL_DIR="$TARGET_ROOT/$SKILL_NAME"
fi

echo "=== 初始化 skill: $SKILL_NAME ==="
echo "资源：$RESOURCES_INPUT"
if [[ -n "$LAYER_INPUT" ]]; then
  echo "layer：$LAYER_INPUT"
else
  echo "layer：<无>"
fi
echo "目标根目录：$TARGET_ROOT"

CMD=(bash "$INIT_INTERNAL" "$SKILL_INPUT" --resources "$RESOURCES_INPUT" --target "$TARGET_INPUT")
if [[ -n "$LAYER_INPUT" ]]; then
  CMD+=(--layer "$LAYER_INPUT")
fi
"${CMD[@]}"

bash "$VALIDATE_SCRIPT" "$TARGET_SKILL_DIR" >/dev/null
echo "初始化并校验完成：$TARGET_SKILL_DIR"
