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

    def tearDown(self):
        self.temp.cleanup()

    def cli(self, home, action):
        return subprocess.run([str(ROOT/'workbench'), 'private', action, str(self.bundle)],
                              env=dict(os.environ, HOME=str(home)), text=True,
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
