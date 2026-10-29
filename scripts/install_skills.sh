#!/usr/bin/env bash
set -euo pipefail

# 将当前仓库的 skills 目录下所有技能安装到目标目录。
# 支持两种模式：
# 1. 过滤链接模式：入口文件实拷、运行目录链接到用户级 agent 目录
# 2. 过滤拷贝模式：安装到项目目录内（<project>/.agents/skills 等）
#
# skill 根目录下的 tests/ 与 evals/ 只供源码维护，不进入任何安装目标。
# 安装来源写入隐藏标记；再次安装时只清理本仓库已退役的入口。
#
# 安装前自动验证：
# 1. 运行 scripts/harness/validate_registry.py 校验 registry.yaml
# 2. 对比 registry.yaml 中列出的技能路径与文件系统扫描结果，必须完全一致
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
VERBOSE=false
COLOR_MODE=auto

# 在实际输出的文件描述符上判断 TTY，重定向的 stdout/stderr 不混入 ANSI。
color_enabled() {
  [[ -z "${NO_COLOR:-}" ]] && { [[ "$COLOR_MODE" == always ]] || {
    [[ "$COLOR_MODE" == auto && -t 1 && "${TERM:-dumb}" != dumb ]]
  }; }
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
  local installed_style=2 updated_style=2 warning_style=2
  if [[ "$2" -gt 0 ]]; then installed_style='1;32'; fi
  if [[ "$3" -gt 0 ]]; then updated_style='1;34'; fi
  if [[ "$5" -gt 0 ]]; then warning_style='1;33'; fi
  styled 1 "$1"
  styled "$installed_style" "新增 $2"
  printf ' · '
  styled "$updated_style" "更新 $3"
  printf ' · '
  styled 2 "跳过 $4"
  printf ' · '
  styled "$warning_style" "警告 $5"
  printf '\n'
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      echo "用法: $0 [--agent <name>] [--dir <path>] [--verbose] [--color auto|always|never]"
      echo ""
      echo "选项:"
      echo "  --agent <name>  指定 agent 类型（codex | qwen | qoder | claudecode | openclaw）"
      echo "  --dir <path>    指定目标路径"
      echo "  --verbose       显示逐项跳过、保留原因和验证详情"
      echo "  --color <mode>  auto（默认，按终端检测）| always | never；NO_COLOR 非空时禁用样式"
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
    --verbose)
      VERBOSE=true
      ;;
    --color)
      shift
      if [[ $# -eq 0 ]]; then
        status_line failed "--color 缺少参数（auto | always | never）" >&2
        exit 1
      fi
      COLOR_MODE="$1"
      case "$COLOR_MODE" in
        auto|always|never) ;;
        *) status_line failed "无效颜色模式：${COLOR_MODE}（auto | always | never）" >&2; exit 1 ;;
      esac
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
  echo "codex qwen qoder claudecode openclaw"
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

  # rg 的 1 表示无匹配，是合法的空依赖列表；真正的扫描错误继续上抛。
  { rg -o --no-filename '\$REPO_ROOT/[A-Za-z0-9._/-]+' "$SRC_ROOT" -g '*.sh' \
      -g '!**/tests/**' -g '!**/evals/**' || [[ "$?" -eq 1 ]]; } \
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

is_skill_development_dir() {
  case "$1" in
    tests|evals) return 0 ;;
    *) return 1 ;;
  esac
}

