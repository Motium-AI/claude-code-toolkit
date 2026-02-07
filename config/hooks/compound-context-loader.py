#!/usr/bin/env python3
"""
Compound Context Loader - SessionStart Hook

Injects relevant memory events at session start. Reads from the
append-only event store at ~/.claude/memory/{project-hash}/events/.

Selection: 3-signal scoring with time-bound entity gate.
Scoring: entity overlap 45%, recency 35%, quality 20%.
Entity gate rejects zero-overlap events older than 4h.

Part of the Compound Memory System that enables cross-session learning.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add hooks directory to path for shared imports
sys.path.insert(0, str(Path(__file__).parent))

import glob as glob_mod
import re

from _common import log_debug, timed_hook, VERSION_TRACKING_EXCLUSIONS
from _scoring import (
    build_file_components,
    entity_overlap_score,
    event_age_hours,
    score_event,
    ENTITY_GATE_BYPASS_HOURS,
    MIN_SCORE_SESSION_START,
)

MAX_EVENTS = 5
MAX_CHARS_STANDALONE = 8000   # No native MEMORY.md present
MAX_CHARS_INTEGRATED = 4500   # Native MEMORY.md consuming ~4-6K chars

# Budget tiers: higher-scoring events get more space
BUDGET_HIGH = 600     # score >= 0.6
BUDGET_MEDIUM = 350   # score >= 0.35
BUDGET_LOW = 200      # score < 0.35

# Bootstrap sources to filter out (commit-message-level, near-zero learning value)
BOOTSTRAP_SOURCES = frozenset({"async-task-bootstrap", "bootstrap"})


# ============================================================================
# Native Memory Detection
# ============================================================================


def _detect_native_memory(cwd: str) -> tuple[bool, str]:
    """Detect if Claude's native MEMORY.md exists and return its content.

    Encodes the repo path the same way Claude Code does (replace / with -,
    strip leading -). Falls back to glob if exact encoding fails.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=5, cwd=cwd,
        )
        repo_root = result.stdout.strip()
        if not repo_root:
            return False, ""

        # Encode path the same way Claude Code does:
        # /Users/foo/my_bar → -Users-foo-my-bar (replace / and _ with -)
        encoded = repo_root.replace("/", "-").replace("_", "-").lstrip("-")
        memory_path = (
            Path.home() / ".claude" / "projects"
            / f"-{encoded}" / "memory" / "MEMORY.md"
        )

        if memory_path.exists():
            content = memory_path.read_text(encoding="utf-8").strip()
            if content:
                return True, content

        # Glob fallback: if encoding changed, find by project name
        pattern = str(
            Path.home() / ".claude" / "projects"
            / "*-claude-code-toolkit" / "memory" / "MEMORY.md"
        )
        for match in glob_mod.glob(pattern):
            p = Path(match)
            if p.exists():
                content = p.read_text(encoding="utf-8").strip()
                if content:
                    return True, content

    except (subprocess.TimeoutExpired, FileNotFoundError, OSError, IOError):
        pass
    return False, ""


# ============================================================================
# MEMORY.md Dedup Guard
# ============================================================================

# Words too common to be meaningful for dedup matching
_STOP_WORDS = frozenset({
    "the", "this", "that", "with", "from", "have", "been", "were", "will",
    "when", "what", "which", "where", "their", "there", "about", "would",
    "could", "should", "does", "into", "than", "then", "them", "these",
    "those", "other", "after", "before", "because", "between", "through",
    "during", "each", "every", "only", "also", "just", "more", "most",
    "some", "such", "very", "same", "make", "made", "like", "over",
    "using", "used", "first", "need", "instead", "rather",
})


def _build_memory_tokens(content: str) -> set[str]:
    """Extract significant words from MEMORY.md for dedup matching.

    Returns lowercased words >4 chars, minus stop words.
    """
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{4,}", content.lower())
    return {w for w in words if w not in _STOP_WORDS}


def _event_overlaps_memory(event: dict, memory_tokens: set[str]) -> bool:
    """Check if >60% of an event's significant words already appear in MEMORY.md.

    Conservative threshold: only filters near-duplicates where the lesson
    is already well-documented in native memory.
    """
    if not memory_tokens:
        return False
    content = event.get("content", "")
    event_words = re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{4,}", content.lower())
    event_tokens = {w for w in event_words if w not in _STOP_WORDS}
    if len(event_tokens) < 3:
        return False  # Too few words to judge
    overlap = event_tokens & memory_tokens
    return len(overlap) / len(event_tokens) > 0.6


# ============================================================================
# File Context
# ============================================================================


def _get_changed_files(cwd: str) -> set[str]:
    """Get files changed in recent commits + uncommitted changes."""
    files = set()
    try:
        # Uncommitted changes (exclude .claude/ and other metadata)
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD", "--"] + VERSION_TRACKING_EXCLUSIONS,
            capture_output=True, text=True, timeout=5, cwd=cwd,
        )
        for line in result.stdout.strip().split("\n"):
            if line.strip():
                files.add(line.strip())

        # Last 5 commits (exclude .claude/ and other metadata)
        result = subprocess.run(
            ["git", "log", "--name-only", "--format=", "-5", "--"] + VERSION_TRACKING_EXCLUSIONS,
            capture_output=True, text=True, timeout=5, cwd=cwd,
        )
        for line in result.stdout.strip().split("\n"):
            if line.strip():
                files.add(line.strip())
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return files


