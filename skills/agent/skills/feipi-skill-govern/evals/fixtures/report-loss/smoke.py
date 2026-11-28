"""检查报告包含目标。"""

import importlib.util
from pathlib import Path


spec = importlib.util.spec_from_file_location("report", Path(__file__).resolve().parents[1] / "scripts/report.py")
report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report)
output, notification = report.render([{"skill": "feipi-notes-collect-pages"}])
assert "feipi-notes-collect-pages" in output
assert "feipi-notes-collect-pages" in notification
print("通过")
