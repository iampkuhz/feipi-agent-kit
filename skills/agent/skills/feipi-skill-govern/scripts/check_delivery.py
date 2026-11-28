#!/usr/bin/env python3
"""检查治理交接的格式、输入绑定、产物与引用；不判断业务分析是否正确。"""

import argparse
import hashlib
import json
from pathlib import Path
import re


KINDS = {"technical", "semantic", "integration"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def objects(data, key):
    value = data.get(key)
    require(isinstance(value, list) and all(isinstance(x, dict) for x in value),
            f"{key} 必须是对象列表")
    return value


def indexed(items, key):
    result = {}
    for item in items:
        value = item.get(key)
        require(nonempty(value) and value not in result, f"{key} 缺失或重复：{value}")
        result[value] = item
    return result


def references(value, known, label, exact=False):
    require(isinstance(value, list) and all(nonempty(x) for x in value), f"{label} 必须是字符串列表")
    require(len(value) == len(set(value)), f"{label} 有重复引用")
    require(set(value) <= set(known), f"{label} 存在未知引用")
    if exact:
        require(set(value) == set(known), f"{label} 未覆盖全部问题")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_file(root, item):
    require(nonempty(item.get("path")), "文件 path 缺失")
    expected = item.get("sha256")
    require(isinstance(expected, str) and re.fullmatch(r"[0-9a-f]{64}", expected), "sha256 格式错误")
    path = root / item["path"]
    require(path.is_file(), f"缺少交接文件：{item['path']}")
    require(digest(path) == expected, f"文件指纹不符：{item['path']}")


def validate(record, request_file, final=False):
    data = json.loads(record.read_text(encoding="utf-8"))
    require(isinstance(data, dict), "记录必须是 JSON 对象")
    require(type(data.get("schema_version")) is int and data["schema_version"] == 1, "schema_version 必须为 1")
    require(nonempty(data.get("target_skill")), "缺少 target_skill")
    require(data.get("request_sha256") == digest(request_file), "当前请求与交接记录不匹配")
    root = record.parent
    inputs = indexed(objects(data, "inputs"), "id")
    require("request" not in inputs, "request 是保留来源 ID")
    artifacts = indexed(objects(data, "artifacts"), "path")
    for item in list(inputs.values()) + list(artifacts.values()):
        verify_file(root, item)
    checks = indexed(objects(data, "checks"), "id")
    for check in checks.values():
        require(check.get("kind") in KINDS, "未知验证类型")
        require(check.get("status") in {"passed", "failed", "not_run", "not_applicable"}, "未知验证状态")
        require(nonempty(check.get("method")) and nonempty(check.get("result")), "验证缺少方法、结果或不足说明")
        references(check.get("evidence"), artifacts, "验证证据")
        if check["status"] in {"passed", "failed"}:
            require(bool(check["evidence"]), "已执行的验证必须引用证据")
    problems = indexed(objects(data, "problems"), "id")
    for problem in problems.values():
        for key in ("observation", "expected", "failure_case", "outcome"):
            require(nonempty(problem.get(key)), f"问题缺少 {key}")
        require(problem.get("owner") in {"规约", "材料", "Agent 交付", "脚本处理", "展示"}, "未知问题所属环节")
        require(problem.get("status") in {"open", "fixed", "not_applicable"}, "未知问题状态")
        references(problem.get("source_ids"), set(inputs) | {"request"}, "问题来源")
        require(bool(problem["source_ids"]), "问题必须引用来源")
        references(problem.get("check_ids"), checks, "问题验证")
        if problem["status"] == "fixed":
            require(any(checks[x]["status"] == "passed" for x in problem["check_ids"]), "已修复项缺少通过证据")
    require("report" in data and "notification" in data, "必须声明报告及通知，尚未交付时填写 null")
    report = data["report"]
    if report is not None:
        require(isinstance(report, dict) and nonempty(report.get("path")), "报告缺少 path")
        require(report["path"] in artifacts, "报告未登记为产物")
        references(report.get("problem_ids"), problems, "报告问题", exact=final)
    notification = data["notification"]
    if notification is not None:
        require(isinstance(notification, dict), "通知必须是对象或 null")
        require(notification.get("status") in {"prepared", "delivered", "not_requested"}, "未知通知状态")
        require(nonempty(notification.get("text")), "通知缺少正文或无需通知的理由")
        references(notification.get("problem_ids"), problems, "通知问题",
                   exact=final and notification["status"] != "not_requested")
        references(notification.get("evidence"), artifacts, "通知证据")
        if notification["status"] == "delivered":
            require(bool(notification["evidence"]), "已送达通知缺少接收证据")
    if final:
        require(report is not None and notification is not None, "最终交接缺少报告或通知声明")
        require({c["kind"] for c in checks.values()} == KINDS, "最终交接必须分别声明三类验证状态")
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record", type=Path)
    parser.add_argument("--request-file", type=Path, required=True)
    parser.add_argument("--final", action="store_true", help="检查最终交付的覆盖声明，允许如实记录未解决问题")
    args = parser.parse_args()
    try:
        validate(args.record, args.request_file, args.final)
    except (OSError, ValueError, TypeError) as error:
        parser.exit(1, f"[FAIL] 交接技术检查失败：{error}\n")
    print("[PASS] 交接技术检查通过；业务正确性、声明真实性和最终完成度仍需依据实际内容审阅")


if __name__ == "__main__":
    main()
