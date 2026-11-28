#!/usr/bin/env bash
set -euo pipefail

# 将当前仓库的 skills 目录下所有技能安装到目标目录。
# 支持两种模式：
# 1. 过滤链接模式：入口文件实拷、运行目录链接到用户级 agent 目录
# 2. 过滤拷贝模式：安装到项目目录内（<project>/.agents/skills 等）
#
# 递归排除 maintenance/、tests/、evals/ 、node_modules/ 和 Python 缓存，不进入安装目标。
# 安装来源写入隐藏标记；再次安装时只清理本仓库已退役的入口。
#
# 安装前自动验证：
# 读取注册表，校验入口与文件系统的一致性，之后才写入安装目标。
#
# 注意：OpenClaw 安全策略拒绝 realpath 超出根目录的软链接
# （"resolved realpath stays inside the configured root"），
# 因此对 openclaw 用户级安装也使用实拷，而非软链接。
#
# 用法：
#   ./scripts/install_skills.sh
#     过滤安装到所有已存在的用户级 agent 目录
#   ./scripts/install_skills.sh --agent claudecode
#     过滤安装到 ~/.claude/skills
#   ./scripts/install_skills.sh --agent openclaw
#     实拷到 ~/.openclaw/skills（非软链接）
#   ./scripts/install_skills.sh --dir /path/to/project
#     拷贝到 /path/to/project/.agents/skills
#   ./scripts/install_skills.sh --agent qwen --dir /path/to/project
#     拷贝到 /path/to/project/.qwen/skills

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SRC_ROOT="$REPO_ROOT/skills"
INSTALL_SOURCE_MARKER=".feipi-agent-kit-source"

AGENT_NAME=""
TARGET_DIR=""
COPY_USER=false
SKILL_NAME=""

# 在实际输出的文件描述符上判断 TTY，重定向的 stdout/stderr 不混入 ANSI。
color_enabled() {
  [[ -z "${NO_COLOR:-}" && -t 1 && "${TERM:-dumb}" != dumb ]]
}

styled() {
  if color_enabled; then
    printf '\033[%sm%s\033[0m' "$1" "$2"
  else
    printf '%s' "$2"
  fi
}

status_line() {
  local status="$1" label style
  shift
  case "$status" in
    installed) label=新增; style='1;32' ;;
    updated) label=更新; style='1;34' ;;
    skipped) label=跳过; style=2 ;;
    warning) label=警告; style='1;33' ;;
    failed) label=失败; style='1;31' ;;
    passed) label=通过; style=32 ;;
    info) label=提示; style=36 ;;
  esac
  printf '  '
  styled "$style" "[$label]"
  printf ' %s\n' "$*"
}

heading() {
  printf '\n'
  styled '1;36' "$1"
  printf '\n'
}

