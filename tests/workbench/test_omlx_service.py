"""oMLX 配置只覆盖工作台管理项，并保留本机私有设置。"""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[2]/'scripts/workbench/omlx_service.py'
spec = importlib.util.spec_from_file_location('omlx_service', SCRIPT)
omlx = importlib.util.module_from_spec(spec)
spec.loader.exec_module(omlx)


class OmlxService(unittest.TestCase):
    def test_apply_merges_managed_values_and_preserves_private_settings(self):
        with tempfile.TemporaryDirectory(prefix='feipi omlx settings ') as scratch:
            base = Path(scratch)/'.omlx'
            settings = base/'settings.json'
            base.mkdir()
            settings.write_text(json.dumps({
                'auth': {'api_key': 'private-key'},
                'model': {'model_dirs': ['/Volumes/Models']},
                'server': {'port': 8123, 'cors_origins': ['http://localhost']},
                'scheduler': {'embedding_batch_size': 64},
            }))
            with patch.object(omlx, 'CONFIG', Path(scratch)/'managed.json'), \
                    patch.object(omlx, 'APP_BASE_PATH', Path(scratch)/'missing-base-path'), \
                    patch.dict(omlx.os.environ, {}, clear=True), \
                    patch.object(omlx.Path, 'home', return_value=Path(scratch)):
                omlx.CONFIG.write_text(json.dumps({
                    'server': {'host': '127.0.0.1', 'port': 8037, 'log_level': 'info'},
                    'scheduler': {'max_concurrent_requests': 8},
                }))
                target = omlx.apply_config(omlx.managed_settings())
            saved = json.loads(settings.read_text())
            self.assertEqual(target, settings.resolve())
            self.assertEqual(saved['server'], {
                'port': 8037, 'cors_origins': ['http://localhost'],
                'host': '127.0.0.1', 'log_level': 'info',
            })
            self.assertEqual(saved['auth'], {'api_key': 'private-key'})
            self.assertEqual(saved['model'], {'model_dirs': ['/Volumes/Models']})
            self.assertEqual(saved['scheduler'], {
                'embedding_batch_size': 64, 'max_concurrent_requests': 8,
            })
            self.assertEqual(settings.stat().st_mode & 0o777, 0o600)

    def test_rejects_non_loopback_host_and_invalid_port(self):
        with tempfile.TemporaryDirectory(prefix='feipi omlx config ') as scratch:
            config = Path(scratch)/'managed.json'
            with patch.object(omlx, 'CONFIG', config):
                config.write_text(json.dumps({'server': {'host': '0.0.0.0', 'port': 8000}}))
                with self.assertRaisesRegex(ValueError, '本机回环'):
                    omlx.managed_settings()
                config.write_text(json.dumps({'server': {'host': '127.0.0.1', 'port': 70000}}))
                with self.assertRaisesRegex(ValueError, '1 到 65535'):
                    omlx.managed_settings()


if __name__ == '__main__':
    unittest.main()
