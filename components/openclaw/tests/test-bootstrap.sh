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
git -C "$TEST_ROOT/source" init --quiet
git -C "$TEST_ROOT/source" add skill
git -C "$TEST_ROOT/source" -c user.name=Test -c user.email=test@example.invalid commit --quiet -m fixture
fixture_commit="$(git -C "$TEST_ROOT/source" rev-parse HEAD)"
# A later HEAD proves that the requested object, not the current branch, is used.
echo later >"$TEST_ROOT/source/later.txt"
git -C "$TEST_ROOT/source" add later.txt
git -C "$TEST_ROOT/source" -c user.name=Test -c user.email=test@example.invalid commit --quiet -m later
jq -n --arg repository "$TEST_ROOT/source" --arg ref "$fixture_commit" \
  '{version:1,name:"bootstrap-commit-fixture",source:{type:"git-subdirectory",repository:$repository,ref:$ref,path:"skill"}}' \
  >"$TEST_ROOT/consumer/skill-list/fixture.json"
output="$(bash "$TEST_ROOT/consumer/scripts/bootstrap.sh" --dry-run)"
[[ "$output" == *"commit $fixture_commit ->"* ]]
echo "bootstrap 固定 commit 回归通过。"
