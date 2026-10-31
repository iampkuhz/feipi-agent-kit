#!/usr/bin/env bash
# 离线验证链接安全性；HOME 仅在子进程中指向临时目录，不加载真实 shell 配置。
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEST_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/dotfiles-links.XXXXXX")"
# 失败时保留诊断输出供阅读；无论成功或失败都只删除本次测试目录。
cleanup() {
  local status=$?
  if [[ "$status" -ne 0 && -f "$TEST_ROOT/output.log" ]]; then
    cat "$TEST_ROOT/output.log" >&2
  fi
  rm -rf "$TEST_ROOT"
}
trap cleanup EXIT
run_linker() {
  HOME="$1" bash "$REPO_ROOT/bootstrap/macosinit.sh" "${2:-install}" >"$TEST_ROOT/output.log" 2>&1
}
expect_conflict() {
  if run_linker "$1"; then
    echo "预期拒绝冲突，但脚本成功：$1" >&2
    exit 1
  fi
  # 冲突时不能提前链接另一个包，保证先整体预检。
  [[ ! -e "$1/bin/doctor-zsh-config" ]]
}

# 首次安装：连 HOME 本身都不存在，验证父目录创建及 Neovim 的真实层级。
test_home="$TEST_ROOT/fresh home/home"
run_linker "$test_home"
[[ "$test_home/.config/nvim/init.vim" -ef "$REPO_ROOT/neovim/.config/nvim/init.vim" ]]
[[ "$test_home/.config/nvim/lazy-lock.json" -ef "$REPO_ROOT/neovim/.config/nvim/lazy-lock.json" ]]
[[ "$test_home/.zshrc" -ef "$REPO_ROOT/zsh/.zshrc" ]]
run_linker "$test_home"
run_linker "$test_home" check
run_linker "$test_home" verify
echo "通过：全新 HOME、重复执行、只读预检。"

# 四文件抽查之外的模块也必须验证；移除的仅是临时 HOME 内的软链。
rm "$test_home/.zsh_config/62-nvm.zsh"
printf '# old configuration\n' >"$TEST_ROOT/old-nvm.zsh"
ln -s "$TEST_ROOT/old-nvm.zsh" "$test_home/.zsh_config/62-nvm.zsh"
if run_linker "$test_home" verify; then
  echo "来源错误的非抽查模块不应通过。" >&2
  exit 1
fi
grep -q '62-nvm.zsh' "$TEST_ROOT/output.log"
[[ "$test_home/.zsh_config/62-nvm.zsh" -ef "$TEST_ROOT/old-nvm.zsh" ]]
rm "$test_home/.zsh_config/62-nvm.zsh"
if run_linker "$test_home" verify; then
  echo "缺失模块不应通过。" >&2
  exit 1
fi
run_linker "$test_home"
run_linker "$test_home" verify
echo "通过：全量来源验证发现错误链接与缺失，不修改目标。"

# 只读预检面对缺失 HOME 也不能偷偷创建父目录。
if run_linker "$TEST_ROOT/readonly/missing" check; then
  echo "缺失 HOME 的检查不应成功。" >&2
  exit 1
fi
[[ ! -e "$TEST_ROOT/readonly" ]]
if run_linker "$TEST_ROOT/readonly/missing" verify; then
  echo "缺失 HOME 不应被报告为已安装。" >&2
  exit 1
fi
[[ ! -e "$TEST_ROOT/readonly" ]]
echo "通过：缺失 HOME 的只读检查不创建目录。"

# 正确的旧式目录链接也可复用，不能为了重新安装而删除它们。
test_home="$TEST_ROOT/legacy"
mkdir -p "$test_home/.config"
ln -s "$REPO_ROOT/neovim/.config/nvim" "$test_home/.config/nvim"
ln -s "$REPO_ROOT/zsh/.zshrc" "$test_home/.zshrc"
ln -s "$REPO_ROOT/zsh/.zsh_config" "$test_home/.zsh_config"
run_linker "$test_home"
run_linker "$test_home"
run_linker "$test_home" verify
[[ "$test_home/.config/nvim/init.vim" -ef "$REPO_ROOT/neovim/.config/nvim/init.vim" ]]
[[ "$(readlink "$test_home/.config/nvim")" == "$REPO_ROOT/neovim/.config/nvim" ]]
echo "通过：正确的旧式链接与重复执行。"

# 用户级 Stow 的 ignore 不能让入口悄悄跳过配置。
test_home="$TEST_ROOT/user-ignore"
mkdir -p "$test_home"
echo '--ignore=.*' >"$test_home/.stowrc"
run_linker "$test_home"
run_linker "$test_home" verify
[[ "$test_home/.zshrc" -ef "$REPO_ROOT/zsh/.zshrc" ]]
[[ "$test_home/.config/nvim/init.vim" -ef "$REPO_ROOT/neovim/.config/nvim/init.vim" ]]
echo "通过：用户级 Stow ignore 不影响固定安装范围。"

# 真实文件、断链和原先的错误 Neovim 目录链接都不能被覆盖。
for conflict_kind in zsh_file nvim_file broken_link wrong_nvim parent_file user_adopt; do
  test_home="$TEST_ROOT/$conflict_kind"
  mkdir -p "$test_home/.config/nvim"
  case "$conflict_kind" in
  zsh_file) echo "保留我的配置" >"$test_home/.zshrc" ;;
  user_adopt)
    echo '--adopt' >"$test_home/.stowrc"
    echo "保留我的配置" >"$test_home/.zshrc"
    ;;
  nvim_file) echo "保留我的配置" >"$test_home/.config/nvim/init.vim" ;;
  broken_link) ln -s "$test_home/missing" "$test_home/.zshrc" ;;
  wrong_nvim)
    rmdir "$test_home/.config/nvim"
    ln -s "$REPO_ROOT/neovim" "$test_home/.config/nvim"
    ;;
  parent_file)
    rmdir "$test_home/.config/nvim" "$test_home/.config"
    echo "保留我的配置" >"$test_home/.config"
    ;;
  esac
  expect_conflict "$test_home"
  case "$conflict_kind" in
  zsh_file | user_adopt) [[ "$(cat "$test_home/.zshrc")" == "保留我的配置" ]] ;;
  nvim_file) [[ "$(cat "$test_home/.config/nvim/init.vim")" == "保留我的配置" ]] ;;
  broken_link) [[ "$(readlink "$test_home/.zshrc")" == "$test_home/missing" ]] ;;
  wrong_nvim) [[ "$(readlink "$test_home/.config/nvim")" == "$REPO_ROOT/neovim" ]] ;;
  parent_file) [[ "$(cat "$test_home/.config")" == "保留我的配置" ]] ;;
  esac
  echo "通过：拒绝冲突并保全内容（${conflict_kind}）。"
done
