#!/usr/bin/env bash
set -euo pipefail

# 将当前仓库的 skills 目录下所有技能安装到目标目录。
# 支持两种模式：
# 1. 过滤链接模式：入口文件实拷、运行目录链接到用户级 agent 目录
# 2. 过滤拷贝模式：安装到项目目录内（<project>/.agents/skills 等）
#
# skill 根目录下的 tests/ 与 evals/ 只供源码维护，不进入任何安装目标。
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

AGENT_NAME=""
TARGET_DIR=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      echo "用法: $0 [--agent <name>] [--dir <path>]"
      echo ""
      echo "选项:"
      echo "  --agent <name>  指定 agent 类型（codex | qwen | qoder | claudecode | openclaw）"
      echo "  --dir <path>    指定目标路径"
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
        echo "--agent 缺少参数。" >&2
        exit 1
      fi
      AGENT_NAME="$1"
      ;;
    --dir)
      shift
      if [[ $# -eq 0 ]]; then
        echo "--dir 缺少参数。" >&2
        exit 1
      fi
      TARGET_DIR="$1"
      ;;
    -*)
      echo "未知参数：$1" >&2
      exit 1
      ;;
    *)
      echo "多余参数：$1" >&2
      exit 1
      ;;
  esac
  shift
done

if [[ ! -d "$SRC_ROOT" ]]; then
  echo "未找到 skills 目录：$SRC_ROOT" >&2
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

  rg -o --no-filename '\$REPO_ROOT/[A-Za-z0-9._/-]+' "$SRC_ROOT" -g '*.sh' 2>/dev/null \
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

link_item() {
  local src="$1"
  local dest="$2"
  local label="$3"

  # Skill 目录不能整目录软链接，否则 tests/evals 会绕过安装过滤。
  # SKILL.md 等根文件必须实拷，避免客户端忽略软链接入口；运行目录保留源码联动。
  if [[ -f "$src/SKILL.md" ]]; then
    local staging
    staging="$(mktemp -d "${dest}.tmp.XXXXXX")"
    local entry name
    while IFS= read -r -d '' entry; do
      name="$(basename "$entry")"
      if is_skill_development_dir "$name"; then
        continue
      fi
      if [[ -d "$entry" ]]; then
        ln -s "$entry" "$staging/$name"
      else
        cp -p "$entry" "$staging/$name"
      fi
    done < <(find "$src" -mindepth 1 -maxdepth 1 -print0)

    if [[ -L "$dest" ]]; then
      rm -f "$dest"
    elif [[ -e "$dest" ]]; then
      rm -rf "$dest"
    fi
    mv "$staging" "$dest"
    echo "  已安装：${label}（入口实拷，已排除 tests/evals）"
    return 0
  fi

  if [[ -L "$dest" ]]; then
    local current_target
    current_target="$(readlink "$dest")"

    # 检查软链接是否有效（目标是否存在）
    local is_broken=false
    if [[ ! -e "$current_target" ]]; then
      is_broken=true
    fi

    if [[ "$current_target" == "$src" ]] && [[ "$is_broken" == false ]]; then
      echo "  已存在，跳过：$label"
      return 0
    fi

    # 需要移除旧软链接的情况：
    # 1. 软链接已失效（目标不存在）
    # 2. 软链接指向其他路径
    rm -f "$dest"
    if [[ "$is_broken" == true ]]; then
      echo "  已移除失效软链接：$label"
    fi
  elif [[ -e "$dest" ]]; then
    echo "  警告：目标已存在且非软链接，跳过：$dest" >&2
    return 1
  fi

  ln -s "$src" "$dest"
  echo "  已安装：$label"
  return 0
}

