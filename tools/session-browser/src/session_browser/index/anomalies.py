"""Anomaly detection engine for session-browser.

Detects session-level anomalies using percentile-based thresholds with fallbacks.
Each anomaly output contains: type, severity, label, reason.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from session_browser.index.percentiles import compute_session_thresholds, FALLBACK_THRESHOLDS


# ─── Anomaly types ────────────────────────────────────────────────────────

class AnomalyType:
    LONG_DURATION = "long_duration"
    TOOL_SPIKE = "tool_spike"
    CONTEXT_BLOAT = "context_bloat"
    LOW_CACHE_REUSE = "low_cache_reuse"
    CACHE_WRITE_SPIKE = "cache_write_spike"
    LOW_OUTPUT_RATIO = "low_output_ratio"
    FAILED_RUN = "failed_run"
    PARSE_PARTIAL = "parse_partial"
    POSSIBLE_IDLE = "possible_idle"
    HIGH_TOKENS_PER_ROUND = "high_tokens_per_round"


SEVERITY_CRITICAL = "critical"
SEVERITY_WARNING = "warning"
SEVERITY_INFO = "info"


@dataclass
class Anomaly:
    """A single anomaly detected for a session."""
    type: str
    severity: str  # "critical", "warning", "info"
    label: str  # Short display label (e.g., "Long Duration")
    reason: str  # Human-readable explanation

    @property
    def badge_class(self) -> str:
        if self.severity == SEVERITY_CRITICAL:
            return "badge-anomaly-critical"
        elif self.severity == SEVERITY_WARNING:
            return "badge-anomaly-warning"
        return "badge-anomaly-info"


@dataclass
class SessionAnomalies:
    """All anomalies for a single session."""
    session_key: str
    anomalies: list[Anomaly] = field(default_factory=list)

    @property
    def max_severity(self) -> str:
        if any(a.severity == SEVERITY_CRITICAL for a in self.anomalies):
            return SEVERITY_CRITICAL
        if any(a.severity == SEVERITY_WARNING for a in self.anomalies):
            return SEVERITY_WARNING
        return SEVERITY_INFO

    @property
    def main_reason(self) -> str:
        """Return the reason of the highest-severity anomaly."""
        if not self.anomalies:
            return ""
        ordered = sorted(
            self.anomalies,
            key=lambda a: (0 if a.severity == SEVERITY_CRITICAL else 1 if a.severity == SEVERITY_WARNING else 2),
        )
        return ordered[0].reason

    @property
    def display_count(self) -> int:
        return len(self.anomalies)


def safe_divide(a: Optional[float], b: Optional[float], default: Optional[float] = None) -> Optional[float]:
    """Safe division returning default when b is 0 or None."""
    if b is None or b == 0:
        return default
    if a is None:
        return default
    return a / b


def detect_session_anomalies(
    session: dict,
    thresholds: Optional[dict] = None,
) -> SessionAnomalies:
    """Detect anomalies for a single session.

    Args:
        session: Dict with session fields (from DB row or enriched dict).
        thresholds: Pre-computed thresholds. If None, uses fallback.

    Returns:
        SessionAnomalies with detected anomalies.
    """
    anomalies: list[Anomaly] = []
    session_key = session.get("session_key", "")

    duration = session.get("duration_seconds", 0) or 0
    tools = session.get("tool_call_count", 0) or 0
    failed = session.get("failed_tool_count", 0) or 0
    input_tokens = session.get("input_tokens", 0) or 0
    output_tokens = session.get("output_tokens", 0) or 0
    cache_read = session.get("cached_input_tokens", 0) or 0
    cache_write = session.get("cached_output_tokens", 0) or 0
    rounds = session.get("assistant_message_count", 0) or 0
    title = session.get("title", "")

    total_input = input_tokens + cache_read + cache_write
    input_side_total = total_input

    # ─── Failed run (always critical) ───
    if failed > 0:
        anomalies.append(Anomaly(
            type=AnomalyType.FAILED_RUN,
            severity=SEVERITY_CRITICAL,
            label="Failed Tools",
            reason=f"{failed} failed tool call(s)",
        ))

    # ─── Long duration ───
    if duration > 0:
        if thresholds and "duration_seconds" in thresholds:
            warn = thresholds["duration_seconds"]["warning"]
            crit = thresholds["duration_seconds"]["critical"]
        else:
            fb = FALLBACK_THRESHOLDS["duration_seconds"]
            warn = fb["warning"]
            crit = fb["critical"]

        if duration >= crit:
            hours = duration / 3600
            anomalies.append(Anomaly(
                type=AnomalyType.LONG_DURATION,
                severity=SEVERITY_CRITICAL,
                label="Long Duration",
                reason=f"Duration {hours:.1f}h exceeds critical threshold ({crit/3600:.1f}h)",
            ))
        elif duration >= warn:
            hours = duration / 3600
            anomalies.append(Anomaly(
                type=AnomalyType.LONG_DURATION,
                severity=SEVERITY_WARNING,
                label="Long Duration",
                reason=f"Duration {hours:.1f}h exceeds warning threshold ({warn/3600:.1f}h)",
            ))

    # ─── Tool spike ───
    if tools > 0:
        if thresholds and "tool_call_count" in thresholds:
            warn = thresholds["tool_call_count"]["warning"]
            crit = thresholds["tool_call_count"]["critical"]
        else:
            fb = FALLBACK_THRESHOLDS["tool_call_count"]
            warn = fb["warning"]
            crit = fb["critical"]

        if tools >= crit:
            anomalies.append(Anomaly(
                type=AnomalyType.TOOL_SPIKE,
                severity=SEVERITY_WARNING,
                label="High Tools",
                reason=f"{tools} tool calls exceeds critical threshold ({crit:.0f})",
            ))
        elif tools >= warn:
            anomalies.append(Anomaly(
                type=AnomalyType.TOOL_SPIKE,
                severity=SEVERITY_WARNING,
                label="High Tools",
                reason=f"{tools} tool calls exceeds warning threshold ({warn:.0f})",
            ))

    # ─── Low cache reuse ───
    if input_side_total > 0:
        cache_reuse_ratio = safe_divide(cache_read, input_side_total, 0)
        if cache_reuse_ratio < 0.1 and input_side_total > 10000:
            anomalies.append(Anomaly(
                type=AnomalyType.LOW_CACHE_REUSE,
                severity=SEVERITY_WARNING,
                label="Low Cache",
                reason=f"Cache reuse {cache_reuse_ratio*100:.1f}% (input-side {input_side_total:,})",
            ))

    # ─── Cache write spike ───
    if thresholds and "cached_output_tokens" in thresholds:
        warn = thresholds["cached_output_tokens"]["warning"]
        crit = thresholds["cached_output_tokens"]["critical"]
    else:
        fb = FALLBACK_THRESHOLDS["cached_output_tokens"]
        warn = fb["warning"]
        crit = fb["critical"]

    if cache_write >= crit:
        anomalies.append(Anomaly(
            type=AnomalyType.CACHE_WRITE_SPIKE,
            severity=SEVERITY_WARNING,
            label="Cache Write",
            reason=f"Cache write {cache_write:,} exceeds critical ({crit:,})",
        ))
    elif cache_write >= warn:
        anomalies.append(Anomaly(
            type=AnomalyType.CACHE_WRITE_SPIKE,
            severity=SEVERITY_INFO,
            label="Cache Write",
            reason=f"Cache write {cache_write:,} exceeds warning ({warn:,})",
        ))

    # ─── Low output ratio ───
    if input_side_total > 0 and output_tokens is not None:
        output_ratio = safe_divide(output_tokens, input_side_total, 0)
        if output_ratio < 0.05 and input_side_total > 10000:
            anomalies.append(Anomaly(
                type=AnomalyType.LOW_OUTPUT_RATIO,
                severity=SEVERITY_WARNING,
                label="Low Output",
                reason=f"Output ratio {output_ratio*100:.1f}% (very low for input size)",
            ))

    # ─── High tokens per round ───
    if rounds > 0:
        tokens_per_round = safe_divide(input_side_total + output_tokens, rounds, 0)
        if thresholds and "tokens_per_round" in thresholds:
            warn = thresholds["tokens_per_round"]["warning"]
            crit = thresholds["tokens_per_round"]["critical"]
        else:
            fb = FALLBACK_THRESHOLDS["tokens_per_round"]
            warn = fb["warning"]
            crit = fb["critical"]

        if tokens_per_round >= crit:
            anomalies.append(Anomaly(
                type=AnomalyType.HIGH_TOKENS_PER_ROUND,
                severity=SEVERITY_INFO,
                label="High Tokens/Round",
                reason=f"{tokens_per_round:,.0f} tokens/round exceeds critical ({crit:,.0f})",
            ))
        elif tokens_per_round >= warn:
            anomalies.append(Anomaly(
                type=AnomalyType.HIGH_TOKENS_PER_ROUND,
                severity=SEVERITY_INFO,
                label="High Tokens/Round",
                reason=f"{tokens_per_round:,.0f} tokens/round exceeds warning ({warn:,.0f})",
            ))

    # ─── Context bloat: high input-side relative to output ───
    if output_tokens > 0 and input_side_total > 0:
        context_ratio = safe_divide(input_side_total, output_tokens, 0)
        if context_ratio > 50 and input_side_total > 100000:
            anomalies.append(Anomaly(
                type=AnomalyType.CONTEXT_BLOAT,
                severity=SEVERITY_WARNING,
                label="Context Bloat",
                reason=f"Input/output ratio {context_ratio:.0f}x (context much larger than output)",
            ))

    return SessionAnomalies(session_key=session_key, anomalies=anomalies)


def detect_all_anomalies(
    sessions_data: list[dict],
) -> dict[str, SessionAnomalies]:
    """Detect anomalies for all sessions.

    Args:
        sessions_data: List of session dicts.

    Returns:
        Dict of {session_key: SessionAnomalies}.
    """
    thresholds = compute_session_thresholds(sessions_data)

    result = {}
    for s in sessions_data:
        key = s.get("session_key", "")
        result[key] = detect_session_anomalies(s, thresholds)

    return result


def get_needs_attention(
    anomalies_map: dict[str, SessionAnomalies],
    sessions_lookup: dict[str, dict],
    limit: int = 8,
    filter_type: str = "all",
) -> list[dict]:
    """Get top sessions needing attention.

    Args:
        anomalies_map: {session_key: SessionAnomalies}
        sessions_lookup: {session_key: session_dict}
        limit: Max items to return.
        filter_type: "all", "critical", "long_duration", "high_tools", "low_cache", "failed".

    Returns:
        List of dicts with session info + anomaly details, sorted by severity.
    """
    items = []
    for key, sa in anomalies_map.items():
        if not sa.anomalies:
            continue

        # Apply filter
        if filter_type == "critical" and sa.max_severity != SEVERITY_CRITICAL:
            continue
        if filter_type == "long_duration" and not any(a.type == AnomalyType.LONG_DURATION for a in sa.anomalies):
            continue
        if filter_type == "high_tools" and not any(a.type == AnomalyType.TOOL_SPIKE for a in sa.anomalies):
            continue
        if filter_type == "low_cache" and not any(a.type == AnomalyType.LOW_CACHE_REUSE for a in sa.anomalies):
            continue
        if filter_type == "failed" and not any(a.type == AnomalyType.FAILED_RUN for a in sa.anomalies):
            continue

        session = sessions_lookup.get(key, {})
        items.append({
            "session_key": key,
            "session_id": session.get("session_id", ""),
            "agent": session.get("agent", ""),
            "title": session.get("title", "Untitled"),
            "project_name": session.get("project_name", ""),
            "project_key": session.get("project_key", ""),
            "model": session.get("model", ""),
            "ended_at": session.get("ended_at", ""),
            "max_severity": sa.max_severity,
            "main_reason": sa.main_reason,
            "anomaly_count": sa.display_count,
            "anomaly_types": [a.type for a in sa.anomalies],
            "anomaly_labels": [a.label for a in sa.anomalies],
            "anomaly_badge_classes": [a.badge_class for a in sa.anomalies],
        })

    # Sort: critical first, then by anomaly count
    severity_order = {SEVERITY_CRITICAL: 0, SEVERITY_WARNING: 1, SEVERITY_INFO: 2}
    items.sort(key=lambda x: (severity_order.get(x["max_severity"], 3), -x["anomaly_count"]))

    return items[:limit]


def enrich_sessions_with_anomalies(
    sessions: list,
    anomalies_map: dict[str, SessionAnomalies],
) -> list[dict]:
    """Add anomaly info to a list of SessionSummary objects.

    Returns list of dicts with anomaly fields appended.
    """
    result = []
    for s in sessions:
        key = s.session_key if hasattr(s, "session_key") else s.get("session_key", "")
        sa = anomalies_map.get(key)
        d = s.to_dict() if hasattr(s, "to_dict") else dict(s)

        if sa and sa.anomalies:
            d["anomalies"] = [
                {
                    "type": a.type,
                    "severity": a.severity,
                    "label": a.label,
                    "reason": a.reason,
                    "badge_class": a.badge_class,
                }
                for a in sa.anomalies
            ]
            d["max_severity"] = sa.max_severity
            d["main_reason"] = sa.main_reason
        else:
            d["anomalies"] = []
            d["max_severity"] = None
            d["main_reason"] = None

        result.append(d)
    return result
