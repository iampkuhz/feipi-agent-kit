#!/usr/bin/env bash
# Launch script for session-browser.
# Usage:
#   ./scripts/session-browser.sh scan    # Scan and index sessions
#   ./scripts/session-browser.sh serve   # Start web server

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# SRC_DIR is one level up from scripts (session-browser/src)
SRC_DIR="$(cd "$SCRIPT_DIR/../src" && pwd)"

export PYTHONPATH="$SRC_DIR:${PYTHONPATH:-}"

CMD="${1:-help}"
shift || true

case "$CMD" in
    scan)
        exec python3 -m session_browser scan "$@"
        ;;
    serve)
        exec python3 -m session_browser serve --allow-empty "$@"
        ;;
    stop)
        exec python3 -m session_browser stop "$@"
        ;;
    *)
        echo "Usage: $0 {scan|serve|stop} [options]"
        echo ""
        echo "Commands:"
        echo "  scan                          Full scan: drop DB and re-scan all sessions"
        echo "  scan --incremental            Incremental scan: only re-parse changed .jsonl files"
        echo "  scan --agent <name>           Scan only a specific agent (claude_code or codex)"
        echo "  serve                         Start local web server (with background incremental scanner)"
        echo "  serve --no-scan               Start server without background scanner"
        echo "  stop                          Stop the running web server"
        echo ""
        echo "Background scanner tiers:"
        echo "  Hot  (<30min ended_at):  scanned every 30s"
        echo "  Warm (<24h ended_at):   scanned every 5min"
        echo "  Cold (>24h):            only scanned by 'scan' (full rescan)"
        echo ""
        echo "Examples:"
        echo "  $0 scan"
        echo "  $0 scan --incremental"
        echo "  $0 scan --agent codex"
        echo "  $0 scan --agent claude_code"
        echo "  $0 serve --port 8899"
        echo "  $0 stop"
        ;;
esac
