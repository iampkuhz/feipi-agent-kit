"""HTTP server and routes for session-browser.

Uses Python's built-in http.server + jinja2 templates.
No external web framework needed for MVP.
"""

from __future__ import annotations

import json
import os
import subprocess
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

import jinja2
from markdown_it import MarkdownIt

from session_browser.index.indexer import (
    _get_connection,
    get_dashboard_stats,
    list_sessions,
    count_sessions,
    list_projects,
    get_project_stats,
    get_session,
    get_trend_data,
    list_agents,
)
from session_browser.index.metrics import (
    get_token_breakdown,
    get_model_distribution,
    get_agent_distribution,
    compute_derived_metrics,
    compute_aggregate_metrics,
    compute_agent_efficiency,
)
from session_browser.index.anomalies import (
    detect_all_anomalies,
    get_needs_attention,
    enrich_sessions_with_anomalies,
    AnomalyType,
)
from session_browser.domain.models import (
    ChatMessage,
    ConversationRound,
    LLMCall,
    ToolCall,
)

# Template directory
_TEMPLATE_DIR = Path(__file__).parent / "templates"

_template_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=True,
)


def _get_repo_root(cwd: str | None = None) -> str | None:
    """Detect git repo root from cwd. Returns None if not in a git repo."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=cwd or os.getcwd(),
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None

# Cache the repo root at server startup
_REPO_ROOT = _get_repo_root()

# Markdown renderer (shared instance)
_md = MarkdownIt().enable("table")


def _md_filter(text: str) -> str:
    """Render markdown to HTML."""
    if not text:
        return ""
    return _md.render(text)


# Register template filters
_template_env.filters["format_number"] = lambda n: (
    f"{n / 1_000_000:.1f}M" if n >= 1_000_000
    else f"{n / 1_000:.1f}K" if n >= 1_000
    else str(n)
)
_template_env.globals["max"] = max
_template_env.filters["truncate_path"] = lambda path: (
    _truncate_path(path)
)
_template_env.filters["relative_to_repo"] = lambda path: (
    _relative_to_repo(path)
)
_template_env.filters["format_duration"] = lambda seconds: (
    f"{int(seconds // 3600)}h {int((seconds % 3600) // 60)}min" if seconds >= 3600
    else f"{int(seconds // 60)}min {int(seconds % 60)}s" if seconds >= 60
    else f"{int(seconds)}s"
)
_template_env.filters["relative_time"] = lambda iso_str: (
    _relative_time(iso_str)
)
_template_env.filters["urlencode"] = urllib.parse.quote
_template_env.filters["urldecode"] = urllib.parse.unquote
_template_env.filters["markdown"] = _md_filter
_template_env.filters["tojson_safe"] = lambda v: json.dumps(v) if v else "null"


def _truncate_path(path: str) -> str:
    """Truncate a long path, keeping first and last segments."""
    if not path or len(path) <= 40:
        return path or ""
    parts = path.replace("\\", "/").split("/")
    if len(parts) <= 3:
        return path[:40] + "…"
    # Keep first 2 and last 2 segments
    return "/".join(parts[:2]) + "/…/" + "/".join(parts[-2:])


def _relative_to_repo(path: str) -> str:
    """If path is within the git repo, return relative path. Otherwise return absolute path."""
    if not path or not _REPO_ROOT:
        return path or ""
    try:
        abs_path = os.path.abspath(path)
        if abs_path.startswith(_REPO_ROOT + os.sep) or abs_path == _REPO_ROOT:
            return os.path.relpath(abs_path, _REPO_ROOT)
    except Exception:
        pass
    return path


def _relative_time(iso_str: str) -> str:
    """Convert ISO8601 to relative time string."""
    if not iso_str:
        return ""
    from datetime import datetime, timezone
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        delta = now - dt
        days = delta.days
        if days > 30:
            return f"{days // 30}mo ago"
        if days > 0:
            return f"{days}d ago"
        hours = delta.seconds // 3600
        if hours > 0:
            return f"{hours}h ago"
        minutes = delta.seconds // 60
        return f"{minutes}m ago"
    except (ValueError, TypeError):
        return iso_str[:16]


def _build_rounds(
    messages: list[ChatMessage],
    tool_calls: list[ToolCall],
    session_input_tokens: int,
    session_output_tokens: int,
    session_cached_tokens: int,
    session_cache_write_tokens: int,
    agent: str,
) -> list[ConversationRound]:
    """Group messages into conversation rounds and compute token ratios.

    Each assistant LLM response becomes its own round. Consecutive user
    messages before an assistant response are merged; assistant responses that
    happen during tool loops get an empty user_msg so repeated tool iterations
    stay visible instead of collapsing into one giant round.

    Token ratio is derived from the assistant message's usage data (Claude)
    or distributed evenly (Codex).
    """
    if not messages:
        return []

    total_session_tokens = session_input_tokens + session_output_tokens + session_cached_tokens + session_cache_write_tokens

    # Step 1: Render markdown and pair each assistant LLM response into its
    # own round. Tool-result pseudo-user messages are filtered in sources, so
    # consecutive assistant responses are expected during tool loops.
    pending_users: list[ChatMessage] = []
    rounds: list[ConversationRound] = []
    for msg in messages:
        msg.content_html = _md_filter(msg.content)

        if msg.role == "user":
            pending_users.append(msg)
            continue

        if msg.role == "assistant":
            if pending_users:
                merged_user = _merge_messages(pending_users)
                pending_users = []
            else:
                merged_user = ChatMessage(role="user", content="", timestamp=msg.timestamp)
            rounds.append(
                _make_round(merged_user, msg, tool_calls,
                            total_session_tokens, agent, session_cache_write_tokens)
            )

    if pending_users:
        rounds.append(
            _make_round(
                _merge_messages(pending_users),
                ChatMessage(role="assistant", content="", timestamp=""),
                tool_calls,
                total_session_tokens,
                agent,
                session_cache_write_tokens,
            )
        )

    return rounds


def _merge_messages(msgs: list[ChatMessage]) -> ChatMessage:
    """Merge a list of same-role messages into one ChatMessage."""
    if len(msgs) == 1:
        return msgs[0]

    content = "\n\n".join(m.content for m in msgs if m.content)
    content_html = "\n\n".join(m.content_html for m in msgs if m.content_html)
    # Use the latest timestamp
    timestamp = msgs[-1].timestamp
    # Merge tool_calls from all messages
    all_tool_calls = []
    for m in msgs:
        all_tool_calls.extend(m.tool_calls)
    # Merge usage (take the last non-None)
    usage = None
    for m in msgs:
        if m.usage:
            usage = m.usage

    return ChatMessage(
        role=msgs[0].role,
        content=content,
        timestamp=timestamp,
        model=msgs[-1].model,
        tool_calls=all_tool_calls,
        usage=usage,
        content_html=content_html,
        llm_call_id=msgs[-1].llm_call_id,
        llm_status=msgs[-1].llm_status,
    )


def _make_round(
    user_msg: ChatMessage,
    assistant_msg: ChatMessage,
    all_tool_calls: list[ToolCall],
    total_session_tokens: int,
    agent: str,
    session_cache_write_tokens: int = 0,
) -> ConversationRound:
    """Create a ConversationRound with token calculation and tool call matching."""
    # Match tool calls from assistant message
    round_tool_calls = []
    if assistant_msg.tool_calls:
        matched_ids = {
            mt.get("id")
            for mt in assistant_msg.tool_calls
            if mt.get("id")
        }
        for tc in all_tool_calls:
            if tc.tool_use_id and tc.tool_use_id in matched_ids:
                round_tool_calls.append(tc)

    # Token info (Claude only)
    round_input = 0
    round_output = 0
    round_cached = 0
    round_cache_write = 0
    if agent == "claude_code" and assistant_msg.usage:
        round_input = assistant_msg.usage.get("input_tokens", 0)
        round_output = assistant_msg.usage.get("output_tokens", 0)
        round_cached = assistant_msg.usage.get("cache_read_input_tokens", 0)
        round_cache_write = assistant_msg.usage.get("cache_creation_input_tokens", 0)

    round_total = round_input + round_output + round_cached + round_cache_write
    token_ratio = round_total / total_session_tokens if total_session_tokens > 0 else 0
    direct_llm_calls = 1 if assistant_msg.llm_call_id else 0
    nested_llm_calls = sum(tc.llm_call_count for tc in round_tool_calls)
    nested_llm_errors = sum(tc.llm_error_count for tc in round_tool_calls)

    return ConversationRound(
        user_msg=user_msg,
        assistant_msg=assistant_msg,
        tool_calls=round_tool_calls,
        total_tokens=round_total,
        token_ratio=token_ratio,
        llm_call_count=direct_llm_calls + nested_llm_calls,
        llm_error_count=nested_llm_errors,
    )


def _derive_prompt_preview(
    msg: ChatMessage,
    round_tool_calls: list[ToolCall],
    prev_call_tools: list[ToolCall],
    round: ConversationRound,
    messages: list[ChatMessage],
    call_index_in_round: int,
) -> str:
    """Derive a human-readable hint for what was sent as prompt to this LLM call.

    Returns a short string (≤120 chars) summarising the prompt context.
    """
    # First call in round → show user message
    if call_index_in_round == 0:
        user_text = round.user_msg.content[:80] if round.user_msg.content else ""
        if user_text:
            return f"User: {user_text}"

    # Subsequent calls → tool results from prior call(s)
    if prev_call_tools:
        tool_names = ", ".join(tc.name for tc in prev_call_tools[:3])
        suffix = f" +{len(prev_call_tools) - 3}" if len(prev_call_tools) > 3 else ""
        return f"{len(prev_call_tools)} tool results: {tool_names}{suffix}"

    return ""


def _build_llm_calls(
    messages: list[ChatMessage],
    tool_calls: list[ToolCall],
    rounds: list[ConversationRound],
    subagent_runs: list[dict],
) -> list[LLMCall]:
    """Extract individual LLMCall objects (one per LLM turn).

    Main agent: one call per assistant message.
    Subagent: one call per internal turn (so the LLM Calls tab shows all).
    """
    llm_calls: list[LLMCall] = []

    # Map assistant llm_call_id -> round_index
    call_id_to_round: dict[str, int] = {}
    for r_idx, r in enumerate(rounds):
        if r.assistant_msg.llm_call_id:
            call_id_to_round[r.assistant_msg.llm_call_id] = r_idx

    # Main agent calls — track prior call's tools for prompt context
    main_calls_in_round: dict[int, list[LLMCall]] = {}
    for msg in messages:
        if msg.role != "assistant" or not msg.llm_call_id:
            continue
        r_idx = call_id_to_round.get(msg.llm_call_id, 0)
        usage = msg.usage or {}
        round_tools = rounds[r_idx].tool_calls if r_idx < len(rounds) else []
        round_obj = rounds[r_idx] if r_idx < len(rounds) else None

        prior_tools: list[ToolCall] = []
        call_index = 0
        if r_idx in main_calls_in_round and main_calls_in_round[r_idx]:
            prior_call = main_calls_in_round[r_idx][-1]
            prior_tools = prior_call.tool_calls
            call_index = len(main_calls_in_round[r_idx])

        prompt_hint = ""
        if round_obj:
            prompt_hint = _derive_prompt_preview(
                msg, round_tools, prior_tools, round_obj, messages, call_index
            )

        llm_call = LLMCall(
            id=msg.llm_call_id,
            model=msg.model,
            scope="main",
            subagent_id="",
            round_index=r_idx,
            parent_id="",
            parent_tool_name="",
            timestamp=msg.timestamp,
            status=msg.llm_status,
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            cache_read_tokens=usage.get("cache_read_input_tokens", 0),
            cache_write_tokens=usage.get("cache_creation_input_tokens", 0),
            prompt_preview=prompt_hint,
            response_preview=msg.content[:200],
            response_full=msg.content,
            tool_calls=[tc for tc in round_tools if tc.scope == "main"],
            tool_call_count=len([tc for tc in round_tools if tc.scope == "main"]),
            failed_tool_count=sum(1 for tc in round_tools if tc.scope == "main" and tc.is_failed),
        )
        main_calls_in_round.setdefault(r_idx, []).append(llm_call)
        llm_calls.append(llm_call)

    # Subagent individual calls — one per internal LLM turn
    for run in subagent_runs:
        summary = run["summary"]
        agent_id = summary["agent_id"]

        parent_tc = None
        for tc in tool_calls:
            if tc.name == "Agent" and tc.subagent_summary.get("agent_id") == agent_id:
                parent_tc = tc
                break

        parent_round = 0
        if parent_tc:
            for r_idx, r in enumerate(rounds):
                if any(tc.tool_use_id == parent_tc.tool_use_id for tc in r.tool_calls):
                    parent_round = r_idx
                    break

        for msg in run["messages"]:
            if msg.role != "assistant" or not msg.llm_call_id:
                continue
            usage = msg.usage or {}

            llm_calls.append(LLMCall(
                id=msg.llm_call_id,
                model=msg.model,
                scope="subagent",
                subagent_id=agent_id,
                round_index=parent_round,
                parent_id=parent_tc.tool_use_id if parent_tc else "",
                parent_tool_name=parent_tc.name if parent_tc else "Agent",
                timestamp=msg.timestamp,
                status="ok",
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
                cache_read_tokens=usage.get("cache_read_input_tokens", 0),
                cache_write_tokens=usage.get("cache_creation_input_tokens", 0),
                prompt_preview=f"Subagent turn ({msg.content[:80]})" if msg.content else "Subagent turn",
                response_preview=msg.content[:200],
                response_full=msg.content,
                tool_calls=[],
                tool_call_count=0,
                failed_tool_count=0,
            ))

    return llm_calls


def _build_subagent_interactions(
    llm_calls: list[LLMCall],
    subagent_runs: list[dict],
    tool_calls: list[ToolCall],
) -> list[LLMCall]:
    """Build one aggregated interaction per subagent run (for rounds view).

    Each subagent run becomes a single interaction that aggregates all its
    internal LLM calls and tools, so the round expand shows it as one nested
    block instead of repeating 260 times.
    """
    interactions: list[LLMCall] = []
    for run in subagent_runs:
        summary = run["summary"]
        agent_id = summary["agent_id"]

        parent_tc = None
        for tc in tool_calls:
            if tc.name == "Agent" and tc.subagent_summary.get("agent_id") == agent_id:
                parent_tc = tc
                break

        # Find individual subagent calls for this run
        sub_calls = [c for c in llm_calls if c.scope == "subagent" and c.subagent_id == agent_id]
        if not sub_calls:
            continue

        parent_round = sub_calls[0].round_index
        total_input = sum(c.input_tokens for c in sub_calls)
        total_output = sum(c.output_tokens for c in sub_calls)
        total_cr = sum(c.cache_read_tokens for c in sub_calls)
        total_cw = sum(c.cache_write_tokens for c in sub_calls)

        response = ""
        for c in reversed(sub_calls):
            if c.response_full:
                response = c.response_full
                break

        sub_tools = [tc for tc in tool_calls if tc.subagent_id == agent_id]

        interactions.append(LLMCall(
            id=f"subagent-{agent_id}",
            model=sub_calls[0].model if sub_calls else "",
            scope="subagent",
            subagent_id=agent_id,
            round_index=parent_round,
            parent_id=parent_tc.tool_use_id if parent_tc else "",
            parent_tool_name=parent_tc.name if parent_tc else "Agent",
            timestamp=sub_calls[0].timestamp,
            status="ok",
            input_tokens=total_input,
            output_tokens=total_output,
            cache_read_tokens=total_cr,
            cache_write_tokens=total_cw,
            prompt_preview="",
            response_preview=response[:200],
            response_full=response,
            tool_calls=sub_tools,
            tool_call_count=len(sub_tools),
            failed_tool_count=sum(1 for t in sub_tools if t.is_failed),
        ))

    return interactions


def _assign_interactions_to_rounds(
    rounds: list[ConversationRound],
    llm_calls: list[LLMCall],
    tool_calls: list[ToolCall],
    subagent_runs: list[dict],
) -> None:
    """Populate round.interactions.

    Main agent: individual calls stay as individual interactions.
    Subagent: replaced by one aggregated interaction per run (so round expand
    shows it as a single nested block, not repeated for every internal turn).
    """
    # Group main-agent calls by round
    main_by_round: dict[int, list[LLMCall]] = {}
    for call in llm_calls:
        if call.scope == "main":
            main_by_round.setdefault(call.round_index, []).append(call)

    # Build aggregated subagent interactions
    subagent_interactions = _build_subagent_interactions(llm_calls, subagent_runs, tool_calls)
    sub_by_round: dict[int, list[LLMCall]] = {}
    for ix in subagent_interactions:
        sub_by_round.setdefault(ix.round_index, []).append(ix)

    for r_idx, r in enumerate(rounds):
        main_calls = main_by_round.get(r_idx, [])
        sub_calls = sub_by_round.get(r_idx, [])
        # Main calls first, then subagent interactions
        r.interactions = main_calls + sub_calls


class SessionBrowserHandler(BaseHTTPRequestHandler):
    """HTTP request handler for session-browser."""

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        params = urllib.parse.parse_qs(parsed.query)

        try:
            if path == "/" or path == "/dashboard":
                self._serve_dashboard()
            elif path == "/projects":
                self._serve_projects()
            elif path.startswith("/projects/"):
                project_key = urllib.parse.unquote(path[len("/projects/"):])
                self._serve_project(project_key)
            elif path == "/sessions":
                self._serve_all_sessions()
            elif path.startswith("/sessions/"):
                parts = path[len("/sessions/"):].split("/", 1)
                if len(parts) == 2:
                    agent, session_id = parts
                    self._serve_session(agent, session_id)
                else:
                    self._serve_all_sessions()
            elif path == "/agents":
                self._serve_agents()
            elif path.startswith("/agents/"):
                agent = urllib.parse.unquote(path[len("/agents/"):])
                self._serve_agent(agent)
            elif path == "/glossary":
                self._serve_glossary()
            elif path.startswith("/static/"):
                self._serve_static(path[len("/static/"):])
            else:
                self._send_404()
        except Exception as e:
            self._send_500(str(e))

    def _render_template(self, name: str, **context) -> str:
        template = _template_env.get_template(name)
        return template.render(**context)

    def _send_html(self, html: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def _send_404(self) -> None:
        self._send_html(self._render_template("404.html"), 404)

    def _send_500(self, error: str) -> None:
        self._send_html(self._render_template("error.html", error=error), 500)

    def _serve_dashboard(self) -> None:
        conn = _get_connection()
        stats = get_dashboard_stats(conn)
        projects = list_projects(conn, limit=10)
        recent = list_sessions(conn, limit=20, order_by="ended_at")
        trend = get_trend_data(conn, days=30)
        model_dist = get_model_distribution(conn)
        agent_dist = get_agent_distribution(conn)
        token_breakdown = get_token_breakdown(conn)
        aggregate_metrics = compute_aggregate_metrics(conn)

        # Anomaly detection for all sessions
        all_sessions_raw = list_sessions(conn, limit=2000, order_by="ended_at")
        sessions_data = []
        sessions_lookup = {}
        for s in all_sessions_raw:
            d = compute_derived_metrics(s.to_dict())
            sessions_data.append(d)
            sessions_lookup[d["session_key"]] = d

        anomalies_map = detect_all_anomalies(sessions_data)
        needs_attention = get_needs_attention(anomalies_map, sessions_lookup, limit=8)

        # Enrich recent sessions with anomalies
        recent_enriched = enrich_sessions_with_anomalies(recent, anomalies_map)

        conn.close()

        html = self._render_template(
            "dashboard.html",
            stats=stats,
            projects=projects,
            recent=recent_enriched,
            trend=trend,
            model_dist=model_dist.distribution,
            agent_dist=agent_dist,
            tokens=token_breakdown,
            aggregate=aggregate_metrics,
            needs_attention=needs_attention,
            active_page="dashboard",
        )
        self._send_html(html)

    def _serve_projects(self) -> None:
        conn = _get_connection()
        projects = list_projects(conn, limit=100)
        conn.close()

        html = self._render_template(
            "projects.html",
            projects=projects,
            active_page="projects",
        )
        self._send_html(html)

    def _serve_project(self, project_key: str) -> None:
        conn = _get_connection()
        pstats = get_project_stats(conn, project_key)
        sessions = list_sessions(conn, project_key=project_key, limit=100)
        conn.close()

        html = self._render_template(
            "project.html",
            project=pstats,
            sessions=sessions,
            project_key=project_key,
            active_page="projects",
        )
        self._send_html(html)

    def _serve_session(self, agent: str, session_id: str) -> None:
        session_key = f"{agent}:{session_id}"
        conn = _get_connection()
        session = get_session(conn, session_key)
        conn.close()

        if session is None:
            self._send_404()
            return

        # Get raw conversation data from source
        if agent == "claude_code":
            from session_browser.sources.claude import parse_session_detail
            raw_summary, messages, tool_calls, subagent_runs = parse_session_detail(
                session.project_key, session_id
            )
        else:
            from session_browser.sources.codex import parse_session_detail
            raw_summary, messages, tool_calls, subagent_runs = parse_session_detail(session_id)

        # Use freshly parsed detail counts on the session page so newly added
        # diagnostics do not require a rescan before they become visible.
        if raw_summary is not None:
            session.user_message_count = raw_summary.user_message_count
            session.assistant_message_count = raw_summary.assistant_message_count
            session.tool_call_count = raw_summary.tool_call_count
            session.failed_tool_count = raw_summary.failed_tool_count
            session.input_tokens = raw_summary.input_tokens
            session.output_tokens = raw_summary.output_tokens
            session.cached_input_tokens = raw_summary.cached_input_tokens
            session.cached_output_tokens = raw_summary.cached_output_tokens
            session.duration_seconds = raw_summary.duration_seconds or session.duration_seconds

        # Build conversation rounds with token data and markdown rendering
        rounds = _build_rounds(
            messages,
            tool_calls,
            session.input_tokens,
            session.output_tokens,
            session.cached_input_tokens,
            session.cached_output_tokens,
            agent,
        )

        # Build LLM calls and assign interactions to rounds
        llm_calls = _build_llm_calls(messages, tool_calls, rounds, subagent_runs)
        _assign_interactions_to_rounds(rounds, llm_calls, tool_calls, subagent_runs)

        # Compute derived metrics
        session_data = compute_derived_metrics(session.to_dict())

        # Detect anomalies for this session
        from session_browser.index.anomalies import detect_session_anomalies
        sa = detect_session_anomalies(session_data)

        html = self._render_template(
            "session.html",
            session=session,
            session_data=session_data,
            rounds=rounds,
            tool_calls=tool_calls,
            llm_calls=llm_calls,
            current_agent=agent,
            session_anomalies=sa,
        )
        self._send_html(html)

    def _serve_agent(self, agent: str) -> None:
        conn = _get_connection()
        agents = list_agents(conn)
        sessions = list_sessions(conn, agent=agent, limit=100, order_by="ended_at")
        conn.close()

        agent_info = None
        for a in agents:
            if a["agent"] == agent:
                agent_info = a
                break

        html = self._render_template(
            "agent.html",
            agents=agents,
            agent_info=agent_info,
            sessions=sessions,
            current_agent=agent,
            active_page="agents",
        )
        self._send_html(html)

    def _serve_agents(self) -> None:
        conn = _get_connection()
        agents = list_agents(conn)
        efficiency = compute_agent_efficiency(conn)
        conn.close()

        html = self._render_template(
            "agents.html",
            agents=agents,
            efficiency=efficiency,
            current_agent="__all__",
            active_page="agents",
        )
        self._send_html(html)

    def _serve_static(self, filename: str) -> None:
        static_dir = Path(__file__).parent / "static"
        filepath = static_dir / filename
        if not filepath.exists():
            self._send_404()
            return

        content_type = "text/css" if filename.endswith(".css") else "application/javascript"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.end_headers()
        self.wfile.write(filepath.read_bytes())

    def _serve_all_sessions(self, sort_by: str = "ended_at") -> None:
        """Global sessions page — all sessions across all projects."""
        conn = _get_connection()
        sessions = list_sessions(conn, limit=200, order_by=sort_by)
        total_count = count_sessions(conn)

        # Get distinct models and projects for filters
        models = conn.execute(
            "SELECT DISTINCT model FROM sessions WHERE model != '' ORDER BY model"
        ).fetchall()
        projects = conn.execute(
            "SELECT DISTINCT project_key, project_name FROM sessions ORDER BY project_name"
        ).fetchall()

        # Anomaly detection for all sessions
        all_sessions_raw = list_sessions(conn, limit=2000, order_by="ended_at")
        sessions_data = []
        sessions_lookup = {}
        for s in all_sessions_raw:
            d = compute_derived_metrics(s.to_dict())
            sessions_data.append(d)
            sessions_lookup[d["session_key"]] = d

        anomalies_map = detect_all_anomalies(sessions_data)
        sessions_enriched = enrich_sessions_with_anomalies(sessions, anomalies_map)

        conn.close()

        model_list = [r["model"] for r in models]
        project_list = [(r["project_key"], r["project_name"]) for r in projects]

        html = self._render_template(
            "sessions.html",
            sessions=sessions_enriched,
            total_count=total_count,
            model_list=model_list,
            project_list=[p[0] for p in project_list],
            active_page="sessions",
        )
        self._send_html(html)

    def _serve_glossary(self) -> None:
        """Token glossary page."""
        html = self._render_template(
            "glossary.html",
            active_page="glossary",
        )
        self._send_html(html)

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        """Suppress default request logging."""
        pass


def create_server(
    host: str = "127.0.0.1",
    port: int = 8899,
) -> HTTPServer:
    """Create and return an HTTPServer instance."""
    server = HTTPServer((host, port), SessionBrowserHandler)
    server.allow_reuse_address = True
    return server
