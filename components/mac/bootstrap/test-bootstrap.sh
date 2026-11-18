#!/usr/bin/env bash
# 用替身验证唯一安装顺序与失败传播。
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEST_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/dotfiles-bootstrap.XXXXXX")"
trap 'rm -rf "$TEST_ROOT"' EXIT
mkdir -p "$TEST_ROOT/repo/bootstrap" "$TEST_ROOT/bin" "$TEST_ROOT/home/.nvm/test-bin" "$TEST_ROOT/home/.cargo/bin"
cp "$REPO_ROOT/bootstrap/run.sh" "$REPO_ROOT/bootstrap/environment.sh" "$TEST_ROOT/repo/bootstrap/"
for stage in brew node rust agents ohmyzsh apps desktop-extras; do
  cat >"$TEST_ROOT/repo/bootstrap/$stage.sh" <<'STUB'
#!/bin/bash
set -eu
stage="${0##*/}"
stage="${stage%.sh}"
[[ "$1" == install ]]
printf '%s\n' "$stage" >>"$TEST_CALLS"
if [[ "$stage" == agents || "$stage" == ohmyzsh ]]; then
  [[ "$(node --version)" == TEST_NODE_READY ]]
  [[ "$(rustup --version)" == TEST_RUST_READY ]]
fi
if [[ "$stage" == "${TEST_FAIL_STAGE:-}" ]]; then exit 42; fi
STUB
done
printf '#!/bin/sh\necho Darwin\n' >"$TEST_ROOT/bin/uname"
# shellcheck disable=SC2016
printf '#!/bin/sh\necho "${TEST_UID:-501}"\n' >"$TEST_ROOT/bin/id"
printf '#!/bin/sh\necho TEST_NODE_READY\n' >"$TEST_ROOT/home/.nvm/test-bin/node"
printf '#!/bin/sh\necho TEST_RUST_READY\n' >"$TEST_ROOT/home/.cargo/bin/rustup"
chmod +x "$TEST_ROOT/bin/"* "$TEST_ROOT/home/.nvm/test-bin/node" "$TEST_ROOT/home/.cargo/bin/rustup"
cat >"$TEST_ROOT/home/.nvm/nvm.sh" <<'NVM'
nvm() { export PATH="$HOME/.nvm/test-bin:$PATH"; }
NVM

run_entry() {
  : >"$TEST_ROOT/calls"
  env -i HOME="$TEST_ROOT/home" PATH="$TEST_ROOT/bin:/usr/bin:/bin" \
    LANG="${TEST_LOCALE:-C}" LC_ALL="${TEST_LOCALE:-C}" \
    TEST_CALLS="$TEST_ROOT/calls" TEST_FAIL_STAGE="${fail_stage:-}" TEST_UID="${test_uid:-501}" \
    /bin/bash "$TEST_ROOT/repo/bootstrap/run.sh"
}
status=0
test_uid=0
run_entry || status=$?
[[ "$status" == 2 && ! -s "$TEST_ROOT/calls" ]]
test_uid=501
run_entry
printf '%s\n' brew node rust agents ohmyzsh apps desktop-extras >"$TEST_ROOT/expected"
cmp "$TEST_ROOT/expected" "$TEST_ROOT/calls"
for fail_stage in brew node rust agents ohmyzsh apps desktop-extras; do
  status=0
  run_entry || status=$?
  [[ "$status" == 42 && "$(tail -n 1 "$TEST_ROOT/calls")" == "$fail_stage" ]]
done
echo "通过：固定安装顺序，Agent CLI 和补全继承运行环境，失败立即停止。"

# 首次打开应用会新建 ~/.omlx/bin；激活时目录尚不存在也必须预留其 PATH 优先级。
# 只有通用入口时可调用，原生入口出现后必须自动使用它，不依赖手工追加 PATH。
cli_home="$TEST_ROOT/cli-home"
mkdir -p "$cli_home/.local/bin"
printf '#!/bin/sh\necho COMPAT_CLI\n' >"$cli_home/.local/bin/omlx"
chmod +x "$cli_home/.local/bin/omlx"
# 测试脚本里的变量由子进程展开，不能在父进程提前替换 HOME。
# shellcheck disable=SC2016
env -i HOME="$cli_home" PATH="$TEST_ROOT/bin:/usr/bin:/bin" \
  ENVIRONMENT_SCRIPT="$REPO_ROOT/bootstrap/environment.sh" /bin/bash -c '
  set -eu
  source "$ENVIRONMENT_SCRIPT"
  [[ "$(omlx)" == COMPAT_CLI ]]
  mkdir -p "$HOME/.omlx/bin"
  printf "#!/bin/sh\\necho NATIVE_CLI\\n" >"$HOME/.omlx/bin/omlx"
  chmod +x "$HOME/.omlx/bin/omlx"
  [[ "$(omlx)" == NATIVE_CLI ]]
'
cli_home="$TEST_ROOT/zsh-cli-home"
mkdir -p "$cli_home/.local/bin"
printf '#!/bin/sh\necho COMPAT_CLI\n' >"$cli_home/.local/bin/omlx"
chmod +x "$cli_home/.local/bin/omlx"
# 测试脚本里的变量由子进程展开，不能在父进程提前替换 HOME。
# shellcheck disable=SC2016
env -i HOME="$cli_home" PATH="/usr/bin:/bin" ZSH_RC="$REPO_ROOT/zsh/.zshrc" \
  zsh -fc '
  source "$ZSH_RC"
  [[ "$(omlx)" == COMPAT_CLI ]] || exit 1
  mkdir -p "$HOME/.omlx/bin"
  printf "#!/bin/sh\\necho NATIVE_CLI\\n" >"$HOME/.omlx/bin/omlx"
  chmod +x "$HOME/.omlx/bin/omlx"
  [[ "$(omlx)" == NATIVE_CLI ]] || exit 1
'
echo "通过：Bash/Zsh 无需手工改 PATH，首次创建后优先使用 oMLX 原生入口。"
