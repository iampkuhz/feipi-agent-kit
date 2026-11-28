from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import count_tokens
from count_review_tokens import count_review


class ByteTokenizer:
    name = "fixture"

    def encode_ordinary(self, text):
        return text.encode("utf-8")


class TokenCountTests(unittest.TestCase):
    def test_cli_counts_raw_json_and_markdown(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "example.json"
            source.write_bytes(b'{"x": 1}\r\n')
            candidate = Path(temp) / "reference.md"
            candidate.write_bytes("# 指南\n".encode("utf-8"))
            output = io.StringIO()
            with (
                patch.object(sys, "argv", ["count_tokens.py", str(source), str(candidate)]),
                patch.object(count_tokens, "load_tokenizer", return_value=ByteTokenizer()),
                patch.object(count_tokens, "version", return_value="fixture-version"),
                redirect_stdout(output),
            ):
                count_tokens.main()

            self.assertEqual(json.loads(output.getvalue()), {
                "encoding": "fixture",
                "tiktoken_version": "fixture-version",
                "inputs": [{"source": str(source), "tokens": 10}, {"source": str(candidate), "tokens": 9}],
                "difference": -1,
                "change_percent": -10.0,
            })

    def test_zero_baseline_keeps_difference_without_percentage(self):
        self.assertEqual(count_tokens.token_delta(0, 5), {"difference": 5, "change_percent": None})

    def test_bilingual_review_keeps_group_result_and_encodes_the_whole_text(self):
        class BoundaryTokenizer(ByteTokenizer):
            def encode_ordinary(self, text):
                return [1] if text == "a\nb\n" else super().encode_ordinary(text)

        groups = [
            {"title": "first", "english": [1, 1], "chinese": [1, 1]},
            {"title": "removed", "english": [2, 2], "chinese": None},
        ]
        with patch.object(count_tokens, "version", return_value="fixture-version"):
            result = count_review("a\nb\n", "中\n", groups, BoundaryTokenizer())

        self.assertEqual(result["total"], {"english": 1, "chinese": 4, "difference": 3, "change_percent": 300.0})
        self.assertEqual(result["groups"][1], {
            "title": "removed", "english_lines": [2, 2], "chinese_lines": None,
            "english": 2, "chinese": 0, "difference": -2, "change_percent": -100.0,
        })


if __name__ == "__main__":
    unittest.main()
