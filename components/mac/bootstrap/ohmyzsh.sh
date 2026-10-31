#!/usr/bin/env bash
set -euo pipefail

# 共享的缓存发布函数只在命令和语法检查成功后替换旧文件。
# shellcheck source=bootstrap/completion-cache.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/completion-cache.sh"
completion_failures=0
update_completion() {
  if ! write_completion_cache "$@"; then
    completion_failures=$((completion_failures + 1))
  fi
}

# 这个脚本补装 oh-my-zsh 及当前仓库 zsh 配置依赖的外部主题/插件。
# 默认保留已有仓库，只有显式 upgrade 才更新。
# 同时预生成部分补全缓存，避免 zsh 启动时执行耗时的补全生成命令。

ZSH_DIR="${ZSH:-$HOME/.oh-my-zsh}"
ZSH_CUSTOM_DIR="${ZSH_CUSTOM:-$ZSH_DIR/custom}"
ZSH_CACHE_DIR="${ZSH_CACHE_DIR:-$ZSH_DIR/cache}"
MODE="${1:-install}"
if [[ "$MODE" != install && "$MODE" != upgrade ]]; then
  echo "用法：bash bootstrap/ohmyzsh.sh [install|upgrade]" >&2
  exit 2
fi

# 目标存在但不是 Git 仓库时拒绝接管，避免覆盖用户手工安装的内容。
install_or_update_repo() {
  local repo_url="$1"
  local target_dir="$2"

  if [[ -d "$target_dir/.git" ]]; then
    if [[ "$MODE" == upgrade ]]; then
      # 有本地修改时交给用户处理，不自动 stash、reset 或合并。
      if [[ -n "$(git -C "$target_dir" status --porcelain)" ]]; then
        echo "仓库存在本地修改，停止升级：$target_dir" >&2
        exit 1
      fi
      echo "更新: $target_dir"
      git -C "$target_dir" pull --ff-only
    else
      echo "保留已有仓库: $target_dir"
    fi
  elif [[ -e "$target_dir" || -L "$target_dir" ]]; then
    echo "目录冲突，请人工检查：$target_dir" >&2
    exit 1
  else
    echo "安装: $target_dir"
    # 使用浅克隆减少首次安装时间和流量。
    git clone --depth=1 "$repo_url" "$target_dir"
  fi
}

if ! command -v git >/dev/null 2>&1; then
  echo "错误: 未检测到 git，请先安装 git 后再执行。"
  exit 1
fi

# 不继承业务目录的 rust-toolchain 覆盖设置，补全生成不应触发业务工具链下载。
cd "$HOME"

# 先准备 oh-my-zsh 主体目录；后续主题与插件都依赖该目录结构。
install_or_update_repo "https://github.com/ohmyzsh/ohmyzsh.git" "$ZSH_DIR"

# 确保 custom 目录存在；主题和第三方插件统一放在这里，避免污染主仓库。
mkdir -p "$ZSH_CUSTOM_DIR/themes" "$ZSH_CUSTOM_DIR/plugins"

# 确保缓存目录存在（helm/rust/npm 等插件需要写入补全缓存）
mkdir -p "$ZSH_CACHE_DIR/completions"

# 安装 spaceship 主题，并创建 oh-my-zsh 可识别的主题软链名称。
install_or_update_repo \
  "https://github.com/spaceship-prompt/spaceship-prompt.git" \
  "$ZSH_CUSTOM_DIR/themes/spaceship-prompt"
# 正确链接可重复使用；错误链接或真实文件均不覆盖。
theme_source="$ZSH_CUSTOM_DIR/themes/spaceship-prompt/spaceship.zsh-theme"
theme_target="$ZSH_CUSTOM_DIR/themes/spaceship.zsh-theme"
if [[ -L "$theme_target" && "$theme_target" -ef "$theme_source" ]]; then
  echo "保留已有主题链接。"
elif [[ -e "$theme_target" || -L "$theme_target" ]]; then
  echo "主题链接冲突，请人工检查：$theme_target" >&2
  exit 1
else
  ln -s "$theme_source" "$theme_target"
fi

# 安装 zsh 配置中声明的外部插件（内置插件 git/kubectl 不需要单独安装）。
install_or_update_repo \
  "https://github.com/zsh-users/zsh-autosuggestions.git" \
  "$ZSH_CUSTOM_DIR/plugins/zsh-autosuggestions"
install_or_update_repo \
  "https://github.com/zdharma-continuum/fast-syntax-highlighting.git" \
  "$ZSH_CUSTOM_DIR/plugins/fast-syntax-highlighting"
# zsh-autocomplete 已在配置中禁用，不把未启用插件列为新机必装项。
install_or_update_repo \
  "https://github.com/Katrovsky/zsh-ollama-completion.git" \
  "$ZSH_CUSTOM_DIR/plugins/ollama"

# ===========================================================================
# 预生成补全缓存（避免 zsh 启动时执行耗时的补全生成命令）
# 这些补全脚本安装到本地 $ZSH_CACHE_DIR/completions，不进入代码仓库。
# ===========================================================================
echo "预生成补全缓存..."

