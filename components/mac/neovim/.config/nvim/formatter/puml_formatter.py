#!/usr/bin/env python3
"""
puml_formatter.py — pragmatic formatter for .puml-like DSLs (v0.4)

Fix:
- For DOT/Graph-like files (digraph/graph/subgraph or heavy '{}/}'), we now
  *only* run the curly-brace indenter and skip PlantUML block indentation
  to avoid wiping brace indentation.
- Brace indenter rewritten to correctly handle leading '}' and trailing '{'
  on the same line (e.g., "} else {").
"""

from __future__ import annotations
import argparse
import re
import sys
from typing import List, Tuple

# ---------- PlantUML helpers ----------

ARROW_RE = re.compile(
    r"""
    ^(?P<lead>\s*)
    (?P<left>\S[^\s:]*)\s*
    (?P<arrow>
        (?:<-->)|(?:<->)|(?:o?-->)|(?:o?->)|(?:<--o?)|(?:<-o?)|(?:-->)|(?:->)|(?:<--)|(?:<-)
    )
    \s*
    (?P<right>\S[^\s:]*?)
    (?:\s*:\s*(?P<label>.*?))?
    \s*$
    """, re.VERBOSE,
)

BLOCK_START = {"alt","loop","group","opt","par","break","critical","box"}
BLOCK_ELSE  = {"else","elseif","elif"}
BLOCK_END   = {"end","end box","endbox"}

NOTE_START_RE = re.compile(r"^\s*note\s+(left|right|over|top|bottom)\b.*$", re.IGNORECASE)
NOTE_END_RE   = re.compile(r"^\s*end\s+note\s*$", re.IGNORECASE)
PARTICIPANT_RE= re.compile(r"^\s*(participant|actor|boundary|control|entity|database)\s+(.+)$", re.IGNORECASE)

def _classify_puml(line: str):
    if NOTE_START_RE.match(line): return ("note_start", None)
    if NOTE_END_RE.match(line):   return ("note_end", None)
    stripped = line.strip().lower()
    if stripped in BLOCK_END: return ("block_end", None)
    first = stripped.split()[0] if stripped else ""
    if first in BLOCK_START: return ("block_start", None)
    if first in BLOCK_ELSE:  return ("block_else", None)
    m = ARROW_RE.match(line)
    if m: return ("arrow", m)
    if PARTICIPANT_RE.match(line): return ("participant", None)
    return ("other", None)

def _align_arrows(lines: List[str]) -> List[str]:
    out, bufm, raw = [], [], []
    def flush():
        nonlocal out, bufm, raw
        if not raw: return
        if not bufm:
            out.extend(raw)
        else:
            ml = max(len(m.group("left"))  for m in bufm)
            ma = max(len(m.group("arrow")) for m in bufm)
            mr = max(len(m.group("right")) for m in bufm)
            for ln in raw:
                m = ARROW_RE.match(ln)
                if not m:
                    out.append(ln)
                else:
                    lead = m.group("lead")
                    left = m.group("left").ljust(ml)
                    arr  = m.group("arrow").ljust(ma)
                    rig  = m.group("right").ljust(mr)
                    lab  = m.group("label")
                    out.append(f"{lead}{left} {arr} {rig}" + (f" : {lab.strip()}" if lab else ""))
        bufm, raw = [], []
    for ln in lines:
        t, m = _classify_puml(ln)
        if t == "arrow":
            raw.append(ln); bufm.append(m)  # type: ignore
        else:
            flush(); out.append(ln)
    flush(); return out

def _indent_puml_blocks(lines: List[str], indent_size=2) -> List[str]:
    ind, in_note, out = 0, False, []
    for ln in lines:
        t, _ = _classify_puml(ln)
        s = ln.strip()
        if NOTE_START_RE.match(ln): out.append(" "*(ind*indent_size)+s); in_note=True;  continue
        if NOTE_END_RE.match(ln):   out.append(" "*(ind*indent_size)+s); in_note=False; continue
        if in_note and t=="other":  out.append(" "*((ind+1)*indent_size)+s); continue
        if t=="block_end": ind=max(0,ind-1); out.append(" "*(ind*indent_size)+s); continue
        if t=="block_else": out.append(" "*(max(0,ind-1)*indent_size)+s); continue
        if t=="block_start": out.append(" "*(ind*indent_size)+s); ind+=1; continue
        out.append(" "*(ind*indent_size)+s)
    return out

