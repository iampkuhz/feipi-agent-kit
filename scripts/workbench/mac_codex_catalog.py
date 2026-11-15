"""只传模型选择，从固定版 Codex 原生目录重建可派生元数据。"""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
CATALOGS = {'.codex/model-catalog.selected.json', '.codex/model-catalogs/litellm-local.json'}


def fingerprint(value):
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
    return hashlib.sha256(data).hexdigest()


def bundled_models():
    expected = json.loads((ROOT/'components/multica/config/agents.json').read_text())['compatibility']['codex']
    command = shutil.which('codex')
    if not command:
        raise ValueError('重建模型目录前先安装锁定版 Codex：workbench install mac --agents。')
    try:
        actual = subprocess.check_output([command, '--version'], text=True, stderr=subprocess.PIPE, timeout=30)
        if not re.fullmatch(r'codex-cli\s+'+re.escape(expected), actual.strip()):
            raise ValueError('Codex 与锁定版本不一致，未重建模型目录。')
        raw = subprocess.check_output([command, 'debug', 'models', '--bundled'], text=True,
                                      stderr=subprocess.PIPE, timeout=30)
        catalog = json.loads(raw)
        models = catalog.get('models') if isinstance(catalog, dict) else None
    except (subprocess.SubprocessError, json.JSONDecodeError) as error:
        raise ValueError('无法读取 Codex 原生模型目录，未恢复配置。') from error
    if not isinstance(models, list) or any(not isinstance(m, dict) or not isinstance(m.get('slug'), str) for m in models):
        raise ValueError('Codex 原生模型目录结构无效。')
    if len({model['slug'] for model in models}) != len(models):
        raise ValueError('Codex 原生模型目录含重复名称。')
    return expected, {model['slug']: model for model in models}


def validate_recipes(recipes):
    if not isinstance(recipes, list):
        raise ValueError('模型重建清单格式无效。')
    seen = set()
    for item in recipes:
        if (not isinstance(item, dict) or not isinstance(item.get('path'), str)
                or item['path'] not in CATALOGS or item['path'] in seen):
            raise ValueError('模型重建路径不在白名单内或重复。')
        slugs = item.get('slugs')
        if (not isinstance(slugs, list) or not slugs or any(not isinstance(s, str) for s in slugs)
                or len(set(slugs)) != len(slugs) or not isinstance(item.get('codex_version'), str)
                or not isinstance(item.get('sha256'), str) or not re.fullmatch('[0-9a-f]{64}', item['sha256'])):
            raise ValueError('模型选择或校验信息无效。')
        seen.add(item['path'])


def export_recipes(home):
    config = home/'.codex/config.toml'
    if not config.is_file():
        return []
    try:
        import tomllib
    except ImportError as error:
        raise ValueError('读取 Codex TOML 配置需要 Python 3.11+；先激活 Homebrew Python。') from error
    paths = set()

    def visit(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key == 'model_catalog_json':
                    if not isinstance(child, str) or not Path(child).is_absolute():
                        raise ValueError('Codex 模型目录必须使用原生支持的绝对路径。')
                    path = Path(child)
                    if not path.is_relative_to(home) or str(path.relative_to(home)) not in CATALOGS:
                        raise ValueError('自定义模型目录需作为本地文件单独复制；未打包其他目录。')
                    paths.add(str(path.relative_to(home)))
                visit(child)
    visit(tomllib.loads(config.read_text()))
    if not paths:
        return []
    version, bundled = bundled_models()
    recipes = []
    for name in sorted(paths):
        original = json.loads((home/name).read_text())
        models = original.get('models') if isinstance(original, dict) else None
        if (not isinstance(original, dict) or set(original) != {'models'} or not isinstance(models, list) or not models or
                any(not isinstance(m, dict) or not isinstance(m.get('slug'), str) for m in models)):
            raise ValueError('自定义模型元数据需单独复制，不能当作原生派生数据省略。')
        slugs = [model['slug'] for model in models]
        if len(set(slugs)) != len(slugs) or any(model != bundled.get(model['slug']) for model in models):
            raise ValueError('模型元数据与锁定程序不同，需单独复制；未用近似目录替代。')
        recipes.append({'path': name, 'slugs': slugs, 'codex_version': version,
                        'sha256': fingerprint(original)})
    return recipes


def rebuild(recipes):
    validate_recipes(recipes)
    if not recipes:
        return []
    version, bundled = bundled_models()
    pending = []
    for item in recipes:
        if item['codex_version'] != version or any(slug not in bundled for slug in item['slugs']):
            raise ValueError('固定版 Codex 不包含待恢复模型；未替换配置。')
        value = {'models': [bundled[slug] for slug in item['slugs']]}
        if fingerprint(value) != item['sha256']:
            raise ValueError('原生模型元数据与导出记录不同；未替换配置。')
        pending.append((Path(item['path']), (json.dumps(value, ensure_ascii=False, indent=2)+'\n').encode()))
    return pending
