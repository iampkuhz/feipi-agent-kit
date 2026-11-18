if [[ -r "$HOME/.oh-my-zsh/oh-my-zsh.sh" ]]; then
  export ZSH="$HOME/.oh-my-zsh"

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

  # 手动更新使用 omz update，启动时不执行 Git 更新。
  zstyle ':omz:update' mode disabled

  # 关闭自动转义字符串
  DISABLE_MAGIC_FUNCTIONS="true"

  # 自动纠错
  ENABLE_CORRECTION="false"

  # 历史记录时间戳格式
  HIST_STAMPS="yyyy-mm-dd"

  # 【性能优化】禁用 yarn 插件的 global bin 路径检测（执行 yarn global bin 很慢）
  # 如果需要 yarn global bin，可手动添加 ~/.yarn/bin 到 PATH
  zstyle ':omz:plugins:yarn' global-path no

  # 插件列表
  plugins=(
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
  # 让 oh-my-zsh 统一初始化补全、加载主题和插件。
  source "$ZSH/oh-my-zsh.sh"
  if (( ${plugins[(Ie)openclaw]} == 0 )) && [[ -r "$HOME/.openclaw/completions/openclaw.zsh" ]]; then
    source "$HOME/.openclaw/completions/openclaw.zsh"
  fi
fi
