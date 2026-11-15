"""真实 tar/SQLite 验证状态恢复、程序链接重建与已有资料保全。"""
import io
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'scripts/workbench'))
from migration_state import MODELS, restore_models, restore_openclaw
from migration_projects import archive_paths


class MigrationState(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='feipi native state ')
        self.base = Path(self.temp.name).resolve()
        self.old = self.base/'old home'; self.old.mkdir()
        self.home = self.base/'new home'; self.home.mkdir()
        self.bundle = self.base/'bundle'; self.bundle.mkdir()
        (self.bundle/'openclaw').mkdir()
        self.state = self.old/'.openclaw'; self.state.mkdir()
        (self.state/'openclaw.json').write_text(json.dumps({'workspace': str(self.old)+'/notes',
                                                         'credential': 'fixture-secret'}))
        (self.state/'workspace').mkdir()
        (self.state/'workspace/MEMORY.md').write_text('Preserve original memory.\n')
        (self.state/'.env').symlink_to(self.old/'.env')
        self.db = self.state/'state/openclaw.sqlite'; self.db.parent.mkdir()
        connection = sqlite3.connect(self.db)
        connection.execute('CREATE TABLE records (value TEXT)')
        connection.execute("INSERT INTO records VALUES ('preserved')")
        connection.commit(); connection.close()
        (self.bundle/'openclaw/sqlite-integrity.json').write_text(json.dumps({'.openclaw/state/openclaw.sqlite':'ok'}))
        self.package = self.base/'new installed openclaw'
        (self.package/'dist/extensions/canvas/skills/canvas').mkdir(parents=True)
        (self.package/'dist/extensions/canvas/skills/canvas/SKILL.md').write_text('native installed skill')

    def tearDown(self):
        self.temp.cleanup()

    def archive_state(self):
        with tarfile.open(self.bundle/'openclaw/state.tar.gz', 'w:gz') as archive:
            archive.add(self.state, arcname='.openclaw')

    def test_state_restores_database_memory_home_and_native_program_links(self):
        (self.state/'plugin-skills').mkdir()
        (self.state/'plugin-skills/canvas').symlink_to('/old/opt/node_modules/openclaw/dist/extensions/canvas/skills/canvas')
        self.archive_state()
        restore_openclaw(self.bundle, self.home, self.old, self.package)
        restored = self.home/'.openclaw'
        self.assertEqual((restored/'workspace/MEMORY.md').read_text(), 'Preserve original memory.\n')
        value = json.loads((restored/'openclaw.json').read_text())
        self.assertEqual(value['workspace'],str(self.home)+'/notes')
        self.assertEqual(value['credential'],'fixture-secret')
        self.assertEqual((restored/'.env').readlink(),self.home/'.env')
        self.assertEqual((restored/'plugin-skills/canvas').resolve(),self.package/'dist/extensions/canvas/skills/canvas')
        connection = sqlite3.connect(restored/'state/openclaw.sqlite')
        self.assertEqual(connection.execute('SELECT value FROM records').fetchall(),[('preserved',)])
        connection.close()
        with self.assertRaises(ValueError):
            restore_openclaw(self.bundle,self.home,self.old,self.package)

    def test_unknown_external_link_is_rejected_before_publish(self):
        (self.state/'unsafe').symlink_to('/outside/private')
        self.archive_state()
        with self.assertRaises(ValueError):
            restore_openclaw(self.bundle,self.home,self.old,self.package)
        self.assertFalse((self.home/'.openclaw').exists())
        self.assertEqual(list(self.home.iterdir()),[])

    def test_corrupt_database_is_rejected_without_partial_state(self):
        self.db.write_bytes(b'bad database')
        self.archive_state()
        with self.assertRaises(sqlite3.Error):
            restore_openclaw(self.bundle,self.home,self.old,self.package)
        self.assertFalse((self.home/'.openclaw').exists())
        self.assertEqual(list(self.home.iterdir()),[])

    def test_models_require_config_and_weights_and_preserve_existing_target(self):
        source = self.base/'model source'; source.mkdir()
        names=[]
        for name in MODELS:
            directory=source/'mlx-community'/name;directory.mkdir(parents=True)
            for file,data in [('config.json','{}'),('model.safetensors','synthetic fixture')]:
                (directory/file).write_text(data);names.append(str((directory/file).relative_to(source)))
        archive_paths(source,names,self.bundle/'omlx-models.tar.gz')
        restore_models(self.bundle,self.home,self.old)
        self.assertTrue((self.home/'.omlx/models/mlx-community'/MODELS[0]/'model.safetensors').is_file())
        with self.assertRaises(ValueError):
            restore_models(self.bundle,self.home,self.old)

    def test_missing_model_weights_leave_no_published_model_directory(self):
        with tarfile.open(self.bundle/'omlx-models.tar.gz','w:gz') as archive:
            item=tarfile.TarInfo('mlx-community/'+MODELS[0]+'/config.json');item.size=2
            archive.addfile(item,io.BytesIO(b'{}'))
        with self.assertRaises(ValueError):
            restore_models(self.bundle,self.home,self.old)
        self.assertFalse((self.home/'.omlx/models').exists())
        self.assertEqual(list((self.home/'.omlx').glob('.models-restore-*')),[])

    def test_invalid_complete_bundle_rejected_by_cli_before_any_restore(self):
        (self.bundle/'manifest.json').write_text('{}')
        result=subprocess.run([ROOT/'workbench','private','restore-state','omlx',self.bundle],
                              env=dict(os.environ,HOME=str(self.home)),capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0)
        self.assertFalse((self.home/'.omlx').exists())


if __name__ == '__main__':
    unittest.main()
