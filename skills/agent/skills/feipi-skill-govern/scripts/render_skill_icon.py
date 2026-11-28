#!/usr/bin/env python3
"""按飞皮图标样式绘制一个 Codex PNG 母版。"""

import argparse
from pathlib import Path
import re
import shutil
import subprocess
from xml.etree import ElementTree as ET


PALETTES = {
    "blue": ("#21467c", "#8ac3ff"),
    "cyan": ("#125561", "#83e4e2"),
    "green": ("#225d44", "#adebb8"),
    "magenta": ("#6b275a", "#f0a6d5"),
    "orange": ("#7c361d", "#ffb277"),
    "purple": ("#462879", "#b99afa"),
    "red": ("#7b3042", "#ffa4ad"),
    "yellow": ("#61460d", "#f9db83"),
}


def draw(main, accent_path, palette):
    background, accent = PALETTES[palette]
    svg = ET.Element("svg", {"xmlns": "http://www.w3.org/2000/svg", "viewBox": "0 0 32 32"})
    ET.SubElement(svg, "rect", {"x": "1", "y": "1", "width": "30", "height": "30", "rx": "8", "fill": background})
    strokes = ET.SubElement(svg, "g", {"fill": "none", "stroke-linecap": "round", "stroke-linejoin": "round",
                                       "stroke-width": "2.15"})
    for path, color in ((main, "#fff"), (accent_path, accent)):
        if path is None:
            continue
        if not re.fullmatch(r"[Mm][0-9 +,\-\.eEMmLlHhVvCcSsQqTtAaZz]+", path):
            raise ValueError("线稿须使用 SVG path 的 d 值，从 M 或 m 开始")
        ET.SubElement(strokes, "path", {"d": path, "stroke": color})
    return ET.tostring(svg, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--main", required=True, help="32×32 画布上的主体线稿 SVG 路径")
    parser.add_argument("--accent-path", help="可选的点缀线稿路径")
    parser.add_argument("--palette", choices=PALETTES, required=True)
    args = parser.parse_args()
    try:
        if args.output.suffix != ".png" or args.output.exists():
            raise ValueError("输出须为尚不存在的 .png 文件")
        renderer = shutil.which("rsvg-convert")
        if not renderer:
            raise ValueError("缺少 rsvg-convert。macOS 可安装 librsvg，Debian/Ubuntu 可安装 librsvg2-bin")
        svg = draw(args.main, args.accent_path, args.palette)
        png = subprocess.check_output([renderer, "-w", "256", "-h", "256"], input=svg)
        with args.output.open("xb") as output:
            output.write(png)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"[FAIL] {error}\n")


if __name__ == "__main__":
    main()
