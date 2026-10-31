# Homebrew 自动更新频率（秒）：7 天
export HOMEBREW_AUTO_UPDATE_SECS=604800
# API 元数据更新也改成7天
export HOMEBREW_API_AUTO_UPDATE_SECS=604800

# Homebrew 官方源：直接获取元数据、Git 仓库和预编译包，避免镜像失败后再回退
export HOMEBREW_API_DOMAIN="https://formulae.brew.sh/api"
export HOMEBREW_BREW_GIT_REMOTE="https://github.com/Homebrew/brew"
export HOMEBREW_CORE_GIT_REMOTE="https://github.com/Homebrew/homebrew-core"
export HOMEBREW_BOTTLE_DOMAIN="https://ghcr.io/v2/homebrew/core"

# 将 Homebrew 路径放到前面（Apple Silicon）
path_prepend "/opt/homebrew/bin"
path_prepend "/opt/homebrew/sbin"
