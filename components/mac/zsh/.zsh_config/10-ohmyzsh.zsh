# ===========================================================================
# 内部耗时分析辅助函数（仅当 ZSH_STARTUP_PROFILE=1 时打印）
# ===========================================================================
_omz_profile_print() {
  if [[ "$ZSH_STARTUP_PROFILE" == "1" && -n "${EPOCHREALTIME:-}" ]]; then
    local now="$EPOCHREALTIME"
    local cost_ms=$(( (now - _omz_last_checkpoint) * 1000.0 ))
    printf '  [omz-detail] %s cost=%.2fms\n' "$1" "$cost_ms"
    _omz_last_checkpoint="$now"
  fi
}

# 初始化检查点时间戳
_omz_last_checkpoint="${EPOCHREALTIME:-0}"

# oh-my-zsh 主目录
export ZSH="$HOME/.oh-my-zsh"

# ===========================================================================
# 关键变量初始化（必须在加载任何 oh-my-zsh 组件之前设置）
# 这些变量原本由 oh-my-zsh.sh 设置，但我们为了性能跳过了部分加载流程，
# 所以需要手动初始化。
# ===========================================================================

# ZSH_CUSTOM: 自定义主题和插件目录
[[ -n "$ZSH_CUSTOM" ]] || ZSH_CUSTOM="$ZSH/custom"

# ZSH_CACHE_DIR: 缓存目录（helm/rust/npm 等插件需要写入补全缓存）
[[ -n "$ZSH_CACHE_DIR" ]] || ZSH_CACHE_DIR="$ZSH/cache"
# 确保缓存目录可写，否则使用 $HOME/.cache
if [[ ! -w "$ZSH_CACHE_DIR" ]]; then
  ZSH_CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/oh-my-zsh"
fi
# 创建补全缓存目录
mkdir -p "$ZSH_CACHE_DIR/completions"

# 主题
ZSH_THEME="spaceship"

# ===========================================================================
# oh-my-zsh 行为配置
# ===========================================================================

# 更新频率：13 天一次（减少启动时的 git 检查开销）
zstyle ':omz:update' frequency 13

# 【性能优化】禁用自动更新检查，启动时不执行 git 操作
# 这是之前 5 秒延迟的主要原因！手动更新可运行: omz update
DISABLE_AUTO_UPDATE="true"

# 关闭自动转义字符串
DISABLE_MAGIC_FUNCTIONS="true"

# 自动纠错
ENABLE_CORRECTION="false"

# 历史记录时间戳格式
HIST_STAMPS="yyyy-mm-dd"

# 【性能优化】禁用 yarn 插件的 global bin 路径检测（执行 yarn global bin 很慢）
# 如果需要 yarn global bin，可手动添加 ~/.yarn/bin 到 PATH
zstyle ':omz:plugins:yarn' global-path no

_omz_profile_print "config-vars-ready"

# 插件列表
plugins=(
  # zsh-autocomplete 必须放在最前面：
  # 它内部会调用 compinit 并接管补全系统，需要先于其他插件加载。
  # 注意：.zshrc 中不能手动调用 compinit，否则会导致 .autocomplete:async:* bad file descriptor。
  #  有 bug，运行冲突
  # zsh-autocomplete

  # 以下插件由 oh-my-zsh 内置，主要用于补全与常用别名。
  # 这类命令可以直接通过 plugins 参数启用，不需要额外安装第三方插件仓库。
  git
  kubectl
  aws
  brew
  docker
  docker-compose
  gh
  helm
  node
  npm
  pip
  poetry
  python
  rust
  terraform
  uv
  yarn

  # 以下是第三方增强插件（需要 bootstrap/ohmyzsh.sh 安装到 custom/plugins）。

  # 当前行补全提示，按 → 接受
  zsh-autosuggestions

  # 高亮（与 zsh-syntax-highlighting 二选一）
  fast-syntax-highlighting

  # https://github.com/Katrovsky/zsh-ollama-completion
  ollama
)

# codex 补全插件由 bootstrap/ohmyzsh.sh 生成到 custom/plugins/codex。
# 为了避免首次启动时出现 `[oh-my-zsh] plugin 'codex' not found`，这里按文件存在再启用。
_codex_plugin_file="${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/plugins/codex/codex.plugin.zsh"
if [[ -r "$_codex_plugin_file" ]]; then
  plugins+=(codex)
fi
unset _codex_plugin_file

# openclaw 补全插件由 bootstrap/ohmyzsh.sh 生成到 custom/plugins/openclaw。
# 与 codex 相同：只有插件文件存在时才加入 plugins，避免首次启动时报 plugin not found。
_openclaw_plugin_file="${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/plugins/openclaw/openclaw.plugin.zsh"
if [[ -r "$_openclaw_plugin_file" ]]; then
  plugins+=(openclaw)
fi
unset _openclaw_plugin_file

_omz_profile_print "plugins-list-ready"

# ===========================================================================
# 为了深入分析 oh-my-zsh 内部加载耗时，临时 hook source 函数
# 这会打印每个插件和主题的加载时间
# ===========================================================================
if [[ "$ZSH_STARTUP_PROFILE" == "1" ]]; then
  # 保存原始 source 命令（用于后续恢复）
  # 创建一个 wrapper 来追踪 oh-my-zsh 加载的插件/主题文件
  _omz_tracked_sources=()

  # 在 oh-my-zsh 加载前，hook 掉 compinit（它是最慢的部分之一）
  # 通过设置 skip_global_compinit 来观察是否是 compinit 导致的慢
  # （注：这里不真正跳过，只是打印提示）

  _omz_source_start="$EPOCHREALTIME"
