#!/usr/bin/env python3
"""
Compound Context Loader - SessionStart Hook

Injects relevant memory events at session start. Reads from the
append-only event store at ~/.claude/memory/{project-hash}/events/.

Part of the Compound Memory System that enables cross-session learning.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

# Add hooks directory to path for shared imports
sys.path.insert(0, str(Path(__file__).parent))

from _common import log_debug

MAX_EVENTS = 5
MAX_CHARS = 3000


def _get_changed_files(cwd: str) -> set[str]:
    """Get files changed in recent commits + uncommitted changes."""
    files = set()
    try:
        # Uncommitted changes
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            capture_output=True, text=True, timeout=5, cwd=cwd,
        )
        for line in result.stdout.strip().split("\n"):
            if line.strip():
                files.add(line.strip())

        # Last 5 commits
        result = subprocess.run(
            ["git", "log", "--name-only", "--format=", "-5"],
            capture_output=True, text=True, timeout=5, cwd=cwd,
        )
        for line in result.stdout.strip().split("\n"):
            if line.strip():
                files.add(line.strip())
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return files


def _score_event(event: dict, changed_files: set[str]) -> float:
    """Score an event by recency (60%) + entity overlap (40%)."""
    # Recency score: 1.0 for today, decays to 0.0 over 30 days
    ts = event.get("ts", "")
    try:
        from datetime import datetime, timezone
        event_time = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        age_days = (datetime.now(timezone.utc) - event_time).total_seconds() / 86400
        recency = max(0.0, 1.0 - (age_days / 30.0))
    except (ValueError, TypeError):
        recency = 0.5

    # Entity overlap score: fraction of event entities that match changed files
    entities = event.get("entities", [])
    if entities and changed_files:
        overlap = sum(
            1 for e in entities
            if any(e in f or f in e for f in changed_files)
        )
        entity_score = min(1.0, overlap / max(1, len(entities)))
    else:
        entity_score = 0.0

    return (0.6 * recency) + (0.4 * entity_score)


def main():
    input_data = json.loads(sys.stdin.read() or "{}")
    cwd = input_data.get("cwd", "")

    if not cwd:
        sys.exit(0)

    # Import memory primitives
    try:
        from _memory import get_recent_events, cleanup_old_events
    except ImportError:
        log_debug(
            "Cannot import _memory module",
            hook_name="compound-context-loader",
        )
        sys.exit(0)

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
    events = get_recent_events(cwd, limit=20)
    if not events:
        log_debug(
            "No memory events found",
            hook_name="compound-context-loader",
        )
        sys.exit(0)

    # Score events by relevance
    changed_files = _get_changed_files(cwd)
    scored = [(event, _score_event(event, changed_files)) for event in events]
    scored.sort(key=lambda x: x[1], reverse=True)

    # Take top N
    top_events = scored[:MAX_EVENTS]

    # Format output
    lines = []
    for event, score in top_events:
        content = event.get("content", "").strip()
        if not content:
            continue
        # Truncate long content
        if len(content) > 200:
            content = content[:197] + "..."
        source = event.get("source", "unknown")
        tag = "auto" if source == "auto-capture" else source.split("-")[0]
        lines.append(f"  [{tag}] {content}")

    if not lines:
        sys.exit(0)

    output = "[memory] Recent learnings from past sessions:\n"
    output += "\n".join(lines)

    if len(output) > MAX_CHARS:
        output = output[:MAX_CHARS - 3] + "..."

    log_debug(
        "Injecting memory context",
        hook_name="compound-context-loader",
        parsed_data={"events_count": len(lines), "output_chars": len(output)},
    )

    print(output)
    sys.exit(0)


if __name__ == "__main__":
    main()
