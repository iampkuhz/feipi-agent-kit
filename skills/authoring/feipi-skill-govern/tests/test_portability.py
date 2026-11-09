"""Cross-platform and path scanner regression tests."""

import importlib.util
from pathlib import Path
import tempfile
import unittest


SKILL = Path(__file__).resolve().parents[1]
CHECKER = SKILL / "scripts/check_portability.py"
spec = importlib.util.spec_from_file_location("check_portability", CHECKER)
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class PortabilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def scan(self, name, source):
        path = self.root / name
        path.write_text(source, encoding="utf-8")
        return checker.scan_file(path, self.root)

    def test_flags_machine_and_fixed_temp_paths(self):
        user_root = "/" + "Users"
        temp_root = "/" + "tmp"
        issues = self.scan("run.sh", f'echo "{user_root}/alice/work/output"\nprintf x >{temp_root}/result.json\n')
        self.assertEqual(len(issues), 2)

    def test_allows_dynamic_temp_and_regex_examples(self):
        dynamic_temp = "${TMPDIR:-" + "/" + "tmp}/check.XXXXXX"
        user_pattern = "/" + "Users/.*/Downloads"
        issues = self.scan("run.sh", f'mktemp "{dynamic_temp}"\ngrep -E "{user_pattern}" file\n')
        self.assertEqual(issues, [])

    def test_flags_nonportable_shell_commands(self):
        ripgrep = "rg" + " -q"
        issues = self.scan("run.sh", f'mapfile -t values < input\nreadlink -f "$file"\n{ripgrep} text file\n')
        self.assertEqual(len(issues), 3)

    def test_accepts_guarded_bsd_and_gnu_variants(self):
        issues = self.scan("run.sh", 'stat -f%z file || stat -c%s file\ndate -j -f x y || date -d y\n')
        self.assertEqual(issues, [])


if __name__ == "__main__":
    unittest.main()