# ============================================================================
# Injection Formatting
# ============================================================================


def _human_age(ts: str, now: datetime) -> str:
    """Convert ISO timestamp to human-readable relative age."""
    try:
        event_time = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        delta = now - event_time
        hours = delta.total_seconds() / 3600
        if hours < 1:
            return "<1h"
        if hours < 24:
            return f"{int(hours)}h"
        days = delta.days
        if days < 7:
            return f"{days}d"
        if days < 30:
            return f"{days // 7}w"
        return f"{days // 30}mo"
    except (ValueError, TypeError):
        return "?"


def _budget_for_score(score: float) -> int:
    """Return character budget based on event score tier."""
    if score >= 0.6:
        return BUDGET_HIGH
    if score >= 0.35:
        return BUDGET_MEDIUM
    return BUDGET_LOW


def _truncate_content(content: str, max_len: int) -> str:
    """Truncate at sentence boundary if possible, preserving LESSON prefix."""
    if len(content) <= max_len:
        return content
    trunc = content[:max_len]
    # Try to cut at sentence boundary
    last_period = trunc.rfind(". ")
    last_newline = trunc.rfind("\n")
    cut_point = max(last_period, last_newline)
    if cut_point > max_len * 0.6:
        return trunc[:cut_point + 1].rstrip()
    return trunc.rstrip() + "..."


def _format_injection(scored_events: list[tuple[dict, float]]) -> str:
    """Format scored events as structured XML with metadata attributes.

    Score-tiered budget: high-score events get more space for richer content.
    Shows concept tags alongside file names for retrieval transparency.
    """
    now = datetime.now(timezone.utc)
    event_count = 0
    parts = []

    for event, score in scored_events:
        content = event.get("content", "").strip()
        if not content:
            continue

        # Schemas always get full budget (consolidated knowledge)
        if event.get("type") == "schema":
            budget = BUDGET_HIGH
        else:
            budget = _budget_for_score(score)
        content = _truncate_content(content, budget)

        entities = event.get("entities", [])

        # Separate file entities and concept entities
        file_entities = [
            e.split("/")[-1] for e in entities
            if "." in e.split("/")[-1]
        ][:3]
        concept_entities = [
            e for e in entities
            if "/" not in e and "." not in e
        ][:5]

        files_attr = ", ".join(file_entities) if file_entities else ""
        tags_attr = ", ".join(concept_entities) if concept_entities else ""

        age_str = _human_age(event.get("ts", ""), now)
        # Category: top-level first, fall back to meta for backward compatibility
        cat = event.get("category", "") or event.get("meta", {}).get("category", "session")

        event_id = event.get("id", "")
        problem = event.get("problem_type", "")
        # Dual-ID: ref="m1" for easy citation, id="evt_..." for utility tracking
        ref_id = f"m{event_count + 1}"
        attrs = f'ref="{ref_id}" id="{event_id}" files="{files_attr}" age="{age_str}" cat="{cat}"'
        if problem:
            attrs += f' problem="{problem}"'
        if tags_attr:
            attrs += f' tags="{tags_attr}"'
        parts.append(f"<m {attrs}>\n{content}\n</m>")
        event_count += 1

    if not parts:
        return ""

    header = (
        f'<memories count="{event_count}">\n'
        f"BEFORE starting: scan m1-m{event_count} for applicable lessons.\n"
        "At stop: list any that helped in memory_that_helped (e.g., [\"m1\", \"m3\"]).\n"
    )
    body = "\n\n".join(parts)
    footer = "\n</memories>"

    return header + "\n" + body + footer


# ============================================================================
# Doc Debt
# ============================================================================


def _get_doc_debt(cwd: str) -> str:
    """Check for documentation debt and return brief injection if present."""
    debt_path = Path(cwd) / ".claude" / "doc-debt.json"
    try:
        if not debt_path.exists():
            return ""
        debt = json.loads(debt_path.read_text())
        entries = debt.get("entries", [])
        if not entries:
            return ""

        # Collect unique changed files across all debt entries
        all_files = set()
        for e in entries:
            for f in e.get("changed_files", []):
                all_files.add(f.split("/")[-1])  # basename only

        files_str = ", ".join(sorted(all_files)[:8])
        return (
            f'<doc-debt count="{len(entries)}">\n'
            f'{len(entries)} commit(s) with code changes since last documentation update. '
            f'Key files: {files_str}. Consider updating relevant docs.\n'
            f'</doc-debt>'
        )
    except (json.JSONDecodeError, IOError):
        return ""


# ============================================================================
# Main
# ============================================================================


