#!/usr/bin/env bash
# 新 Mac 初始化：plan 只读展示；无参数才按固定依赖顺序安装。
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="${1:-install}"
dependencies_only=0
if [[ "${2:-}" == --dependencies-only ]]; then dependencies_only=1; fi
if [[ $# -gt 2 || ($# == 2 && "$dependencies_only" == 0) || ("$MODE" != install && "$MODE" != plan) ]]; then
  echo "用法：bash bootstrap/run.sh [plan|install]；日常检查用 bash bootstrap/check.sh。" >&2
  exit 2
fi
# 统一仓库中由工作台备份、发布运行副本；保留独立组件的源码链接调试和隔离测试。
workbench_entry="$REPO_ROOT/../../workbench"
if [[ "$dependencies_only" == 0 && -f "$workbench_entry" ]]; then
  if [[ "$MODE" == plan ]]; then exec bash "$workbench_entry" plan mac; fi
  bash "$workbench_entry" install mac
  exec bash "$workbench_entry" apply mac
fi
# 顺序只有这一处定义，预览和执行共用；Node/Rust 先于依赖它们生成补全的 oh-my-zsh。
stages=(brew node rust ohmyzsh macosinit)
labels=(Homebrew Node/npm Rust oh-my-zsh 配置链接)
results=(未执行 未执行 未执行 未执行 未执行)
if [[ "$dependencies_only" == 1 ]]; then
  stages=(brew node rust ohmyzsh)
  labels=(Homebrew Node/npm Rust oh-my-zsh)
  results=(未执行 未执行 未执行 未执行)
fi
brew_command=""

check_prerequisites() {
  local result=0 required_command
  if [[ "$(uname -s)" != Darwin ]]; then
    echo "[阻塞] 该入口仅支持 macOS。" >&2
    result=1
  fi
  if [[ "$(id -u)" == 0 ]]; then
    echo "[阻塞] 请以普通用户运行，不要 sudo 整个初始化脚本。" >&2
    result=1
  fi
  if [[ -z "${HOME:-}" || "$HOME" != /* || "$HOME" == / ]]; then
    echo "[阻塞] HOME 必须是非根目录的绝对路径。" >&2
    return 1
  fi
  if [[ -e "$HOME" && ! -d "$HOME" ]]; then
    echo "[阻塞] HOME 已被文件占用：$HOME" >&2
    result=1
  fi
  # 目录记录之外还检查 clang；这两项都不会打开安装界面。
  if xcode-select -p >/dev/null 2>&1 && xcrun --find clang >/dev/null 2>&1; then
    echo "[通过] Command Line Tools 已可定位编译器。"
  else
    echo "[阻塞] 请先执行 xcode-select --install，在系统界面完成后重试。" >&2
    result=1
  fi
  brew_command="$(command -v brew || true)"
  if [[ -z "$brew_command" ]]; then
    if [[ -x /opt/homebrew/bin/brew ]]; then
      brew_command=/opt/homebrew/bin/brew
    elif [[ -x /usr/local/bin/brew ]]; then
      brew_command=/usr/local/bin/brew
    fi
  fi
  if [[ -n "$brew_command" ]]; then
    echo "[已发现] Homebrew：${brew_command}（预检不执行 brew）"
  else
    echo "[阻塞] 请先按 https://brew.sh/ 安装 Homebrew。" >&2
    result=1
  fi
  for required_command in git curl; do
    if command -v "$required_command" >/dev/null 2>&1; then
      echo "[已发现] ${required_command}：$(command -v "$required_command")"
    else
      echo "[阻塞] 缺少前置命令：$required_command" >&2
      result=1
    fi
  done
  if [[ ! -f "$REPO_ROOT/Brewfile" ]]; then
    echo "[阻塞] 缺少共享清单：$REPO_ROOT/Brewfile" >&2
    result=1
  fi
  return "$result"
}

show_plan() {
  local result=0 index
  echo "首次准备检查（不是每次开机重装）："
  check_prerequisites || result=1
  echo
  echo "安装计划（只读，不执行安装、升级、下载或用户启动配置）："
  for index in "${!stages[@]}"; do
    printf '[%s/%s] %s：bash bootstrap/%s.sh install\n' "$((index + 1))" "${#stages[@]}" "${labels[$index]}" "${stages[$index]}"
  done
  echo "共享依赖：$REPO_ROOT/Brewfile（不在预览中解析 Ruby 或核验包版本）"
  if [[ -f "$REPO_ROOT/Brewfile.local" ]]; then
    echo "单机依赖：$REPO_ROOT/Brewfile.local"
  else
    echo "单机依赖：没有 Brewfile.local，跳过。"
  fi
  if [[ -s "${NVM_DIR:-${HOME:-}/.nvm}/nvm.sh" ]]; then
    echo "Node：发现 nvm.sh；计划优先复用，default 是否有效留待安装阶段核验。"
  elif command -v node >/dev/null 2>&1; then
    echo "Node：发现系统入口，计划复用；npm 完整性留待安装阶段核验。"
  else
    echo "Node：未发现 nvm.sh/Node 入口；安装阶段将检查目录冲突后补装 nvm + LTS。"
  fi
  echo "Rust：保留已有工具链；缺失时补装，默认版本留待安装阶段核验。"
  echo "oh-my-zsh：补装主题/插件并更新补全；失败的补全保留旧缓存。"
  echo "配置目标：${HOME:-<未设置>} 下的 Zsh/Neovim；冲突不接管。"
  # 缺 Stow 或 HOME 时只标记未核实；安装完成 Homebrew 后还会强制复检。
  if [[ "$dependencies_only" == 1 ]]; then
    echo "配置由 workbench apply mac 备份后发布到运行副本；不建立源码链接。"
  elif [[ -n "${HOME:-}" && "$HOME" == /* && "$HOME" != / && -d "$HOME" ]] && command -v stow >/dev/null 2>&1; then
    bash "$REPO_ROOT/bootstrap/macosinit.sh" check || result=1
  else
    echo "[未核实] 链接冲突：需要已有 HOME 和 PATH 中的 Stow；没有为预览创建或安装。"
  fi
  echo "桌面应用由 install mac --apps 安装，配置由 apply mac 备份后恢复；独立组件可用 desktop.sh。"
  echo "仍需人工确认：安装网络/代理可用；没有执行联网探测。"
  if [[ "$result" == 0 ]]; then
    echo "预览结束：未发现已检查范围内的阻塞；未核实项不代表通过。"
  else
    echo "预览结束：存在阻塞，请处理上方提示；本次没有安装或修改文件。" >&2
  fi
  return "$result"
}

if [[ "$MODE" == plan ]]; then
  show_plan
  exit 0
fi

current_step="首次准备检查"
current_index=-1
retry="bash bootstrap/run.sh plan"
finish() {
  # EXIT 覆盖前置检查和阶段子进程失败；保留原退出码，不靠最后一次 echo 判成功。
  local status=$? index
  trap - EXIT
  if [[ "$status" != 0 ]]; then
    if [[ "$current_index" -ge 0 ]]; then results[current_index]=失败; fi
    echo "初始化未完成；已成功的安装保留，不自动回滚。" >&2
    for index in "${!stages[@]}"; do
      printf '  %s：%s\n' "${labels[$index]}" "${results[$index]}" >&2
    done
    printf '失败位置：%s（退出码 %s）\n处理原因后重试：%s\n' "$current_step" "$status" "$retry" >&2
    echo "单模块成功后，可重新运行 bash bootstrap/run.sh；仍会重新核验前置条件。" >&2
  fi
  exit "$status"
}
trap finish EXIT
check_prerequisites
# 只有安装分支执行 Homebrew 环境初始化，plan 不执行任何 brew 子命令。
if ! command -v brew >/dev/null 2>&1; then
  # 先捕获输出，让 shellenv 本身的失败也能停止入口，而不是被 eval 的成功掩盖。
  brew_environment="$("$brew_command" shellenv)"
  eval "$brew_environment"
fi
current_step="安装前链接冲突预检"
retry="bash bootstrap/macosinit.sh check"
if [[ "$dependencies_only" == 0 ]] && command -v stow >/dev/null 2>&1 && [[ -d "$HOME" ]]; then
  bash "$REPO_ROOT/bootstrap/macosinit.sh" check
fi

for index in "${!stages[@]}"; do
  current_index=$index
  current_step="${labels[$index]}"
  retry="bash bootstrap/${stages[$index]}.sh install"
  results[index]=执行中
  printf '[%s/%s] %s\n' "$((index + 1))" "${#stages[@]}" "$current_step"
  if [[ "${stages[$index]}" == ohmyzsh ]]; then
    # 前面的 Node 子进程无法改变父进程 PATH；为补全重新激活同一个 default。
    if [[ -s "${NVM_DIR:-$HOME/.nvm}/nvm.sh" ]]; then
      export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
      set +u
      # shellcheck source=/dev/null
      source "$NVM_DIR/nvm.sh" --no-use
      nvm use --silent default
      set -u
    fi
    export PATH="${CARGO_HOME:-$HOME/.cargo}/bin:$PATH"
  fi
  # 独立 Bash 子进程保留子脚本的 set -e 语义，不用 if 包住整段安装函数。
  bash "$REPO_ROOT/bootstrap/${stages[$index]}.sh" install
  results[index]=完成
  current_index=-1
  if [[ "${stages[$index]}" == brew && "$dependencies_only" == 0 ]]; then
    current_step="Homebrew 后链接冲突复检"
    retry="bash bootstrap/macosinit.sh check"
    mkdir -p "$HOME"
    bash "$REPO_ROOT/bootstrap/macosinit.sh" check
  fi
done
if [[ "$dependencies_only" == 1 ]]; then
  echo "依赖安装阶段完成；配置仍需 workbench apply mac 发布。"
else
  echo "初始化完成。新开终端后执行 bash bootstrap/check.sh 和 bash bootstrap/brew.sh check。"
fi
echo "GUI、编辑器插件和业务服务仍需按 docs/setup.md 与 MIGRATION.md 人工验收。"
