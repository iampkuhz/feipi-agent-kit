#!/usr/bin/env bash
# 在隔离 HOME 中通过工作台实际运行 Stow，不下载安装软件或加载自启。
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKBENCH_DIR="$REPO_ROOT/../../scripts/workbench"
TEST_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/dotfiles-links.XXXXXX")"
trap 'rm -rf "$TEST_ROOT"' EXIT

test_home="$TEST_ROOT/runtime home"
runtime_root="$test_home/.local/share/feipi-workbench/mac"
mkdir -p "$runtime_root/zsh" "$runtime_root/neovim/.config/nvim" "$test_home/.config" "$test_home/.qwen" "$test_home/bin"
printf '# Previous standalone .zshrc\n' >"$runtime_root/zsh/.zshrc"
cp "$runtime_root/zsh/.zshrc" "$test_home/.zshrc"
ln -s "$runtime_root/neovim/.config/nvim" "$test_home/.config/nvim"
printf 'FEIPI_TEST_ENV=local\n' >"$test_home/.env"
printf 'keep Qwen settings\n' >"$test_home/.qwen/settings.json"
printf 'keep personal bin\n' >"$test_home/bin/user-tool"
printf '%s\n' '--adopt' >"$test_home/.stowrc"

run_install() {
  HOME="$test_home" PYTHONDONTWRITEBYTECODE=1 python3 - "$WORKBENCH_DIR" <<'PY'
import sys

sys.path.insert(0, sys.argv[1])
import main

run = main.run


def run_local_stow(args, **kwargs):
    if args[0] == 'stow':
        return run(args, **kwargs)
    if args[1].name in ('run.sh', 'env-history.py'):
        return
    raise AssertionError(f'Unexpected installation command: {args}')


main.run = run_local_stow
main.install('mac')
PY
}

run_verify() {
  HOME="$1" bash "$REPO_ROOT/bootstrap/verify-config.sh" >"$TEST_ROOT/output.log" 2>&1
}

run_install
run_install
run_verify "$test_home" || {
  cat "$TEST_ROOT/output.log" >&2
  exit 1
}
for target in .zshrc .zsh_config/10-ohmyzsh.zsh .config/nvim/init.vim .qwen/output-language.md \
  .config/karabiner/karabiner.json 'Library/Application Support/iTerm2/DynamicProfiles/dotfiles.json'; do
  [[ -L "$test_home/$target" && "$test_home/$target" -ef "$runtime_root/dotfiles/$target" ]]
done
[[ ! -L "$test_home/.env" && "$(cat "$test_home/.env")" == 'FEIPI_TEST_ENV=local' ]]
[[ "$(cat "$test_home/.qwen/settings.json")" == 'keep Qwen settings' ]]
[[ "$(cat "$test_home/bin/user-tool")" == 'keep personal bin' ]]
printf 'FEIPI_LOCAL_MODULE=loaded\n' >"$test_home/.zsh_config/98-local.zsh"
# shellcheck disable=SC2016
HOME="$test_home" ZDOTDIR="$test_home" zsh -ic '
  [[ "$FEIPI_TEST_ENV" == local && "$EDITOR" == nvim && "$FEIPI_LOCAL_MODULE" == loaded ]] &&
    (( $+functions[path_prepend] ))
'

printf '\n-- stale runtime\n' >>"$runtime_root/dotfiles/.config/nvim/lua/basic.lua"
if run_verify "$test_home"; then exit 1; fi
grep -q 'basic.lua' "$TEST_ROOT/output.log"
run_install
run_verify "$test_home"
[[ -f "$test_home/.zsh_config/98-local.zsh" ]]

rm "$test_home/.zshrc"
printf 'keep custom zshrc\n' >"$test_home/.zshrc"
if run_install >"$TEST_ROOT/output.log" 2>&1; then exit 1; fi
grep -q '配置文件已存在' "$TEST_ROOT/output.log"
[[ ! -L "$test_home/.zshrc" && "$(cat "$test_home/.zshrc")" == 'keep custom zshrc' ]]
if run_verify "$TEST_ROOT/missing"; then exit 1; fi
[[ ! -e "$TEST_ROOT/missing" ]]
echo "通过：Stow 发布与重复安装、真实 Zsh 加载、用户配置冲突及漂移检查。"