def main():
    input_data = json.loads(sys.stdin.read() or "{}")
    cwd = input_data.get("cwd", "")

    if not cwd:
        sys.exit(0)

    # Detect native MEMORY.md and adjust context budget
    has_native_memory, native_content = _detect_native_memory(cwd)
    effective_max_chars = MAX_CHARS_INTEGRATED if has_native_memory else MAX_CHARS_STANDALONE
    memory_tokens = _build_memory_tokens(native_content) if has_native_memory else set()

    # Import memory primitives
    try:
        from _memory import get_recent_events, cleanup_old_events
    except ImportError:
        log_debug(
            "Cannot import _memory module",
            hook_name="compound-context-loader",
        )
        sys.exit(0)

    # Compact and inject core assertions BEFORE event scoring
    assertions_block = ""
    try:
        from _memory import compact_assertions, read_assertions
        compact_assertions(cwd)
        assertions = read_assertions(cwd)
        if assertions:
            assertion_lines = []
            for a in assertions:
                topic = a.get("topic", "")
                text = a.get("assertion", "")
                assertion_lines.append(f"  <a topic=\"{topic}\">{text}</a>")
            assertions_block = (
                "<core-assertions>\n"
                + "\n".join(assertion_lines)
                + "\n</core-assertions>"
            )
    except (ImportError, Exception):
        pass

    # Cleanup old events at session start
    try:
        removed = cleanup_old_events(cwd)
        if removed:
            log_debug(
                f"Cleaned up {removed} old events",
                hook_name="compound-context-loader",
            )
    except Exception:
        pass

    # Load recent events (manifest fast-path)
    events = get_recent_events(cwd, limit=30)
    if not events:
        log_debug(
            "No memory events found",
            hook_name="compound-context-loader",
        )
        sys.exit(0)

    # Filter bootstrap events (commit-message-level noise)
    events = [e for e in events if e.get("source") not in BOOTSTRAP_SOURCES]

    # Filter events superseded by schemas (archived_by set during consolidation)
    events = [e for e in events if not e.get("meta", {}).get("archived_by")]

    if not events:
        log_debug(
            "No non-bootstrap events found",
            hook_name="compound-context-loader",
        )
        sys.exit(0)

    # Get changed files for context
    changed_files = _get_changed_files(cwd)

    # 3-signal scoring with time-bound entity gate
    basenames, stems, dirs = build_file_components(changed_files)

    scored = []
    gated_count = 0
    dedup_count = 0
    for event in events:
        entity_score = entity_overlap_score(event, basenames, stems, dirs)
        # Time-bound entity gate: reject zero-overlap events only if >= 4h old.
        # Fresh events (<4h) bypass to let recency compensate.
        if entity_score == 0.0 and event_age_hours(event) >= ENTITY_GATE_BYPASS_HOURS:
            gated_count += 1
            continue
        # Dedup guard: skip events whose content overlaps MEMORY.md
        if memory_tokens and _event_overlaps_memory(event, memory_tokens):
            dedup_count += 1
            continue
        score = score_event(event, basenames, stems, dirs)
        if score >= MIN_SCORE_SESSION_START:
            scored.append((event, score))
    scored.sort(key=lambda x: x[1], reverse=True)

    # Take top N
    top_events = scored[:MAX_EVENTS]

    # Format as structured XML
    output = _format_injection(top_events)
    if not output:
        sys.exit(0)

    # Prepend core assertions and doc debt before memories
    prefix_parts = []
    if assertions_block:
        prefix_parts.append(assertions_block)
    doc_debt = _get_doc_debt(cwd)
    if doc_debt:
        prefix_parts.append(doc_debt)
    if prefix_parts:
        output = "\n\n".join(prefix_parts) + "\n\n" + output

    # Enforce total budget (dynamic based on native MEMORY.md presence)
    if len(output) > effective_max_chars:
        # Truncate memories portion, preserve assertions + closing tag
        output = output[:effective_max_chars - 15] + "\n</memories>"

    log_debug(
        "Injecting memory context",
        hook_name="compound-context-loader",
        parsed_data={
            "events_count": len(top_events),
            "gated_count": gated_count,
            "dedup_count": dedup_count,
            "native_memory_detected": has_native_memory,
            "effective_budget": effective_max_chars,
            "assertions_count": len(assertions) if assertions_block else 0,
            "output_chars": len(output),
        },
    )

    print(output)

    # Write injection log for mid-session recall (read by memory-recall.py)
    try:
        from _memory import atomic_write_json
        session_id = ""
        snap_path = Path(cwd) / ".claude" / "session-snapshot.json"
        if snap_path.exists():
            session_id = json.loads(snap_path.read_text()).get("session_id", "")
        log_path = Path(cwd) / ".claude" / "injection-log.json"
        log_data = {
            "session_id": session_id,
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "native_memory_detected": has_native_memory,
            "effective_budget": effective_max_chars,
            "dedup_count": dedup_count,
            "events": [
                {"ref": f"m{i+1}", "id": e.get("id", ""), "score": round(s, 3)}
                for i, (e, s) in enumerate(top_events) if e.get("id")
            ],
        }
        atomic_write_json(log_path, log_data)
    except Exception:
        pass

    sys.exit(0)


if __name__ == "__main__":
    with timed_hook("compound-context-loader"):
        main()
