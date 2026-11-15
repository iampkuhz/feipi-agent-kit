#!/bin/bash
set -euo pipefail
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
TEST_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/feipi-bootstrap-test.XXXXXX")"
trap 'rm -rf "$TEST_ROOT"' EXIT
mkdir -p "$TEST_ROOT/source/skill" "$TEST_ROOT/consumer/scripts" "$TEST_ROOT/consumer/skill-list"
cp "$REPO_DIR/scripts/bootstrap.sh" "$TEST_ROOT/consumer/scripts/bootstrap.sh"
cat >"$TEST_ROOT/source/skill/SKILL.md" <<'EOF'
---
name: bootstrap-commit-fixture
description: Fixed commit installation regression fixture.
---
EOF
mkdir -p "$TEST_ROOT/source/skill/scripts"
printf 'runtime\n' >"$TEST_ROOT/source/skill/scripts/keep.txt"
for development_dir in maintenance tests evals node_modules nested/maintenance nested/tests nested/evals nested/node_modules; do
  mkdir -p "$TEST_ROOT/source/skill/$development_dir"
  printf 'development-only\n' >"$TEST_ROOT/source/skill/$development_dir/sentinel"
done
git -C "$TEST_ROOT/source" init --quiet
git -C "$TEST_ROOT/source" add -f skill
git -C "$TEST_ROOT/source" -c user.name=Test -c user.email=test@example.invalid commit --quiet -m fixture
fixture_commit="$(git -C "$TEST_ROOT/source" rev-parse HEAD)"
# A later HEAD proves that the requested object, not the current branch, is used.
echo later >"$TEST_ROOT/source/later.txt"
git -C "$TEST_ROOT/source" add later.txt
git -C "$TEST_ROOT/source" -c user.name=Test -c user.email=test@example.invalid commit --quiet -m later
jq -n --arg repository "../source" --arg ref "$fixture_commit" \
  '{version:1,name:"bootstrap-commit-fixture",source:{type:"git-subdirectory",repository:$repository,ref:$ref,path:"skill"}}' \
  >"$TEST_ROOT/consumer/skill-list/fixture.json"
output="$(bash "$TEST_ROOT/consumer/scripts/bootstrap.sh" --dry-run)"
[[ "$output" == *"commit $fixture_commit ->"* ]]
# 当前 HOME 含空格且不同于开发者 HOME，真实本地 Git 工作树仍应可发现。
fixture_home="$TEST_ROOT/isolated home"
mkdir -p "$fixture_home"
cp -R "$TEST_ROOT/source" "$fixture_home/local source"
fixture_branch="$(git -C "$TEST_ROOT/source" symbolic-ref --short HEAD)"
# 保留字面 ~/，验证安装器自行解析；此处故意不让 Shell 展开。
# shellcheck disable=SC2088
jq -n --arg repository '~/local source' --arg ref "$fixture_branch" \
  '{version:1,name:"bootstrap-commit-fixture",source:{type:"git-subdirectory",repository:$repository,ref:$ref,path:"skill"},setup:{useLocalWorkingTree:true}}' \
  >"$TEST_ROOT/consumer/skill-list/fixture.json"
output="$(HOME="$fixture_home" bash "$TEST_ROOT/consumer/scripts/bootstrap.sh" --dry-run)"
[[ "$output" == *"local working tree $fixture_home/local source"* ]]
# 原生安装命令用最小替身保留接收到的真实分发内容；不模拟过滤规则。
mkdir -p "$TEST_ROOT/bin"
cat >"$TEST_ROOT/bin/openclaw" <<'SH'
#!/bin/bash
set -euo pipefail
[[ "$1 $2" == 'skills install' && "$5" == '--as' ]]
target="$OPENCLAW_STATE_DIR/skills/$6"
mkdir -p "$target"
cp -R "$3/." "$target/"
SH
chmod +x "$TEST_ROOT/bin/openclaw"
HOME="$fixture_home" PATH="$TEST_ROOT/bin:$PATH" bash "$TEST_ROOT/consumer/scripts/bootstrap.sh" --yes >/dev/null
installed="$fixture_home/.openclaw/skills/bootstrap-commit-fixture"
[[ -f "$installed/scripts/keep.txt" ]]
for development_dir in maintenance tests evals node_modules nested/maintenance nested/tests nested/evals nested/node_modules; do
  [[ ! -e "$installed/$development_dir" ]]
done
echo "bootstrap 固定 commit、独立 HOME 与递归分发边界回归通过。"
