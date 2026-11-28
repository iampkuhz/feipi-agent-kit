# /// script
# requires-python = ">=3.10,<3.15"
# dependencies = ["tiktoken==0.12.0"]
# ///
"""Count tokens in the frozen source spans used by a bilingual review."""

import argparse
import json
from pathlib import Path

from count_tokens import load_tokenizer, token_delta, tokenizer_metadata


def compare(english, chinese):
    return {
        "english": english,
        "chinese": chinese,
        **token_delta(english, chinese),
    }


def count_review(english, chinese, groups, tokenizer):
    texts = {"english": english, "chinese": chinese}
    lines = {side: text.splitlines(keepends=True) for side, text in texts.items()}
    next_line = dict.fromkeys(texts, 1)
    counts = []
    for group in groups:
        name = group["title"]
        spans = {side: group[side] for side in texts}
        if all(span is None for span in spans.values()):
            raise ValueError(f"{name} 没有可比较的英文或中文")
        group_tokens = {}
        for side, span in spans.items():
            if span is None:
                group_tokens[side] = 0
                continue
            start, end = span
            if type(start) is not int or type(end) is not int or not (
                start == next_line[side] and start <= end <= len(lines[side])
            ):
                raise ValueError(f"{name} 的 {side} 行号有重叠、遗漏或越界：{span}")
            chunk = "".join(lines[side][start - 1:end])
            group_tokens[side] = len(tokenizer.encode_ordinary(chunk))
            next_line[side] = end + 1
        counts.append({
            "title": name,
            "english_lines": spans["english"],
            "chinese_lines": spans["chinese"],
            **compare(**group_tokens),
        })
    for side, last in next_line.items():
        if last != len(lines[side]) + 1:
            raise ValueError(f"{side} 未完整覆盖全文，从第 {last} 行起尚未计入")
    return {
        **tokenizer_metadata(tokenizer),
        "total": compare(*(len(tokenizer.encode_ordinary(text)) for text in texts.values())),
        "groups": counts,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("english", type=Path, help="固定英文 Markdown 源文件")
    parser.add_argument("chinese", type=Path, help="对应中文候选 Markdown 源文件")
    parser.add_argument("plan", type=Path, help="含 english/chinese 行号范围的分组 JSON")
    args = parser.parse_args()
    try:
        result = count_review(
            args.english.read_bytes().decode("utf-8"),
            args.chinese.read_bytes().decode("utf-8"),
            json.loads(args.plan.read_text(encoding="utf-8"))["groups"],
            load_tokenizer(),
        )
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.error(str(error))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
