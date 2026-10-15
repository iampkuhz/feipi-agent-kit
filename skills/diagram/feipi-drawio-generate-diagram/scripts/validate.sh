#!/usr/bin/env bash
set -euo pipefail
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 - "$SKILL_DIR" <<'PY'
import pathlib, sys
root = pathlib.Path(sys.argv[1])
sys.path.insert(0, str(root / 'scripts'))
from core import generate, inspect_source, read_json, validate_brief
for name in ('SKILL.md', 'agents/openai.yaml', 'scripts/run_diagram.py', 'scripts/verify_package.py'):
    if not (root / name).is_file():
        raise SystemExit(f'缺少文件：{name}')
brief = validate_brief(read_json(root / 'assets/brief.example.json'))
inspect_source(brief, generate(brief))
print('draw.io skill 资源与示例校验通过')
PY
