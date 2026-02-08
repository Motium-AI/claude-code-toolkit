#!/usr/bin/env python3
"""
PostToolUse Hook - Mid-Session Verification Monitor

Tracks edits-since-last-verification and nudges the agent to verify
when it has been building without testing. Catches the "build everything,
verify nothing, claim completion" anti-pattern mid-session.

Based on Replit's Decision-Time Guidance pattern: environment feedback
during execution prevents verification drift on long trajectories.

Advisory only — never blocks.

Hook event: PostToolUse (matcher: *)
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import log_debug, timed_hook
from _session import is_autonomous_mode_active, get_autonomous_state

STATE_FILE = ".claude/verification-monitor.json"
NUDGE_THRESHOLD = 10  # Edits before first nudge
NUDGE_COOLDOWN_SECONDS = 300  # Don't nudge more than once per 5 min

# Tool names that count as edits
EDIT_TOOLS = {"Edit", "Write", "NotebookEdit"}

# Patterns in Bash commands that count as verification
VERIFY_PATTERNS = [
    r"\b(ruff|eslint|pylint|mypy|flake8)\b",  # Linters
    r"\b(pytest|jest|vitest|mocha|npm\s+test|npm\s+run\s+test)\b",  # Test runners
    r"\bnpm\s+run\s+lint\b",  # Lint scripts
    r"\btsc\s+--noEmit\b",  # Type checking
    r"\bcurl\s+",  # API testing
    r"\bpython3?\s+-c\b.*\btest\b",  # Inline Python tests
    r"\bpython3?\s+-c\b.*\bassert\b",  # Inline assertions
    r"surf-verify",  # Web smoke tests
    r"maestro\s+test",  # Mobile tests
    r"\bast\.parse\b",  # Syntax validation (minimal but counts)
]


def _load_state(cwd: str) -> dict:
    """Load monitor state."""
    state_path = Path(cwd) / STATE_FILE
    try:
        if state_path.exists():
            return json.loads(state_path.read_text())
    except (json.JSONDecodeError, IOError):
        pass
    return {"edits_since_verify": 0, "last_nudge_ts": 0}


def _save_state(cwd: str, state: dict) -> None:
    """Save monitor state."""
    state_path = Path(cwd) / STATE_FILE
    try:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(state))
    except IOError:
        pass


def _is_verification_command(tool_input: dict) -> bool:
    """Check if a Bash command is a verification/testing command."""
    command = tool_input.get("command", "")
    return any(re.search(p, command, re.IGNORECASE) for p in VERIFY_PATTERNS)


def main():
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    cwd = input_data.get("cwd", "")
    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})
    session_id = input_data.get("session_id", "")

    if not cwd:
        sys.exit(0)

    # Only monitor in autonomous mode
    if not is_autonomous_mode_active(cwd, session_id):
        sys.exit(0)

    state = _load_state(cwd)

    # Track edits
    if tool_name in EDIT_TOOLS:
        state["edits_since_verify"] = state.get("edits_since_verify", 0) + 1
        _save_state(cwd, state)
        sys.exit(0)

    # Reset counter on verification
    if tool_name == "Bash" and _is_verification_command(tool_input):
        if state.get("edits_since_verify", 0) > 0:
            log_debug(
                f"Verification detected after {state['edits_since_verify']} edits",
                hook_name="verification-monitor",
            )
        state["edits_since_verify"] = 0
        _save_state(cwd, state)
        sys.exit(0)

    # Check if nudge is needed
    edits = state.get("edits_since_verify", 0)
    last_nudge = state.get("last_nudge_ts", 0)
    now = time.time()

    if edits >= NUDGE_THRESHOLD and (now - last_nudge) > NUDGE_COOLDOWN_SECONDS:
        state["last_nudge_ts"] = now
        _save_state(cwd, state)

        output = {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": (
                    f"VERIFICATION REMINDER: You've made {edits} edits without running "
                    "any verification (linters, tests, or functional checks). "
                    "The stop-validator will require verification.tests in your checkpoint. "
                    "Consider verifying now rather than discovering issues at exit.\n"
                    "Quick checks: ruff check . | npm run lint | python3 -c 'import ast; ...' | "
                    "curl <endpoint> | run your test suite"
                ),
            }
        }

        log_debug(
            f"Nudge: {edits} edits without verification",
            hook_name="verification-monitor",
        )

        print(json.dumps(output))
    sys.exit(0)


if __name__ == "__main__":
    with timed_hook("verification-monitor"):
        main()
