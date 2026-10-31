#!/usr/bin/env bash
# 总入口只在临时仓库中运行：所有安装阶段和外部命令都是离线替身。
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEST_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/dotfiles-bootstrap.XXXXXX")"
cleanup() {
  local status=$?
  if [[ "$status" != 0 && -f "$TEST_ROOT/output" ]]; then cat "$TEST_ROOT/output" >&2; fi
  rm -rf "$TEST_ROOT"
}
trap cleanup EXIT
mkdir -p "$TEST_ROOT/repo/bootstrap" "$TEST_ROOT/bin" "$TEST_ROOT/home"
cp "$REPO_ROOT/bootstrap/run.sh" "$TEST_ROOT/repo/bootstrap/run.sh"
touch "$TEST_ROOT/repo/Brewfile"
# 每个替身记录阶段；中途失败后不应再到达“阶段完成”记录。
for stage in brew node rust ohmyzsh macosinit; do
  cat >"$TEST_ROOT/repo/bootstrap/$stage.sh" <<'STAGE'
#!/bin/bash
set -euo pipefail
stage="${0##*/}"
stage="${stage%.sh}:$1"
printf '%s\n' "$stage" >> "$TEST_CALLS"
if [[ "$stage" == "${TEST_FAIL_STAGE:-}" ]]; then
  /bin/sh -c 'exit 42'
fi
if [[ "$stage" == macosinit:check && "${TEST_FAIL_AFTER_BREW:-0}" == 1 ]] && grep -qx brew:install "$TEST_COMPLETED"; then
  /bin/sh -c 'exit 43'
fi
printf '%s\n' "$stage" >> "$TEST_COMPLETED"
STAGE
done
cat >"$TEST_ROOT/bin/uname" <<'MOCK'
#!/bin/sh
echo Darwin
MOCK
cat >"$TEST_ROOT/bin/id" <<'MOCK'
#!/bin/sh
echo "${TEST_UID:-501}"
MOCK
cat >"$TEST_ROOT/bin/xcode-select" <<'MOCK'
#!/bin/sh
[ "$1" = -p ] || exit 98
echo /mock/clt
MOCK
cat >"$TEST_ROOT/bin/xcrun" <<'MOCK'
#!/bin/sh
[ "$*" = '--find clang' ] || exit 98
exit "${TEST_CLT_STATUS:-0}"
MOCK
for forbidden in brew curl git node npm rustup stow; do
  cat >"$TEST_ROOT/bin/$forbidden" <<'MOCK'
#!/bin/sh
echo "不应真实调用：$0 $*" >> "$TEST_FORBIDDEN"
exit 97
MOCK
done
chmod +x "$TEST_ROOT/bin/"*
run_entry() {
  : >"$TEST_ROOT/calls"
  : >"$TEST_ROOT/completed"
  # env -i 不继承用户 BASH_ENV、工具目录或凭据；HOME 只传给这个测试子进程。
  env -i HOME="$test_home" PATH="$TEST_ROOT/bin:/usr/bin:/bin" \
    TEST_CALLS="$TEST_ROOT/calls" TEST_COMPLETED="$TEST_ROOT/completed" \
    TEST_FORBIDDEN="$TEST_ROOT/forbidden" TEST_FAIL_STAGE="${test_fail_stage:-}" \
    TEST_FAIL_AFTER_BREW="${test_fail_after_brew:-0}" \
    TEST_CLT_STATUS="${test_clt_status:-0}" TEST_UID="${test_uid:-501}" \
    /bin/bash "$TEST_ROOT/repo/bootstrap/run.sh" "$@" >"$TEST_ROOT/output" 2>&1
}

test_home="$TEST_ROOT/missing/home"
run_entry plan
[[ ! -e "$TEST_ROOT/missing" && ! -s "$TEST_ROOT/calls" && ! -e "$TEST_ROOT/forbidden" ]]
grep -q '未核实.*链接冲突' "$TEST_ROOT/output"
echo "通过：预览不创建 HOME，不执行已发现的工具。"

test_home="$TEST_ROOT/home"
mkdir -p "$test_home/.nvm"
for startup in .env .zshrc .nvm/nvm.sh; do
  # 保留字面量 HOME；只有被错误加载时才在被测子进程中展开。
  # shellcheck disable=SC2016
  printf 'echo loaded >"$HOME/should-not-exist"\n' >"$test_home/$startup"
