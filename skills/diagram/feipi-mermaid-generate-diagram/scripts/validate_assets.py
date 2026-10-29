#!/usr/bin/env python3
"""独立安装后仍可运行的结构与资源校验。"""
import json
import sys
from pathlib import Path
import jsonschema
import yaml
from model import validate,load,generate,check_source,TYPES
root=Path(sys.argv[1]).resolve()
entry=(root/'SKILL.md').read_text()
assert entry.startswith('---\n')
front=yaml.safe_load(entry.split('---',2)[1])
assert front['name']==root.name=='feipi-mermaid-generate-diagram'
assert front['description'] and not any(x in entry for x in ('待补','TODO'))
ui=yaml.safe_load((root/'agents/openai.yaml').read_text())
assert isinstance(ui['version'],int) and ui['version']>0
assert '$feipi-mermaid-generate-diagram' in ui['interface']['default_prompt']
schema=json.loads((root/'assets/brief.schema.json').read_text());jsonschema.Draft202012Validator.check_schema(schema)
for path in sorted((root/'assets/examples').glob('*.json')):
 b=validate(load(path),path.parent)
 if b['diagram_type'] in TYPES:check_source(b,generate(b))
 else:check_source(b,path.with_suffix('.mmd').read_text())
for name in ('run.py','render.mjs','model.py','package.py','review_package.py','verify_package.py'):
 assert (root/'scripts'/name).is_file(),name
assert (root/'package-lock.json').is_file()
print('结构、schema、全部示例与元数据通过')
