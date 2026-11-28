#!/usr/bin/env python3
"""完整解析 SRT/VTT 后原子写入 UTF-8 文本，保留原始字幕。"""

import codecs
import os
from pathlib import Path
import re
import sys
import tempfile


TIMING = re.compile(
    r"^((?:\d{2,}:)?\d{2}:\d{2}[.,]\d{3})\s+-->\s+"
    r"((?:\d{2,}:)?\d{2}:\d{2}[.,]\d{3})(?:\s+.*)?$"
)


def convert(source, target):
    replaced_bytes = 0

    def replace_invalid(error):
        nonlocal replaced_bytes
        replaced_bytes += error.end - error.start
        return "\ufffd", error.end

    codecs.register_error("subtitle_replace", replace_invalid)
    content = source.read_bytes().decode("utf-8-sig", errors="subtitle_replace")
    rows = []
    cue_count = 0
    last_timestamp = None
    # SRT/VTT 的 cue 以空行分隔；忽略文件头、NOTE 与 STYLE 块。
    for block in re.split(r"\n\s*\n", content.replace("\r\n", "\n").replace("\r", "\n")):
        lines = block.strip().splitlines()
        if not lines or re.match(r"^(WEBVTT|NOTE|STYLE|REGION)(?:\s|$)", lines[0]):
            continue
        timing_index = next((i for i, line in enumerate(lines) if "-->" in line), None)
        if timing_index is None:
            raise ValueError("字幕片段缺少时间戳")
        match = TIMING.fullmatch(lines[timing_index].strip())
        if not match:
            raise ValueError("字幕时间戳格式无效")
        timestamp = re.split(r"[.,]", match.group(1))[0]
        payload = [re.sub(r"\s+", " ", re.sub(r"<[^>]*>", "", line)).strip()
                   for line in lines[timing_index + 1:]]
        payload = [line for line in payload if line]
        if not payload:
            continue
        cue_count += 1
        last_timestamp = timestamp
        rows.append("- [{}] {}".format(timestamp, payload[0]))
        rows.extend("  " + line for line in payload[1:])
    if not rows:
        raise ValueError("字幕没有带有效时间戳的正文")

    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                         dir=str(target.parent), prefix=".subtitle-text-",
                                         delete=False) as handle:
            temporary = Path(handle.name)
            handle.write("\n".join(rows) + "\n")
        # 验证实际写入文件覆盖全部有效 cue，包含来源的最后一个正文时间戳。
        written = temporary.read_text(encoding="utf-8")
        anchors = re.findall(r"^- \[([^\]]+)\] ", written, flags=re.M)
        if len(anchors) != cue_count or anchors[-1] != last_timestamp:
            raise ValueError("转换后的文本未覆盖全部字幕")
        os.replace(str(temporary), str(target))
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink()
    print("subtitle_encoding_replaced_bytes={}".format(replaced_bytes), file=sys.stderr)
    print("subtitle_cue_count={}".format(cue_count), file=sys.stderr)
    print("text_last_timestamp={}".format(last_timestamp), file=sys.stderr)


if __name__ == "__main__":
    try:
        convert(Path(sys.argv[1]), Path(sys.argv[2]))
    except (OSError, ValueError, IndexError) as error:
        print("字幕转换失败: {}".format(error), file=sys.stderr)
        sys.exit(1)
