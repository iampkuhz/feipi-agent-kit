# /// script
# requires-python = ">=3.10,<3.15"
# dependencies = ["tiktoken==0.12.0", "PyYAML==6.0.3"]
# ///
"""统计 UTF-8 文本的 token 数，或比较同一内容的两个版本。"""

import argparse
from importlib.metadata import version
import json
from pathlib import Path
import sys


def load_tokenizer():
    import tiktoken

    return tiktoken.get_encoding("o200k_base")


def tokenizer_metadata(tokenizer):
    return {"encoding": tokenizer.name, "tiktoken_version": version("tiktoken")}


def token_delta(baseline, candidate):
    difference = candidate - baseline
    return {
        "difference": difference,
        "change_percent": difference * 100 / baseline if baseline else None,
    }


def frontmatter_value(text, field):
    import yaml

    lines = text.removeprefix("\ufeff").splitlines(keepends=True)
    closing = next(
        (index for index, line in enumerate(lines[1:], 1) if line.rstrip("\r\n") == "---"),
        None,
    )
    if not lines or lines[0].rstrip("\r\n") != "---" or closing is None:
        raise ValueError("缺少完整的 YAML frontmatter")
    try:
        fields = yaml.safe_load("".join(lines[1:closing]))
    except yaml.YAMLError as error:
        raise ValueError(f"YAML frontmatter 无法解析：{error}") from error
    if not isinstance(fields, dict) or not isinstance(fields.get(field), str):
        raise ValueError(f"frontmatter 的 {field} 必须是字符串")
    return fields[field]


def compare_inputs(inputs, tokenizer):
    counts = [
        {"source": source, "tokens": len(tokenizer.encode_ordinary(text))}
        for source, text in inputs
    ]
    result = {**tokenizer_metadata(tokenizer), "inputs": counts}
    if len(counts) == 2:
        result.update(token_delta(counts[0]["tokens"], counts[1]["tokens"]))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="文本文件。传 - 可从标准输入读取")
    parser.add_argument("candidate", nargs="?", help="候选文本文件。若提供，source 作为基线")
    parser.add_argument(
        "--frontmatter-field", metavar="KEY", help="只统计 YAML frontmatter 中解析后的指定字符串值",
    )
    args = parser.parse_args()
    sources = [args.source, args.candidate] if args.candidate is not None else [args.source]
    if sources.count("-") > 1:
        parser.error("标准输入只能读取一次")

    inputs = []
    for source in sources:
        try:
            data = sys.stdin.buffer.read() if source == "-" else Path(source).read_bytes()
            text = data.decode("utf-8")
            if args.frontmatter_field is not None:
                text = frontmatter_value(text, args.frontmatter_field)
        except (OSError, ValueError) as error:
            parser.error(f"{source}：{error}")
        inputs.append((source, text))
    try:
        result = compare_inputs(inputs, load_tokenizer())
    except (OSError, ValueError) as error:
        parser.error(f"无法加载分词器或统计 token：{error}")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
