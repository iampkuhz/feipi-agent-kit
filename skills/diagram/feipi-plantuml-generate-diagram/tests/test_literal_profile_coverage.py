"""六个 typed profile 的显示文本编码与 coverage 回归。"""

from pathlib import Path
import sys
import unittest

SKILL = Path(__file__).resolve().parent.parent
SCRIPTS = SKILL / "scripts"
sys.path.insert(0, str(SCRIPTS))

from check_coverage import (
    check_activity_coverage,
    check_architecture_coverage,
    check_component_coverage,
    check_deployment_coverage,
    check_sequence_coverage,
    load_yaml,
    normalize_text,
)
from lib.mindmap import coverage_errors
from lib.text_codec import encode_display_text
from generate_mindmap import generate

EXAMPLES = SKILL / "assets/examples"
LABEL = '__main__.py ** // ~~ -- == ^^ ,, "" <tag> [x] {x} ; : | \\n !include @enduml $x %x & <U+0041>'


def encoded_name(raw: str) -> str:
    return f'"{encode_display_text(raw)}"'


class LiteralProfileCoverageTests(unittest.TestCase):
    def fixture(self, profile: str):
        brief_path = EXAMPLES / profile / f"{profile}-brief.example.yaml"
        diagram_path = EXAMPLES / profile / f"{profile}-diagram.example.puml"
        return load_yaml(brief_path), diagram_path.read_text(encoding="utf-8")

    def test_architecture_labels(self):
        brief, source = self.fixture("architecture")
        brief["layers"][0]["name"] = LABEL
        source = source.replace('"接入层"', encoded_name(LABEL), 1)
        brief["components"][0]["name"] = LABEL
        source = source.replace('"用户"', encoded_name(LABEL), 1)
        brief["flows"][0]["description"] = LABEL
        source = source.replace("S1 提交下单请求", "S1 " + encode_display_text(LABEL), 1)
        self.assertFalse(check_architecture_coverage(brief, source, normalize_text(source)))

    def test_sequence_labels(self):
        brief, source = self.fixture("sequence")
        brief["participants"][0]["name"] = LABEL
        source = source.replace('"用户"', encoded_name(LABEL), 1)
        brief["groups"][0]["name"] = LABEL
        source = source.replace('"前端层"', encoded_name(LABEL), 1)
        multiline = "文件 __main__.py\n第二行 @include"
        brief["messages"][0]["description"] = multiline
        source = source.replace("M1 提交下单请求", "M1 " + encode_display_text(multiline), 1)
        self.assertFalse(check_sequence_coverage(brief, source, normalize_text(source)))

    def test_component_and_deployment_labels(self):
        for profile, container_key, node_key, original_container, original_node in (
            ("component", "groups", "nodes", "申请业务域", "凭据申请系统"),
            ("deployment", "zones", "nodes", "在线签发区", "在线签发系统"),
        ):
            with self.subTest(profile=profile):
                brief, source = self.fixture(profile)
                brief[container_key][0]["name"] = LABEL
                source = source.replace(encoded_name(original_container), encoded_name(LABEL), 1)
                brief[node_key][0]["name"] = LABEL
                source = source.replace(encoded_name(original_node), encoded_name(LABEL), 1)
                check = check_component_coverage if profile == "component" else check_deployment_coverage
                self.assertFalse(check(brief, source, normalize_text(source)))

    def test_activity_labels(self):
        brief, source = self.fixture("activity")
        multiline = "文件 __main__.py\n第二行 @include"
        brief["steps"][0]["name"] = multiline
        source = source.replace(":S1 接收申请;", ":S1 " + encode_display_text(multiline) + ";", 1)
        self.assertFalse(check_activity_coverage(brief, source, normalize_text(source)))

    def test_mindmap_labels(self):
        brief, _ = self.fixture("mindmap")
        brief["nodes"][1]["label"] = "文件 __main__.py\n第二行 @include"
        self.assertFalse(coverage_errors(brief, generate(brief)))


if __name__ == "__main__":
    unittest.main()
