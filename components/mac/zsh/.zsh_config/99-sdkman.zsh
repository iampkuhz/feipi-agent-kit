# SDKMAN：默认放在最后，避免 PATH / function 被前面配置覆盖。
#
# Homebrew tap 安装的 sdkman-cli 不放在 ~/.sdkman，而是放在：
#   /opt/homebrew/opt/sdkman-cli/libexec  （Apple Silicon）
#   /usr/local/opt/sdkman-cli/libexec     （Intel / 老 Homebrew）
# 官方 curl 安装器仍然使用 ~/.sdkman。这里优先选择 Homebrew tap 的目录，
# 避免旧的 ~/.sdkman 残留或父进程里的 SDKMAN_DIR 抢占 Homebrew 安装。
if [[ -s "/opt/homebrew/opt/sdkman-cli/libexec/bin/sdkman-init.sh" ]]; then
  # Homebrew Apple Silicon 默认安装位置。
  export SDKMAN_DIR="/opt/homebrew/opt/sdkman-cli/libexec"
elif [[ -s "/usr/local/opt/sdkman-cli/libexec/bin/sdkman-init.sh" ]]; then
  # Homebrew Intel 默认安装位置。
  export SDKMAN_DIR="/usr/local/opt/sdkman-cli/libexec"
elif [[ -n "${SDKMAN_DIR:-}" && -s "$SDKMAN_DIR/bin/sdkman-init.sh" ]]; then
  # 如果外部环境已经提供了可用的 SDKMAN_DIR，且没有检测到 Homebrew 安装，就直接沿用。
  export SDKMAN_DIR
elif [[ -s "$HOME/.sdkman/bin/sdkman-init.sh" ]]; then
  # 官方 curl 安装器默认安装位置。
  export SDKMAN_DIR="$HOME/.sdkman"
else
  # 新机未安装 SDKMAN 时不定义 java 等占位函数，保留系统或独立 JDK 的命令。
  # 本文件由 .zshrc source；return 只结束当前模块，不退出交互 shell。
  return 0
fi

# 启动加速：改为懒加载，只有首次调用 sdk/java/javac/mvn/gradle 时才 source sdkman-init.sh。
# 每个 wrapper 自包含 lazy-load 逻辑，不依赖外部 helper 函数，避免 shell snapshot 恢复时缺失。
sdk() {
  if [[ ! -s "$SDKMAN_DIR/bin/sdkman-init.sh" ]]; then
    print -u2 "SDKMAN init 脚本不存在：$SDKMAN_DIR/bin/sdkman-init.sh"
    print -u2 "如果通过 Homebrew 安装，请确认 brew info sdkman-cli 的 caveats 与 SDKMAN_DIR 一致。"
    return 127
  fi
  source "$SDKMAN_DIR/bin/sdkman-init.sh"
  # sdkman-init.sh 会定义真正的 sdk 函数；这里不能 unset sdk，
  # 否则会把刚加载出来的真实函数也删掉，只清掉其他懒加载占位函数。
  unset -f java javac mvn gradle
  sdk "$@"
}
java() {
  if [[ ! -s "$SDKMAN_DIR/bin/sdkman-init.sh" ]]; then
    print -u2 "SDKMAN init 脚本不存在：$SDKMAN_DIR/bin/sdkman-init.sh"
    print -u2 "如果通过 Homebrew 安装，请确认 brew info sdkman-cli 的 caveats 与 SDKMAN_DIR 一致。"
    return 127
  fi
  source "$SDKMAN_DIR/bin/sdkman-init.sh"
  # java 本身是 PATH 里的可执行文件，不是 SDKMAN 函数；source 后删除占位函数再重新查找命令。
  unset -f java javac mvn gradle
  java "$@"
}
javac() {
  if [[ ! -s "$SDKMAN_DIR/bin/sdkman-init.sh" ]]; then
    print -u2 "SDKMAN init 脚本不存在：$SDKMAN_DIR/bin/sdkman-init.sh"
    print -u2 "如果通过 Homebrew 安装，请确认 brew info sdkman-cli 的 caveats 与 SDKMAN_DIR 一致。"
    return 127
  fi
  source "$SDKMAN_DIR/bin/sdkman-init.sh"
  # javac 本身是 PATH 里的可执行文件，不是 SDKMAN 函数；source 后删除占位函数再重新查找命令。
  unset -f java javac mvn gradle
  javac "$@"
}
mvn() {
  if [[ ! -s "$SDKMAN_DIR/bin/sdkman-init.sh" ]]; then
    print -u2 "SDKMAN init 脚本不存在：$SDKMAN_DIR/bin/sdkman-init.sh"
    print -u2 "如果通过 Homebrew 安装，请确认 brew info sdkman-cli 的 caveats 与 SDKMAN_DIR 一致。"
    return 127
  fi
  source "$SDKMAN_DIR/bin/sdkman-init.sh"
  # mvn 本身是 PATH 里的可执行文件，不是 SDKMAN 函数；source 后删除占位函数再重新查找命令。
  unset -f java javac mvn gradle
  mvn "$@"
}
gradle() {
  if [[ ! -s "$SDKMAN_DIR/bin/sdkman-init.sh" ]]; then
    print -u2 "SDKMAN init 脚本不存在：$SDKMAN_DIR/bin/sdkman-init.sh"
    print -u2 "如果通过 Homebrew 安装，请确认 brew info sdkman-cli 的 caveats 与 SDKMAN_DIR 一致。"
    return 127
  fi
  source "$SDKMAN_DIR/bin/sdkman-init.sh"
  # gradle 本身是 PATH 里的可执行文件，不是 SDKMAN 函数；source 后删除占位函数再重新查找命令。
  unset -f java javac mvn gradle
  gradle "$@"
}