done
run_entry plan
[[ ! -e "$test_home/should-not-exist" && ! -e "$TEST_ROOT/forbidden" ]]
[[ "$(cat "$TEST_ROOT/calls")" == macosinit:check ]]
grep -q '发现 nvm.sh' "$TEST_ROOT/output"
# 安装流程的替身不会准备真实 Node，后面的安装测试不需要这个诱饵文件。
rm "$test_home/.nvm/nvm.sh"
echo "通过：预览不加载 .env、.zshrc 或 nvm.sh，仅调用链接预检。"

test_clt_status=1
if run_entry; then
  echo "CLT 不完整时不应安装。" >&2
  exit 1
fi
[[ ! -s "$TEST_ROOT/calls" ]]
grep -q '失败位置：首次准备检查' "$TEST_ROOT/output"
if run_entry plan; then
  echo "预览应报告 CLT 阻塞。" >&2
  exit 1
fi
grep -q '存在阻塞' "$TEST_ROOT/output"
test_clt_status=0
test_uid=0
if run_entry; then
  echo "root 不应执行安装。" >&2
  exit 1
fi
[[ ! -s "$TEST_ROOT/calls" ]]
test_uid=501
echo "通过：CLT 不完整或 root 时，安装阶段零调用。"

test_fail_stage=macosinit:check
status=0
run_entry || status=$?
[[ "$status" == 42 && "$(cat "$TEST_ROOT/calls")" == macosinit:check ]]
grep -q '失败位置：安装前链接冲突预检' "$TEST_ROOT/output"
if run_entry plan; then
  echo "预览应报告链接冲突。" >&2
  exit 1
fi
[[ "$(cat "$TEST_ROOT/calls")" == macosinit:check ]]
echo "通过：安装前冲突阻止全部安装。"

test_fail_stage=""
test_fail_after_brew=1
status=0
run_entry || status=$?
[[ "$status" == 43 && "$(tail -n 1 "$TEST_ROOT/calls")" == macosinit:check ]]
grep -q 'Homebrew：完成' "$TEST_ROOT/output"
grep -q 'Node/npm：未执行' "$TEST_ROOT/output"
grep -q '失败位置：Homebrew 后链接冲突复检' "$TEST_ROOT/output"
test_fail_after_brew=0
echo "通过：Homebrew 后复检失败保留已完成项，阻止后续工具链。"

for stage in brew node rust ohmyzsh macosinit; do
  test_fail_stage="$stage:install"
  status=0
  run_entry || status=$?
  [[ "$status" == 42 ]]
  [[ "$(tail -n 1 "$TEST_ROOT/calls")" == "$test_fail_stage" ]]
  if grep -qx "$test_fail_stage" "$TEST_ROOT/completed"; then
    echo "失败阶段不应继续运行。" >&2
    exit 1
  fi
  grep -q "处理原因后重试：bash bootstrap/$stage.sh install" "$TEST_ROOT/output"
  if grep -q '^初始化完成。' "$TEST_ROOT/output"; then exit 1; fi
  echo "通过：$stage 失败保留退出码，停止后续阶段并给出重试入口。"
done
test_fail_stage=""
run_entry
cat >"$TEST_ROOT/expected" <<'EXPECTED'
macosinit:check
brew:install
macosinit:check
node:install
rust:install
ohmyzsh:install
macosinit:install
EXPECTED
cmp "$TEST_ROOT/expected" "$TEST_ROOT/calls"
grep -q '^初始化完成。' "$TEST_ROOT/output"
[[ ! -e "$TEST_ROOT/forbidden" ]]
echo "通过：固定顺序、Homebrew 后复检以及成功提示。"

# 当前 PATH 没有 Stow 时，首次冲突检查跳过，但 Homebrew 后的复检仍必须执行。
rm "$TEST_ROOT/bin/stow"
run_entry
[[ "$(head -n 1 "$TEST_ROOT/calls")" == brew:install ]]
grep -qx macosinit:check "$TEST_ROOT/calls"
echo "通过：首次没有 Stow 时仍执行 Homebrew 后的强制复检。"
