#!/bin/bash
# 新机分阶段入口；prepare/network 在尚无 Homebrew Python/Git 时也可执行。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
stage="${1:-help}"
case "$stage" in
help | -h | --help)
  cat <<'HELP'
用法：./workbench new-mac 阶段 [参数]

新机：network → prepare → software → config → services
旧机：export（小配置）；backup（排空后备份业务）
传输：receive 账号@IP；copy-data 账号@IP；receive-backup 账号@IP
恢复：restore openclaw|litellm|multica；login-multica；bind-multica；apply-multica 已审阅摘要
最后：startup；verify；verify（完整关机开机并登录后再次执行）

每次只运行指定阶段，不自动进入下一阶段。人工检查项见 docs/new-mac-prepare.md。
HELP
  exit 0
  ;;
network | prepare | software | config | services | export | backup | receive | copy-data | receive-backup | restore | login-multica | bind-multica | apply-multica | startup | verify) ;;
*)
  echo '未知阶段；运行 ./workbench new-mac help 查看。' >&2
  exit 2
  ;;
esac
if [[ "$(uname -s)" != Darwin || "$(id -u)" == 0 || -z "${HOME:-}" || "$HOME" != /* || "$HOME" == / || ! -d "$HOME" ]]; then
  echo '请在 macOS 普通用户账号下运行，HOME 必须是已有用户目录。' >&2
  exit 1
fi
# FlClash 的系统代理不一定传给终端；保留显式代理，否则发现项目约定的本机端口。
if [[ -z "${https_proxy:-${HTTPS_PROXY:-${http_proxy:-${HTTP_PROXY:-${ALL_PROXY:-${all_proxy:-}}}}}}" ]] &&
  nc -z -G 1 127.0.0.1 7890 >/dev/null 2>&1; then
  export http_proxy=http://127.0.0.1:7890 https_proxy=http://127.0.0.1:7890
fi
export NO_PROXY="${NO_PROXY:-localhost,127.0.0.1,::1}"
if [[ "$stage" == network || "$stage" == prepare ]]; then
  [[ $# == 1 ]] || {
    echo '此阶段不接受额外参数。' >&2
    exit 2
  }
  for url in https://raw.githubusercontent.com/Homebrew/install/HEAD/README.md https://github.com/iampkuhz/feipi-agent-kit; do
    curl -fsIL --connect-timeout 10 --max-time 45 "$url" >/dev/null
  done
  echo '终端访问 GitHub 和 Homebrew 来源通过；不代表容器镜像和账号已验收。'
  if [[ "$stage" == network ]]; then
    echo '人工检查：FlClash 已登录并同步节点，浏览器能正常打开所需网站。下一步：prepare。'
    exit 0
  fi
  if ! /bin/bash "$ROOT/scripts/bootstrap/prerequisites.sh" check; then
    echo '准备系统工具需要本人管理员授权；密码只在终端输入。'
    sudo -v
    /bin/bash "$ROOT/scripts/bootstrap/prerequisites.sh" install
  fi
  # shellcheck source=../../components/mac/bootstrap/environment.sh
  source "$ROOT/components/mac/bootstrap/environment.sh"
  destination="$HOME/Documents/tools/llm/feipi-agent-kit"
  if [[ -e "$destination" || -L "$destination" ]]; then
    actual="$(git -C "$destination" rev-parse --show-toplevel)"
    [[ "$(cd "$destination" && pwd -P)" == "$actual" ]] || {
      echo '正式目录不是独立 Git 仓库，未覆盖。' >&2
      exit 1
    }
    origin="$(git -C "$destination" remote get-url origin)"
    case "$origin" in
    https://github.com/iampkuhz/feipi-agent-kit.git | git@github.com:iampkuhz/feipi-agent-kit.git) ;;
    *)
      echo '正式目录的 origin 不匹配，未修改。' >&2
      exit 1
      ;;
    esac
    echo '保留已有正式仓库及其修改，不自动 pull。'
  else
    mkdir -p "$(dirname "$destination")"
    git clone --depth 1 https://github.com/iampkuhz/feipi-agent-kit.git "$destination"
  fi
  echo "人工检查：正式仓库位于 $destination；在 Codex/终端中切换到该目录。"
  echo '下一步：./workbench new-mac software'
  exit 0
fi
# 后续阶段只用正式 Git 工作区；ZIP 源码用于前置准备。
if [[ ! -e "$ROOT/.git" ]]; then
  echo '请先 prepare，再从正式 Git 仓库运行此阶段。' >&2
  exit 1
fi
# shellcheck source=../../components/mac/bootstrap/environment.sh
source "$ROOT/components/mac/bootstrap/environment.sh"
/bin/bash "$ROOT/scripts/bootstrap/prerequisites.sh" check >/dev/null
exec python3 "$ROOT/scripts/workbench/new_mac.py" "$@"
