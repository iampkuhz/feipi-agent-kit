#!/usr/bin/env python3
"""记录专利交底真实执行阶段、活动与 subagent 耗时。"""

from __future__ import annotations

import argparse
import fcntl
import json
import subprocess
import sys
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "1.0"
ACTIVITIES = {
    "phase",
    "resource_read",
    "retrieval",
    "diagram_generation",
    "render",
    "validation",
    "subagent_execution",
    "subagent_wait",
}


def _now() -> dict[str, Any]:
    wall_ns = time.time_ns()
    return {
        "wall_time": datetime.fromtimestamp(wall_ns / 1_000_000_000, timezone.utc).isoformat(),
        "wall_time_epoch_ms": round(wall_ns / 1_000_000, 3),
        "monotonic_ns": time.monotonic_ns(),
    }


def _append(log_path: Path, event: dict[str, Any]) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n"
    with log_path.open("a", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        handle.write(payload)
        handle.flush()
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _read_events(log_path: Path) -> list[dict[str, Any]]:
    if not log_path.is_file():
        return []
    events = []
    for index, line in enumerate(log_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{log_path}:{index} JSONL 解析失败：{exc}") from exc
        if isinstance(value, dict):
            events.append(value)
    return events


def _current_session(events: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    start_index = -1
    session_id = ""
    for index, event in enumerate(events):
        if event.get("event") == "session_start" and isinstance(event.get("session_id"), str):
            start_index = index
            session_id = event["session_id"]
    if start_index < 0:
        raise ValueError("timing log 尚未 init")
    return session_id, events[start_index:]


def _base_event(session_id: str, event_type: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "session_id": session_id,
        "event": event_type,
        **_now(),
    }


def _span_fields(args: argparse.Namespace) -> dict[str, Any]:
    fields = {
        "stage": args.stage,
        "activity": args.activity,
        "label": args.label,
    }
    for name in ("agent_role", "agent_id", "model", "reasoning_effort"):
        value = getattr(args, name, "")
        if value:
            fields[name] = value
    return fields


def _start_span(args: argparse.Namespace) -> str:
    log_path = Path(args.log)
    session_id, _ = _current_session(_read_events(log_path))
    span_id = uuid.uuid4().hex
    event = _base_event(session_id, "span_start")
    event.update({"span_id": span_id, **_span_fields(args)})
    _append(log_path, event)
    return span_id


def _end_span(log_path: Path, span_id: str, status: str, exit_code: int | None = None) -> float:
    session_id, current = _current_session(_read_events(log_path))
    starts = [event for event in current if event.get("event") == "span_start" and event.get("span_id") == span_id]
    if len(starts) != 1:
        raise ValueError(f"span_start 不唯一或不存在：{span_id}")
    if any(event.get("event") == "span_end" and event.get("span_id") == span_id for event in current):
        raise ValueError(f"span 已结束：{span_id}")
    start = starts[0]
    now = _now()
    duration_ms = max(0.0, (now["monotonic_ns"] - int(start["monotonic_ns"])) / 1_000_000)
    event = {
        "schema_version": SCHEMA_VERSION,
        "session_id": session_id,
        "event": "span_end",
        "span_id": span_id,
        "stage": start.get("stage", ""),
        "activity": start.get("activity", ""),
        "label": start.get("label", ""),
        "status": status,
        "duration_ms": round(duration_ms, 3),
        **now,
    }
    for name in ("agent_role", "agent_id", "model", "reasoning_effort"):
        if start.get(name):
            event[name] = start[name]
    if exit_code is not None:
        event["exit_code"] = exit_code
    _append(log_path, event)
    return duration_ms


def _measurement(log_path: Path, stage: str, activity: str, label: str, duration_ms: float, **fields: Any) -> None:
    session_id, _ = _current_session(_read_events(log_path))
    event = _base_event(session_id, "measurement")
    event.update(
        {
            "stage": stage,
            "activity": activity,
            "label": label,
            "status": "success",
            "duration_ms": round(max(0.0, duration_ms), 3),
        }
    )
    event.update({key: value for key, value in fields.items() if value not in (None, "")})
    _append(log_path, event)


def _summarize(log_path: Path) -> dict[str, Any]:
    session_id, events = _current_session(_read_events(log_path))
    starts = {event["span_id"]: event for event in events if event.get("event") == "span_start"}
    completed = [event for event in events if event.get("event") in {"span_end", "measurement"}]
    ended_ids = {event.get("span_id") for event in completed if event.get("event") == "span_end"}
    activity_totals: dict[str, dict[str, Any]] = defaultdict(lambda: {"execution_count": 0, "duration_ms": 0.0})
    phases: dict[str, dict[str, Any]] = {}
    for event in completed:
        activity = str(event.get("activity", "unknown"))
        duration = float(event.get("duration_ms", 0.0))
        activity_totals[activity]["execution_count"] += 1
        activity_totals[activity]["duration_ms"] += duration
        if activity == "phase":
            phases[str(event.get("stage", "unknown"))] = {
                "label": event.get("label", ""),
                "status": event.get("status", ""),
                "duration_ms": round(duration, 3),
                "ended_at": event.get("wall_time", ""),
            }

    spawns = [event for event in events if event.get("event") == "subagent_spawn"]
    executions = [event for event in completed if event.get("activity") == "subagent_execution"]
    waits = [event for event in completed if event.get("activity") == "subagent_wait"]
    unique_agents = {
        str(event.get("agent_id") or f"{event.get('agent_role', 'unknown')}#{index}")
        for index, event in enumerate(spawns, start=1)
    }
    roles: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"spawn_count": 0, "execution_count": 0, "execution_duration_ms": 0.0, "wait_count": 0, "wait_duration_ms": 0.0}
    )
    for event in spawns:
        roles[str(event.get("agent_role", "unknown"))]["spawn_count"] += 1
    for event in executions:
        role = str(event.get("agent_role", "unknown"))
        roles[role]["execution_count"] += 1
        roles[role]["execution_duration_ms"] += float(event.get("duration_ms", 0.0))
    for event in waits:
        role = str(event.get("agent_role", "unknown"))
        roles[role]["wait_count"] += 1
        roles[role]["wait_duration_ms"] += float(event.get("duration_ms", 0.0))

    def rounded_map(values: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
        result = {}
        for key, item in sorted(values.items()):
            result[key] = {
                name: round(value, 3) if isinstance(value, float) else value
                for name, value in item.items()
            }
        return result

    return {
        "schema_version": SCHEMA_VERSION,
        "session_id": session_id,
        "generated_at": _now()["wall_time"],
        "timing_log": str(log_path),
        "phases": phases,
        "activities": rounded_map(activity_totals),
        "subagents": {
            "unique_count": len(unique_agents),
            "spawn_count": len(spawns),
            "execution_count": len(executions),
            "wait_count": len(waits),
            "wait_duration_ms": round(sum(float(event.get("duration_ms", 0.0)) for event in waits), 3),
            "roles": rounded_map(roles),
        },
        "incomplete_spans": sorted(span_id for span_id in starts if span_id not in ended_ids),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="开始一个新 timing session")
    init.add_argument("--log", required=True)
    init.add_argument("--label", default="patent-disclosure")

    for name in ("start", "run"):
        item = sub.add_parser(name)
        item.add_argument("--log", required=True)
        item.add_argument("--stage", required=True)
        item.add_argument("--activity", required=True, choices=sorted(ACTIVITIES))
        item.add_argument("--label", required=True)
        item.add_argument("--agent-role", default="")
        item.add_argument("--agent-id", default="")
        item.add_argument("--model", default="")
        item.add_argument("--reasoning-effort", default="")
        if name == "run":
            item.add_argument("argv", nargs=argparse.REMAINDER)

    end = sub.add_parser("end")
    end.add_argument("--log", required=True)
    end.add_argument("--span-id", required=True)
    end.add_argument("--status", choices=("success", "failed", "blocked", "review_required"), default="success")

    record = sub.add_parser("record-subagent")
    record.add_argument("--log", required=True)
    record.add_argument("--agent-role", required=True)
    record.add_argument("--agent-id", required=True)
    record.add_argument("--model", required=True)
    record.add_argument("--reasoning-effort", required=True)

    ingest = sub.add_parser("ingest-diagram")
    ingest.add_argument("--log", required=True)
    ingest.add_argument("--stage", default="phase_3_final_drafting")
    ingest.add_argument("--label", required=True)
    ingest.add_argument("--validation", required=True)

    summary = sub.add_parser("summarize")
    summary.add_argument("--log", required=True)
    summary.add_argument("--output", default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    log_path = Path(args.log)
    if args.command == "init":
        session_id = uuid.uuid4().hex
        event = _base_event(session_id, "session_start")
        event["label"] = args.label
        _append(log_path, event)
        print(f"session_id={session_id}")
        print(f"timing_log={log_path}")
        return 0
    if args.command == "start":
        print(_start_span(args))
        return 0
    if args.command == "end":
        _end_span(log_path, args.span_id, args.status)
        return 0
    if args.command == "record-subagent":
        session_id, _ = _current_session(_read_events(log_path))
        event = _base_event(session_id, "subagent_spawn")
        event.update(
            {
                "agent_role": args.agent_role,
                "agent_id": args.agent_id,
                "model": args.model,
                "reasoning_effort": args.reasoning_effort,
            }
        )
        _append(log_path, event)
        return 0
    if args.command == "run":
        command = list(args.argv)
        if command and command[0] == "--":
            command = command[1:]
        if not command:
            raise ValueError("run 缺少 -- 后的命令")
        span_id = _start_span(args)
        try:
            completed = subprocess.run(command, check=False)
        except OSError:
            _end_span(log_path, span_id, "failed", 127)
            raise
        _end_span(log_path, span_id, "success" if completed.returncode == 0 else "failed", completed.returncode)
        return completed.returncode
    if args.command == "ingest-diagram":
        data = json.loads(Path(args.validation).read_text(encoding="utf-8"))
        timings = data.get("timings")
        if not isinstance(timings, dict):
            raise ValueError("diagram validation 缺少 timings")
        _measurement(log_path, args.stage, "render", args.label, float(timings.get("render_ms", 0.0)), source=args.validation)
        _measurement(
            log_path,
            args.stage,
            "validation",
            args.label,
            float(timings.get("static_validation_ms", 0.0)),
            source=args.validation,
        )
        return 0
    if args.command == "summarize":
        summary = _summarize(log_path)
        payload = json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(payload, encoding="utf-8")
        else:
            print(payload, end="")
        return 0
    raise AssertionError(args.command)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, AssertionError, json.JSONDecodeError) as exc:
        print(f"timing error: {exc}", file=sys.stderr)
        raise SystemExit(2)