copy_dir() {
  local src="$1"
  local dest="$2"
  local label="$3"

  if [[ -f "$src/SKILL.md" ]]; then
    local staging
    staging="$(mktemp -d "${dest}.tmp.XXXXXX")"
    local entry name
    while IFS= read -r -d '' entry; do
      name="$(basename "$entry")"
      if is_skill_development_dir "$name"; then
        continue
      fi
      cp -R -p "$entry" "$staging/$name"
    done < <(find "$src" -mindepth 1 -maxdepth 1 -print0)
    if [[ -e "$dest" || -L "$dest" ]]; then
      rm -rf "$dest"
    fi
    mv "$staging" "$dest"
    echo "  已安装：${label}（已排除 tests/evals）"
  else
    if [[ -e "$dest" || -L "$dest" ]]; then
      rm -rf "$dest"
    fi
    cp -R -p "$src" "$dest"
    echo "  已安装：$label"
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
  echo "=== 注册表验证 ==="
  local validator="$REPO_ROOT/scripts/harness/validate_registry.py"
  if [[ ! -f "$validator" ]]; then
    echo "  [ERROR] 注册表验证脚本不存在：$validator" >&2
    return 1
  fi
  if ! python3 "$validator"; then
    echo ""
    echo "[ERROR] 注册表验证失败，已中止安装。" >&2
    echo "请先修复 skills/registry.yaml 中的问题，再重试安装。" >&2
    return 1
  fi
  return 0
}

