# 用户自行安装的命令；例如 uv tool 的入口和少量本机启动脚本。
path_prepend "$HOME/.local/bin"
# Stow 将 doctor-zsh-config 放在 ~/bin；放到 PATH 末尾以便直接调用。
path_append "$HOME/bin"

# Rust
path_prepend "$HOME/.cargo/bin"

# Perl（用于 LaTeX format）
path_prepend "/opt/homebrew/opt/perl/bin"

# Solana CLI
path_prepend "$HOME/.local/share/solana/install/active_release/bin"

# LM Studio CLI
path_prepend "$HOME/.lmstudio/bin"

# utoo-proxy
path_prepend "$HOME/.utoo-proxy"

# postgresql
#只有安装了 postgresql@18 才加到环境变量里面
# 启动： brew services start postgresql@18

# 启动加速：避免每次 shell 启动都调用 `brew --prefix`（外部进程开销较大）。
# 对于 Apple Silicon，brew 标准安装路径固定为 /opt/homebrew/opt/<formula>/bin，可直接检测目录。
if [[ -d "/opt/homebrew/opt/postgresql@18/bin" ]]; then
  path=("/opt/homebrew/opt/postgresql@18/bin" $path)
fi

# libpq（包含 psql 等命令，不需要安装完整的 postgresql）
if [[ -d "/opt/homebrew/opt/libpq/bin" ]]; then
  path=("/opt/homebrew/opt/libpq/bin" $path)
fi
