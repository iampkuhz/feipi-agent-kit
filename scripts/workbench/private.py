#!/usr/bin/env python3
"""固定私有目录清单与现有备份入口；不复制数据库热文件冒充一致性备份。"""
import argparse
import json
import re
from pathlib import Path
import subprocess
import sys

HOME = Path.home()
ROOT = Path(__file__).resolve().parents[2]


def check():
    # 必需项针对当前配置：不把可重建缓存或可选浏览器状态作为新机硬阻塞。
    required = [('.env', '全局 env vault；从原机/加密备份恢复，不生成替代密钥'),
                ('.openclaw/openclaw.json', 'OpenClaw 受管声明；workbench apply openclaw'),
                ('.openclaw/agents', '原有会话；从 OpenClaw 同批备份恢复'),
                ('.openclaw/workspace', '原有记忆、人格和用户产物；从 OpenClaw 备份恢复'),
                ('.openclaw/state', 'OpenClaw SQLite 状态；从停写备份恢复'),
                ('.config/multica-selfhost/machine.json', '本机绑定；同机恢复原文件，新机重新注册 runtime'),
                ('.config/multica-selfhost/server.env', 'Multica 数据库/服务加密密钥，须与数据库同批恢复'),
                ('.multica/profiles/personal/config.json', 'Multica 登录；迁新机重新认证'),
                ('.config/feipi-workbench/private/openclash/oixCloud.yaml', 'OpenClash 私有订阅；从路由器备份恢复')]
    optional = [('.openclaw/browser', '浏览器状态；缺失需重新登录'),
                ('.qwen/settings.json', '含本机 env/登录配置，保留私有；公开 qwen/settings 仅作模板，不整份覆盖'),
                ('.config/feipi-workbench/private/services/crawl4ai.env', 'Crawl4AI 私有覆盖；启用相关上游时需要，不随源码发布删除'),
                ('.openclaw/openclaw-weixin', '微信登录态；启用微信时必需，否则可选'),
                ('.openclaw/credentials', '渠道配对与授权；启用相关渠道时必需'),
                ('.local/share/multica/openclaw-state', '隔离执行配置可由 Multica 生成；不替代个人记忆'),
                ('Documents/service-data/litellm/chatgpt-tokens', '仅 ChatGPT OAuth 上游需要'),
                ('.local/state/multica/adaptation', '请求回执/验收/机器适配历史；恢复原机时应保留')]
    missing = False
    for label, entries in [('必需', required), ('按功能可选', optional)]:
        for relative, recovery in entries:
            path = HOME/relative
            exists = path.exists()
            count = sum(1 for p in path.rglob('*') if p.is_file()) if path.is_dir() else int(path.is_file())
            if label == '必需' and (not exists or not count):
                missing = True
            print(f'[{label}] {relative}: '+(f'已发现 {count} 个文件' if exists else '缺失')+'；'+recovery)
    # 只检查当前声明引用的 env 键是否有定义，不求值或打印秘密，也不推断凭据有效。
    env = HOME/'.env'
    declared = {'HOME'}  # 由运行时提供，不是需要从 env vault 恢复的凭据。
    if env.is_file():
        for line in env.read_text().splitlines():
            match = re.match(r'^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+)', line)
            if match and match[2].strip() not in ('""', "''"):
                declared.add(match[1])
    references = set()
    def visit(value):
        if isinstance(value, dict):
            if value.get('enabled') is False:
                return
            if value.get('source') == 'env' and isinstance(value.get('id'), str):
                references.add(value['id'])
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
        elif isinstance(value, str):
            references.update(re.findall(r'\$\{([A-Za-z_][A-Za-z0-9_]*)\}', value))
    visit(json.loads((ROOT/'components/openclaw/openclaw.json').read_text()))
    absent = sorted(references-declared)
    print('OpenClaw 当前声明引用 env：'+str(len(references))+' 项；缺少定义：'+(', '.join(absent) or '无')+'。定义存在不证明值有效。')
    missing |= bool(absent)
    print('以上只证明目录/文件存在。完整性需备份校验/隔离恢复；功能需真实交互。')
    print('Multica 数据库和附件位于容器数据卷：workbench private backup multica；不按目录存在判断完整。')
    return int(missing)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='action', required=True)
    sub.add_parser('check')
    backup = sub.add_parser('backup')
    backup.add_argument('component', choices=['openclaw', 'multica', 'openclash'])
    verify = sub.add_parser('verify')
    verify.add_argument('component', choices=['openclaw', 'multica', 'openclash'])
    verify.add_argument('batch')
    a = p.parse_args()
    if a.action == 'check':
        return check()
    if a.component == 'openclash':
        args = ['backup'] if a.action == 'backup' else ['verify-backup', a.batch]
        return subprocess.run(['python3', str(ROOT/'components/openclash/router.py'), *args]).returncode
    if a.component == 'multica':
        script = ROOT/'components/multica/scripts'/('backup.py' if a.action == 'backup' else 'restore-check.py')
        args = ['--apply'] if a.action == 'backup' else [a.batch]
        return subprocess.run(['python3', str(script), *args]).returncode
    if a.action == 'backup':
        return subprocess.run(['bash', str(ROOT/'components/openclaw/scripts/backup-state.sh')]).returncode
    batch = Path(a.batch).expanduser()
    if batch.is_dir():
        # 标准离线归档的字节校验；数据库恢复验证按手册在新目录执行。
        return subprocess.run(['shasum', '-a', '256', '-c', str(batch.resolve()/'SHA256SUMS')], cwd=batch).returncode
    return subprocess.run(['openclaw', 'backup', 'verify', str(batch), '--json']).returncode


if __name__ == '__main__':
    sys.exit(main())