parse_registry_skills() {
  local reg_file="$REPO_ROOT/skills/registry.yaml"

  if [[ ! -f "$reg_file" ]]; then
    echo "[ERROR] 注册表文件不存在：$reg_file" >&2
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
    echo "[ERROR] 无法读取注册表中的技能列表" >&2
    return 1
  fi

  if [[ ! -f "$collected_file" ]] || [[ ! -s "$collected_file" ]]; then
    echo "[ERROR] 无法读取文件系统扫描的技能列表" >&2
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
    echo "[ERROR] 以下技能存在于文件系统但未注册于 skills/registry.yaml：" >&2
    while IFS= read -r p; do
      echo "  - $p" >&2
    done <<< "$missing_in_registry"
    ok=false
  fi

  if [[ -n "$missing_in_fs" ]]; then
    echo "[ERROR] 以下技能注册于 registry.yaml 但文件系统中不存在：" >&2
    while IFS= read -r p; do
      echo "  - $p" >&2
    done <<< "$missing_in_fs"
    ok=false
  fi

  if [[ "$ok" == false ]]; then
    echo ""
    echo "[ERROR] 注册表与文件系统不一致，已中止安装。" >&2
    echo "请同步 skills/registry.yaml 与 skills/ 目录，再重试安装。" >&2
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

echo ""

# ===== 安装前展示技能列表 =====
_skill_count="$(wc -l < "$_tmp_skills_collected" | tr -d ' ')"
echo "将安装以下 ${_skill_count} 个技能："
while IFS= read -r skill_path; do
  [[ -z "$skill_path" ]] && continue
  _skill_name="$(basename "$skill_path")"
  echo "  - ${_skill_name}  (${skill_path})"
done < "$_tmp_skills_collected"
echo ""

# ===== 开始安装 =====

install_skills() {
  local mode="$1"
  local dest_root="$2"
  local install_func="$3"
  local label="$4"
  local skills_file="${5:-}"

  echo "=== $label ==="
  echo "源目录：$SRC_ROOT"
  echo "目标目录：$dest_root"

  mkdir -p "$dest_root"

  # 清理目标目录中所有失效的软链接（指向不存在的目标）
  echo "清理失效的软链接..."
  local cleaned=0
  for item in "$dest_root"/*; do
    if [[ -L "$item" ]]; then
      local target
      target="$(readlink "$item")"
      if [[ ! -e "$target" ]]; then
        rm -f "$item"
        echo "  已移除：$item (原指向：$target)"
        cleaned=$((cleaned + 1))
      fi
    fi
  done
  if [[ $cleaned -gt 0 ]]; then
    echo "共移除 $cleaned 个失效软链接"
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

  echo "发现 ${#skill_paths[@]} 个技能"

  local installed=0
  local skipped=0

  for src in "${skill_paths[@]}"; do
    local name
    name="$(basename "$src")"
    local dest="$dest_root/$name"
    if $install_func "$src" "$dest" "$name"; then
      installed=$((installed + 1))
    else
      skipped=$((skipped + 1))
    fi
  done

  local dest_base
  dest_base="$(cd "$dest_root/.." && pwd)"

  local shared_roots_text
  shared_roots_text="$(collect_shared_roots)"
  if [[ -n "$shared_roots_text" ]]; then
    while IFS= read -r root_name; do
      [[ -z "$root_name" ]] && continue
      local src="$REPO_ROOT/$root_name"
      local dest="$dest_base/$root_name"

      if [[ "$dest" == "$dest_root" ]]; then
        continue
      fi

      if [[ ! -e "$src" ]]; then
        echo "  警告：共享路径不存在，跳过：$src" >&2
        skipped=$((skipped + 1))
        continue
      fi

      if $install_func "$src" "$dest" "$root_name"; then
        installed=$((installed + 1))
      else
        skipped=$((skipped + 1))
      fi
    done <<< "$shared_roots_text"
  fi

  echo "完成：安装 ${installed}，跳过 ${skipped}"
  echo "$installed $skipped"
}

total_installed=0
total_skipped=0

if [[ -n "$TARGET_DIR" ]]; then
  if [[ ! -d "$TARGET_DIR" ]]; then
    echo "项目路径不存在或不是目录：$TARGET_DIR" >&2
    exit 1
  fi

  project_root="$(cd "$TARGET_DIR" && pwd)"
  dest_root="$(get_project_dest_root "$AGENT_NAME" "$project_root")"

  if [[ -z "$dest_root" ]]; then
    if [[ -n "$AGENT_NAME" ]]; then
      echo "未知 AGENT: ${AGENT_NAME}（支持 codex | qwen | qoder | claudecode | openclaw）" >&2
    else
      echo "无法确定目标目录" >&2
    fi
    exit 1
  fi

  if [[ "$dest_root" != "$project_root"/* ]]; then
    echo "目标路径不在项目目录内，已拒绝：$dest_root" >&2
    exit 1
  fi

  result="$(install_skills "copy" "$dest_root" "copy_dir" "安装到项目：$dest_root" "$_tmp_skills_collected")"
  installed="$(echo "$result" | tail -1 | cut -d' ' -f1)"
  skipped="$(echo "$result" | tail -1 | cut -d' ' -f2)"
  total_installed=$((total_installed + installed))
  total_skipped=$((total_skipped + skipped))
else
  declare -a target_agents=()

  if [[ -n "$AGENT_NAME" ]]; then
    dest="$(get_user_dest_root "$AGENT_NAME")"
    if [[ -z "$dest" ]]; then
      echo "未知 AGENT: ${AGENT_NAME}（支持 codex | qwen | qoder | claudecode | openclaw）" >&2
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
      echo "未发现任何 agent 目标目录，使用默认：$dest"
    else
      for agent in $existing; do
        dest="$(get_user_dest_root "$agent")"
        mkdir -p "$(dirname "$dest")"
        target_agents+=("$agent:$dest")
      done
      echo "检测到已存在的 agent 目录：$existing"
    fi
  fi

  for agent_entry in "${target_agents[@]}"; do
    agent="${agent_entry%%:*}"
    dest_root="${agent_entry#*:}"

    # OpenClaw 安全策略拒绝 realpath 超出根目录的软链接，
    # 因此对 openclaw 使用实拷而非软链接
    if [[ "$agent" == "openclaw" ]]; then
      result="$(install_skills "copy" "$dest_root" "copy_dir" "安装到 ${agent} -> ${dest_root} [实拷]" "$_tmp_skills_collected")"
    elif [[ -n "$agent" ]]; then
      result="$(install_skills "link" "$dest_root" "link_item" "安装到 $agent -> $dest_root" "$_tmp_skills_collected")"
    else
      result="$(install_skills "link" "$dest_root" "link_item" "安装到 $dest_root" "$_tmp_skills_collected")"
    fi
    installed="$(echo "$result" | tail -1 | cut -d' ' -f1)"
    skipped="$(echo "$result" | tail -1 | cut -d' ' -f2)"
    total_installed=$((total_installed + installed))
    total_skipped=$((total_skipped + skipped))
  done
fi

echo ""
echo "========================================"
echo "总计：安装/更新 ${total_installed}，跳过 ${total_skipped}"