# helm 补全（如果 helm 命令存在）
if command -v helm >/dev/null 2>&1; then
  echo "  生成 helm 补全..."
  update_completion "$ZSH_CACHE_DIR/completions/_helm" helm completion zsh
fi

# rustup/cargo 补全（如果 rustup 命令存在）
if command -v rustup >/dev/null 2>&1; then
  echo "  生成 rustup 补全..."
  update_completion "$ZSH_CACHE_DIR/completions/_rustup" rustup completions zsh
  # cargo 补全需要从 rustup 管理的 sysroot 中获取
  if command -v cargo >/dev/null 2>&1; then
    echo "  生成 cargo 补全..."
    # 获取 cargo 补全文件路径
    _cargo_binary="$(rustup which cargo 2>/dev/null)" || _cargo_binary=""
    _cargo_comp_src="${_cargo_binary%/*}/../share/zsh/site-functions/_cargo"
    if [[ -f "$_cargo_comp_src" ]]; then
      update_completion "$ZSH_CACHE_DIR/completions/_cargo" cat "$_cargo_comp_src"
    else
      # 如果找不到，生成一个代理补全文件
      update_completion "$ZSH_CACHE_DIR/completions/_cargo" cat <<'CARGO_EOF'
#compdef cargo
# 代理补全：运行时从 rustup sysroot 加载实际补全
_cargo_sysroot="$(rustup run stable rustc --print sysroot 2>/dev/null)"
if [[ -f "$_cargo_sysroot/share/zsh/site-functions/_cargo" ]]; then
  source "$_cargo_sysroot/share/zsh/site-functions/_cargo"
fi
CARGO_EOF
    fi
  fi
fi
# docker 补全（如果 docker 命令存在）
if command -v docker >/dev/null 2>&1; then
  echo "  生成 docker 补全..."
  update_completion "$ZSH_CACHE_DIR/completions/_docker" docker completion zsh
fi

# ===========================================================================
# 生成 oh-my-zsh custom plugin 包装文件
# ===========================================================================

# Codex 补全插件：预生成到缓存，启动时只读缓存，不执行命令
mkdir -p "$ZSH_CUSTOM_DIR/plugins/codex"
cat >"$ZSH_CUSTOM_DIR/plugins/codex/codex.plugin.zsh" <<'EOF'
# Codex 补全插件
# 【性能优化】不在启动时执行 codex 命令，而是从缓存文件加载补全。

_codex_comp_cache="${ZSH_CACHE_DIR:-$HOME/.oh-my-zsh/cache}/completions/_codex"

if [[ -f "$_codex_comp_cache" ]]; then
  source "$_codex_comp_cache"
elif (( $+commands[codex] )); then
  echo "[codex] 补全缓存不存在，请运行: bash bootstrap/ohmyzsh.sh" >&2
fi

unset _codex_comp_cache
EOF
# 预生成 codex 补全缓存（如果命令存在）
if command -v codex >/dev/null 2>&1; then
  echo "  生成 codex 补全..."
  update_completion "$ZSH_CACHE_DIR/completions/_codex" codex completion zsh
fi

# OpenClaw 也采用同样方式：把补全注册放到 custom plugin 中，统一由 oh-my-zsh 管理加载时机。
# 【重要】不在启动时执行 openclaw 命令，而是预生成到缓存文件，避免启动延迟。
mkdir -p "$ZSH_CUSTOM_DIR/plugins/openclaw"
cat >"$ZSH_CUSTOM_DIR/plugins/openclaw/openclaw.plugin.zsh" <<'EOF'
# OpenClaw 补全插件
# 【性能优化】不在启动时执行 openclaw 命令，而是从缓存文件加载补全。
# 如果缓存不存在，提示用户运行 bootstrap/ohmyzsh.sh 生成。

_openclaw_comp_cache="${ZSH_CACHE_DIR:-$HOME/.oh-my-zsh/cache}/completions/_openclaw"

if [[ -f "$_openclaw_comp_cache" ]]; then
  # 缓存存在，直接 source（快速）
  source "$_openclaw_comp_cache"
elif (( $+commands[openclaw] )); then
  # 命令存在但缓存不存在，提示用户生成
  echo "[openclaw] 补全缓存不存在，请运行: bash bootstrap/ohmyzsh.sh" >&2
fi

unset _openclaw_comp_cache
EOF
# 预生成 openclaw 补全缓存（如果命令存在）
if command -v openclaw >/dev/null 2>&1; then
  echo "  生成 openclaw 补全..."
  update_completion "$ZSH_CACHE_DIR/completions/_openclaw" openclaw completion --shell zsh
fi

echo "oh-my-zsh 与相关插件处理完成（${MODE}）；补全更新失败/跳过 $completion_failures 项。"
if [[ "$completion_failures" -gt 0 ]]; then
  echo "已有补全缓存已保留；排查对应命令后重跑 bash bootstrap/ohmyzsh.sh install。" >&2
fi
echo "   补全缓存目录: $ZSH_CACHE_DIR/completions"
