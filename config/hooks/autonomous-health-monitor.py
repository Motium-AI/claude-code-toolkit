#!/usr/bin/env python3
"""
PostToolUse Hook - Autonomous State Health Monitor

Monitors autonomous session health by tracking:
1. Iteration staleness — warns if no git commits in extended periods
2. State file integrity — detects corrupted or expired state
3. Checkpoint drift — warns if checkpoint exists but is stale for current version

Advisory only — never blocks execution.

Hook event: PostToolUse (matcher: *)
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import log_debug, timed_hook, get_code_version, is_state_expired
from _session import get_autonomous_state, load_checkpoint

# Thresholds
COMMIT_STALENESS_MINUTES = 30  # Warn if no commit in 30 min during autonomous mode
CHECK_INTERVAL_SECONDS = 120   # Don't check more often than every 2 minutes
LAST_CHECK_FILE = ".claude/health-monitor-last-check.json"


def _minutes_since_last_commit(cwd: str) -> float | None:
    """Get minutes since last git commit in this repo."""
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%ct"],
            cwd=cwd, capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            commit_epoch = int(result.stdout.strip())
            return (time.time() - commit_epoch) / 60
    except (subprocess.TimeoutExpired, ValueError, FileNotFoundError):
        pass
    return None


def _should_check(cwd: str) -> bool:
    """Rate-limit health checks to avoid performance drag."""
    check_file = Path(cwd) / LAST_CHECK_FILE
    try:
        if check_file.exists():
            data = json.loads(check_file.read_text())
            last_ts = data.get("last_check", 0)
            if time.time() - last_ts < CHECK_INTERVAL_SECONDS:
                return False
    except (json.JSONDecodeError, IOError):
        pass
    return True


def _record_check(cwd: str) -> None:
    """Record that we just ran a health check."""
    check_file = Path(cwd) / LAST_CHECK_FILE
    try:
        check_file.parent.mkdir(parents=True, exist_ok=True)
        check_file.write_text(json.dumps({"last_check": time.time()}))
    except IOError:
        pass


def main():
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    cwd = input_data.get("cwd", "")
    session_id = input_data.get("session_id", "")

    if not cwd:
        sys.exit(0)

    # Only monitor in autonomous mode
    state, mode = get_autonomous_state(cwd, session_id)
    if not state:
        sys.exit(0)

    # Rate-limit checks
    if not _should_check(cwd):
        sys.exit(0)

    _record_check(cwd)

    warnings = []

    # 1. Check state file integrity
    if is_state_expired(state):
        warnings.append(
            "Autonomous state has expired. The session may have been running too long. "
            "Consider writing a checkpoint and wrapping up."
        )

    # 2. Check commit staleness
    minutes = _minutes_since_last_commit(cwd)
    if minutes is not None and minutes > COMMIT_STALENESS_MINUTES:
        warnings.append(
            f"No git commit in {int(minutes)} minutes during autonomous mode. "
            "Commit incremental progress to avoid losing work if the session ends unexpectedly."
        )

    # 3. Check checkpoint staleness (if checkpoint exists)
    checkpoint = load_checkpoint(cwd)
    if checkpoint:
        cp_version = checkpoint.get("code_version", "")
        current_version = get_code_version(cwd)
        if cp_version and current_version and cp_version != current_version:
            warnings.append(
                f"Checkpoint is stale (version {cp_version} vs current {current_version}). "
                "Update the checkpoint to reflect current state."
            )

    if not warnings:
        sys.exit(0)

    # Build advisory
    parts = ["HEALTH MONITOR:"]
    for w in warnings:
        parts.append(f"  - {w}")

    output = {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": "\n".join(parts),
        }
    }

    log_debug(
        f"Health monitor: {len(warnings)} warning(s)",
        hook_name="autonomous-health-monitor",
    )

    print(json.dumps(output))
    sys.exit(0)


if __name__ == "__main__":
    with timed_hook("autonomous-health-monitor"):
        main()