print_counts() {
  local installed_style=2 updated_style=2 deleted_style=2 warning_style=2
  if [[ "$2" -gt 0 ]]; then installed_style='1;32'; fi
  if [[ "$3" -gt 0 ]]; then updated_style='1;34'; fi
  if [[ "$4" -gt 0 ]]; then deleted_style='1;33'; fi
  if [[ "$7" -gt 0 ]]; then warning_style='1;33'; fi
  styled 1 "$1"
  styled "$installed_style" "新增 $2"
  printf ' · '
  styled "$updated_style" "更新 $3"
  printf ' · '
  styled "$deleted_style" "删除 $4"
  printf ' · '
  styled 2 "保留 $5"
  printf ' · '
  styled 2 "跳过 $6"
  printf ' · '
  styled "$warning_style" "警告 $7"
  printf '\n'
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      echo "用法: $0 [--agent <name>] [--skill <name>] [--dir <path>] [--copy]"
      echo ""
      echo "选项:"
      echo "  --agent <name>  指定 agent 类型（codex | cursor | qwen | qoder | claudecode | openclaw）"
      echo "  --skill <name>  只安装该 skill 及其直接共享依赖，不清理其他入口"
      echo "  --dir <path>    指定目标路径"
      echo "  --copy          用户级安装也使用实拷（日常工作台默认）；不随源码编辑变化"
      echo ""
      echo "安装前自动验证："
      echo "  1. 运行 registry 校验（validate_registry.py）"
      echo "  2. 对比 registry.yaml 与文件系统技能目录的一致性"
      echo ""
      echo "示例:"
      echo "  $0                              # 过滤安装到所有已存在的用户级目录"
      echo "  $0 --agent claudecode           # 过滤安装到 ~/.claude/skills"
      echo "  $0 --agent openclaw             # 实拷到 ~/.openclaw/skills"
      echo "  $0 --dir /path/to/project       # 拷贝到 /path/to/project/.agents/skills"
      echo "  $0 --agent qwen --dir /path     # 拷贝到 /path/to/project/.qwen/skills"
      exit 0
      ;;
    --agent)
      shift
      if [[ $# -eq 0 ]]; then
        status_line failed "--agent 缺少参数。" >&2
        exit 1
      fi
      AGENT_NAME="$1"
      ;;
    --dir)
      shift
      if [[ $# -eq 0 ]]; then
        status_line failed "--dir 缺少参数。" >&2
        exit 1
      fi
      TARGET_DIR="$1"
      ;;
    --skill)
      shift
      if [[ $# -eq 0 || "$1" == -* || -n "$SKILL_NAME" ]]; then
        status_line failed "--skill 需要一个名称，且不能重复。" >&2
        exit 1
      fi
      SKILL_NAME="$1"
      ;;
    --copy)
      COPY_USER=true
      ;;
    -*)
      status_line failed "未知参数：$1" >&2
      exit 1
      ;;
    *)
      status_line failed "多余参数：$1" >&2
      exit 1
      ;;
  esac
  shift
done

if [[ ! -d "$SRC_ROOT" ]]; then
  status_line failed "未找到 skills 目录：$SRC_ROOT" >&2
  exit 1
fi

get_user_dest_root() {
  local agent="$1"
  case "$agent" in
    codex)
      local codex_home_dir="${CODEX_HOME:-$HOME/.codex}"
      echo "$codex_home_dir/skills"
      ;;
    cursor)
      echo "$HOME/.cursor/skills"
      ;;
    qoder)
      echo "$HOME/.qoder/skills"
      ;;
    qwen)
      echo "$HOME/.qwen/skills"
      ;;
    claudecode)
      echo "$HOME/.claude/skills"
      ;;
    openclaw)
      local openclaw_home_dir="${OPENCLAW_HOME:-$HOME/.openclaw}"
      echo "$openclaw_home_dir/skills"
      ;;
    "")
      echo "$HOME/.agents/skills"
      ;;
    *)
      echo ""
      ;;
  esac
}

get_project_dest_root() {
  local agent="$1"
  local project="$2"
  case "$agent" in
    codex)
      echo "$project/.codex/skills"
      ;;
    cursor)
      echo "$project/.cursor/skills"
      ;;
    qoder)
      echo "$project/.qoder/skills"
      ;;
    qwen)
      echo "$project/.qwen/skills"
      ;;
    claudecode)
      echo "$project/.claude/skills"
      ;;
    openclaw)
      echo "$project/.openclaw/skills"
      ;;
    "")
      echo "$project/.agents/skills"
      ;;
    *)
      echo ""
      ;;
  esac
}

get_all_agents() {
  echo "codex cursor qwen qoder claudecode openclaw"
}

find_existing_agents() {
  local existing=""
  for agent in $(get_all_agents); do
    local dest
    dest="$(get_user_dest_root "$agent")"
    if [[ -d "$dest" ]] || [[ -d "$(dirname "$dest")" ]]; then
      existing="$existing $agent"
    fi
  done
  echo "$existing" | xargs
}

