#!/usr/bin/env python3
"""
PostToolUse hook — lightweight tool usage logger for post-session analysis.

Logs {tool_name, input_signature, timestamp} to .claude/tool-usage-log.json.
Rolling window of ~200 entries. Fast (~1ms per call, no LLM).

Hook event: PostToolUse (matcher: *)
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path


MAX_ENTRIES = 200

# Signature extractors: pull the minimal identifying info from tool_input
SIGNATURE_EXTRACTORS = {
    "Read": lambda inp: inp.get("file_path", "")[-60:],
    "Edit": lambda inp: inp.get("file_path", "")[-60:],
    "Write": lambda inp: inp.get("file_path", "")[-60:],
    "Grep": lambda inp: f"{inp.get('pattern', '')}|{inp.get('path', '')[-40:]}",
    "Glob": lambda inp: inp.get("pattern", ""),
    "Bash": lambda inp: inp.get("command", "")[:80],
    "Skill": lambda inp: inp.get("skill", ""),
    "Task": lambda inp: inp.get("description", "")[:60],
}


def extract_signature(tool_name: str, tool_input: dict) -> str:
    """Extract a short identifying signature from tool input."""
    extractor = SIGNATURE_EXTRACTORS.get(tool_name)
    if extractor:
        try:
            return extractor(tool_input)
        except (KeyError, TypeError, AttributeError):
            pass
    # Fallback: first string value found
    for v in tool_input.values():
        if isinstance(v, str) and v:
            return v[:60]
    return ""


def main():
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})
    cwd = input_data.get("cwd", "") or os.getcwd()

    if not tool_name:
        sys.exit(0)

    # Build log entry
    entry = {
        "t": time.time(),
        "tool": tool_name,
        "sig": extract_signature(tool_name, tool_input),
    }

    # Log file location
    log_path = Path(cwd) / ".claude" / "tool-usage-log.json"

    # Load existing log
    entries = []
    if log_path.exists():
        try:
            entries = json.loads(log_path.read_text())
            if not isinstance(entries, list):
                entries = []
        except (json.JSONDecodeError, IOError):
            entries = []

    # Append and trim
    entries.append(entry)
    if len(entries) > MAX_ENTRIES:
        entries = entries[-MAX_ENTRIES:]

    # Atomic write
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(log_path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(entries, f)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, str(log_path))
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
    except (IOError, OSError):
        pass

    sys.exit(0)


if __name__ == "__main__":
    main()
