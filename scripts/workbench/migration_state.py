#!/usr/bin/env python3
"""从独立停写备份或旧迁移包恢复状态，不启动服务、不覆盖已有目录。"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import tempfile

from mac_bundle import relocate
from migration import MODELS, verify
from migration_projects import extract_archive, relative

ROOT = Path(__file__).resolve().parents[2]


def target_directory(home, name):
    home = home.resolve()
    target = home/name
    if os.path.lexists(target):
        raise ValueError('状态目标已存在，未覆盖：'+str(target))
    for parent in target.parents:
        if parent == home:
            break
        if parent.is_symlink() or (parent.exists() and not parent.is_dir()):
            raise ValueError('状态目标父目录冲突，未写入：'+str(parent))
    return target


def installed_openclaw():
    command = shutil.which('openclaw')
    if not command:
        raise ValueError('先安装锁定的 OpenClaw 程序，再恢复状态。')
    package = Path(command).resolve().parent
    baseline = json.loads((ROOT/'components/openclaw/versions.json').read_text())['openclaw']
    metadata = package/'package.json'
    if not metadata.is_file():
        raise ValueError('无法从 OpenClaw 原生入口确定程序目录；先激活安装时的 Node 环境。')
    value = json.loads(metadata.read_text())
    if value.get('name') != 'openclaw' or value.get('version') != baseline:
        raise ValueError('已安装 OpenClaw 与恢复基线不一致，未写入。')
    return package


def verify_openclaw_backup(directory):
    """固定四个原生输出，不依赖全量资料/模型清单。"""
    expected = {'state.tar.gz', 'env-vault.tar.gz', 'env-location.json', 'sqlite-integrity.json'}
    checks = {}
    for line in (directory/'SHA256SUMS').read_text().splitlines():
        fields = line.split()
        if len(fields) != 2:
            raise ValueError('OpenClaw 独立备份摘要格式无效。')
        digest, name = fields
        if (name not in expected or name in checks or len(digest) != 64
                or any(char not in '0123456789abcdef' for char in digest)):
            raise ValueError('OpenClaw 独立备份含非白名单或重复条目。')
        checks[name] = digest
    if set(checks) != expected:
        raise ValueError('OpenClaw 独立备份缺少必要文件。')
    for name, recorded in checks.items():
        path = directory/name
        if path.is_symlink() or not path.is_file():
            raise ValueError('OpenClaw 备份文件缺失或不是普通文件：'+name)
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            for block in iter(lambda: stream.read(1024*1024), b''):
                digest.update(block)
        if digest.hexdigest() != recorded:
            raise ValueError('OpenClaw 备份摘要不符：'+name)
    metadata = json.loads((directory/'env-location.json').read_text())
    value = metadata.get('source_home') if isinstance(metadata, dict) else None
    if not isinstance(value, str) or not Path(value).is_absolute() or '..' in Path(value).parts or value == '/':
        raise ValueError('独立备份缺少有效的 source_home；用当前 backup openclaw 重新导出。')
    return Path(value)


def restore_openclaw(directory, home, source_home, package):
    home = home.resolve()
    target = target_directory(home, '.openclaw')
    source = directory/'state.tar.gz'
    # plugin-skills 是程序生成的链接；只重建已识别且新程序确实提供的 skill。
    replacements = {}
    with tarfile.open(source) as archive:
        for member in archive:
            # 旧版 BSD tar 自动添加的根目录 AppleDouble 不是业务文件。
            if member.name == '._.openclaw' and member.isfile():
                with archive.extractfile(member) as stream:
                    if stream.read(4) != b'\x00\x05\x16\x07':
                        raise ValueError('OpenClaw 归档的根元数据格式无效。')
                replacements[member.name] = None
                continue
            name = relative(member.name.rstrip('/'))
            if name.parts[0] != '.openclaw':
                raise ValueError('OpenClaw 归档包含状态目录外的内容。')
            if member.issym() and member.linkname.startswith('/'):
                link = Path(member.linkname)
                if link.is_relative_to(source_home):
                    continue
                prefix = '/node_modules/openclaw/'
                if len(name.parts) != 3 or name.parts[1] != 'plugin-skills' or prefix not in member.linkname:
                    raise ValueError('OpenClaw 归档含无法重建的外部链接。')
                suffix = relative(member.linkname.split(prefix, 1)[1])
                # 同版本 npm 包可能把内置技能放在 skills/ 或 dist/extensions/*/skills/。
                if (suffix.parts[-2:] != ('skills', name.name) or not
                        (suffix.parts[0] == 'skills' or suffix.parts[:2] == ('dist', 'extensions'))):
                    raise ValueError('无法识别旧程序的原生技能布局。')
                skill = package/suffix
                if not (skill/'SKILL.md').is_file() or not skill.resolve().is_relative_to(package.resolve()):
                    raise ValueError('当前 OpenClaw 缺少需重建的内置 skill：'+name.name)
                replacements[member.name] = skill
    checks = json.loads((directory/'sqlite-integrity.json').read_text())
    if not checks or any(value != 'ok' for value in checks.values()):
        raise ValueError('缺少有效的原数据库完整性记录。')
    stage = Path(tempfile.mkdtemp(prefix='.openclaw-restore-', dir=home))
    try:
        extract_archive(source, stage, home, home, source_home, replacements)
        state = stage/'.openclaw'
        for name, skill in replacements.items():
            if skill is None:
                continue
            destination = stage/name
            if not destination.parent.resolve().is_relative_to(state.resolve()):
                raise ValueError('程序链接父目录越界。')
            destination.symlink_to(skill)
        for name in checks:
            path = stage/relative(name)
            if (not str(name).startswith('.openclaw/') or not path.is_file() or path.is_symlink()
                    or not path.resolve().is_relative_to(state.resolve())):
                raise ValueError('恢复数据库缺失或路径越界。')
            connection = sqlite3.connect(path.as_uri()+'?mode=rw', uri=True)
            try:
                if connection.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
                    raise ValueError('恢复后的 SQLite 完整性不通过。')
            finally:
                connection.close()
        config = state/'openclaw.json'
        if config.is_symlink() or not config.is_file() or not config.resolve().is_relative_to(state.resolve()):
            raise ValueError('恢复的运行声明不是状态目录内的普通文件。')
        config.write_bytes(relocate(config.read_bytes(), str(source_home), home, Path('openclaw.json')))
        config.chmod(0o600)
        link = state/'.env'
        if os.path.lexists(link):
            link.unlink()
        link.symlink_to(home/'.env')
        state.rename(target)
    finally:
        shutil.rmtree(stage)
    print('OpenClaw 原状态已恢复；SQLite '+str(len(checks))+' 项通过，程序链接已重建。')
    print('Gateway 保持未启动；继续安装匹配依赖、发布当前声明，切换旧机后再启动渠道。')


def restore_models(bundle, home, source_home):
    home = home.resolve()
    target = target_directory(home, '.omlx/models')
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    stage = Path(tempfile.mkdtemp(prefix='.models-restore-', dir=target.parent))
    try:
        extract_archive(bundle/'omlx-models.tar.gz', stage, target, home, source_home)
        for name in MODELS:
            choices = [path for path in (stage/name, stage/'mlx-community'/name)
                       if (path/'config.json').is_file()]
            if len(choices) != 1 or not any(choices[0].glob('*.safetensors')):
                raise ValueError('恢复的模型配置或权重缺失：'+name)
        stage.rename(target)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    print('三个 oMLX 模型已恢复：'+str(target)+'；须继续执行真实文本和语音推理验收。')


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('component', choices=['openclaw', 'omlx'])
    parser.add_argument('bundle', type=Path)
    args = parser.parse_args()
    try:
        bundle = args.bundle.expanduser().resolve()
        home = Path.home().resolve()
        if args.component == 'openclaw' and (bundle/'state.tar.gz').is_file():
            source_home = verify_openclaw_backup(bundle)
            directory = bundle
            if not (home/'.env').is_file():
                raise ValueError('先 restore-mac 恢复本机 env，再恢复 OpenClaw 状态。')
        else:
            manifest = verify(bundle)
            source_home = Path(manifest['source_home'])
            directory = bundle/'openclaw'
        if not source_home.is_absolute():
            raise ValueError('原 HOME 记录不是绝对路径。')
        if args.component == 'openclaw':
            restore_openclaw(directory, home, source_home, installed_openclaw())
        else:
            restore_models(bundle, home, source_home)
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error,
            tarfile.TarError, subprocess.SubprocessError) as error:
        raise SystemExit(str(error))


if __name__ == '__main__':
    main()