installation_trees_equal() {
  python3 - "$1" "$2" <<'PYEOF'
import filecmp
import os
from pathlib import Path
import stat
import sys


def equal(left, right):
    if not os.path.lexists(right):
        return False
    left_mode, right_mode = left.lstat().st_mode, right.lstat().st_mode
    if stat.S_IFMT(left_mode) != stat.S_IFMT(right_mode):
        return False
    if stat.S_IMODE(left_mode) != stat.S_IMODE(right_mode):
        return False
    if stat.S_ISLNK(left_mode):
        return os.readlink(left) == os.readlink(right)
    if stat.S_ISDIR(left_mode):
        names = {child.name for child in left.iterdir()}
        return names == {child.name for child in right.iterdir()} and all(
            equal(left / name, right / name) for name in names
        )
    return stat.S_ISREG(left_mode) and filecmp.cmp(left, right, shallow=False)


try:
    sys.exit(0 if equal(Path(sys.argv[1]), Path(sys.argv[2])) else 1)
except OSError as error:
    print(f"[ERROR] 无法比较安装内容：{error}", file=sys.stderr)
    sys.exit(2)
PYEOF
}

# 返回 0 表示新增/更新，2 表示跳过，其他状态表示失败；ITEM_STATUS 区分结果。
finish_staged_install() {
  local staging="$1" dest="$2" label="$3"
  local comparison_status
  if installation_trees_equal "$staging" "$dest"; then
    rm -rf "$staging" || return 1
    ITEM_STATUS=skipped
    if [[ "$VERBOSE" == true ]]; then
      status_line skipped "${label}（内容未变）"
    fi
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
    rm -rf "$dest" || return 1
  fi
  mv "$staging" "$dest" || return 1
  status_line "$ITEM_STATUS" "$label"
  return 0
}

link_item() {
  local src="$1"
  local dest="$2"
  local label="$3"

  # Skill 目录不能整目录软链接，否则 tests/evals 会绕过安装过滤。
  # SKILL.md 等根文件必须实拷，避免客户端忽略软链接入口；运行目录保留源码联动。
  if [[ -f "$src/SKILL.md" ]]; then
    local staging
    staging="$(mktemp -d "${dest}.tmp.XXXXXX")" || return 1
    local entry name
    while IFS= read -r -d '' entry; do
      name="$(basename "$entry")"
      if is_skill_development_dir "$name"; then
        continue
      fi
      if [[ -d "$entry" ]]; then
        ln -s "$entry" "$staging/$name" || { rm -rf "$staging"; return 1; }
      else
        cp -p "$entry" "$staging/$name" || { rm -rf "$staging"; return 1; }
      fi
    done < <(find "$src" -mindepth 1 -maxdepth 1 -print0)
    printf '%s\n' "$src" > "$staging/$INSTALL_SOURCE_MARKER" || { rm -rf "$staging"; return 1; }

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
      if [[ "$VERBOSE" == true ]]; then
        status_line skipped "${label}（链接未变）"
      fi
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
    local entry name
    while IFS= read -r -d '' entry; do
      name="$(basename "$entry")"
      if is_skill_development_dir "$name"; then
        continue
      fi
      cp -R -p "$entry" "$staging/$name" || { rm -rf "$staging"; return 1; }
    done < <(find "$src" -mindepth 1 -maxdepth 1 -print0)
    printf '%s\n' "$src" > "$staging/$INSTALL_SOURCE_MARKER" || { rm -rf "$staging"; return 1; }
    finish_staged_install "$staging" "$dest" "$label"
  else
    local staging
    staging="$(mktemp -d "${dest}.tmp.XXXXXX")" || return 1
    rmdir "$staging" || return 1
    cp -R -p "$src" "$staging" || return 1
    finish_staged_install "$staging" "$dest" "$label"
  fi
}

