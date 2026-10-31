#!/usr/bin/env python3
"""仅管理现有 OpenClash 地区模块；凭据/订阅留在本机与路由器。"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tarfile
import time
import urllib.request
import urllib.parse

ROOT = Path(__file__).resolve().parent
HOME = Path.home()
CONFIG = HOME/'.config/feipi-workbench/router.json'
PRIVATE = HOME/'.config/feipi-workbench/private/openclash'
MODULE = 'OIX-Region-Priority.conf'
REMOTE = '/etc/openclash/overwrite/'+MODULE


def config():
    if not CONFIG.exists():
        raise ValueError('缺少私有 router.json，见 components/openclash/README.md；不猜测账号或密码。')
    return json.loads(CONFIG.read_text())


def api(path, data=None, method=None):
    c = config()
    request = urllib.request.Request(c['controller']+path, data=json.dumps(data).encode() if data is not None else None,
                                     method=method, headers={'Authorization': 'Bearer '+c['secret'], 'Content-Type':'application/json'})
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request, timeout=10) as response:
        return json.load(response) if response.status != 204 else None


def ssh(command, *, capture=True):
    c = config()
    # 仅用现有 SSH 配置/密钥；不在命令行传密码，也不绕过主机密钥检查。
    result = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=5', c['ssh'], command],
                            capture_output=capture)
    if result.returncode:
        raise ValueError('路由器 SSH 未完成；检查私有 router.json 的 ssh 别名及现有认证。')
    return result.stdout


def fetch():
    data = ssh('cat '+shlex.quote(REMOTE))
    if not data.startswith(b'#!NAME') or b'[YAML]' not in data:
        raise ValueError('路由器返回的不是预期覆写模块。')
    PRIVATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    (PRIVATE/MODULE).write_bytes(data)
    (PRIVATE/MODULE).chmod(0o600)
    print('已读取路由器模块到私有目录；尚未回收源码。')


def export_private():
    destination = HOME/'.local/state/feipi-workbench/openclash-backups'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    destination.mkdir(parents=True, mode=0o700)
    c = config()
    archive = destination/'config.tar.gz'
    with archive.open('wb') as stream:
        result = subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=5',c['ssh'],'sh -s'],
                                input=(ROOT/'export-private.sh').read_bytes(), stdout=stream, stderr=subprocess.PIPE)
    if result.returncode:
        raise ValueError('最小备份导出失败；私有临时文件保留，未标记成功。')
    with tarfile.open(archive) as tar:
        names = tar.getnames()
        assert 'etc/config/openclash' in names and 'etc/openclash/overwrite/'+MODULE in names
        assert not any('/core/' in n or '/rule_provider/' in n or '/proxy_provider/' in n for n in names)
    selected = {name: value['now'] for name, value in api('/proxies')['proxies'].items()
                if value.get('type') == 'Selector' and value.get('now')}
    (destination/'selections.json').write_text(json.dumps(selected, ensure_ascii=False, indent=2)+'\n')
    (destination/'versions.json').write_bytes((ROOT/'versions.json').read_bytes())
    manifest = {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in destination.iterdir() if p.is_file()}
    (destination/'SHA256SUMS.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print('私有最小备份：'+str(destination)+'；压缩配置 '+str(archive.stat().st_size)+' bytes；不含内核、GeoIP 或缓存。')
    return destination


def upload(local, remote):
    c = config()
    result = subprocess.run(['ssh','-o','BatchMode=yes',c['ssh'],'umask 077; cat > '+shlex.quote(remote)],
                            input=Path(local).read_bytes(), capture_output=True)
    if result.returncode:
        raise ValueError('暂存文件传输失败；尚未应用。')


def wait_core():
    for _ in range(60):
        try:
            api('/version')
            return
        except (OSError, ValueError):
            time.sleep(2)
    raise ValueError('核心未在两分钟内恢复。')


def doctor():
    version = api('/version')
    proxies = api('/proxies')['proxies']
    expected = ['香港自动', '日本自动', '新加坡自动', '美国自动', '全球自动']
    group = proxies.get('地区优先', {})
    checks = {
        '地区顺序': group.get('all') == expected,
        '地区类型': group.get('type', '').lower() == 'fallback',
        '主代理选择': proxies.get('Proxy', {}).get('now') == '地区优先',
        '国内直连': proxies.get('Domestic', {}).get('now') == 'DIRECT',
        '国内媒体直连': proxies.get('CN Mainland TV', {}).get('now') == 'DIRECT',
        '测速直连': proxies.get('Speedtest', {}).get('now') == 'DIRECT',
        '地区非手动固定': all(not proxies.get(n, {}).get('fixed') for n in expected[:4]),
    }
    print(json.dumps({'kernel': version.get('version'), 'checks': checks,
                      'selected_region': group.get('now'),
                      'note': 'API 运行状态；联网与真实连接规则须另验。'}, ensure_ascii=False, indent=2))
    return int(not all(checks.values()))


def verify():
    """通过路由器代理真实请求，并从核心连接表核对路径；不记录节点名或凭据。"""
    import base64
    import http.client
    c = config()
    proxy = urllib.parse.urlparse(c['proxy'])
    evidence = {}
    allowed = {'DIRECT', 'Proxy', 'Domestic', '地区优先', '香港自动', '日本自动', '新加坡自动', '美国自动', '全球自动'}
    for name, host in [('domestic', 'www.baidu.com'), ('foreign', 'www.google.com')]:
        connection = http.client.HTTPSConnection(proxy.hostname, proxy.port, timeout=20)
        headers = {}
        if c.get('proxy_auth'):
            headers['Proxy-Authorization'] = 'Basic '+base64.b64encode(c['proxy_auth'].encode()).decode()
        try:
            connection.set_tunnel(host, 443, headers=headers)
            connection.request('GET', '/', headers={'Host': host, 'User-Agent': 'feipi-workbench-check', 'Connection': 'keep-alive'})
            response = connection.getresponse()
            response.read(64)
            evidence[name] = {'host': host, 'http_status': response.status}
            # 在关闭 HTTP keep-alive 连接前观察，避免小响应瞬间结束造成漏采样。
            for _ in range(10):
                found = next((x for x in api('/connections').get('connections', [])
                              if x.get('metadata', {}).get('host') == host), None)
                if found:
                    evidence[name].update(rule=found.get('rule'), payload=found.get('rulePayload'),
                        groups=[g for g in found.get('chains', []) if g in allowed])
                    break
                time.sleep(.1)
            response.read()
        except (OSError, http.client.HTTPException):
            evidence.setdefault(name, {'host': host})['error'] = '请求未完整完成；核对私有代理认证、DNS 和上游连接'
        finally:
            connection.close()
    passed = all(v.get('http_status') == 200 and 'error' not in v for v in evidence.values())
    passed &= 'DIRECT' in evidence.get('domestic', {}).get('groups', [])
    passed &= '地区优先' in evidence.get('foreign', {}).get('groups', [])
    evidence.update(passed=passed, checked_at=datetime.datetime.now().astimezone().isoformat())
    target = HOME/'.local/state/feipi-workbench/openclash-connectivity.json'
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    target.write_text(json.dumps(evidence, ensure_ascii=False, indent=2)+'\n')
    target.chmod(0o600)
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return int(not passed)


def verify_backup(batch):
    batch = Path(batch).expanduser()
    manifest = json.loads((batch/'SHA256SUMS.json').read_text())
    for name, expected in manifest.items():
        if Path(name).name != name or hashlib.sha256((batch/name).read_bytes()).hexdigest() != expected:
            raise ValueError('备份摘要不匹配。')
    with tarfile.open(batch/'config.tar.gz') as archive:
        names = archive.getnames()
        if not {'etc/config/openclash', 'etc/openclash/overwrite/'+MODULE}.issubset(names):
            raise ValueError('备份缺少 UCI 或受管模块。')
        if any(n.startswith('/') or '..' in Path(n).parts or '/core/' in n for n in names):
            raise ValueError('备份范围异常。')
        for member in archive:
            if member.isfile():
                archive.extractfile(member).read()
    print('备份摘要和完整压缩流通过；只含配置，恢复时仍须安装匹配内核/数据文件并验证网络。')


def apply():
    # 先通过 SSH 读回，阻止用过期下载快照覆盖路由器刚调好的模块。
    fetch()
    source = ROOT/MODULE
    local_backup = export_private()
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    backup = '/root/feipi-workbench-backup-'+stamp
    command = ('set -eu; test -z "$(uci changes openclash)"; test "$(uci -q get openclash.region_priority_oix.enable)" = 1; '
               'mkdir -m 700 '+shlex.quote(backup)+'; cp '+shlex.quote(REMOTE)+' '+shlex.quote(backup+'/module.conf')+
               '; uci export openclash > '+shlex.quote(backup+'/openclash.uci')+
               '; sha256sum '+shlex.quote(REMOTE))
    result = ssh(command).decode().split()[0]
    expected = hashlib.sha256(source.read_bytes()).hexdigest()
    upload(source, backup+'/new-module.conf')
    upload(ROOT/'validate-module.rb', backup+'/validate-module.rb')
    # 用原订阅生成候选，再让当前核心只做 -t；日志留在路由器私有回退目录。
    ssh('set -eu; ruby '+shlex.quote(backup+'/validate-module.rb')+' '+shlex.quote(backup+'/new-module.conf')+
        ' '+shlex.quote(config()['config'])+' '+shlex.quote(backup)+' > '+shlex.quote(backup+'/validate.log')+
        ' 2>&1; /etc/openclash/core/clash_meta -t -d /etc/openclash -f '+shlex.quote(backup+'/candidate.yaml')+
        ' >> '+shlex.quote(backup+'/validate.log')+' 2>&1')
    changed = result != expected
    if changed:
        selected = json.loads((local_backup/'selections.json').read_text())
        try:
            ssh('set -eu; cp '+shlex.quote(backup+'/new-module.conf')+' '+shlex.quote(REMOTE+'.new')+
                '; mv '+shlex.quote(REMOTE+'.new')+' '+shlex.quote(REMOTE)+
                '; /etc/init.d/openclash restart > '+shlex.quote(backup+'/restart.log')+' 2>&1')
            wait_core()
            current = api('/proxies')['proxies']
            for name, choice in selected.items():
                if choice in current.get(name, {}).get('all', []):
                    api('/proxies/'+urllib.parse.quote(name, safe=''), {'name':choice}, 'PUT')
            if doctor():
                raise ValueError('更新后的策略未通过运行验收。')
        except Exception:
            ssh('cp '+shlex.quote(backup+'/module.conf')+' '+shlex.quote(REMOTE)+
                '; /etc/init.d/openclash restart > '+shlex.quote(backup+'/rollback.log')+' 2>&1')
            wait_core()
            current = api('/proxies')['proxies']
            for name, choice in selected.items():
                if choice in current.get(name, {}).get('all', []):
                    api('/proxies/'+urllib.parse.quote(name, safe=''), {'name':choice}, 'PUT')
            print('应用失败，已恢复原模块、核心与选择状态；回退日志：'+backup+'/rollback.log', file=sys.stderr)
            raise
    # 内容相同时不重启家庭网络；实际合并/核心校验及当前策略共同构成接管证据。
    if doctor():
        raise ValueError('路由器当前运行策略未满足声明，不能登记成功。')
    state = HOME/'.local/state/feipi-workbench/openclash.json'
    state.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    state.write_text(json.dumps({'source':str(ROOT), 'module_sha256':expected, 'router_backup':backup,
                                'applied_at':stamp, 'private_backup':str(local_backup),
                                'method':'validated native merge and core; '+('installed' if changed else 'adopted identical active module')}, indent=2)+'\n')
    state.chmod(0o600)
    print('已接管一致的活动模块；路由器回退目录：'+backup)


def main():
    os.umask(0o077)
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['test', 'fetch', 'doctor', 'apply', 'backup', 'verify', 'verify-backup'])
    p.add_argument('batch', nargs='?')
    a = p.parse_args()
    if a.action == 'test':
        text = (ROOT/MODULE).read_text()
        assert '#!CONFIG = oixCloud.yaml' in text and '[YAML]' in text and '[Overwrite]' in text
        assert all(name in text for name in ['香港自动','日本自动','新加坡自动','美国自动','全球自动','empty-fallback: REJECT'])
        print('模块静态契约通过；真实合并和核心校验必须在路由器执行。')
    elif a.action == 'fetch':
        fetch()
    elif a.action == 'apply':
        apply()
    elif a.action == 'backup':
        export_private()
    elif a.action == 'verify':
        return verify()
    elif a.action == 'verify-backup':
        if not a.batch:
            p.error('verify-backup 需要本机私有备份目录')
        verify_backup(a.batch)
    else:
        return doctor()
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError) as exc:
        print('未完成：'+str(exc), file=sys.stderr)
        sys.exit(1)
