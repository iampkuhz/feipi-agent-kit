# =========================
# 1) 加载全局私有环境变量文件：~/.env（不进 git）
# =========================
ZSH_ENV_FILE="$HOME/.env"
if [[ -r "$ZSH_ENV_FILE" ]]; then
  set -a          # 自动 export 该文件里定义的变量
  source "$ZSH_ENV_FILE"
  set +a
fi

# =========================
# 2) 加载模块化配置：~/.zsh_config/*.zsh（可进 git）
# =========================
ZSH_CONFIG_DIR="$HOME/.zsh_config"
if [[ -d "$ZSH_CONFIG_DIR" ]]; then
  # 启动性能观测开关：1=打印每个 zsh 配置脚本的结束时间和耗时，0=关闭打印。
  # 默认关闭；如果未来需要排查启动慢，可在 ~/.env 里设置 ZSH_STARTUP_PROFILE=1 临时打开。
  : ${ZSH_STARTUP_PROFILE:=0}

  # 启用 EPOCHREALTIME（秒级浮点时间戳），用于计算 source 每个脚本的耗时。
  # 这里直接加载 zsh/datetime，避免某些环境下 `-F b:EPOCHREALTIME` 早期不可用导致前几个脚本漏记。
  zmodload zsh/datetime 2>/dev/null || true

  for f in "$ZSH_CONFIG_DIR"/*.zsh(N); do
    _zsh_file_start="$EPOCHREALTIME"
    source "$f"

    if [[ "$ZSH_STARTUP_PROFILE" == "1" && -n "${EPOCHREALTIME:-}" && -n "${_zsh_file_start:-}" ]]; then
      _zsh_file_end="$EPOCHREALTIME"
      _zsh_file_cost_ms=$(( (_zsh_file_end - _zsh_file_start) * 1000.0 ))
      strftime -s _zsh_end_ts "%Y-%m-%d %H:%M:%S" "$EPOCHSECONDS"
      printf '[zsh-startup] end=%s end_epoch=%.3f file=%s cost=%.2fms\n' \
        "$_zsh_end_ts" "$_zsh_file_end" "${f:t}" "$_zsh_file_cost_ms"
    fi
  done

  unset _zsh_file_start _zsh_file_end _zsh_file_cost_ms _zsh_end_ts
fi

# QODER_DISPATCHER_PATH v1
path=("$HOME/.qoder/entry" ${path:#"$HOME/.qoder/entry"})
export PATH
# END QODER_DISPATCHER_PATH v1
