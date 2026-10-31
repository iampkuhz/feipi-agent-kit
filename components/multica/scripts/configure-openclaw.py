#!/usr/bin/env python3
"""Generate an isolated task runtime from declared provider configuration."""
import json
import datetime
from pathlib import Path
import re
import runpy
import shlex
import os
import subprocess
import tempfile
from adaptation import machine, expand

home = Path.home()
root = Path(__file__).resolve().parent.parent
helper = runpy.run_path(str(root / 'scripts/configure.py'))
m = machine()
source = Path(expand(m['openclaw_source']))
declared = json.loads(source.read_text())
state = Path(expand(m['openclaw_state']))
state.mkdir(mode=0o700, parents=True, exist_ok=True)
state.chmod(0o700)
(state / 'workspace').mkdir(mode=0o700, exist_ok=True)
config = {
    'models': declared['models'],
    'agents': {'defaults': {
        'model': declared['agents']['defaults']['model'],
        'workspace': str(state / 'workspace'),
    }},
    'tools': {'profile': 'coding'},
    'plugins': {'slots': {'memory': 'none'}},
}
catalog = json.loads((root / 'config/litellm-agents.json').read_text())
provider = catalog['provider']
config['models']['providers'][provider] = {
    'baseUrl': '${LITELLM_BASE_URL}',
    'apiKey': {'source': 'env', 'provider': 'default', 'id': 'LITELLM_API_KEY_OPENAI'},
    'api': 'openai-completions',
    'authHeader': True,
    'models': [{
        'id': item['model'], 'name': item['name'], 'reasoning': True,
        'input': item['input'], 'contextWindow': item['contextWindow'],
        'maxTokens': item['maxTokens'],
        'compat': {'maxTokensField': 'max_tokens', 'thinkingFormat': 'openai'},
    } for item in catalog['agents']],
}
config['agents']['ownership'] = 'explicit'
config['agents']['entries'] = {'main': {'workspace': str(state / 'workspace')}}
for item in catalog['agents']:
    workspace = state / 'workspaces' / item['id']
    workspace.mkdir(mode=0o700, parents=True, exist_ok=True)
    config['agents']['entries'][item['id']] = {
        'name': item['name'], 'workspace': str(workspace),
        'model': {'primary': provider + '/' + item['model'], 'fallbacks': []},
    }
config['agents']['defaults']['maxConcurrent'] = 1
names = set(re.findall(r'\$\{([A-Za-z_][A-Za-z0-9_]*)\}', json.dumps(config)))
def discover(value):
    if isinstance(value, dict):
        if value.get('source') == 'env' and isinstance(value.get('id'), str):
            names.add(value['id'])
        for child in value.values():
            discover(child)
    elif isinstance(value, list):
        for child in value:
            discover(child)
discover(config)
values = helper['read_values'](home / '.env', names)
if set(values) != names or any('${' in value for value in values.values()):
    raise SystemExit('Required provider values missing or unresolved in the canonical env vault.')
generated = {
    'openclaw.json': json.dumps(config, ensure_ascii=False, indent=2) + '\n',
    '.env': ''.join(name + '=' + shlex.quote(values[name]) + '\n' for name in sorted(names)),
}
changed = [name for name, content in generated.items()
           if (state / name).exists() and (state / name).read_text() != content]
# 先以候选文件和最小环境校验，成功后再发布。校验输出可能含秘密，不转抄。
with tempfile.TemporaryDirectory(prefix='validate-', dir=state) as candidate:
    candidate_path = Path(candidate) / 'openclaw.json'
    helper['atomic_private_write'](candidate_path, generated['openclaw.json'])
    env = dict(os.environ, **values)
    env.update(OPENCLAW_STATE_DIR=str(state), OPENCLAW_CONFIG_PATH=str(candidate_path))
    checked = subprocess.run([expand(m['commands']['openclaw']), 'config', 'validate'], env=env, capture_output=True, timeout=30)
    if checked.returncode:
        raise SystemExit('候选 OpenClaw 配置未通过 schema 校验；未发布。')
if changed:
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup = home / '.local/state/multica/config-backups' / ('openclaw-' + timestamp)
    backup.mkdir(mode=0o700, parents=True)
    for name in changed:
        helper['atomic_private_write'](backup / name, (state / name).read_text())
    print('Saved private rollback copy:', backup)
for name, content in generated.items():
    helper['atomic_private_write'](state / name, content)
print('Generated isolated OpenClaw config and minimal provider projection; no personal channels/plugins/memory copied.')
