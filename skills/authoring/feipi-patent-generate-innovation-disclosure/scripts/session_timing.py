#!/usr/bin/env python3
"""记录专利交底真实执行阶段、活动与 subagent 耗时。"""

from __future__ import annotations

import argparse
import fcntl
import json
import math
import subprocess
import sys
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "1.1"
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
REQUIRED_STAGES = {
    "phase_1_material_modeling",
    "phase_2_idea_confirmation",
    "phase_3_final_drafting",
    "phase_4_review_delivery",
}
REQUIRED_ACTIVITIES = {"resource_read", "retrieval", "diagram_generation", "render", "validation"}
TIMING_FIELDS = {"total_ms", "render_ms", "static_validation_ms", "cache_hit"}
COUNTER_FIELDS = {
    "render_http_requests",
    "render_rounds",
    "package_validation_runs",
    "package_verifier_runs",
    "cache_hits",
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


def _active_session(events: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    session_id, current = _current_session(events)
    if any(event.get("event") == "session_end" for event in current):
        raise ValueError("timing session 已关闭；需要继续工作时请 init 新 session")
    return session_id, current


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
    session_id, _ = _active_session(_read_events(log_path))
    span_id = uuid.uuid4().hex
    event = _base_event(session_id, "span_start")
    event.update({"span_id": span_id, **_span_fields(args)})
    _append(log_path, event)
    return span_id


def _end_span(
    log_path: Path,
    span_id: str,
    status: str,
    exit_code: int | None = None,
    **fields: Any,
) -> float:
    session_id, current = _active_session(_read_events(log_path))
    starts = [event for event in current if event.get("event") == "span_start" and event.get("span_id") == span_id]
    if len(starts) != 1:
        raise ValueError(f"span_start 不唯一或不存在：{span_id}")
    if any(event.get("event") == "span_end" and event.get("span_id") == span_id for event in current):
        raise ValueError(f"span 已结束：{span_id}")
    start = starts[0]
    now = _now()
    duration_ms = max(0.0, (now["monotonic_ns"] - int(start["monotonic_ns"])) / 1_000_000)
    wall_duration_ms = max(0.0, float(now["wall_time_epoch_ms"]) - float(start["wall_time_epoch_ms"]))
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
        "wall_duration_ms": round(wall_duration_ms, 3),
        **now,
    }
    for name in ("agent_role", "agent_id", "model", "reasoning_effort"):
        if start.get(name):
            event[name] = start[name]
    if exit_code is not None:
        event["exit_code"] = exit_code
    event.update({key: value for key, value in fields.items() if value not in (None, "")})
    _append(log_path, event)
    return duration_ms


def _resolve_open_span(log_path: Path, span_id: str, stage: str, activity: str) -> str:
    if span_id:
        return span_id
    _, current = _active_session(_read_events(log_path))
    starts = {event["span_id"]: event for event in current if event.get("event") == "span_start"}
    ended = {event.get("span_id") for event in current if event.get("event") == "span_end"}
    matches = [
        candidate
        for candidate, event in starts.items()
        if candidate not in ended
        and (not stage or event.get("stage") == stage)
        and (not activity or event.get("activity") == activity)
    ]
    if len(matches) != 1:
        raise ValueError(f"无法唯一定位未结束 span：stage={stage or '*'} activity={activity or '*'} matches={len(matches)}")
    return matches[0]


def _measurement(log_path: Path, stage: str, activity: str, label: str, duration_ms: float, **fields: Any) -> None:
    session_id, _ = _active_session(_read_events(log_path))
    event = _base_event(session_id, "measurement")
    event.update(
        {
            "stage": stage,
            "activity": activity,
            "label": label,
            "status": "success",
            "duration_ms": round(max(0.0, duration_ms), 3),
            "wall_duration_ms": round(max(0.0, duration_ms), 3),
        }
    )
    event.update({key: value for key, value in fields.items() if value not in (None, "")})
    _append(log_path, event)


def _diagram_observation(data: Any) -> tuple[dict[str, Any], dict[str, int]]:
    if not isinstance(data, dict):
        raise ValueError("diagram validation 根节点必须是对象")
    if data.get("final_status") != "success" or data.get("render_result") != "ok":
        raise ValueError("只允许导入 final_status=success 且 render_result=ok 的图包观测")
    timings = data.get("last_run_timings")
    counters = data.get("last_run_counters")
    if not isinstance(timings, dict) or not TIMING_FIELDS.issubset(timings):
        raise ValueError("diagram validation 缺少完整 last_run_timings")
    if not isinstance(counters, dict) or not COUNTER_FIELDS.issubset(counters):
        raise ValueError("diagram validation 缺少完整 last_run_counters")
    for field in TIMING_FIELDS - {"cache_hit"}:
        value = timings[field]
        if type(value) not in {int, float} or not math.isfinite(float(value)) or value < 0:
            raise ValueError(f"last_run_timings.{field} 必须是非负有限数")
    if type(timings["cache_hit"]) is not bool:
        raise ValueError("last_run_timings.cache_hit 必须是布尔值")
    if abs(float(timings["total_ms"]) - float(timings["render_ms"]) - float(timings["static_validation_ms"])) > 0.01:
        raise ValueError("last_run_timings.total_ms 必须等于 render_ms + static_validation_ms")
    normalized_counters: dict[str, int] = {}
    for field in COUNTER_FIELDS:
        value = counters[field]
        if type(value) is not int or value < 0:
            raise ValueError(f"last_run_counters.{field} 必须是非负整数")
        normalized_counters[field] = value
    if normalized_counters["package_validation_runs"] != 1:
        raise ValueError("每次图包观测必须对应一次 package validation")
    if normalized_counters["package_verifier_runs"] < 1:
        raise ValueError("成功图包观测必须至少执行一次 package verifier")
    if timings["cache_hit"]:
        if float(timings["render_ms"]) != 0.0:
            raise ValueError("cache hit 的 render_ms 必须为 0")
        if normalized_counters["render_http_requests"] or normalized_counters["render_rounds"]:
            raise ValueError("cache hit 不得记录 renderer 调用")
        if normalized_counters["cache_hits"] != 1:
            raise ValueError("cache hit 次数必须为 1")
    elif normalized_counters["cache_hits"] != 0:
        raise ValueError("非 cache hit 不得记录 cache_hits")
    elif normalized_counters["render_http_requests"] < 1 or normalized_counters["render_rounds"] < 1:
        raise ValueError("非 cache hit 的成功图包必须记录 renderer 请求与轮次")
    return timings, normalized_counters


def _disclosure_validation_operations(path: Path) -> dict[str, int]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"无法读取完整交底校验观测：{exc}") from exc
    counts = data.get("operation_counts") if isinstance(data, dict) else None
    required = {"disclosure_validation_runs", "diagram_package_verifier_runs"}
    if not isinstance(counts, dict) or not required.issubset(counts):
        raise ValueError("完整交底校验报告缺少 operation_counts")
    normalized: dict[str, int] = {}
    for field in required:
        value = counts[field]
        if type(value) is not int or value < 0:
            raise ValueError(f"operation_counts.{field} 必须是非负整数")
        normalized[field] = value
    if normalized["disclosure_validation_runs"] != 1:
        raise ValueError("完整交底校验必须记录一次 disclosure validation")
    return normalized


