# 个人 Mac 之间共享的 Homebrew 依赖。
#
# 约定：
# - 多台 Mac 都需要的工具放在这里并提交到 dotfiles。
# - 仅当前机器需要的软件写入根目录 Brewfile.local（默认不提交）。
# - 不要用 `brew bundle dump --force` 覆盖本文件，以免混入整台机器的软件快照。

# 基础开发环境
brew "git"
brew "gh"
# 链接入口依赖 Stow；终端编辑器配置依赖 Neovim。
brew "stow"
brew "neovim"
# nvim-treesitter main 分支编译 parser 需要 tree-sitter CLI，不能仅依赖运行库。
brew "tree-sitter-cli"
# Python 为脚本提供基础解释器；项目环境由 uv 管理，不全局恢复旧机 pip 包。
brew "python"
brew "uv"

# 脚本与配置质量检查
brew "shellcheck"
brew "shfmt"
brew "yamlfmt"
brew "stylua"

# 编辑、文档与日常命令行工具
# Node 不在 Homebrew 重复安装；bootstrap/node.sh 先准备 Node，再补装 Yarn/Prettier。
brew "pdf2svg"
brew "imagemagick"
brew "grip"
brew "wget"

# 模型与视频处理能力
brew "hf"
brew "ffmpeg"
brew "yt-dlp"
brew "whisper-cpp"

# 本地服务运行时
brew "podman"
brew "podman-compose"
# GUI 软件和 Java/多版本管理器按需写入 Brewfile.local，默认不安装 Docker Desktop。
