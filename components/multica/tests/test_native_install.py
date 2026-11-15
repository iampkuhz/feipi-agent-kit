"""隔离 HOME、真实本地子进程验证固定安装、摘要、重复执行和冲突保全。"""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('native_install', ROOT/'scripts/install-native.py')
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)


class NativeInstall(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='multica native install ')
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.home = self.base/'new home'; self.home.mkdir()
        self.bin = self.base/'bin'; self.bin.mkdir()
        self.archive = self.base/'cli.tar.gz'
        self.compose = self.base/'compose.yml'; self.compose.write_bytes(b'fixture compose\n')
        self.calls = self.base/'downloads.jsonl'
        self.write_archive()
        curl = self.bin/'curl'
        curl.write_text(f'#!{sys.executable}\n'+'''
import json, os, pathlib, shutil, sys
args=sys.argv[1:]; url=args[-3]
with pathlib.Path(os.environ['CALLS']).open('a') as log: log.write(json.dumps(url)+'\\n')
source=os.environ['ARCHIVE'] if url.endswith('.tar.gz') else os.environ['COMPOSE']
shutil.copyfile(source,args[-1])
''')
        curl.chmod(0o755)
        self.cli = self.home/'.local/bin/multica'
        self.target = self.home/'.local/share/multica/server/docker-compose.selfhost.yml'
        self.data = json.loads((ROOT/'versions.json').read_text())
        self.data['cli_archive_sha256'] = hashlib.sha256(self.archive.read_bytes()).hexdigest()
        self.data['compose_sha256'] = hashlib.sha256(self.compose.read_bytes()).hexdigest()
        for manager in (
            patch.dict(os.environ, {'HOME':str(self.home), 'PATH':str(self.bin)+os.pathsep+os.defpath,
                                    'ARCHIVE':str(self.archive), 'COMPOSE':str(self.compose), 'CALLS':str(self.calls)}),
            patch.object(native.platform, 'system', return_value='Darwin'),
            patch.object(native.platform, 'machine', return_value='arm64'),
            patch.object(native.shutil, 'which', return_value=None),
            patch.object(native, 'lock', return_value=self.data),
        ):
            manager.start(); self.addCleanup(manager.stop)

    def write_archive(self, link=False):
        with tarfile.open(self.archive, 'w:gz') as packed:
            item = tarfile.TarInfo('multica')
            if link:
                item.type = tarfile.SYMTYPE; item.linkname = str(self.base/'outside')
                packed.addfile(item)
            else:
                payload = b'#!/bin/sh\necho "multica 0.6.3 (fixture)"\n'
                item.size = len(payload); item.mode = 0o755
                packed.addfile(item, io.BytesIO(payload))

    def prepare(self, action='install'):
        with contextlib.redirect_stdout(io.StringIO()):
            native.prepare(action)

    def test_fresh_install_and_repeat_check_only_download_needed_files(self):
        self.prepare()
        self.prepare()
        self.prepare('check')
        urls = [json.loads(line) for line in self.calls.read_text().splitlines()]
        self.assertEqual(len(urls), 2)
        self.assertIn('/v0.6.3/multica-cli-0.6.3-darwin-arm64.tar.gz', urls[0])
        self.assertIn(self.data['upstream_commit']+'/docker-compose.selfhost.yml', urls[1])
        self.assertEqual(self.target.read_bytes(), self.compose.read_bytes())
        self.assertEqual(self.cli.stat().st_mode & 0o777, 0o755)
        self.assertEqual(self.target.stat().st_mode & 0o777, 0o600)
        self.assertFalse((self.home/'.multica').exists())
        self.assertEqual(list(self.target.parent.iterdir()), [self.target])

    def test_check_is_read_only_when_missing(self):
        with self.assertRaisesRegex(ValueError, '缺少'):
            self.prepare('check')
        self.assertEqual(list(self.home.iterdir()), [])
        self.assertFalse(self.calls.exists())

    def test_global_cli_does_not_hide_missing_canonical_wrapper_entry(self):
        global_cli = self.base/'global multica'
        original = '#!/bin/sh\necho "multica 0.6.3"\n'
        global_cli.write_text(original); global_cli.chmod(0o755)
        with patch.object(native.shutil, 'which', return_value=str(global_cli)):
            self.prepare()
        self.assertTrue(self.cli.is_file())
        self.assertEqual(global_cli.read_text(), original)

    def test_existing_different_cli_is_preserved_before_downloading(self):
        self.cli.parent.mkdir(parents=True)
        original = '#!/bin/sh\necho "multica 0.8.2"\n'
        self.cli.write_text(original); self.cli.chmod(0o755)
        with self.assertRaisesRegex(ValueError, '未覆盖或降级'):
            self.prepare()
        self.assertEqual(self.cli.read_text(), original)
        self.assertFalse(self.target.exists())
        self.assertFalse(self.calls.exists())

    def test_existing_different_compose_is_preserved_before_downloading(self):
        self.target.parent.mkdir(parents=True); self.target.write_text('keep mine')
        with self.assertRaisesRegex(ValueError, '服务定义'):
            self.prepare()
        self.assertEqual(self.target.read_text(), 'keep mine')
        self.assertFalse(self.cli.exists())
        self.assertFalse(self.calls.exists())

    def test_bad_cli_checksum_publishes_nothing(self):
        self.data['cli_archive_sha256'] = '0'*64
        with self.assertRaisesRegex(ValueError, '摘要'):
            self.prepare()
        self.assertFalse(self.cli.exists())
        self.assertFalse(self.target.exists())

    def test_bad_compose_checksum_does_not_publish_already_validated_cli(self):
        self.data['compose_sha256'] = '0'*64
        with self.assertRaisesRegex(ValueError, '摘要'):
            self.prepare()
        self.assertFalse(self.cli.exists())
        self.assertFalse(self.target.exists())

    def test_archive_link_is_rejected_without_extracting(self):
        self.write_archive(link=True)
        self.data['cli_archive_sha256'] = hashlib.sha256(self.archive.read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError, '普通文件'):
            self.prepare()
        self.assertFalse(self.cli.exists())
        self.assertFalse((self.base/'outside').exists())

    def test_parent_link_is_rejected_without_writing_outside_home(self):
        outside = self.base/'outside'; outside.mkdir()
        (self.home/'.local').symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, '父路径冲突'):
            self.prepare()
        self.assertEqual(list(outside.iterdir()), [])
        self.assertFalse(self.calls.exists())

    def test_other_platform_stops_before_download_or_creation(self):
        with patch.object(native.platform, 'system', return_value='Linux'):
            with self.assertRaisesRegex(ValueError, 'Apple Silicon'):
                self.prepare()
        self.assertEqual(list(self.home.iterdir()), [])
        self.assertFalse(self.calls.exists())


if __name__ == '__main__':
    unittest.main()
