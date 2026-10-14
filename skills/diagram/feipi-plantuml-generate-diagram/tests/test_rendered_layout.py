#!/usr/bin/env python3
"""渲染后文字区域与关系连线的遮挡回归。"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS.parent / "scripts"))
from lib.rendered_layout import inspect_rendered_layout
from lib.package_verifier import verify_package_dir
from lib.validation_result import compute_sha256
from test_package_verifier import build_package

FIXTURES = TESTS / "fixtures/rendered-layout"
TEXT = '<text x="40" y="55" textLength="40" font-size="14">组件标签</text>'
LINE = '<path d="M0,48 L120,48" fill="none" stroke="black"/>'


class RenderedLayoutTests(unittest.TestCase):
    def check(self, content, **attributes):
        with tempfile.TemporaryDirectory() as directory:
            svg = Path(directory) / "diagram.svg"
            attrs = ' '.join(f'{k}="{v}"' for k,v in attributes.items())
            svg.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" {attrs}>{content}</svg>')
            return inspect_rendered_layout(svg)

    def test_real_complex_component_ortho_rejected_and_polyline_accepted(self):
        failed = inspect_rendered_layout(FIXTURES / "component-complex-ortho.svg")
        self.assertEqual(failed["status"], "failed")
        self.assertTrue(any("E2" in issue and "link_a_c" in issue for issue in failed["issues"]))
        self.assertEqual(inspect_rendered_layout(FIXTURES / "component-complex-fixed.svg")["status"], "ok")

    def test_own_label_is_not_exempt_and_reports_location(self):
        result = self.check('<g class="link" id="link_a_b">'+LINE+TEXT+'</g>')
        self.assertEqual(result["status"], "failed")
        self.assertIn("位置", result["issues"][0])

    def test_unrelated_node_text_checked(self):
        result = self.check('<g id="entity_c">'+TEXT+'</g><g id="link_a_b">'+LINE+'</g>')
        self.assertEqual(result["status"], "failed")

    def test_vertical_diagonal_relative_and_multi_subpath(self):
        for path in ('M60,0 V100', 'M0,0 L100,90', 'm0,48 h120', 'M0,48 H20 M30,48 H120'):
            with self.subTest(path=path):
                self.assertEqual(self.check(f'<path d="{path}" fill="none" stroke="black"/>'+TEXT)["status"], "failed")
        # 两个断开的子路径不能凭空连出穿字段。
        self.assertEqual(self.check('<path d="M0,48 H20 M90,48 H120" fill="none" stroke="black"/>'+TEXT)["status"], "ok")

    def test_bezier_contact_and_bounding_box_false_positive(self):
        self.assertEqual(self.check('<path d="M0,48 C30,48 90,48 120,48" fill="none" stroke="black"/>'+TEXT)["status"], "failed")
        # 曲线控制点外接框覆盖文字，但曲线自身绕过文字。
        self.assertEqual(self.check('<path d="M0,0 C0,100 120,100 120,0" fill="none" stroke="black"/>'+TEXT)["status"], "ok")

    def test_quadratic_smooth_and_arc(self):
        for path in ('M0,48 Q60,48 120,48', 'M0,48 Q30,48 60,48 T120,48',
                     'M0,48 C20,48 40,48 60,48 S100,48 120,48', 'M0,48 A1000,1000 0 0 1 120,48'):
            with self.subTest(path=path):
                self.assertEqual(self.check(f'<path d="{path}" fill="none" stroke="black"/>'+TEXT)["status"], "failed")

    def test_painted_background_masks_but_earlier_background_does_not(self):
        mask = '<rect x="30" y="30" width="60" height="40" fill="white"/>'
        self.assertEqual(self.check(LINE+mask+TEXT)["status"], "ok")
        self.assertEqual(self.check(mask+LINE+TEXT)["status"], "failed")
        self.assertEqual(self.check(LINE+mask.replace('fill="white"','fill="white" fill-opacity="0.5"')+TEXT)["status"], "failed")

    def test_partial_mask_does_not_hide_visible_crossing(self):
        self.assertEqual(self.check(LINE+'<rect x="40" y="30" width="10" height="40" fill="white"/>'+TEXT)["status"], "failed")

    def test_transform_and_text_anchor(self):
        for transformation in ('translate(30,40)', 'scale(2)', 'rotate(25)', 'matrix(1,0,0,1,30,50)'):
            with self.subTest(transformation=transformation):
                self.assertEqual(self.check(f'<g transform="{transformation}">'+LINE+TEXT+'</g>')["status"], "failed")
        self.assertEqual(self.check(LINE+TEXT.replace('x="40"','x="60" text-anchor="middle"'))["status"], "failed")

    def test_hidden_and_decoration_excluded(self):
        self.assertEqual(self.check('<g id="entity_a">'+LINE+'</g>'+TEXT)["status"], "ok")
        self.assertEqual(self.check('<g class="entity">'+LINE+'</g>'+TEXT)["status"], "ok")
        self.assertEqual(self.check('<g display="none">'+LINE+'</g>'+TEXT)["status"], "ok")
        self.assertEqual(self.check('<g style="opacity: 0">'+LINE+'</g>'+TEXT)["status"], "ok")
        self.assertEqual(self.check(LINE+TEXT.replace('<text ', '<text fill="none" '))["status"], "ok")

    def test_near_edge_not_treated_as_crossing(self):
        text = '<text x="108" y="55" textLength="24.7559" font-size="13">E10</text>'
        line = '<line x1="133" x2="133" y1="0" y2="100" stroke="black"/>'
        self.assertEqual(self.check(line+text)["status"], "ok")
        self.assertEqual(self.check(line.replace('133','120')+text)["status"], "failed")

    def test_dash_gap_and_thick_stroke(self):
        dashed = LINE.replace('stroke="black"', 'stroke="black" stroke-dasharray="30,60"')
        self.assertEqual(self.check(dashed+TEXT)["status"], "ok")
        self.assertEqual(self.check(dashed.replace('30,60','50,10')+TEXT)["status"], "failed")
        self.assertEqual(self.check(LINE.replace('48','40').replace('stroke="black"','stroke="black" stroke-width="10"')+TEXT)["status"], "failed")

    def test_unmeasurable_text_and_unsupported_features_require_review(self):
        for text in (TEXT.replace('textLength="40"',''), TEXT.replace('>组件标签','><tspan>组件标签</tspan>')):
            self.assertEqual(self.check(LINE+text)["status"], "review_required")
        self.assertEqual(self.check('<g clip-path="url(#clip)">'+LINE+'</g>'+TEXT)["status"], "review_required")

    def test_sequence_lifelines_distinguished_from_message_arrows(self):
        attributes = {'data-diagram-type':'SEQUENCE'}
        self.assertEqual(self.check(LINE+TEXT, **attributes)["status"], "ok")
        self.assertEqual(self.check('<g class="message">'+LINE+TEXT+'</g>', **attributes)["status"], "failed")
        self.assertEqual(self.check('<g class="message">'+LINE.replace('<path ', '<path id="arrow1" ')+TEXT+'</g>', **attributes)["status"], "failed")

    def test_verifier_recomputes_geometry_even_when_hash_and_report_are_forged(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            data = build_package(base)
            svg = base / "diagram.svg"
            svg.write_bytes((FIXTURES / "component-complex-ortho.svg").read_bytes())
            data["svg_sha256"] = data["artifacts"]["svg"]["sha256"] = compute_sha256(str(svg))
            (base / "validation.json").write_text(json.dumps(data))
            errors = verify_package_dir(base)
            self.assertTrue(any("证据不一致" in error for error in errors))
            self.assertTrue(any("E2" in error for error in errors))
            # 即使把失败几何证据也写回，success 仍被拒绝。
            data["rendered_layout"] = inspect_rendered_layout(svg)
            (base / "validation.json").write_text(json.dumps(data))
            self.assertTrue(any("遮挡验收未通过" in error for error in verify_package_dir(base)))


if __name__ == "__main__":
    unittest.main()
