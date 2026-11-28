#!/usr/bin/env bash
set -euo pipefail
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 - "$SKILL_DIR" <<'PY'
import ast
from pathlib import Path
import sys
skill = Path(sys.argv[1])
for path in skill.glob('scripts/*.py'):
    ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
assert (skill / 'SKILL.md').is_file()
assert (skill / 'agents/openai.yaml').is_file()
print('runtime_structure_valid=1')
PY