collect_shared_roots() {
  local root_name=""
  local scan_root="${SELECTED_SKILL_PATH:-$SRC_ROOT}"

  # 不依赖目标机器未必预装的 ripgrep，使用基础系统工具递归扫描脚本。
  find "$scan_root" \
    \( -type d \( -name maintenance -o -name tests -o -name evals -o -name node_modules -o -name __pycache__ \) -prune \) -o \
    \( -type f -name '*.sh' -exec sh -c '
      pattern=$1
      shift
      grep -hEo "$pattern" "$@" || [ "$?" -eq 1 ]
    ' sh '\$REPO_ROOT/[A-Za-z0-9._/-]+' {} + \) \
    | sed -E 's#^\$REPO_ROOT/##' \
    | cut -d'/' -f1 \
    | sort -u \
    | while IFS= read -r root_name; do
      [[ -z "$root_name" ]] && continue
      [[ "$root_name" == "skills" ]] && continue
      [[ "$root_name" == .* ]] && continue
      [[ -e "$REPO_ROOT/$root_name" ]] || continue
      printf '%s\n' "$root_name"
    done
}

installation_trees_equal() {
  python3 "$SCRIPT_DIR/package_skill.py" compare "$1" "$2" "${3:-staged}"
}

stage_skill() {
  python3 "$SCRIPT_DIR/package_skill.py" stage "$1" "$2" "$3"
}

# 读取 skill agents/openai.yaml 中的顶层整数版本号。
get_skill_version() {
  local metadata="$1/agents/openai.yaml"
  [[ -f "$metadata" ]] || return 0
  awk '
    /^version:[[:space:]]*[0-9]+[[:space:]]*$/ {
      sub(/^version:[[:space:]]*/, "")
      sub(/[[:space:]]*$/, "")
      print
      exit
    }
  ' "$metadata"
}

# 返回 0 表示新增/更新，2 表示跳过，其他状态表示失败；ITEM_STATUS 区分结果。
finish_staged_install() {
  local staging="$1" dest="$2" label="$3"
  local comparison_status version_detail="" old_version new_version
  if installation_trees_equal "$staging" "$dest"; then
    rm -rf "$staging" || return 1
    ITEM_STATUS=skipped
    status_line skipped "${label}（内容未变）"
    return 2
  else
    comparison_status=$?
    if [[ "$comparison_status" -ne 1 ]]; then
      rm -rf "$staging"
      return 1
    fi
  fi

  ITEM_STATUS=installed
  if [[ -e "$dest" || -L "$dest" ]]; then
    ITEM_STATUS=updated
    # 仅从已安装的实文件读取旧版本，避免链接模式把源码当前版本误当成旧版本。
    if [[ -f "$staging/SKILL.md" && -f "$staging/agents/openai.yaml" \
      && -f "$dest/agents/openai.yaml" && ! -L "$dest/agents" \
      && ! -L "$dest/agents/openai.yaml" ]]; then
      old_version="$(get_skill_version "$dest")"
      new_version="$(get_skill_version "$staging")"
      if [[ -n "$old_version" && -n "$new_version" ]]; then
        version_detail="（v${old_version} → v${new_version}）"
      fi
    fi
    rm -rf "$dest" || return 1
  fi
  mv "$staging" "$dest" || return 1
  status_line "$ITEM_STATUS" "$label$version_detail"
  return 0
}

link_item() {
  local src="$1"
  local dest="$2"
  local label="$3"

  # Skill 目录不能整目录软链接，否则源码维护与测试目录会绕过安装过滤。
  # SKILL.md 等根文件必须实拷，避免客户端忽略软链接入口；运行目录保留源码联动。
  if [[ -f "$src/SKILL.md" ]]; then
    local staging
    staging="$(mktemp -d "${dest}.tmp.XXXXXX")" || return 1
    stage_skill "$src" "$staging" link || { rm -rf "$staging"; return 1; }
    printf '%s\n' "$src" > "$staging/$INSTALL_SOURCE_MARKER" || { rm -rf "$staging"; return 1; }
    # 来源标记权限固定，避免不同 umask 使未变内容被反复判为更新。
    chmod 600 "$staging/$INSTALL_SOURCE_MARKER" || { rm -rf "$staging"; return 1; }

    finish_staged_install "$staging" "$dest" "$label"
    return $?
  fi

  ITEM_STATUS=installed
  local detail=""
  if [[ -L "$dest" ]]; then
    local current_target
    current_target="$(readlink "$dest")"

    # 检查软链接是否有效（目标是否存在）
    local is_broken=false
    if [[ ! -e "$dest" ]]; then
      is_broken=true
    fi

    if [[ "$current_target" == "$src" ]] && [[ "$is_broken" == false ]]; then
      ITEM_STATUS=skipped
      status_line skipped "${label}（链接未变）"
      return 2
    fi

    # 需要移除旧软链接的情况：
    # 1. 软链接已失效（目标不存在）
    # 2. 软链接指向其他路径
    rm -f "$dest" || return 1
    ITEM_STATUS=updated
    detail="（修正链接目标）"
    if [[ "$is_broken" == true ]]; then
      detail="（修复失效链接）"
    fi
  elif [[ -e "$dest" ]]; then
    ITEM_STATUS=warning
    status_line warning "${label}（目标已存在且非软链接，跳过：${dest}）" >&2
    return 2
  fi

  ln -s "$src" "$dest" || return 1
  status_line "$ITEM_STATUS" "$label$detail"
  return 0
}

copy_dir() {
  local src="$1"
  local dest="$2"
  local label="$3"

  if [[ -f "$src/SKILL.md" ]]; then
    local staging
    staging="$(mktemp -d "${dest}.tmp.XXXXXX")" || return 1
    stage_skill "$src" "$staging" copy || { rm -rf "$staging"; return 1; }
    printf '%s\n' "$src" > "$staging/$INSTALL_SOURCE_MARKER" || { rm -rf "$staging"; return 1; }
    chmod 600 "$staging/$INSTALL_SOURCE_MARKER" || { rm -rf "$staging"; return 1; }
    finish_staged_install "$staging" "$dest" "$label"
  else
    local staging
    staging="$(mktemp -d "${dest}.tmp.XXXXXX")" || return 1
    rmdir "$staging" || return 1
    cp -R -p "$src" "$staging" || return 1
    finish_staged_install "$staging" "$dest" "$label"
  fi
}

# 一次读取完整注册表并校验磁盘一致性，然后按需筛选。
heading "Skills 安装 · 预检查"
_tmp_skills_collected="$(mktemp)"
trap 'rm -f "$_tmp_skills_collected"' EXIT
if ! python3 "$REPO_ROOT/scripts/harness/validate_registry.py" --paths > "$_tmp_skills_collected"; then
  status_line failed "注册表验证失败，已中止安装；请先修复 skills/registry.yaml。" >&2
  exit 1
fi

# 完整注册表校验后再缩小安装范围；未知名称必须在任何目标写入前失败。
SELECTED_SKILL_PATH=""
if [[ -n "$SKILL_NAME" ]]; then
  while IFS= read -r skill_path; do
    if [[ "$(basename "$skill_path")" == "$SKILL_NAME" ]]; then
      SELECTED_SKILL_PATH="$skill_path"
      break
    fi
  done < "$_tmp_skills_collected"
  if [[ -z "$SELECTED_SKILL_PATH" ]]; then
    status_line failed "未注册的 skill：$SKILL_NAME" >&2
    exit 1
  fi
  printf '%s\n' "$SELECTED_SKILL_PATH" > "$_tmp_skills_collected"
fi

# ===== 安装前汇总；明细随实际结果输出，避免重复技能清单 =====
_skill_count="$(wc -l < "$_tmp_skills_collected" | tr -d ' ')"
status_line passed "注册表及目录一致 · ${_skill_count} 个技能"

# ===== 开始安装 =====

cleanup_retired_skills() {
  local dest_root="$1"
  shift

  # 不按名称前缀或链接是否失效判断归属；旧版安装通过直接链接迁移识别。
  # Python 按链接所在目录解析相对路径，即使源码已经删除也能判断归属。
  local repository_origin
  repository_origin="$(git -C "$REPO_ROOT" config --get remote.origin.url 2>/dev/null || true)"
  local use_color=false
  if color_enabled >&3; then use_color=true; fi
  FEIPI_INSTALL_COLOR="$use_color" \
    python3 - "$SRC_ROOT" "$dest_root" "$INSTALL_SOURCE_MARKER" "$repository_origin" "$@" <<'PYEOF'
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from urllib.parse import urlsplit

source_root = Path(os.path.realpath(sys.argv[1]))
destination = Path(sys.argv[2])
marker_name = sys.argv[3]
active_names = {Path(source).name for source in sys.argv[5:]}


def historical_skill_names():
    # 清单记录仓库中已删除 SKILL.md 的名称；同名只用于提示，不能证明安装来源。
    try:
        lines = (source_root / "deleted-skills.txt").read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return set()
    return {line.strip() for line in lines if line.strip() and not line.lstrip().startswith("#")}


def repository_identity(url):
    if not isinstance(url, str) or not url:
        return None
    if url.startswith("git@") and ":" in url:
        url = "ssh://" + url.replace(":", "/", 1)
    try:
        parsed = urlsplit(url)
        if parsed.scheme not in {"https", "http", "ssh", "git"} or not parsed.hostname:
            return None
        path = parsed.path.rstrip("/")
        if path.endswith(".git"):
            path = path[:-4]
        return parsed.hostname, parsed.port, path
    except ValueError:
        return None


repository = repository_identity(sys.argv[4])


def openclaw_repository_source(entry, origin):
    if repository is None or origin.is_symlink() or origin.parent.is_symlink():
        return False
    try:
        data = json.loads(origin.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("source") != "git" or data.get("slug") != entry.name:
            return False
        git_source = data.get("git")
        subdirectory = data.get("subdirectory")
        if not isinstance(git_source, dict) or not isinstance(subdirectory, str):
            return False
        parts = subdirectory.split("/")
        return (
            repository_identity(git_source.get("url")) == repository
            and len(parts) >= 3 and parts[0] == "skills" and parts[-1] == entry.name
            and all(part not in {"", ".", ".."} for part in parts)
        )
    except (OSError, UnicodeError, ValueError):
        return False


def is_repository_source(source):
    if not source.is_absolute():
        return False
    # realpath 可解析仍存在的祖先，兼容 /var 与 /private/var 等路径别名。
    return source_root in Path(os.path.realpath(source)).parents


def link_target(link):
    return Path(os.path.abspath(link.parent / os.readlink(link)))


def belongs_to_repository(entry):
    if entry.is_symlink():
        return is_repository_source(link_target(entry))
    if not entry.is_dir():
        return False

    marker = entry / marker_name
    if os.path.lexists(marker):
        # 显式标记优先，其他仓库或不可读标记不能由内部链接覆盖。
        if marker.is_symlink() or not marker.is_file():
            return False
        try:
            source = Path(marker.read_text(encoding="utf-8").strip())
        except (OSError, UnicodeError):
            return False
        return is_repository_source(Path(os.path.normpath(source)))

    origin = entry / ".openclaw/source-origin.json"
    if os.path.lexists(origin):
        # OpenClaw 的 Git 安装本来就保存来源；其他仓库或无效记录优先保留。
        return openclaw_repository_source(entry, origin)

    if not (entry / "SKILL.md").is_file():
        return False
    links = [child for child in entry.iterdir() if child.is_symlink()]
    if not links:
        return False
    targets = [link_target(link) for link in links]
    source = Path(os.path.realpath(targets[0].parent))
    # 旧过滤安装的所有直接链接都对应同一 skill 的同名资源。
    return (
        is_repository_source(source)
        and source.name == entry.name
        and all(Path(os.path.realpath(target.parent)) == source and target.name == link.name
                for link, target in zip(links, targets))
    )


progress = os.fdopen(3, "w", encoding=sys.stdout.encoding, errors=sys.stdout.errors)


def report(label, text, style):
    badge = f"[{label}]"
    if os.environ["FEIPI_INSTALL_COLOR"] == "true":
        badge = f"\033[{style}m{badge}\033[0m"
    print(f"  {badge} {text}", file=progress, flush=True)


historical_names = historical_skill_names()
deleted = 0
preserved = 0
for entry in sorted(destination.iterdir()):
    if entry.name.startswith(".") or entry.name in active_names:
        continue
    if not belongs_to_repository(entry):
        if entry.name in historical_names:
            report("保留", f"{entry}（与仓库历史 Skill 同名，无法确认归属）", "2")
            preserved += 1
        continue
    if entry.is_symlink():
        entry.unlink()
    else:
        shutil.rmtree(entry)
    report("删除", f"已移除本仓库旧入口：{entry}", "1;33")
    deleted += 1
print(f"{deleted} {preserved}")
PYEOF
}

# 在当前 shell 中计数、即时输出，失败时也保留已经发生的变更日志。
install_entry() {
  local install_func="$1" src="$2" dest="$3" label="$4" status=0
  ITEM_STATUS=""
  if [[ -f "$src/SKILL.md" ]]; then
    local mode=copy comparison=0
    if [[ "$install_func" == link_item ]]; then mode=link; fi
    installation_trees_equal "$src" "$dest" "$mode" || comparison=$?
    if [[ "$comparison" -eq 0 ]]; then
      ITEM_STATUS=skipped
      status_line skipped "${label}（内容未变）"
    elif [[ "$comparison" -eq 1 ]]; then
      "$install_func" "$src" "$dest" "$label" || status=$?
    else
      status=1
    fi
  else
    "$install_func" "$src" "$dest" "$label" || status=$?
  fi
  if [[ "$status" -ne 0 && "$status" -ne 2 ]]; then
    status_line failed "安装失败：$dest" >&2
    return 1
  fi
  case "$ITEM_STATUS" in
    installed)
      installed=$((installed + 1)); total_installed=$((total_installed + 1)) ;;
    updated)
      updated=$((updated + 1)); total_updated=$((total_updated + 1)) ;;
    skipped|warning)
      skipped=$((skipped + 1)); total_skipped=$((total_skipped + 1))
      if [[ "$ITEM_STATUS" == warning ]]; then
        warnings=$((warnings + 1)); total_warnings=$((total_warnings + 1))
      fi ;;
    *) status_line failed "缺少安装结果：$dest" >&2; return 1 ;;
  esac
}

