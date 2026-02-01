#!/usr/bin/env python3
"""
PreCompact Hook - Pre-Compaction Summary Injection

Builds a deterministic summary from session state and injects it into
the post-compaction context via hookSpecificOutput. This ensures key
session context survives context compaction.

Part of the Compound Memory System's two-layer safety net:
  1. PreCompact: summary injection before compaction (this hook)
  2. Stop: structured LESSON capture on clean exit
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

# Add hooks directory to path for shared imports
sys.path.insert(0, str(Path(__file__).parent))

from _common import VERSION_TRACKING_EXCLUSIONS


def _get_changed_files(cwd: str) -> list[str]:
    """Get files changed in this session via git diff."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD", "--"] + VERSION_TRACKING_EXCLUSIONS,
            capture_output=True, text=True, timeout=5, cwd=cwd,
        )
        return [
            line.strip() for line in result.stdout.strip().split("\n")
            if line.strip()
        ]
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return []


def _build_summary(cwd: str, session_id: str) -> str:
    """Build a deterministic summary from session state files (no LLM)."""
    parts = ["SESSION MEMORY CHECKPOINT (pre-compaction)"]

    # Autonomous mode state
    try:
        from _state import get_autonomous_state
        state, mode_type = get_autonomous_state(cwd, session_id)
        if state and mode_type:
            iteration = state.get("iteration", "?")
            parts.append(f"Mode: {mode_type} (iteration {iteration})")
    except (ImportError, Exception):
        pass

    # Changed files
    changed = _get_changed_files(cwd)
    if changed:
        file_list = ", ".join(changed[:8])
        count = len(changed)
        parts.append(f"Files changed: {file_list} ({count} total)")

    # Checkpoint content
    try:
        from _checkpoint import load_checkpoint
        checkpoint = load_checkpoint(cwd)
        if checkpoint:
            reflection = checkpoint.get("reflection", {})
            what_done = reflection.get("what_was_done", "")
            if what_done:
                parts.append(f"Work: {what_done[:200]}")
            key_insight = reflection.get("key_insight", "")
            if key_insight:
                parts.append(f"Insight: {key_insight[:150]}")
    except (ImportError, Exception):
        pass

    return "\n".join(parts)


def main():
    input_data = json.loads(sys.stdin.read() or "{}")
    cwd = input_data.get("cwd", "")
    session_id = input_data.get("session_id", "")

    if not cwd:
        sys.exit(0)

    # Build summary for post-compaction context
    summary = _build_summary(cwd, session_id)

    if summary.strip():
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PreCompact",
                "additionalContext": summary,
            }
        }
        print(json.dumps(output))

    sys.exit(0)


if __name__ == "__main__":
    main()
