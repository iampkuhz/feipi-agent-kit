#!/bin/bash

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
MANIFEST_DIR="$REPO_DIR/skill-list"
OPENCLAW_STATE_ROOT="$HOME/.openclaw"
MANAGED_SKILLS_DIR="$OPENCLAW_STATE_ROOT/skills"
TEMP_PARENT="$(cd "${TMPDIR:-/tmp}" && pwd -P)"
MANIFEST_INPUT=""
DRY_RUN=0
ASSUME_YES=0
TEMP_ROOT=""

usage() {
  cat <<'EOF'
用法：
  scripts/bootstrap.sh
  scripts/bootstrap.sh --manifest skill-list/feipi-video-read-url.json
  scripts/bootstrap.sh [--manifest FILE] [--dry-run] [--yes]

默认读取 skill-list/*.json 并同步全部 skill。安装目标不可配置，始终为
~/.openclaw/skills/<skill-name>。

参数：
  --manifest FILE  只处理一个仓库内的 skill manifest
  --dry-run        下载来源并显示计划，不修改 ~/.openclaw/skills
  --yes            跳过执行前确认；适合非交互调用
  -h, --help       显示帮助
EOF
}

cleanup() {
  if [[ -n "$TEMP_ROOT" && -d "$TEMP_ROOT" ]]; then
    case "$TEMP_ROOT" in
      "$TEMP_PARENT"/feipi-openclaw-skills.*)
        find "$TEMP_ROOT" -depth -delete 2>/dev/null || true
        ;;
    esac
  fi
}
trap cleanup EXIT

read_skill_slug() {
  local skill_file="$1"
  local slug

  slug="$(awk '
    NR == 1 {
      sub(/\r$/, "")
      if ($0 != "---") exit 1
      in_frontmatter = 1
      next
    }
    in_frontmatter && /^---[[:space:]]*$/ { exit }
    in_frontmatter && /^name:[[:space:]]*/ {
      sub(/^name:[[:space:]]*/, "")
      sub(/[[:space:]]+$/, "")
      print
      found = 1
      exit
    }
    END { if (!found) exit 1 }
  ' "$skill_file" 2>/dev/null)" || return 1

  slug="${slug#\"}"
  slug="${slug%\"}"
  slug="${slug#\'}"
  slug="${slug%\'}"
  printf '%s\n' "$slug"
}

is_safe_subdirectory() {
  local path_value="$1"
  [[ -n "$path_value" ]] || return 1
  [[ "$path_value" != /* ]] || return 1
  [[ "$path_value" != ".." && "$path_value" != ../* ]] || return 1
  [[ "$path_value" != */../* && "$path_value" != */.. ]] || return 1
  [[ "$path_value" != *\\* ]] || return 1
}

origin_matches_manifest() {
  local origin_file="$1"
  local slug="$2"
  local repository="$3"
  local ref="$4"
  local commit="$5"
  local subdirectory="$6"
  local manifest_path="$7"
  local source_tree_hash="${8:-}"

  [[ -f "$origin_file" ]] || return 1
  jq -e \
    --arg slug "$slug" \
    --arg repository "$repository" \
    --arg ref "$ref" \
    --arg commit "$commit" \
    --arg subdirectory "$subdirectory" \
    --arg manifest "$manifest_path" \
    --arg sourceTreeHash "$source_tree_hash" \
    '.version == 1
      and .source == "git"
      and .slug == $slug
      and .git.url == $repository
      and .git.ref == $ref
      and .git.commit == $commit
      and .subdirectory == $subdirectory
      and .manifest == $manifest
      and (.git.sourceTreeSha256 // "") == $sourceTreeHash' \
    "$origin_file" >/dev/null 2>&1
}

write_manifest_origin() {
  local target_dir="$1"
  local slug="$2"
  local repository="$3"
  local ref="$4"
  local commit="$5"
  local subdirectory="$6"
  local manifest_path="$7"
  local source_tree_hash="${8:-}"
  local origin_dir="$target_dir/.openclaw"
  local origin_file="$origin_dir/source-origin.json"
  local origin_tmp

  mkdir -p "$origin_dir"
  origin_tmp="$(mktemp "$origin_dir/source-origin.json.XXXXXX")" || return 1
  if ! jq -n \
    --arg slug "$slug" \
    --arg repository "$repository" \
    --arg ref "$ref" \
    --arg commit "$commit" \
    --arg subdirectory "$subdirectory" \
    --arg manifest "$manifest_path" \
    --arg sourceTreeHash "$source_tree_hash" \
    '{
      version: 1,
      source: "git",
      spec: ($repository + "#" + $ref + ":" + $subdirectory),
      slug: $slug,
      installedAt: (now * 1000 | floor),
      git: {
        url: $repository,
        ref: $ref,
        commit: $commit,
        workingTreeSource: ($sourceTreeHash != ""),
        sourceTreeSha256: $sourceTreeHash,
        resolvedAt: (now | todateiso8601)
      },
      subdirectory: $subdirectory,
      manifest: $manifest
    }' >"$origin_tmp"; then
    unlink "$origin_tmp" 2>/dev/null || true
    return 1
  fi
  chmod 644 "$origin_tmp"
  mv "$origin_tmp" "$origin_file"
}