install_skills() {
  local mode="$1"
  local dest_root="$2"
  local install_func="$3"
  local label="$4"
  local skills_file="$5"

  heading "$label"
  printf '  目标：%s\n' "$dest_root"
  if [[ "$mode" == link ]]; then
    printf '  模式：入口实拷、运行目录链接；递归排除 maintenance/tests/evals/node_modules 及 Python 缓存\n'
  else
    printf '  模式：实拷；递归排除 maintenance/tests/evals/node_modules 及 Python 缓存\n'
  fi


  if ! mkdir -p "$dest_root"; then
    status_line failed "无法创建目标目录：$dest_root" >&2
    return 1
  fi

  local skill_paths=()
  while IFS= read -r skill_path; do
    skill_paths+=("$skill_path")
  done < "$skills_file"

  local deleted=0 preserved=0 cleanup_counts
  if [[ -z "$SKILL_NAME" ]]; then
    # 只捕获计数，明细经 FD 3 实时写到原来的 stdout。
    if ! { cleanup_counts="$(cleanup_retired_skills "$dest_root" "${skill_paths[@]}")"; } 3>&1; then
      status_line failed "清理旧入口失败：$dest_root" >&2
      return 1
    fi
    read -r deleted preserved <<< "$cleanup_counts"
    total_deleted=$((total_deleted + deleted))
    total_preserved=$((total_preserved + preserved))
  fi

  local installed=0
  local updated=0
  local skipped=0
  local warnings=0

  for src in "${skill_paths[@]}"; do
    local name
    name="$(basename "$src")"
    local dest="$dest_root/$name"
    install_entry "$install_func" "$src" "$dest" "$name" || return 1
  done

  local dest_base
  dest_base="$(cd "$dest_root/.." && pwd)"

  local shared_roots_text
  if ! shared_roots_text="$(collect_shared_roots)"; then
    status_line failed "无法扫描共享路径：$SRC_ROOT" >&2
    return 1
  fi
  if [[ -n "$shared_roots_text" ]]; then
    while IFS= read -r root_name; do
      [[ -z "$root_name" ]] && continue
      local src="$REPO_ROOT/$root_name"
      local dest="$dest_base/$root_name"

      if [[ "$dest" == "$dest_root" ]]; then
        continue
      fi

      if [[ ! -e "$src" ]]; then
        status_line warning "共享路径不存在，跳过：$src" >&2
        skipped=$((skipped + 1))
        total_skipped=$((total_skipped + 1))
        warnings=$((warnings + 1))
        total_warnings=$((total_warnings + 1))
        continue
      fi

      install_entry "$install_func" "$src" "$dest" "共享/$root_name" || return 1
    done <<< "$shared_roots_text"
  fi

  print_counts "  小计：" "$installed" "$updated" "$deleted" "$preserved" "$skipped" "$warnings"
}

