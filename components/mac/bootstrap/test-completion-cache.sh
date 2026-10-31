#!/usr/bin/env bash
# 离线验证缓存发布和真实 ohmyzsh 调用路径；安装目录和命令均使用临时替身。
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEST_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/dotfiles-completion.XXXXXX")"
trap 'rm -rf "$TEST_ROOT"' EXIT
# shellcheck source=bootstrap/completion-cache.sh
source "$REPO_ROOT/bootstrap/completion-cache.sh"
target="$TEST_ROOT/_example"
printf '#compdef example\necho old\n' >"$target"
cp "$target" "$TEST_ROOT/original"
for failure in 'exit 7' 'echo partial; exit 8' 'exit 0' 'echo "if then"'; do
  if write_completion_cache "$target" /bin/sh -c "$failure"; then
    echo "应拒绝失败、空输出或语法错误。" >&2
    exit 1
  fi
  cmp "$target" "$TEST_ROOT/original"
done
write_completion_cache "$target" printf '#compdef example\necho new\n'
grep -q 'echo new' "$target"
ln -s "$target" "$TEST_ROOT/link"
if write_completion_cache "$TEST_ROOT/link" printf 'echo replaced\n'; then exit 1; fi
grep -q 'echo new' "$target"
if find "$TEST_ROOT" -name '*.tmp.*' -o -name '*.err.*' | grep -q .; then
  echo "临时文件未清理。" >&2
  exit 1
fi
echo "通过：失败/半截/空/语法错误保全旧缓存，成功替换，链接不接管。"

# 模拟已经安装的 Git 目录；若脚本意外尝试 clone，git 替身会立即失败。
test_home="$TEST_ROOT/home"
test_zsh="$test_home/.oh-my-zsh"
mkdir -p "$TEST_ROOT/bin" "$test_zsh/.git" "$test_zsh/cache/completions"
for repo in themes/spaceship-prompt plugins/zsh-autosuggestions plugins/fast-syntax-highlighting plugins/ollama; do
  mkdir -p "$test_zsh/custom/$repo/.git"
done
touch "$test_zsh/custom/themes/spaceship-prompt/spaceship.zsh-theme"
cat >"$TEST_ROOT/bin/git" <<'MOCK'
#!/bin/sh
echo '不应联网安装' >&2
exit 97
MOCK
cat >"$TEST_ROOT/bin/helm" <<'MOCK'
#!/bin/sh
echo partial
exit 9
MOCK
for tool in rustup cargo docker codex openclaw; do
  cat >"$TEST_ROOT/bin/$tool" <<'MOCK'
#!/bin/sh
if [ "$1" = which ]; then exit 1; fi
printf '#compdef mock\n_mock() { :; }\n'
MOCK
done
chmod +x "$TEST_ROOT/bin/"*
cp "$TEST_ROOT/original" "$test_zsh/cache/completions/_helm"
env -i HOME="$test_home" PATH="$TEST_ROOT/bin:/usr/bin:/bin" \
  /bin/bash "$REPO_ROOT/bootstrap/ohmyzsh.sh" install >"$TEST_ROOT/output" 2>&1
cmp "$TEST_ROOT/original" "$test_zsh/cache/completions/_helm"
grep -q '补全更新失败/跳过 1 项' "$TEST_ROOT/output"
for cache in _rustup _cargo _docker _codex _openclaw; do
  [[ -s "$test_zsh/cache/completions/$cache" ]]
done
[[ ! -e "$test_home/.zshrc" ]]
echo "通过：ohmyzsh 实际调用保全失败的 Helm 缓存，其他补全独立更新。"
