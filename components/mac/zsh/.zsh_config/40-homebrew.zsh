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

# 无界面 LibreOffice 使用的内置 Fontconfig 默认找不到本机中文字体。
# 复用 Homebrew 的标准配置，保留用户在私有 env 中明确选择的其他配置。
if [[ -z "${FONTCONFIG_FILE:-}" ]]; then
  for fontconfig_file in /opt/homebrew/etc/fonts/fonts.conf /usr/local/etc/fonts/fonts.conf; do
    if [[ -r "$fontconfig_file" ]]; then
      export FONTCONFIG_FILE="$fontconfig_file"
      break
    fi
  done
  unset fontconfig_file
fi
