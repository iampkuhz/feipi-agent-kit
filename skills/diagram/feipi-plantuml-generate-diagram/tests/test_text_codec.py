"""显示文本的通用 roundtrip、安全边界与跨上下文回归。"""
from pathlib import Path
import json
import subprocess
import sys
import unittest

SKILL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL / 'scripts'))
from lib.text_codec import encode_display_text, decode_display_text, validate_display_text
from lib.mindmap import parse_mindmap, coverage_errors
from generate_mindmap import generate
from lib.brief_loader import load_yaml
from check_coverage import check_component_coverage, check_deployment_coverage

class TextCodecTests(unittest.TestCase):
    def test_all_printable_ascii_and_unicode_roundtrip(self):
        corpus = [''.join(chr(n) for n in range(32,127)), '__main__.py',
                  '中文 é e\u0301 ∞ 😀', '"<>[]{};|/\\@!$%#~_*',
                  r'\n <U+0041> <U+000A> &#95; &lt;',
                  '首行\nend note\n@enduml\n!include x', 'end note', ' actor A', '']
        for raw in corpus:
            with self.subTest(raw=raw):
                self.assertEqual(decode_display_text(encode_display_text(raw)), raw)

    def test_controls_fail_closed(self):
        invalid = [chr(n) for n in list(range(0,10))+list(range(11,32))+list(range(127,160))]
        invalid += ['\u2028', '\u2029', '\u200d', '\ud800']
        for raw in invalid:
            with self.subTest(codepoint=ord(raw)):
                self.assertTrue(validate_display_text(raw))
                with self.assertRaises(ValueError): encode_display_text(raw)
        self.assertFalse(validate_display_text('\n'))

    def test_decoder_nonrecursive_and_invalid_tokens(self):
        for token in ['<U+000A>', '<U+0009>', '<U+0085>', '<U+2028>', '<U+D800>', '<U+110000>']:
            self.assertEqual(decode_display_text(token), token)
        self.assertEqual(decode_display_text('<U+003C>U+0041<U+003E>'), '<U+0041>')
        self.assertEqual(decode_display_text('<U+005C>n'), r'\n')
        self.assertEqual(decode_display_text(r'\n'), '\n')

    def test_note_line_boundaries_not_keywords(self):
        for raw in ['end note', 'actor Foo', 'end legend', 'end title', 'note right', '!include x', '@enduml']:
            encoded = encode_display_text(raw)
            self.assertNotEqual(encoded, raw)
            self.assertEqual(decode_display_text(encoded),raw)

    def test_cli_and_mindmap_default_codec_agree(self):
        raw = 'F08 __main__.py'
        encoded = subprocess.check_output([sys.executable,str(SKILL/'scripts/encode_display_text.py'),'--text',raw],text=True)
        nodes, errors = parse_mindmap('@startmindmap\n+ 根\n++ '+encoded+'\n@endmindmap')
        self.assertFalse(errors, errors)
        self.assertEqual(nodes[1].label, raw)

    def test_container_kind_and_block_stay_required(self):
        for profile, keyword, name, alias, check in [
            ('component','package','申请业务域','request_domain',check_component_coverage),
            ('deployment','node','在线签发区','online_zone',check_deployment_coverage),
        ]:
            brief=load_yaml(SKILL/f'assets/examples/{profile}/{profile}-brief.example.yaml')
            source=(SKILL/f'assets/examples/{profile}/{profile}-diagram.example.puml').read_text()
            wrong=source.replace(f'{keyword} "{name}" as {alias} {{',f'component "{name}" as {alias} {{')
            self.assertTrue(check(brief,wrong,''))
            wrong=source.replace(f'{keyword} "{name}" as {alias} {{',f'{keyword} "{name}" as {alias}')
            self.assertTrue(check(brief,wrong,''))

if __name__ == '__main__': unittest.main()
