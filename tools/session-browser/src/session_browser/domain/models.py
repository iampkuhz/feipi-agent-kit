"""Domain models for session-browser."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional
from datetime import datetime, timezone


# ─── Token types ───────────────────────────────────────────────────────────


class TokenPrecision:
    EXACT = "exact"
    PROVIDER_REPORTED = "provider-reported"
    ESTIMATED = "estimated"
    UNKNOWN = "unknown"


class TokenProvider:
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    CODEX = "codex"
    QWEN_ANTHROPIC_COMPATIBLE = "qwen-anthropic-compatible"
    UNKNOWN = "unknown"


@dataclass
class TokenBreakdown:
    """Per-round or per-session token usage breakdown.

    All fields are in tokens. Missing fields are None, not 0.
    """

    # Input-side
    input_fresh: Optional[int] = None
    input_cache_read: Optional[int] = None
    input_cache_write: Optional[int] = None

    # Output-side
    output_visible: Optional[int] = None
    output_reasoning: Optional[int] = None
    output_thinking: Optional[int] = None

    # Tool-related
    tool_definition_input: Optional[int] = None
    tool_call_output: Optional[int] = None
    tool_result_input: Optional[int] = None

    # Computed totals
    total_input: Optional[int] = None
    total_output: Optional[int] = None

    precision: str = TokenPrecision.UNKNOWN
    provider: Optional[str] = None
    raw_fields: dict = field(default_factory=dict)

    def compute_totals(self) -> None:
        """Compute total_input and total_output from breakdown fields."""
        # total_input = input_fresh + input_cache_read + input_cache_write
        input_parts = [
            self.input_fresh or 0,
            self.input_cache_read or 0,
            self.input_cache_write or 0,
        ]
        if any(p is not None for p in [self.input_fresh, self.input_cache_read, self.input_cache_write]):
            self.total_input = sum(input_parts)

        # total_output = output_visible + output_reasoning + output_thinking
        output_parts = [
            self.output_visible or 0,
            self.output_reasoning or 0,
            self.output_thinking or 0,
        ]
        if any(p is not None for p in [self.output_visible, self.output_reasoning, self.output_thinking]):
            self.total_output = sum(output_parts)


# ─── Session / Message / Tool models ──────────────────────────────────────


@dataclass
class SessionSummary:
    """Unified session index model for both Claude Code and Codex."""

    agent: str  # "claude_code" | "codex"
    session_id: str
    title: str
    project_key: str  # full normalized path
    project_name: str  # last path segment
    cwd: str
    started_at: str  # ISO8601
    ended_at: str  # ISO8601
    duration_seconds: float = 0
    model: str = ""
    git_branch: str = ""
    source: str = ""  # "cli" | "vscode" | ...
    user_message_count: int = 0
    assistant_message_count: int = 0
    tool_call_count: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0  # cache_read_input_tokens
    cached_output_tokens: int = 0  # cache_creation_input_tokens (write cache)
    has_sensitive_data: bool = True

    # New fields for token breakdown
    token_breakdown: Optional[TokenBreakdown] = None
    failed_tool_count: int = 0

    @property
    def session_key(self) -> str:
        return f"{self.agent}:{self.session_id}"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["session_key"] = self.session_key
        return d


@dataclass
class ChatMessage:
    """A single chat message (user or assistant) in a session."""

    role: str  # "user" | "assistant"
    content: str
    timestamp: str  # ISO8601
    model: str = ""
    tool_calls: list[dict] = field(default_factory=list)  # for assistant messages
    usage: Optional[dict] = None  # token usage for assistant messages
    content_html: str = ""  # pre-rendered markdown HTML
    token_ratio: float = 0  # proportion of session tokens used in this message
    token_breakdown: Optional[TokenBreakdown] = None  # per-message token breakdown
    llm_call_id: str = ""  # provider/Claude message id, one logical LLM call
    llm_status: str = "ok"  # "ok" | "error"


@dataclass
class ToolCall:
    """A tool invocation record."""

    name: str
    parameters: dict = field(default_factory=dict)
    result: str = ""
    status: str = "completed"  # "completed" | "error"
    duration_ms: float = 0
    timestamp: str = ""
    exit_code: Optional[int] = None
    error_message: str = ""
    files_touched: list[str] = field(default_factory=list)
    round_index: int = 0
    tool_use_id: str = ""
    scope: str = "main"  # "main" | "subagent"
    parent_tool_use_id: str = ""
    parent_tool_name: str = ""
    subagent_id: str = ""
    subagent_summary: dict = field(default_factory=dict)
    llm_call_count: int = 0
    llm_error_count: int = 0
    subagent_tool_call_count: int = 0
    subagent_failed_tool_count: int = 0

    @property
    def is_failed(self) -> bool:
        return self.status == "error" or (self.exit_code is not None and self.exit_code != 0)


@dataclass
class LLMCall:
    """One logical LLM API call (main agent or subagent)."""

    id: str                          # msg["id"] — the llm_call_id
    model: str                       # e.g. "qwen3.6-plus", "claude-sonnet-4-6"
    scope: str                       # "main" | "subagent"
    subagent_id: str                 # "" for main; agent_id for subagent
    round_index: int                 # 0-based round index
    parent_id: str                   # "" for main; parent Agent tool_use_id for subagent
    parent_tool_name: str            # "" for main; "Agent" for subagent
    timestamp: str                   # ISO8601
    status: str                      # "ok" | "error"
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    prompt_preview: str = ""         # first ~200 chars of prompt context
    response_preview: str = ""       # first ~200 chars of response
    response_full: str = ""          # full response text (for expand)
    tool_calls: list["ToolCall"] = field(default_factory=list)
    tool_call_count: int = 0
    failed_tool_count: int = 0


@dataclass
class ConversationRound:
    """One exchange: user message + assistant response + tool calls."""

    user_msg: ChatMessage
    assistant_msg: ChatMessage
    tool_calls: list[ToolCall] = field(default_factory=list)
    total_tokens: int = 0
    token_ratio: float = 0  # proportion of total session tokens
    round_index: int = 0
    llm_call_count: int = 0
    llm_error_count: int = 0
    interactions: list[LLMCall] = field(default_factory=list)

    @property
    def input_tokens(self) -> int:
        if self.assistant_msg.usage:
            return self.assistant_msg.usage.get("input_tokens", 0)
        return 0

    @property
    def output_tokens(self) -> int:
        if self.assistant_msg.usage:
            return self.assistant_msg.usage.get("output_tokens", 0)
        return 0

    @property
    def cached_tokens(self) -> int:
        if self.assistant_msg.usage:
            return self.assistant_msg.usage.get("cache_read_input_tokens", 0)
        return 0

    @property
    def cache_write_tokens(self) -> int:
        """cache_creation_input_tokens: tokens being written to cache this turn."""
        if self.assistant_msg.usage:
            return self.assistant_msg.usage.get("cache_creation_input_tokens", 0)
        return 0

    def token_breakdown(self) -> dict:
        """Return a dict of token categories for this round."""
        if not self.assistant_msg.usage:
            return {"input": 0, "cache_read": 0, "cache_write": 0, "output": 0}
        return {
            "input": self.assistant_msg.usage.get("input_tokens", 0),
            "cache_read": self.assistant_msg.usage.get("cache_read_input_tokens", 0),
            "cache_write": self.assistant_msg.usage.get("cache_creation_input_tokens", 0),
            "output": self.assistant_msg.usage.get("output_tokens", 0),
        }


@dataclass
class ProjectStats:
    """Aggregated statistics for a project."""

    project_key: str
    project_name: str
    total_sessions: int = 0
    claude_sessions: int = 0
    codex_sessions: int = 0
    first_seen: str = ""
    last_seen: str = ""
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cached_tokens: int = 0  # cache read
    total_cache_write_tokens: int = 0  # cache write
    total_tool_calls: int = 0
    total_user_messages: int = 0
    total_assistant_messages: int = 0
    total_failed_tools: int = 0
