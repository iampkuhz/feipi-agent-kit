#!/usr/bin/env bash
set -euo pipefail

command -v python3 >/dev/null 2>&1 || { echo "需要 Python 3；请先安装后重试。" >&2; exit 1; }
python3 -c 'import yaml' 2>/dev/null || { echo "需要 PyYAML；请为当前 Python 安装 PyYAML。" >&2; exit 1; }
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$SKILL_DIR/../../.." && pwd)"
test_root="$(mktemp -d "${TMPDIR:-/tmp}/interaction-review-test.XXXXXX")"
trap 'rm -rf "$test_root"' EXIT
mkdir -p "$test_root/.agents/skills/unrelated-entry"
printf '%s\n' 'preserve-existing-entry' > "$test_root/.agents/skills/unrelated-entry/marker"
bash "$REPO_ROOT/scripts/install_skills.sh" --dir "$test_root" --skill feipi-interaction-review-output > "$test_root/install.log" 2>&1 || { tail -n 20 "$test_root/install.log"; exit 1; }
python3 - "$SKILL_DIR" "$test_root" <<'PY'
from pathlib import Path
import sys

source, target = map(Path, sys.argv[1:])
installed = target / '.agents/skills/feipi-interaction-review-output'
runtime = ['SKILL.md', 'agents/openai.yaml', 'references/delivery-review.md', 'references/channels.md']
for relative in runtime:
    candidate = installed / relative
    assert candidate.is_file() and not candidate.is_symlink(), relative
    assert candidate.read_bytes() == (source / relative).read_bytes(), relative
for path in installed.rglob('*'):
    assert not {'maintenance', 'tests', 'evals', 'node_modules'} & set(path.relative_to(installed).parts), path
assert (installed / '.feipi-agent-kit-source').is_file()
assert (target / '.agents/skills/unrelated-entry/marker').read_text() == 'preserve-existing-entry\n'
assert {p.name for p in installed.parent.iterdir()} == {'unrelated-entry', installed.name}
print('PASS: 定向安装资源一致、开发目录隔离、其他入口保留；不代表语义或手机实显通过。')
PY