DIFF_EXCLUDES=(
  -x .openclaw
  -x .clawhub
  -x .clawdhub
  -x .git
  -x .DS_Store
  -x node_modules
  -x __pycache__
  -x .pytest_cache
  -x .mypy_cache
  -x .ruff_cache
  -x .venv
  -x venv
  -x output
  -x '*.pyc'
)

while [[ $# -gt 0 ]]; do
  case "$1" in
    --manifest)
      if [[ $# -lt 2 ]]; then
        echo "--manifest 缺少文件参数。" >&2
        exit 2
      fi
      MANIFEST_INPUT="$2"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --yes)
      ASSUME_YES=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "未知参数：$1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

for command_name in git jq shasum; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "未检测到命令：$command_name" >&2
    exit 1
  fi
done
if [[ "$DRY_RUN" -eq 0 ]] && ! command -v openclaw >/dev/null 2>&1; then
  echo "未检测到 openclaw，无法安装 skill。" >&2
  exit 1
fi

manifest_files=()
if [[ -n "$MANIFEST_INPUT" ]]; then
  if [[ "$MANIFEST_INPUT" != /* ]]; then
    MANIFEST_INPUT="$REPO_DIR/$MANIFEST_INPUT"
  fi
  if [[ ! -f "$MANIFEST_INPUT" ]]; then
    echo "skill manifest 不存在：$MANIFEST_INPUT" >&2
    exit 1
  fi
  MANIFEST_INPUT="$(cd "$(dirname "$MANIFEST_INPUT")" && pwd -P)/$(basename "$MANIFEST_INPUT")"
  case "$MANIFEST_INPUT" in
    "$MANIFEST_DIR"/*.json) ;;
    *)
      echo "只允许使用仓库 skill-list/ 下的 manifest：$MANIFEST_INPUT" >&2
      exit 1
      ;;
  esac
  manifest_files+=("$MANIFEST_INPUT")
else
  while IFS= read -r manifest_file; do
    manifest_files+=("$manifest_file")
  done < <(find "$MANIFEST_DIR" -maxdepth 1 -type f -name '*.json' -print | LC_ALL=C sort)
fi

if [[ "${#manifest_files[@]}" -eq 0 ]]; then
  echo "skill-list/ 中没有安装 manifest。" >&2
  exit 1
fi

TEMP_ROOT="$(mktemp -d "$TEMP_PARENT/feipi-openclaw-skills.XXXXXX")" || exit 1
mkdir -p "$TEMP_ROOT/repos"

skill_names=()
repositories=()
refs=()
subdirectories=()
manifest_paths=()
npm_installs=()
required_env_sets=()
source_dirs=()
commits=()
source_tree_hashes=()
actions=()
seen_names="|"

echo "读取 skill manifests 并下载 Git 来源..."

for manifest_file in "${manifest_files[@]}"; do
  manifest_path="${manifest_file#$REPO_DIR/}"
  if ! jq -e '
    (if has("enabled") then .enabled else true end) as $enabled
    | .version == 1
    and (.name | type == "string" and length > 0)
    and (.source | type == "object")
    and (.source.type == "git-subdirectory")
    and (.source.repository | type == "string" and length > 0)
    and (.source.ref | type == "string" and length > 0)
    and (.source.path | type == "string" and length > 0)
    and ($enabled | type == "boolean")
    and (($enabled == true) or (.disabledReason | type == "string" and length > 0))
    and ((.setup // {}) | type == "object")
    and ((.setup.npmInstall // false) | type == "boolean")
    and ((.setup.useLocalWorkingTree // false) | type == "boolean")
    and ((.runtime.requiredEnv // []) | type == "array")
    and all((.runtime.requiredEnv // [])[];
      type == "string" and test("^[A-Z_][A-Z0-9_]*$")
    )
  ' "$manifest_file" >/dev/null; then
    echo "无效的 skill manifest：$manifest_path" >&2
    exit 1
  fi

  slug="$(jq -r '.name' "$manifest_file")"
  repository="$(jq -r '.source.repository' "$manifest_file")"
  ref="$(jq -r '.source.ref' "$manifest_file")"
  subdirectory="$(jq -r '.source.path' "$manifest_file")"
  npm_install="$(jq -r '.setup.npmInstall // false' "$manifest_file")"
  use_local_working_tree="$(jq -r '.setup.useLocalWorkingTree // false' "$manifest_file")"
  required_env_json="$(jq -c '.runtime.requiredEnv // []' "$manifest_file")"
  enabled="$(jq -r 'if has("enabled") then .enabled else true end' "$manifest_file")"

  if [[ ! "$slug" =~ ^[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?$ ]]; then
    echo "manifest 中的 skill name 无效：$slug ($manifest_path)" >&2
    exit 1
  fi
  case "$seen_names" in
    *"|$slug|"*)
      echo "skill-list 中存在重复 name：$slug" >&2
      exit 1
      ;;
  esac
  seen_names="${seen_names}${slug}|"
  if [[ "$repository" == -* || "$repository" == *$'\n'* ]]; then
    echo "manifest 中的 Git repository 不安全：$manifest_path" >&2
    exit 1
  fi
  if [[ "$ref" == -* || "$ref" == *$'\n'* ]]; then
    echo "manifest 中的 Git ref 不安全：$manifest_path" >&2
    exit 1
  fi
  if ! is_safe_subdirectory "$subdirectory"; then
    echo "manifest 中的 Git 子目录不安全：$subdirectory ($manifest_path)" >&2
    exit 1
  fi

  if [[ "$enabled" == "false" ]]; then
    reason="$(jq -r '.disabledReason // "未说明原因"' "$manifest_file")"
    printf '  disabled %-48s %s\n' "$slug" "$reason"
    continue
  fi

  repo_key="$(printf '%s\n%s\n' "$repository" "$ref" | shasum -a 256 | awk '{print substr($1, 1, 20)}')"
  checkout_dir="$TEMP_ROOT/repos/$repo_key"
  if [[ "$use_local_working_tree" == "true" ]]; then
    if [[ "$repository" != /* || ! -d "$repository/.git" ]]; then
      echo "useLocalWorkingTree 仅支持声明的本地 Git 仓库。" >&2
      exit 1
    fi
    if [[ "$(git -C "$repository" symbolic-ref --quiet --short HEAD)" != "$ref" ]]; then
      echo "本地工作树当前分支与 manifest ref 不一致：$manifest_path" >&2
      exit 1
    fi
    checkout_dir="$repository"
    echo "  local working tree $repository @ $ref"
  elif [[ ! -d "$checkout_dir/.git" ]]; then
    echo "  clone $repository @ $ref"
    if [[ "$ref" =~ ^[0-9a-fA-F]{40}$ ]]; then
      # clone --branch 只接受分支/标签；固定 commit 需显式 fetch。
      git init --quiet "$checkout_dir"
      git -C "$checkout_dir" remote add origin "$repository"
      if ! git -C "$checkout_dir" fetch --quiet --depth 1 origin "$ref" \
        || ! git -C "$checkout_dir" checkout --quiet --detach FETCH_HEAD; then
        echo "无法下载 Git commit：$repository @ $ref" >&2
        exit 1
      fi
    elif ! git clone --quiet --depth 1 --branch "$ref" "$repository" "$checkout_dir"; then
      echo "无法下载 Git 来源：$repository @ $ref" >&2
      exit 1
    fi
  fi
  checkout_dir="$(cd "$checkout_dir" && pwd -P)"
  source_candidate="$checkout_dir/$subdirectory"
  if [[ ! -f "$source_candidate/SKILL.md" ]]; then
    echo "Git 子目录缺少 SKILL.md：$repository#$ref:$subdirectory" >&2
    exit 1
  fi
  source_dir="$(cd "$source_candidate" && pwd -P)"
  case "$source_dir/" in
    "$checkout_dir"/*) ;;
    *)
      echo "Git skill 子目录逃逸 checkout：$manifest_path" >&2
      exit 1
      ;;
  esac

  source_slug="$(read_skill_slug "$source_dir/SKILL.md")" || {
    echo "来源 SKILL.md 缺少 name：$manifest_path" >&2
    exit 1
  }
  if [[ "$source_slug" != "$slug" ]]; then
    echo "manifest name 与 SKILL.md 不一致：$slug != $source_slug ($manifest_path)" >&2
    exit 1
  fi

  # 安装包只保留运行资源；测试、评估与临时产物不分发到运行目录。
  runtime_source_dir="$TEMP_ROOT/runtime/$slug"
  mkdir -p "$runtime_source_dir"
  cp -R "$source_dir/." "$runtime_source_dir/"
  for development_dir in tests evals tmp; do
    if [[ -e "$runtime_source_dir/$development_dir" || -L "$runtime_source_dir/$development_dir" ]]; then
      find "$runtime_source_dir/$development_dir" -depth -delete
    fi
  done
  find "$runtime_source_dir" -type d -name __pycache__ -prune -exec rm -rf {} +
  source_tree_hash=""
  if [[ "$use_local_working_tree" == "true" ]]; then
    source_tree_hash="$(python3 - "$runtime_source_dir" <<'PY'
import hashlib
from pathlib import Path
import sys
root = Path(sys.argv[1])
value = hashlib.sha256()
for path in sorted(p for p in root.rglob('*') if p.is_file()):
    value.update(str(path.relative_to(root)).encode())
    value.update(b'\0')
    value.update(hashlib.sha256(path.read_bytes()).digest())
print(value.hexdigest())
PY
)"
  fi

  skill_names+=("$slug")
  repositories+=("$repository")
  refs+=("$ref")
  subdirectories+=("$subdirectory")
  manifest_paths+=("$manifest_path")
  npm_installs+=("$npm_install")
  required_env_sets+=("$required_env_json")
  source_dirs+=("$runtime_source_dir")
  commits+=("$(git -C "$checkout_dir" rev-parse HEAD)")
  source_tree_hashes+=("$source_tree_hash")
done

if [[ "${#skill_names[@]}" -eq 0 ]]; then
  echo "没有启用的 skill manifest。"
  exit 0
fi

echo
echo "manifest 目录：$MANIFEST_DIR"
echo "固定安装目录：$MANAGED_SKILLS_DIR"
echo

add_count=0
update_count=0
skip_count=0
error_count=0
env_warning_count=0

for index in "${!skill_names[@]}"; do
  slug="${skill_names[$index]}"
  source_dir="${source_dirs[$index]}"
  target_dir="$MANAGED_SKILLS_DIR/$slug"
  action=""
  detail=""

  while IFS= read -r env_name; do
    [[ -n "$env_name" ]] || continue
    if [[ -z "${!env_name-}" ]]; then
      echo "[warn]   $slug 运行时缺少环境变量：$env_name"
      env_warning_count=$((env_warning_count + 1))
    fi
  done < <(printf '%s\n' "${required_env_sets[$index]}" | jq -r '.[]')

  if [[ -L "$target_dir" ]]; then
    action="error"
    detail="目标是软链接，拒绝覆盖"
    error_count=$((error_count + 1))
  elif [[ ! -e "$target_dir" ]]; then
    action="add"
    detail="新增"
    add_count=$((add_count + 1))
  elif [[ ! -d "$target_dir" || ! -f "$target_dir/SKILL.md" ]]; then
    action="error"
    detail="目标存在但不是有效 skill，拒绝覆盖"
    error_count=$((error_count + 1))
  else
    if diff -qr "${DIFF_EXCLUDES[@]}" "$source_dir" "$target_dir" >/dev/null 2>&1; then
      if ! origin_matches_manifest \
        "$target_dir/.openclaw/source-origin.json" \
        "$slug" \
        "${repositories[$index]}" \
        "${refs[$index]}" \
        "${commits[$index]}" \
        "${subdirectories[$index]}" \
        "${manifest_paths[$index]}" \
        "${source_tree_hashes[$index]}"; then
        action="update"
        detail="内容一致，更新 Git 来源记录"
        update_count=$((update_count + 1))
      elif [[ "${npm_installs[$index]}" == "true" && ! -d "$target_dir/node_modules" ]]; then
        action="update"
        detail="缺少 manifest 声明的 npm 依赖"
        update_count=$((update_count + 1))
      else
        action="skip"
        detail="内容、Git commit 和安装配置均一致"
        skip_count=$((skip_count + 1))
      fi
    else
      diff_status=$?
      if [[ "$diff_status" -eq 1 ]]; then
        action="update"
        detail="Git 内容有变化"
        update_count=$((update_count + 1))
      else
        action="error"
        detail="无法比较来源与安装目录"
        error_count=$((error_count + 1))
      fi
    fi
  fi

  actions+=("$action")
  printf '%-8s %-48s %s\n' "[$action]" "$slug" "$detail"
  printf '         %s#%s:%s\n' \
    "${repositories[$index]}" "${refs[$index]}" "${subdirectories[$index]}"
  printf '         commit %s -> %s\n' "${commits[$index]}" "$target_dir"
done

echo
printf '计划汇总：新增 %d，更新 %d，跳过 %d，错误 %d，环境警告 %d。\n' \
  "$add_count" "$update_count" "$skip_count" "$error_count" "$env_warning_count"

if [[ "$error_count" -gt 0 ]]; then
  echo "存在不安全或无法判断的目标，本次不执行任何安装。" >&2
  exit 1
fi
if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "dry-run 完成，未修改 ~/.openclaw。"
  exit 0
fi
if [[ $((add_count + update_count)) -eq 0 ]]; then
  echo "所有 manifest 对应 skill 均为最新。"
  exit 0
fi

if [[ "$ASSUME_YES" -eq 0 ]]; then
  if [[ ! -t 0 ]]; then
    echo "非交互执行安装时必须显式添加 --yes。" >&2
    exit 2
  fi
  read -r -p "确认按以上 manifest 写入 ~/.openclaw/skills？[y/N] " answer
  case "$answer" in
    y|Y|yes|YES) ;;
    *)
      echo "已取消，未修改 ~/.openclaw。"
      exit 0
      ;;
  esac
fi

installed_count=0
failed_count=0

for index in "${!skill_names[@]}"; do
  action="${actions[$index]}"
  [[ "$action" == "skip" ]] && continue

  slug="${skill_names[$index]}"
  source_dir="${source_dirs[$index]}"
  target_dir="$MANAGED_SKILLS_DIR/$slug"
  install_args=(skills install "$source_dir" --global --as "$slug")
  [[ "$action" == "update" ]] && install_args+=(--force)

  echo "安装 $slug ..."
  if ! OPENCLAW_STATE_DIR="$OPENCLAW_STATE_ROOT" \
    OPENCLAW_CONFIG_PATH="${OPENCLAW_CONFIG_PATH:-$REPO_DIR/openclaw.json}" \
    openclaw "${install_args[@]}"; then
    failed_count=$((failed_count + 1))
    continue
  fi

  if [[ "${npm_installs[$index]}" == "true" ]]; then
    if ! command -v npm >/dev/null 2>&1; then
      echo "$slug 需要 npm，但当前未检测到 npm。" >&2
      failed_count=$((failed_count + 1))
      continue
    fi
    if [[ ! -f "$target_dir/package-lock.json" ]]; then
      echo "$slug 声明 npmInstall，但安装目录缺少 package-lock.json。" >&2
      failed_count=$((failed_count + 1))
      continue
    fi
    echo "安装 $slug 的 npm 依赖 ..."
    if ! npm ci --omit=dev --ignore-scripts --no-audit --no-fund --prefix "$target_dir"; then
      failed_count=$((failed_count + 1))
      continue
    fi
  fi

  if ! write_manifest_origin \
    "$target_dir" \
    "$slug" \
    "${repositories[$index]}" \
    "${refs[$index]}" \
    "${commits[$index]}" \
    "${subdirectories[$index]}" \
    "${manifest_paths[$index]}" \
    "${source_tree_hashes[$index]}"; then
    echo "无法写入 $slug 的 Git 来源记录。" >&2
    failed_count=$((failed_count + 1))
    continue
  fi

  installed_count=$((installed_count + 1))
done

printf '执行汇总：成功 %d，失败 %d，跳过 %d。\n' \
  "$installed_count" "$failed_count" "$skip_count"

[[ "$failed_count" -eq 0 ]]