def _summarize(log_path: Path) -> dict[str, Any]:
    session_id, events = _current_session(_read_events(log_path))
    starts = {event["span_id"]: event for event in events if event.get("event") == "span_start"}
    completed = [event for event in events if event.get("event") in {"span_end", "measurement"}]
    ended_ids = {event.get("span_id") for event in completed if event.get("event") == "span_end"}
    activity_totals: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"execution_count": 0, "duration_ms": 0.0, "wall_duration_ms": 0.0, "status_counts": {}}
    )
    phase_runs: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in completed:
        activity = str(event.get("activity", "unknown"))
        duration = float(event.get("duration_ms", 0.0))
        wall_duration = float(event.get("wall_duration_ms", duration))
        activity_totals[activity]["execution_count"] += 1
        activity_totals[activity]["duration_ms"] += duration
        activity_totals[activity]["wall_duration_ms"] += wall_duration
        status = str(event.get("status", "unknown"))
        status_counts = activity_totals[activity]["status_counts"]
        status_counts[status] = int(status_counts.get(status, 0)) + 1
        if activity == "phase":
            start = starts.get(str(event.get("span_id")), {})
            phase_runs[str(event.get("stage", "unknown"))].append(
                {
                    "label": event.get("label", ""),
                    "status": status,
                    "duration_ms": round(duration, 3),
                    "wall_duration_ms": round(wall_duration, 3),
                    "started_at": start.get("wall_time", ""),
                    "ended_at": event.get("wall_time", ""),
                }
            )

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
        roles[role]["wait_duration_ms"] += float(event.get("wall_duration_ms", event.get("duration_ms", 0.0)))

    def rounded_map(values: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
        result = {}
        for key, item in sorted(values.items()):
            result[key] = {
                name: round(value, 3) if isinstance(value, float) else value
                for name, value in item.items()
            }
        return result

    phases = {
        stage: {
            "execution_count": len(runs),
            "duration_ms": round(sum(float(item["duration_ms"]) for item in runs), 3),
            "wall_duration_ms": round(sum(float(item["wall_duration_ms"]) for item in runs), 3),
            "started_at": runs[0]["started_at"],
            "ended_at": runs[-1]["ended_at"],
            "runs": runs,
        }
        for stage, runs in sorted(phase_runs.items())
    }
    incomplete_spans = sorted(span_id for span_id in starts if span_id not in ended_ids)
    present_activities = set(activity_totals)
    missing_phases = sorted(REQUIRED_STAGES - set(phases))
    missing_activities = sorted(REQUIRED_ACTIVITIES - present_activities)
    final_validation_operations = {
        counter: sum(int(event.get(counter, 0)) for event in completed)
        for counter in ("disclosure_validation_runs", "diagram_package_verifier_runs")
    }
    missing_observations = []
    if final_validation_operations["disclosure_validation_runs"] < 1:
        missing_observations.append("final_validation_operation_counts")
    session_start = events[0]
    session_end = next((event for event in reversed(events) if event.get("event") == "session_end"), None)
    generated = _now()
    wall_end = session_end or generated
    return {
        "schema_version": SCHEMA_VERSION,
        "session_id": session_id,
        "runtime_session_id": session_start.get("runtime_session_id", "unknown"),
        "started_at": session_start.get("wall_time", ""),
        "ended_at": session_end.get("wall_time", "") if session_end else "",
        "generated_at": generated["wall_time"],
        "session_wall_duration_ms": round(
            max(0.0, float(wall_end["wall_time_epoch_ms"]) - float(session_start.get("wall_time_epoch_ms", wall_end["wall_time_epoch_ms"]))),
            3,
        ),
        "timing_log": log_path.name,
        "observer_event_count": len(events),
        "phases": phases,
        "activities": rounded_map(activity_totals),
        "subagents": {
            "unique_count": len(unique_agents),
            "spawn_count": len(spawns),
            "execution_count": len(executions),
            "wait_count": len(waits),
            "wait_duration_ms": round(
                sum(float(event.get("wall_duration_ms", event.get("duration_ms", 0.0))) for event in waits),
                3,
            ),
            "roles": rounded_map(roles),
            "assignments": [
                {
                    key: event.get(key, "")
                    for key in (
                        "agent_role",
                        "agent_id",
                        "requested_model",
                        "effective_model",
                        "requested_reasoning_effort",
                        "effective_reasoning_effort",
                        "fallback_reason",
                    )
                }
                for event in spawns
            ],
        },
        "diagram_operations": {
            counter: sum(
                int(event.get(counter, 0))
                for event in completed
                if event.get("event") == "measurement" and event.get("activity") == "validation"
            )
            for counter in (
                "render_http_requests",
                "render_rounds",
                "package_validation_runs",
                "package_verifier_runs",
                "cache_hits",
            )
        },
        "final_validation_operations": final_validation_operations,
        "total_package_verifier_runs": (
            sum(
                int(event.get("package_verifier_runs", 0))
                for event in completed
                if event.get("event") == "measurement" and event.get("activity") == "validation"
            )
            + final_validation_operations["diagram_package_verifier_runs"]
        ),
        "coverage": {
            "complete": not missing_phases and not missing_activities and not missing_observations and not incomplete_spans,
            "missing_phases": missing_phases,
            "missing_activities": missing_activities,
            "missing_observations": missing_observations,
            "incomplete_spans": incomplete_spans,
        },
        "incomplete_spans": incomplete_spans,
        "observability_limits": [
            "skill timing 不包含宿主隐藏的模型排队、首 token、token 用量或隐藏 reasoning 时长",
            "活动允许重叠，关键路径以阶段墙钟和宿主 runtime session 为准",
            "每次 timing CLI 进程启动和 JSONL 写入的观测开销不计入被测 span",
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="开始一个新 timing session")
    init.add_argument("--log", required=True)
    init.add_argument("--label", default="patent-disclosure")
    init.add_argument("--runtime-session-id", default="")
    init.add_argument("--resume", action="store_true")

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
            item.add_argument("--result-json", default="")
            item.add_argument("argv", nargs=argparse.REMAINDER)

    end = sub.add_parser("end")
    end.add_argument("--log", required=True)
    end.add_argument("--span-id", default="")
    end.add_argument("--stage", default="")
    end.add_argument("--activity", choices=sorted(ACTIVITIES), default="")
    end.add_argument("--status", choices=("success", "failed", "blocked", "review_required"), default="success")

    record = sub.add_parser("record-subagent")
    record.add_argument("--log", required=True)
    record.add_argument("--agent-role", required=True)
    record.add_argument("--agent-id", required=True)
    record.add_argument("--model", required=True)
    record.add_argument("--effective-model", default="")
    record.add_argument("--effective-reasoning-effort", default="")
    record.add_argument("--fallback-reason", default="")
    record.add_argument("--reasoning-effort", required=True)

    ingest = sub.add_parser("ingest-diagram")
    ingest.add_argument("--log", required=True)
    ingest.add_argument("--stage", default="phase_3_final_drafting")
    ingest.add_argument("--label", required=True)
    ingest.add_argument("--validation", required=True)

    summary = sub.add_parser("summarize")
    summary.add_argument("--log", required=True)
    summary.add_argument("--output", default="")
    summary.add_argument("--require-complete", action="store_true")
    summary.add_argument("--close-session", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    log_path = Path(args.log)
    if args.command == "init":
        events = _read_events(log_path)
        if events:
            current_session_id, current = _current_session(events)
            active = not any(event.get("event") == "session_end" for event in current)
            if active:
                if args.resume:
                    print(f"session_id={current_session_id}")
                    print(f"timing_log={log_path}")
                    print("resumed=true")
                    return 0
                raise ValueError("已有未关闭 timing session；使用 init --resume 继续，或完成后 summarize --close-session")
        session_id = uuid.uuid4().hex
        event = _base_event(session_id, "session_start")
        event["label"] = args.label
        if args.runtime_session_id:
            event["runtime_session_id"] = args.runtime_session_id
        _append(log_path, event)
        print(f"session_id={session_id}")
        print(f"timing_log={log_path}")
        return 0
    if args.command == "start":
        print(_start_span(args))
        return 0
    if args.command == "end":
        span_id = _resolve_open_span(log_path, args.span_id, args.stage, args.activity)
        _end_span(log_path, span_id, args.status)
        return 0
    if args.command == "record-subagent":
        session_id, _ = _active_session(_read_events(log_path))
        event = _base_event(session_id, "subagent_spawn")
        effective_model = args.effective_model or "unknown"
        effective_reasoning_effort = args.effective_reasoning_effort or "unknown"
        fallback_reason = args.fallback_reason
        if effective_model == "unknown" and not fallback_reason:
            fallback_reason = "runtime_not_reported"
        event.update(
            {
                "agent_role": args.agent_role,
                "agent_id": args.agent_id,
                "model": effective_model,
                "requested_model": args.model,
                "effective_model": effective_model,
                "requested_reasoning_effort": args.reasoning_effort,
                "effective_reasoning_effort": effective_reasoning_effort,
                "fallback_reason": fallback_reason,
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
        if completed.returncode == 0:
            status = "success"
        elif completed.returncode == 2:
            status = "review_required"
        else:
            status = "failed"
        operation_counts: dict[str, int] = {}
        if args.result_json:
            try:
                operation_counts = _disclosure_validation_operations(Path(args.result_json))
            except ValueError:
                _end_span(log_path, span_id, "failed", completed.returncode, observation_error="result_json_invalid")
                raise
        _end_span(log_path, span_id, status, completed.returncode, **operation_counts)
        return completed.returncode
    if args.command == "ingest-diagram":
        data = json.loads(Path(args.validation).read_text(encoding="utf-8"))
        timings, counters = _diagram_observation(data)
        cache_hit = timings["cache_hit"]
        source = f"{args.label}/validation.json"
        _measurement(
            log_path,
            args.stage,
            "render",
            args.label,
            float(timings["render_ms"]),
            source=source,
            cache_hit=cache_hit,
        )
        _measurement(
            log_path,
            args.stage,
            "validation",
            args.label,
            float(timings["static_validation_ms"]),
            source=source,
            cache_hit=cache_hit,
            **counters,
        )
        return 0
    if args.command == "summarize":
        summary = _summarize(log_path)
        complete = bool(summary.get("coverage", {}).get("complete"))
        if args.close_session and complete:
            session_id, current = _current_session(_read_events(log_path))
            if not any(event.get("event") == "session_end" for event in current):
                _append(log_path, _base_event(session_id, "session_end"))
            summary = _summarize(log_path)
        payload = json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(payload, encoding="utf-8")
        else:
            print(payload, end="")
        if (args.close_session or args.require_complete) and not complete:
            return 1
        return 0
    raise AssertionError(args.command)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, AssertionError, json.JSONDecodeError) as exc:
        print(f"timing error: {exc}", file=sys.stderr)
        raise SystemExit(2)
