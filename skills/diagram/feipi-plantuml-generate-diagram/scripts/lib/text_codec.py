"""PlantUML 显示文本与源码安全表示之间的单次 codec。"""

from __future__ import annotations

import re
import unicodedata


_CODEPOINT = re.compile(r"<U\+([0-9A-Fa-f]{4,6})>")


def validate_display_text(text: str) -> list[str]:
    """拒绝不适合作为显示文本的控制字符，保留其余字面内容。"""
    if any((unicodedata.category(char).startswith("C") and char != "\n") or char in "\u2028\u2029" for char in text):
        return ["显示文本不支持控制字符、隐藏格式字符或非 LF 行分隔符"]
    return []


def encode_display_text(text: str, *, protect_line_start: bool = True) -> str:
    """将显示内容编码为 PlantUML Creole Unicode 转义，保护标点与行首结构关键字。"""
    if errors := validate_display_text(text):
        raise ValueError("；".join(errors))
    output = []
    line_start = True
    for char in text:
        if char == "\n":
            output.append(r"\n")
            line_start = True
        elif protect_line_start and line_start and char in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz":
            # 以转义字母起行，避免 note 等多行显示块把文本解释成命令。
            output.append(f"<U+{ord(char):04X}>")
            line_start = False
        elif char.isspace() or char.isalnum() or unicodedata.category(char).startswith(("L", "N", "M")):
            output.append(char)
            if not char.isspace():
                line_start = False
        else:
            output.append(f"<U+{ord(char):04X}>")
            line_start = False
    return "".join(output)


def decode_display_text(text: str) -> str:
    """仅解码已解析出的显示字段；单次、非递归，不解码控制字符或非法码点。"""
    text = text.replace(r"\n", "\n")

    def decode(match: re.Match[str]) -> str:
        codepoint = int(match.group(1), 16)
        if codepoint > 0x10FFFF or 0xD800 <= codepoint <= 0xDFFF:
            return match.group(0)
        char = chr(codepoint)
        safe = not unicodedata.category(char).startswith("C") and char not in "\u2028\u2029"
        return char if safe else match.group(0)

    return _CODEPOINT.sub(decode, text)
