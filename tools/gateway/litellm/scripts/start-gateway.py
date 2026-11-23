#!/usr/bin/env python3
"""Start the proxy without blocking unrelated routes on first-time ChatGPT login."""
import json
import os
from pathlib import Path
import sys
import tempfile


def authorized_models(models, auth_file):
    try:
        auth = json.loads(auth_file.read_text())
    except (FileNotFoundError, ValueError):
        auth = None
    if isinstance(auth, dict) and any(
        isinstance(auth.get(key), str) and auth[key]
        for key in ('access_token', 'refresh_token')
    ):
        return models
    return [model for model in models if not model['litellm_params']['model'].startswith('chatgpt/')]


def main():
    import yaml

    source = Path('/app/config.yaml')
    settings = yaml.safe_load(source.read_text())
    auth_file = Path(os.environ['CHATGPT_TOKEN_DIR']) / os.environ.get('CHATGPT_AUTH_FILE', 'auth.json')
    models = authorized_models(settings['model_list'], auth_file)
    active = source
    if len(models) != len(settings['model_list']):
        settings['model_list'] = models
        with tempfile.NamedTemporaryFile(mode='w', prefix='litellm-', suffix='.yaml', delete=False) as config:
            yaml.safe_dump(settings, config)
            active = Path(config.name)
        print('ChatGPT 订阅尚未授权，已暂缓加载订阅模型。', flush=True)
    entrypoint = '/app/docker/prod_entrypoint.sh'
    os.execv(entrypoint, [entrypoint, '--config', str(active), *sys.argv[1:]])


if __name__ == '__main__':
    main()
