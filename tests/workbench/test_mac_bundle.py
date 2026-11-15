"""实际 CLI 验证配置包迁机，不读取真实 HOME 或凭据。"""
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class MacBundle(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='feipi private migration ')
        self.base = Path(self.temp.name).resolve()
        self.old = self.base/'old home'; self.old.mkdir()
        self.new = self.base/'new home'; self.new.mkdir()
        vault = self.old/'.local/env-vault'; vault.mkdir(parents=True)
        (vault/'.env').write_text('TEST_SECRET=fixture-secret\nTEST_DIR="'+str(self.old)+'/data"\n')
        (self.old/'.env').symlink_to(vault/'.env')
        (self.old/'.qwen').mkdir()
        (self.old/'.qwen/settings.json').write_text(json.dumps({'path': str(self.old)+'/notes'}))
        self.bundle = self.base/'transfer bundle'
        self.extra_env = {}

    def tearDown(self):
        self.temp.cleanup()

    def cli(self, home, action):
        env = dict(os.environ, HOME=str(home)); env.update(self.extra_env)
        return subprocess.run([str(ROOT/'workbench'), 'private', action, str(self.bundle)],
                              env=env, text=True,
                              capture_output=True, timeout=20)

    def export(self):
        proc = self.cli(self.old, 'export-mac')
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn('fixture-secret', proc.stdout+proc.stderr)

    def test_export_restore_relocates_home_and_is_repeatable(self):
        self.export()
        self.assertEqual(stat.S_IMODE(self.bundle.stat().st_mode), 0o700)
        for _ in range(2):
            proc = self.cli(self.new, 'restore-mac')
            self.assertEqual(proc.returncode, 0, proc.stderr)
        env = self.new/'.env'
        self.assertTrue(env.is_symlink())
        self.assertEqual(env.resolve(), self.new/'.local/env-vault/.env')
        self.assertIn('fixture-secret', env.read_text())
        self.assertIn(str(self.new)+'/data', env.read_text())
        self.assertEqual(stat.S_IMODE(env.stat().st_mode), 0o600)
        self.assertEqual(json.loads((self.new/'.qwen/settings.json').read_text())['path'], str(self.new)+'/notes')
        self.assertTrue(list((self.new/'.local/state/feipi-workbench/changes').glob('*-mac-private-restore')))

    def test_corrupt_package_rejected_before_any_target_write(self):
        self.export()
        (self.new/'.env').write_text('keep-existing')
        (self.bundle/'payload/.qwen/settings.json').write_text('{}')
        proc = self.cli(self.new, 'restore-mac')
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual((self.new/'.env').read_text(), 'keep-existing')
        self.assertFalse((self.new/'.local/env-vault').exists())

    def codex_fixture(self):
        native = {'models': [{'slug': 'first', 'base_instructions': 'native instructions '*1024},
                             {'slug': 'second', 'base_instructions': 'other instructions'}]}
        version = json.loads((ROOT/'components/multica/config/agents.json').read_text())['compatibility']['codex']
        binary = self.base/'bin/codex'; binary.parent.mkdir()
        binary.write_text('#!/usr/bin/env python3\nimport sys\n'
                          'if sys.argv[1:] == ["--version"]: print('+repr('codex-cli '+version)+')\n'
                          'elif sys.argv[1:] == ["debug", "models", "--bundled"]: print('+repr(json.dumps(native))+')\n'
                          'else: raise SystemExit(99)\n')
        binary.chmod(0o755)
        self.extra_env['PATH'] = str(binary.parent)+os.pathsep+os.environ['PATH']
        return native

    def test_codex_catalog_is_rebuilt_exactly_without_copying_derived_metadata(self):
        native = self.codex_fixture()
        codex = self.old/'.codex'; (codex/'model-catalogs').mkdir(parents=True)
        catalog = codex/'model-catalog.selected.json'
        (codex/'config.toml').write_text('model_catalog_json = "'+str(catalog)+'"\n')
        content = json.dumps({'models': [native['models'][1], native['models'][0]]})
        catalog.write_text(content)
        (codex/'model-catalogs/litellm-local.json').write_text(content)
        self.export()
        manifest = json.loads((self.bundle/'manifest.json').read_text())
        self.assertEqual(manifest['generated_codex_catalogs'][0]['slugs'], ['second', 'first'])
        self.assertLess(len(json.dumps(manifest['generated_codex_catalogs'])), 1024)
        self.assertFalse((self.bundle/'payload/.codex/model-catalog.selected.json').exists())
        self.assertFalse((self.bundle/'payload/.codex/model-catalogs/litellm-local.json').exists())
        proc = self.cli(self.new, 'restore-mac')
        self.assertEqual(proc.returncode, 0, proc.stderr)
        restored = self.new/'.codex/model-catalog.selected.json'
        self.assertEqual(json.loads(restored.read_text()), json.loads(content))
        self.assertIn(str(restored), (self.new/'.codex/config.toml').read_text())
        self.assertFalse((self.new/'.codex/model-catalogs/litellm-local.json').exists())

    def test_custom_model_metadata_is_not_silently_replaced_by_bundled_defaults(self):
        native = self.codex_fixture()
        codex = self.old/'.codex'; codex.mkdir()
        (codex/'config.toml').write_text('model_catalog_json = "'+str(codex/'model-catalog.selected.json')+'"\n')
        native['models'][0]['base_instructions'] = 'custom instructions'
        (codex/'model-catalog.selected.json').write_text(json.dumps(native))
        result = self.cli(self.old, 'export-mac')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.bundle.exists())

    def test_legacy_catalog_payload_still_restores_without_native_codex(self):
        self.export()
        content = json.dumps({'models': [{'slug': 'legacy', 'base_instructions': 'custom'}]}).encode()
        relative = '.codex/model-catalog.selected.json'
        payload = self.bundle/'payload'/relative; payload.parent.mkdir(parents=True)
        payload.write_bytes(content)
        path = self.bundle/'manifest.json'; manifest = json.loads(path.read_text())
        manifest.pop('generated_codex_catalogs')
        manifest['files'].append({'path': relative, 'sha256': hashlib.sha256(content).hexdigest(),
                                  'size': len(content)})
        path.write_text(json.dumps(manifest))
        result = self.cli(self.new, 'restore-mac')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads((self.new/relative).read_text()), json.loads(content))

    def test_changed_native_metadata_fails_before_overwriting_existing_configuration(self):
        native = self.codex_fixture()
        codex = self.old/'.codex'; codex.mkdir()
        (codex/'config.toml').write_text('model_catalog_json = "'+str(codex/'model-catalog.selected.json')+'"\n')
        (codex/'model-catalog.selected.json').write_text(json.dumps(native))
        self.export()
        (self.new/'.env').write_text('keep-existing')
        path = self.bundle/'manifest.json'; manifest = json.loads(path.read_text())
        manifest['generated_codex_catalogs'][0]['sha256'] = '0'*64
        path.write_text(json.dumps(manifest))
        result = self.cli(self.new, 'restore-mac')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.new/'.env').read_text(), 'keep-existing')
        self.assertFalse((self.new/'.codex/config.toml').exists())

    def test_manifest_traversal_rejected(self):
        self.export()
        path = self.bundle/'manifest.json'
        data = json.loads(path.read_text())
        data['files'][0]['path'] = '../../outside'
        path.write_text(json.dumps(data))
        proc = self.cli(self.new, 'restore-mac')
        self.assertNotEqual(proc.returncode, 0)
        self.assertFalse((self.new/'.env').exists())

    def test_restore_rejects_parent_symlink_without_writing_outside_home(self):
        self.export()
        outside = self.base/'outside'; outside.mkdir()
        (self.new/'.qwen').symlink_to(outside)
        proc = self.cli(self.new, 'restore-mac')
        self.assertNotEqual(proc.returncode, 0)
        self.assertFalse((outside/'settings.json').exists())
        self.assertFalse((self.new/'.local/env-vault').exists())

    def test_existing_export_is_never_overwritten(self):
        self.export()
        before = hashlib.sha256((self.bundle/'manifest.json').read_bytes()).hexdigest()
        proc = self.cli(self.old, 'export-mac')
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(hashlib.sha256((self.bundle/'manifest.json').read_bytes()).hexdigest(), before)


if __name__ == '__main__':
    unittest.main()