total_installed=0
total_updated=0
total_deleted=0
total_preserved=0
total_skipped=0
total_warnings=0

if [[ -n "$TARGET_DIR" ]]; then
  if [[ ! -d "$TARGET_DIR" ]]; then
    status_line failed "项目路径不存在或不是目录：$TARGET_DIR" >&2
    exit 1
  fi

  project_root="$(cd "$TARGET_DIR" && pwd)"
  dest_root="$(get_project_dest_root "$AGENT_NAME" "$project_root")"

  if [[ -z "$dest_root" ]]; then
    if [[ -n "$AGENT_NAME" ]]; then
      status_line failed "未知 AGENT: ${AGENT_NAME}（支持 $(get_all_agents)）" >&2
    else
      status_line failed "无法确定目标目录" >&2
    fi
    exit 1
  fi

  if [[ "$dest_root" != "$project_root"/* ]]; then
    status_line failed "目标路径不在项目目录内，已拒绝：$dest_root" >&2
    exit 1
  fi

  install_skills "copy" "$dest_root" "copy_dir" "项目 · ${AGENT_NAME:-agents}" "$_tmp_skills_collected"
else
  declare -a target_agents=()

  if [[ -n "$AGENT_NAME" ]]; then
    dest="$(get_user_dest_root "$AGENT_NAME")"
    if [[ -z "$dest" ]]; then
      status_line failed "未知 AGENT: ${AGENT_NAME}（支持 $(get_all_agents)）" >&2
      exit 1
    fi
    mkdir -p "$(dirname "$dest")"
    target_agents+=("$AGENT_NAME:$dest")
  else
    existing="$(find_existing_agents)"
    if [[ -z "$existing" ]]; then
      dest="$(get_user_dest_root "")"
      mkdir -p "$(dirname "$dest")"
      target_agents+=(":$dest")
      status_line info "未发现 agent 目录，使用默认：$dest"
    else
      for agent in $existing; do
        dest="$(get_user_dest_root "$agent")"
        mkdir -p "$(dirname "$dest")"
        target_agents+=("$agent:$dest")
      done
      status_line info "安装目标：$existing"
    fi
  fi

  for agent_entry in "${target_agents[@]}"; do
    agent="${agent_entry%%:*}"
    dest_root="${agent_entry#*:}"

    # OpenClaw 安全策略拒绝 realpath 超出根目录的软链接，
    # 因此对 openclaw 使用实拷而非软链接
    if [[ "$agent" == "openclaw" || "$COPY_USER" == true ]]; then
      install_skills "copy" "$dest_root" "copy_dir" "$agent" "$_tmp_skills_collected"
    elif [[ -n "$agent" ]]; then
      install_skills "link" "$dest_root" "link_item" "$agent" "$_tmp_skills_collected"
    else
      install_skills "link" "$dest_root" "link_item" "agents" "$_tmp_skills_collected"
    fi
  done
fi

echo ""
print_counts "总计：" "$total_installed" "$total_updated" "$total_deleted" "$total_preserved" "$total_skipped" "$total_warnings"
if [[ "$total_warnings" -gt 0 ]]; then
  status_line warning "有 ${total_warnings} 项因警告跳过，请查看上方原因。"
fi