# 递归收集所有技能目录（平铺到一维）
# 技能目录的识别规则：
# 1. 包含 SKILL.md 文件
# 2. 包含 .smile 文件
# 3. 包含 agents/ 子目录（Claude Code skills 结构）
# 只选择最深层的技能目录，中间分类目录不会被选中
collect_all_skills() {
  local src_root="$1"
  local all_skill_dirs=()
  local final_skills=()

  # 第一遍：收集所有技能目录
  while IFS= read -r -d '' skill_dir; do
    # 跳过根目录本身
    [[ "$skill_dir" == "$src_root" ]] && continue

    # 跳过隐藏目录
    local basename
    basename="$(basename "$skill_dir")"
    [[ "$basename" == .* ]] && continue

    # 检查是否是有效的技能目录（满足任一条件）：
    # 1. 包含 SKILL.md 文件
    # 2. 包含 .smile 文件
    # 3. 包含 agents/ 子目录
    local is_skill=false

    if [[ -f "$skill_dir/SKILL.md" ]]; then
      is_skill=true
    elif [[ -f "$skill_dir/.smile" ]]; then
      is_skill=true
    elif [[ -d "$skill_dir/agents" ]]; then
      is_skill=true
    fi

    if [[ "$is_skill" == true ]]; then
      all_skill_dirs+=("$skill_dir")
    fi
  done < <(find "$src_root" -type d -print0 2>/dev/null)

  # 第二遍：排除那些有子技能的父目录
  # 如果一个技能目录的子目录中还有其他技能目录，则排除这个父目录
  for skill_dir in "${all_skill_dirs[@]}"; do
    local has_child_skill=false

    for other_dir in "${all_skill_dirs[@]}"; do
      # 检查 other_dir 是否是 skill_dir 的子目录
      if [[ "$other_dir" != "$skill_dir" ]] && [[ "$other_dir" == "$skill_dir"/* ]]; then
        has_child_skill=true
        break
      fi
    done

    # 只有当没有子技能时，才将这个目录加入最终列表
    if [[ "$has_child_skill" == false ]]; then
      final_skills+=("$skill_dir")
    fi
  done

  # 输出去重后的技能路径
  printf '%s\n' "${final_skills[@]}" | sort -u
}

# ===== 注册表验证与解析 =====

validate_registry() {
  heading "Skills 安装 · 预检查"
  local validator="$REPO_ROOT/scripts/harness/validate_registry.py"
  if [[ ! -f "$validator" ]]; then
    status_line failed "注册表验证脚本不存在：$validator" >&2
    return 1
  fi
  local validation_output
  if ! validation_output="$(python3 "$validator" 2>&1)"; then
    printf '%s\n' "$validation_output" >&2
    status_line failed "注册表验证失败，已中止安装；请先修复 skills/registry.yaml。" >&2
    return 1
  fi
  if [[ "$VERBOSE" == true || "$validation_output" == *'[WARN'* ]]; then
    printf '%s\n' "$validation_output"
  fi
  return 0
}

parse_registry_skills() {
  local reg_file="$REPO_ROOT/skills/registry.yaml"

  if [[ ! -f "$reg_file" ]]; then
    status_line failed "注册表文件不存在：$reg_file" >&2
    return 1
  fi

  python3 << 'PYEOF'
import sys, re, os

reg_file = os.environ.get("REG_FILE", "")
if not reg_file:
    print("[ERROR] REG_FILE not set", file=sys.stderr)
    sys.exit(1)

try:
    import yaml
    with open(reg_file, "r") as f:
        data = yaml.safe_load(f)
    for s in data.get("skills", []):
        print(s.get("path", ""))
except ImportError:
    with open(reg_file, "r") as f:
        text = f.read()
    for line in text.splitlines():
        m = re.match(r"^\s+path:\s*(.+)$", line)
        if m:
            print(m.group(1).strip().strip('"').strip("'"))
except Exception as e:
    print(f"[ERROR] 解析注册表失败: {e}", file=sys.stderr)
    sys.exit(1)
PYEOF
}

validate_registry_consistency() {
  local registry_file="$1"
  local collected_file="$2"

  if [[ ! -f "$registry_file" ]] || [[ ! -s "$registry_file" ]]; then
    status_line failed "无法读取注册表中的技能列表" >&2
    return 1
  fi

  if [[ ! -f "$collected_file" ]] || [[ ! -s "$collected_file" ]]; then
    status_line failed "无法读取文件系统扫描的技能列表" >&2
    return 1
  fi

  # 将文件系统收集的绝对路径转为相对路径（相对于 REPO_ROOT）
  # 以便与 registry.yaml 中的相对路径进行比较
  local _normalized_collected
  _normalized_collected="$(mktemp)"
  sed "s|^${REPO_ROOT}/||" "$collected_file" | sort -u > "$_normalized_collected"

  local missing_in_registry missing_in_fs
  missing_in_registry="$(comm -23 <(sort "$_normalized_collected") <(sort "$registry_file"))"
  missing_in_fs="$(comm -13 <(sort "$_normalized_collected") <(sort "$registry_file"))"

  rm -f "$_normalized_collected"

  local ok=true

  if [[ -n "$missing_in_registry" ]]; then
    status_line failed "以下技能存在于文件系统但未注册于 skills/registry.yaml：" >&2
    while IFS= read -r p; do
      echo "  - $p" >&2
    done <<< "$missing_in_registry"
    ok=false
  fi

  if [[ -n "$missing_in_fs" ]]; then
    status_line failed "以下技能注册于 registry.yaml 但文件系统中不存在：" >&2
    while IFS= read -r p; do
      echo "  - $p" >&2
    done <<< "$missing_in_fs"
    ok=false
  fi

  if [[ "$ok" == false ]]; then
    echo ""
    status_line failed "注册表与文件系统不一致，已中止安装；请同步 skills/registry.yaml 与 skills/ 目录。" >&2
    return 1
  fi

  return 0
}

# ===== 主流程：注册表验证 =====

if ! validate_registry; then
  exit 1
fi

# 收集技能列表（一次），用于注册表一致性校验和安装前展示
_tmp_skills_registry="$(mktemp)"
_tmp_skills_collected="$(mktemp)"
trap 'rm -f "$_tmp_skills_registry" "$_tmp_skills_collected"' EXIT

export REG_FILE="$REPO_ROOT/skills/registry.yaml"
parse_registry_skills | sort -u > "$_tmp_skills_registry"
collect_all_skills "$SRC_ROOT" | sort -u > "$_tmp_skills_collected"

if ! validate_registry_consistency "$_tmp_skills_registry" "$_tmp_skills_collected"; then
  exit 1
fi

# ===== 安装前汇总；明细随实际结果输出，避免重复技能清单 =====
_skill_count="$(wc -l < "$_tmp_skills_collected" | tr -d ' ')"
status_line passed "注册表及目录一致 · ${_skill_count} 个技能"
if [[ "$VERBOSE" == false ]]; then
  status_line info "仅显示变更和警告；逐项跳过/保留原因：VERBOSE=1（脚本：--verbose）"
fi

# ===== 开始安装 =====

cleanup_retired_skills() {
  local dest_root="$1"
  shift

  # 不按名称前缀或链接是否失效判断归属；旧版安装通过直接链接迁移识别。
  # Python 按链接所在目录解析相对路径，即使源码已经删除也能判断归属。
  local repository_origin
  repository_origin="$(git -C "$REPO_ROOT" config --get remote.origin.url 2>/dev/null || true)"
  local use_color=false
  if color_enabled; then use_color=true; fi
  FEIPI_INSTALL_VERBOSE="$VERBOSE" FEIPI_INSTALL_COLOR="$use_color" \
    python3 - "$SRC_ROOT" "$dest_root" "$INSTALL_SOURCE_MARKER" "$repository_origin" "$@" <<'PYEOF'
import json
import os
from pathlib import Path
import shutil
import sys
from urllib.parse import urlsplit

source_root = Path(os.path.realpath(sys.argv[1]))
destination = Path(sys.argv[2])
marker_name = sys.argv[3]
active_names = {Path(source).name for source in sys.argv[5:]}


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


def report(label, text, style):
    badge = f"[{label}]"
    if os.environ["FEIPI_INSTALL_COLOR"] == "true":
        badge = f"\033[{style}m{badge}\033[0m"
    print(f"  {badge} {text}", flush=True)


cleaned = 0
preserved = 0
for entry in sorted(destination.iterdir()):
    if entry.name.startswith(".") or entry.name in active_names:
        continue
    if not belongs_to_repository(entry):
        reason = "无法确认属于本仓库"
        if not entry.is_symlink() and os.path.lexists(entry / ".openclaw/source-origin.json"):
            reason = "OpenClaw 来源不属于本仓库或记录无效"
        elif entry.is_dir() and not entry.is_symlink() and not os.path.lexists(entry / marker_name):
            reason = "无来源标记，内部链接不足以确认归属"
        if os.environ["FEIPI_INSTALL_VERBOSE"] == "true":
            report("保留", f"{entry}（{reason}）", "2")
        preserved += 1
        continue
    if entry.is_symlink():
        entry.unlink()
    else:
        shutil.rmtree(entry)
    report("清理", f"已移除本仓库旧入口：{entry}", "1;33")
    cleaned += 1
report("清理", f"移除 {cleaned} · 保留 {preserved}（其他来源或归属未确认）", "2")
PYEOF
}

# 在当前 shell 中计数、即时输出，失败时也保留已经发生的变更日志。
install_entry() {
  local install_func="$1" src="$2" dest="$3" label="$4" status=0
  ITEM_STATUS=""
  "$install_func" "$src" "$dest" "$label" || status=$?
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
  local skills_file="${5:-}"

  heading "$label"
  printf '  目标：%s\n' "$dest_root"
  if [[ "$mode" == link ]]; then
    printf '  模式：入口实拷、运行目录链接；排除 tests/evals\n'
  else
    printf '  模式：实拷；排除 tests/evals\n'
  fi
  if [[ "$VERBOSE" == true ]]; then printf '  源目录：%s\n' "$SRC_ROOT"; fi

  if ! mkdir -p "$dest_root"; then
    status_line failed "无法创建目标目录：$dest_root" >&2
    return 1
  fi

  # 收集所有技能（递归扫描，平铺输出）
  # 如果提供了预收集的列表（用于注册表校验），直接使用
  local skill_paths=()
  if [[ -n "$skills_file" ]] && [[ -f "$skills_file" ]] && [[ -s "$skills_file" ]]; then
    while IFS= read -r skill_path; do
      [[ -n "$skill_path" ]] && skill_paths+=("$skill_path")
    done < "$skills_file"
  else
    while IFS= read -r skill_path; do
      [[ -n "$skill_path" ]] && skill_paths+=("$skill_path")
    done < <(collect_all_skills "$SRC_ROOT")
  fi

  if ! cleanup_retired_skills "$dest_root" "${skill_paths[@]}"; then
    status_line failed "清理旧入口失败：$dest_root" >&2
    return 1
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

  print_counts "  小计：" "$installed" "$updated" "$skipped" "$warnings"
}

total_installed=0
total_updated=0
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
      status_line failed "未知 AGENT: ${AGENT_NAME}（支持 codex | qwen | qoder | claudecode | openclaw）" >&2
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
      status_line failed "未知 AGENT: ${AGENT_NAME}（支持 codex | qwen | qoder | claudecode | openclaw）" >&2
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
    if [[ "$agent" == "openclaw" ]]; then
      install_skills "copy" "$dest_root" "copy_dir" "$agent" "$_tmp_skills_collected"
    elif [[ -n "$agent" ]]; then
      install_skills "link" "$dest_root" "link_item" "$agent" "$_tmp_skills_collected"
    else
      install_skills "link" "$dest_root" "link_item" "agents" "$_tmp_skills_collected"
    fi
  done
fi

echo ""
print_counts "总计：" "$total_installed" "$total_updated" "$total_skipped" "$total_warnings"
if [[ "$total_warnings" -gt 0 ]]; then
  status_line warning "有 ${total_warnings} 项因警告跳过，请查看上方原因。"
fi