# ---------- Curly-brace indenter (generic) ----------

def _brace_indent(lines: List[str], indent_size=2) -> List[str]:
    out: List[str] = []
    level = 0
    for ln in lines:
        raw = ln.rstrip("\n")
        # remove leading spaces for consistent output
        stripped = raw.lstrip()

        # count leading '}' to pre-dedent
        i = 0
        while i < len(stripped) and stripped[i] == "}":
            i += 1
        lead_closes = i  # number of leading } at start of content
        if lead_closes > 0:
            level = max(0, level - lead_closes)

        # render with current level
        out.append(" " * (level * indent_size) + stripped)

        # compute opens/closes to update level AFTER rendering
        total_opens  = stripped.count("{")
        total_closes = stripped.count("}")
        nonleading_closes = max(0, total_closes - lead_closes)
        level = max(0, level + total_opens - nonleading_closes)
    return out

def _normalize(text: str) -> List[str]:
    return [ln.rstrip() for ln in text.splitlines()]

def _looks_like_dot(lines: List[str]) -> bool:
    for ln in lines:
        s = ln.strip().lower()
        if s.startswith(("digraph", "graph", "subgraph")):
            return True
    # heavy brace use is also a hint
    brace_lines = sum(1 for ln in lines if "{" in ln or "}" in ln)
    return brace_lines >= max(3, len(lines)//10)  # heuristic

def _looks_like_plantuml(lines: List[str]) -> bool:
    for ln in lines:
        s = ln.strip().lower()
        if s.startswith(("@startuml", "@enduml", "participant", "actor", "skinparam", "title")):
            return True
        if ARROW_RE.match(ln):
            return True
    return False

def format_text(text: str, indent_size=2) -> str:
    lines = _normalize(text)
    is_dot = _looks_like_dot(lines)
    is_puml = _looks_like_plantuml(lines)

    if is_dot:
        # Only brace-indent; do NOT run PlantUML block indentation
        lines = _brace_indent(lines, indent_size=indent_size)
        # arrow alignment is harmless but unnecessary; skip
    elif is_puml:
        # PlantUML minimal passes
        lines = _indent_puml_blocks(lines, indent_size=indent_size)
        lines = _align_arrows(lines)
    else:
        # Unknown DSL: leave text as-is
        pass

    out = "\n".join(lines).rstrip() + "\n"
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--stdin", action="store_true")
    ap.add_argument("--indent-size", type=int, default=2)
    a = ap.parse_args()

    if a.stdin:
        txt = sys.stdin.read()
        sys.stdout.write(format_text(txt, indent_size=a.indent_size))
        return

    if not a.files:
        sys.stderr.write("No files provided. Use --stdin or pass files.\n")
        sys.exit(2)

    rc = 0
    for p in a.files:
        with open(p, "r", encoding="utf-8") as f:
            orig = f.read()
        fmt = format_text(orig, indent_size=a.indent_size)
        # 如果没检测到 DOT，但文件有 { 或 }，强制启用 brace 缩进
        if fmt == orig and ("{" in orig or "}" in orig):
            from io import StringIO
            lines = orig.splitlines()
            fmt = "\n".join(_brace_indent(lines, indent_size=a.indent_size)) + "\n"
        if a.check:
            if fmt != orig:
                sys.stderr.write(f"Would reformat: {p}\n")
                rc = 1
        elif a.write:
            if fmt != orig:
                with open(p, "w", encoding="utf-8") as f:
                    f.write(fmt)
        else:
            sys.stdout.write(fmt)
    sys.exit(rc)

if __name__ == "__main__":
    main()
