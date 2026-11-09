#!/usr/bin/env bash
# scripts/repo/check_stale_paths.sh
# 检查文档中是否引用了不存在的文件或旧路径/旧 skill 名称
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"
REPO_ROOT="$(find_git_root)"

warns=0
blocks=0

# --- 内置旧路径映射表（来自 task 015 审计） ---
# 格式: "旧路径|建议新路径"
declare -a STALE_PATH_MAP=(
  "tools/search/searxng-mcp|已退役（请删除或标注[历史]）"
  "skills/feipi-plantuml-diagram/|skills/authoring/feipi-plantuml-generate-*/"
  "skills/feipi-video-read-url/|skills/authoring/feipi-video-read-url/"
)

# --- 1. 死链检测：扫描 .md 文件中的相对路径引用 ---
while IFS= read -r -d '' md_file; do
  rel_path="${md_file#$REPO_ROOT/}"
  md_dir="$(dirname "$md_file")"

  while IFS= read -r link; do
    # 排除纯锚点和外部 URL
    [[ "$link" =~ ^https?:// ]] && continue
    [[ "$link" =~ ^# ]] && continue
    [[ -z "$link" ]] && continue

    # 解析相对路径
    if [[ "$link" == ./* || "$link" == ../* ]]; then
      # 移除锚点部分
      clean_link="${link%%#*}"
      target="$md_dir/$clean_link"
      if ! [[ -e "$target" ]]; then
        log_warn "$rel_path" "references non-existent path: $link"
        ((warns++))
      fi
    fi
  done < <(extract_markdown_links "$md_file")
done < <(find "$REPO_ROOT" -name "*.md" -type f -print0 2>/dev/null)

# --- 2. 旧路径检测：扫描 .md 文件内容 ---
while IFS= read -r -d '' md_file; do
  rel_path="${md_file#$REPO_ROOT/}"
  for mapping in "${STALE_PATH_MAP[@]}"; do
    old_path="${mapping%%|*}"
    suggestion="${mapping#*|}"
    if grep -qF "$old_path" "$md_file" 2>/dev/null; then
      log_warn "$rel_path" "contains stale path: $old_path -> use $suggestion"
      ((warns++))
    fi
  done
done < <(find "$REPO_ROOT" -name "*.md" -type f -print0 2>/dev/null)

# --- 3. 硬编码绝对路径检测 ---
while IFS= read -r -d '' md_file; do
  rel_path="${md_file#$REPO_ROOT/}"
  # 检测硬编码绝对路径（排除 /tmp, /dev, /proc, /usr 等系统路径）
  abs_paths=$(grep -oE '/[A-Z][a-zA-Z0-9_.-]+(/[A-Za-z0-9_.-]+){2,}' "$md_file" 2>/dev/null | grep -vE '^/(tmp|dev|proc|usr|var|etc|bin|sbin|opt|lib|boot|run|sys)/' || true)
  if [[ -n "$abs_paths" ]]; then
    while IFS= read -r abs_path; do
      [[ -z "$abs_path" ]] && continue
      log_warn "$rel_path" "contains hardcoded absolute path: $abs_path (use relative or \$REPO_ROOT)"
      ((warns++))
    done <<< "$abs_paths"
  fi
done < <(find "$REPO_ROOT" -maxdepth 3 -name "*.md" -o -name "*.sh" -o -name "*.py" -print0 2>/dev/null)

# --- 4. 入口文件死链（BLOCK 级别） ---
for entry in CLAUDE.md AGENTS.md; do
  [[ -f "$REPO_ROOT/$entry" ]] || continue
  while IFS= read -r link; do
    [[ "$link" =~ ^https?:// ]] && continue
    [[ "$link" =~ ^# ]] && continue
    [[ -z "$link" ]] && continue
    clean_link="${link%%#*}"
    if [[ "$clean_link" == ./* || "$clean_link" == ../* ]]; then
      target="$REPO_ROOT/$clean_link"
      target="${target%/*}" # 如果是目录路径
      if ! [[ -e "${target}" || -e "${target%.md}.md" ]]; then
        log_block "$entry" "contains dead link: $link"
        ((blocks++))
      fi
    fi
  done < <(extract_markdown_links "$REPO_ROOT/$entry")
done

exit_with_status "$warns" "$blocks"
