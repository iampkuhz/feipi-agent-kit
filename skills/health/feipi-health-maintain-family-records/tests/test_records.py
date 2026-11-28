"""真实文件操作回归；全部使用合成成员、材料和临时资料库。"""
from pathlib import Path
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1]/'scripts/health_records.py'


class Records(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='family health ')
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = self.base/'健康库'
        self.root.mkdir()
        for name in ('AGENTS.md', 'README.md', '家庭健康总览.md'):
            (self.root/name).write_text('合成资料库')
        (self.root/'模板').mkdir()
        self.member = self.root/'家庭成员/测试成员'
        self.event = self.event_for('测试成员', '某月_同一事件')
        self.incoming = self.base/'source.bin'
        self.incoming.write_bytes(b'original synthetic bytes\x00')

    def event_for(self, member, event):
        p = self.root/'家庭成员'/member
        p.mkdir(parents=True, exist_ok=True)
        (p/'健康概况.md').write_text('- 家庭称呼：测试长辈；仅为合成测试。')
        event = p/'健康记录'/event
        event.mkdir(parents=True, exist_ok=True)
        (event/'记录.md').write_text('# 事件\n多天继续追加，不拆每天。')
        return event

    def cli(self, action, *args, ok=True):
        result = subprocess.run([sys.executable, str(SCRIPT), action, '--root', str(self.root), *args], capture_output=True, text=True)
        self.assertEqual(result.returncode == 0, ok, result.stdout+result.stderr)
        return json.loads(result.stdout if result.returncode == 0 else result.stderr or result.stdout)

    def archive(self, *args, ok=True, member='测试成员', event='某月_同一事件'):
        return self.cli('archive', '--member', member, '--event', event, '--file', str(self.incoming),
                        '--source', '用户上传的合成附件', '--verification', '仅验证字节，未核验内容', *args, ok=ok)

    def test_context_resolves_explicit_alias_without_reading_medical_content(self):
        found = self.cli('context', '--member', '测试长辈')
        self.assertEqual(found['status'], 'unique')
        self.assertEqual(found['matches'][0]['name'], '测试成员')
        self.assertEqual(self.cli('context', '--member', '奶奶')['status'], 'unresolved')

    def test_ambiguous_alias_never_selects_member(self):
        self.event_for('其他成员', '年度_观察')
        found = self.cli('context', '--member', '测试长辈')
        self.assertEqual(found['status'], 'ambiguous')
        self.assertEqual(len(found['matches']), 2)

    def test_archive_preserves_bytes_manifest_and_is_idempotent(self):
        result = self.archive('--name', '报告.bin')
        original = self.root/result['local_path']
        self.assertEqual(original.read_bytes(), self.incoming.read_bytes())
        self.assertEqual(result['status'], 'archived')
        manifest = self.event/'附件清单.json'
        before = manifest.read_bytes()
        self.assertEqual(self.archive('--name', '报告.bin')['status'], 'already_archived')
        self.assertEqual(before, manifest.read_bytes())
        self.assertTrue(self.cli('check')['ok'])

    def test_multiple_days_reuse_event_and_duplicate_is_not_copied(self):
        first = self.archive()
        other = self.event_for('测试成员', '下一周_补充')
        repeat = self.archive(event=other.name)
        self.assertEqual(repeat['status'], 'duplicate')
        self.assertEqual(repeat['local_path'], first['local_path'])
        self.assertFalse((other/'原始资料').exists())
        self.assertEqual(len(list(self.member.glob('健康记录/*/原始资料/*'))), 1)

    def test_same_filename_with_changed_content_is_preserved(self):
        self.archive()
        before = (self.event/'原始资料/source.bin').read_bytes()
        self.incoming.write_bytes(b'different content')
        self.assertIn('拒绝覆盖', self.archive(ok=False)['error'])
        self.assertEqual((self.event/'原始资料/source.bin').read_bytes(), before)

    def test_cross_member_duplicate_requires_identity_review(self):
        self.archive()
        self.event_for('其他成员', '一次检查')
        self.assertIn('另一成员', self.archive(member='其他成员', event='一次检查', ok=False)['error'])

    def test_signed_download_url_is_not_written(self):
        for suffix in ('?X-Amz-Signature=secret', '?token=secret', '?Expires=123'):
            with self.subTest(suffix=suffix):
                result = self.archive('--source', 'https://example.invalid/file'+suffix, ok=False)
                self.assertIn('临时签名', result['error'])
                self.assertFalse((self.event/'附件清单.json').exists())

    def test_stable_notion_reference_is_allowed(self):
        self.archive('--source', 'notion-file-block://synthetic/file?space_id=synthetic&name=report.pdf')
        self.assertTrue(self.cli('check')['ok'])

    def test_traversal_and_symlink_escape_are_rejected(self):
        self.archive('--name', '../escape.bin', ok=False)
        (self.event/'原始资料').symlink_to(self.base, target_is_directory=True)
        self.assertIn('超出资料库', self.archive(ok=False)['error'])
        self.assertFalse((self.base/'附件清单.json').exists())

    def test_unknown_manifest_is_not_replaced_and_no_file_is_copied(self):
        manifest = self.event/'附件清单.json'
        manifest.write_text('{"unrecognized":true}')
        self.archive(ok=False)
        self.assertEqual(manifest.read_text(), '{"unrecognized":true}')
        self.assertFalse((self.event/'原始资料').exists())

    def test_damage_and_broken_link_are_reported(self):
        self.archive()
        (self.event/'原始资料/source.bin').write_bytes(b'damaged')
        (self.event/'记录.md').write_text('[附件](原始资料/missing.bin)')
        result = self.cli('check', ok=False)
        self.assertFalse(result['ok'])
        self.assertEqual(len(result['errors']), 2)

    def test_global_manifest_relative_to_root_is_supported(self):
        data = self.archive()
        manifest = self.root/'共用资料/来源记录/source.json'
        manifest.parent.mkdir(parents=True)
        manifest.write_text(json.dumps({'files':[{'local_path':data['local_path'], 'sha256':data['sha256'], 'bytes':data['bytes']}]}))
        result = self.cli('check')
        self.assertEqual(result['file_entries_checked'], 2)

    def test_no_library_is_created_for_mistyped_root(self):
        missing = self.base/'missing'
        self.cli('context', '--root', str(missing), ok=False)
        self.assertFalse(missing.exists())

    def test_archive_requires_existing_event_and_nonempty_file(self):
        self.archive(event='不存在', ok=False)
        self.incoming.write_bytes(b'')
        self.archive(ok=False)
        self.assertFalse((self.event/'附件清单.json').exists())


if __name__ == '__main__':
    unittest.main()