fi

# 加载 oh-my-zsh（必须在 plugins / theme 之后）
# ===========================================================================
# 分步加载以精确定位耗时（替代直接 source oh-my-zsh.sh）
# ===========================================================================
if [[ "$ZSH_STARTUP_PROFILE" == "1" ]]; then
  # ---------- 分步加载 oh-my-zsh 以精确定位耗时 ----------
  # 参考 oh-my-zsh.sh 的加载顺序：
  # 1) 设置 fpath（补全函数路径）
  # 2) autoload 并执行 compinit（必须在加载 lib 之前，否则 compdef 报错）
  # 3) 加载 lib/*.zsh（核心函数库）
  # 4) 加载插件
  # 5) 加载主题

  # ---------- 1. 设置 fpath ----------
  # 添加 oh-my-zsh 的函数和补全路径
  fpath=($ZSH/{functions,completions} $ZSH_CUSTOM/{functions,completions} $fpath)
  # 添加缓存补全目录到 fpath
  (( ${fpath[(Ie)$ZSH_CACHE_DIR/completions]} )) || fpath=("$ZSH_CACHE_DIR/completions" $fpath)
  # 添加所有插件目录到 fpath（插件可能提供补全函数）
  for _omz_plugin in "${plugins[@]}"; do
    _omz_plugin_dir="${ZSH_CUSTOM}/plugins/$_omz_plugin"
    [[ -d "$_omz_plugin_dir" ]] || _omz_plugin_dir="$ZSH/plugins/$_omz_plugin"
    [[ -d "$_omz_plugin_dir" ]] && fpath=("$_omz_plugin_dir" $fpath)
  done
  _omz_profile_print "fpath-setup"

  # ---------- 2. 先初始化 compinit（解决 compdef not found） ----------
  _omz_compinit_start="$EPOCHREALTIME"
  autoload -Uz compinit
  # -C: 跳过安全检查（不检查 zcompdump 文件权限），加速启动
  # -d: 指定 zcompdump 缓存文件路径
  compinit -C -d "${ZSH_COMPDUMP:-$HOME/.zcompdump}"
  _omz_compinit_end="$EPOCHREALTIME"
  _omz_compinit_cost_ms=$(( (_omz_compinit_end - _omz_compinit_start) * 1000.0 ))
  printf '    [omz-compinit] cost=%.2fms\n' "$_omz_compinit_cost_ms"

  # ---------- 3. 加载 oh-my-zsh 核心库 ----------
  for _omz_lib_file in "$ZSH"/lib/*.zsh(N); do
    source "$_omz_lib_file"
  done
  _omz_profile_print "lib/*.zsh-loaded"

  # ---------- 4. 逐个加载插件并计时 ----------
  for _omz_plugin in "${plugins[@]}"; do
    _omz_plugin_start="$EPOCHREALTIME"

    # 插件可能在 custom/plugins 或 plugins 目录
    _omz_plugin_dir="${ZSH_CUSTOM:-$ZSH/custom}/plugins/$_omz_plugin"
    if [[ ! -d "$_omz_plugin_dir" ]]; then
      _omz_plugin_dir="$ZSH/plugins/$_omz_plugin"
    fi

    # 加载插件主文件
    if [[ -f "$_omz_plugin_dir/$_omz_plugin.plugin.zsh" ]]; then
      source "$_omz_plugin_dir/$_omz_plugin.plugin.zsh"
    elif [[ -f "$_omz_plugin_dir/_$_omz_plugin" ]]; then
      # 有些插件只提供补全函数文件
      fpath=("$_omz_plugin_dir" $fpath)
    fi

    _omz_plugin_end="$EPOCHREALTIME"
    _omz_plugin_cost_ms=$(( (_omz_plugin_end - _omz_plugin_start) * 1000.0 ))
    printf '    [omz-plugin] %s cost=%.2fms\n' "$_omz_plugin" "$_omz_plugin_cost_ms"
  done
  _omz_profile_print "all-plugins-loaded"

  # ---------- 5. 加载主题 ----------
  _omz_theme_file="$ZSH/themes/$ZSH_THEME.zsh-theme"
  if [[ ! -f "$_omz_theme_file" ]]; then
    # 尝试 custom 主题目录
    _omz_theme_file="$ZSH/custom/themes/$ZSH_THEME.zsh-theme"
  fi
  if [[ -f "$_omz_theme_file" ]]; then
    source "$_omz_theme_file"
  fi
  _omz_profile_print "theme($ZSH_THEME)-loaded"

  # 清理临时变量
  unset _omz_lib_file _omz_theme_file _omz_plugin _omz_plugin_dir
  unset _omz_plugin_start _omz_plugin_end _omz_plugin_cost_ms
  unset _omz_compinit_start _omz_compinit_end _omz_compinit_cost_ms

else
  # 非 profile 模式：正常加载 oh-my-zsh
  source "$ZSH/oh-my-zsh.sh"
fi

# 清理 profile 辅助函数
unset -f _omz_profile_print
unset _omz_last_checkpoint