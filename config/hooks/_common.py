#!/usr/bin/env python3
"""
Shared utilities for Claude Code hooks.

Constants, logging, git utilities, TTL checks, and worktree detection.
For state file operations, see _state.py.
For checkpoint operations, see _checkpoint.py.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path


# TTL for autonomous mode state files (hours).
# State older than this is considered expired and cleaned up.
SESSION_TTL_HOURS = 8


# Files/patterns excluded from version tracking (dirty calculation)
# These don't represent code changes requiring re-deployment
VERSION_TRACKING_EXCLUSIONS = [
    ".",
    ":(exclude).claude",
    ":(exclude).claude/**",
    ":(exclude)**/.claude",
    ":(exclude)**/.claude/**",
    ":(exclude)*.lock",
    ":(exclude)package-lock.json",
    ":(exclude)yarn.lock",
    ":(exclude)pnpm-lock.yaml",
    ":(exclude)poetry.lock",
    ":(exclude)Pipfile.lock",
    ":(exclude)Cargo.lock",
    ":(exclude).gitmodules",
    ":(exclude)*.pyc",
    ":(exclude)__pycache__",
    ":(exclude)*/__pycache__",
    ":(exclude).env*",
    ":(exclude)*.log",
    ":(exclude).DS_Store",
    ":(exclude)*.swp",
    ":(exclude)*.swo",
    ":(exclude)*.orig",
    ":(exclude).idea",
    ":(exclude).idea/*",
    ":(exclude).vscode",
    ":(exclude).vscode/*",
]

# Debug log location - shared across all hooks
DEBUG_LOG = Path(tempfile.gettempdir()) / "claude-hooks-debug.log"


# ============================================================================
# Git Utilities
# ============================================================================


def get_diff_hash(cwd: str = "") -> str:
    """Get hash of current git diff (excluding metadata files).

    Used to detect if THIS session made changes by comparing against
    the snapshot taken at session start.
    """
    try:
        result = subprocess.run(
            ["git", "diff", "HEAD", "--"] + VERSION_TRACKING_EXCLUSIONS,
            capture_output=True,
            text=True,
            timeout=5,
            cwd=cwd or None,
        )
        return hashlib.sha1(result.stdout.encode()).hexdigest()[:12]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return "unknown"


def get_code_version(cwd: str = "") -> str:
    """Get current code version (git HEAD + dirty indicator).

    Returns format:
    - "abc1234" - clean commit
    - "abc1234-dirty" - commit with uncommitted changes
    - "unknown" - not a git repo or error

    NOTE: The dirty indicator is boolean, NOT a hash. This ensures version
    stability during development - version only changes at commit boundaries.
    """
    try:
        head = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=cwd or None,
        )
        head_hash = head.stdout.strip()
        if not head_hash:
            return "unknown"

        diff = subprocess.run(
            ["git", "diff", "HEAD", "--"] + VERSION_TRACKING_EXCLUSIONS,
            capture_output=True,
            text=True,
            timeout=5,
            cwd=cwd or None,
        )
        if diff.stdout.strip():
            return f"{head_hash}-dirty"

        return head_hash
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return "unknown"


# ============================================================================
# Logging
# ============================================================================


def log_debug(
    message: str,
    hook_name: str = "unknown",
    raw_input: str = "",
    parsed_data: dict | None = None,
    error: Exception | None = None,
) -> None:
    """Log diagnostic info for debugging hook issues."""
    try:
        with open(DEBUG_LOG, "a", encoding="utf-8") as f:
            f.write(f"\n{'=' * 60}\n")
            f.write(f"Timestamp: {datetime.now().isoformat()}\n")
            f.write(f"Hook: {hook_name}\n")
            f.write(f"Message: {message}\n")
            if error:
                f.write(f"Error: {type(error).__name__}: {error}\n")
            if raw_input:
                f.write(
                    f"Raw stdin ({len(raw_input)} bytes): {repr(raw_input[:500])}\n"
                )
            if parsed_data is not None:
                f.write(f"Parsed data: {json.dumps(parsed_data, indent=2)}\n")
            f.write(f"{'=' * 60}\n")
    except Exception:
        pass  # Never fail on logging


# ============================================================================
# TTL & Session Utilities
# ============================================================================


def is_state_expired(state: dict, ttl_hours: int = SESSION_TTL_HOURS) -> bool:
    """Check if a state file has exceeded its TTL.

    Uses last_activity_at if present, falls back to started_at.
    Missing or malformed timestamps are treated as expired.
    """
    timestamp_str = state.get("last_activity_at") or state.get("started_at")
    if not timestamp_str:
        return True

    try:
        if timestamp_str.endswith("Z"):
            timestamp_str = timestamp_str[:-1] + "+00:00"
        ts = datetime.fromisoformat(timestamp_str)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        return (now - ts) > timedelta(hours=ttl_hours)
    except (ValueError, TypeError):
        return True


def is_state_for_session(state: dict, session_id: str) -> bool:
    """Check if a state file belongs to the given session.

    No session_id in state = True (backward compatibility).
    Empty session_id argument = True (caller doesn't have session info).
    """
    if not session_id:
        return True
    state_session = state.get("session_id")
    if not state_session:
        return True
    return state_session == session_id


# ============================================================================
# Process Utilities
# ============================================================================


def is_pid_alive(pid: int) -> bool:
    """Check if a process with the given PID is still running.

    Uses os.kill(pid, 0) which doesn't actually send a signal,
    just checks if the process exists.
    """
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # Process exists but we don't own it
    except OSError:
        return False


# ============================================================================
# Worktree Detection
# ============================================================================


def is_worktree(cwd: str = "") -> bool:
    """Check if the current directory is a git worktree (not the main repo)."""
    try:
        git_dir = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=cwd or None,
        )
        git_common = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=cwd or None,
        )
        return git_dir.stdout.strip() != git_common.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def get_worktree_info(cwd: str = "") -> dict | None:
    """Get information about the current worktree if in one.

    Returns:
        Dict with branch, agent_id, path, is_claude_worktree.
        None if not in a worktree.
    """
    if not is_worktree(cwd):
        return None
    try:
        branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=cwd or None,
        )
        worktree_path = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=cwd or None,
        )

        state_file = (
            Path(worktree_path.stdout.strip()) / ".claude" / "worktree-agent-state.json"
        )
        agent_id = None
        if state_file.exists():
            try:
                state = json.loads(state_file.read_text())
                agent_id = state.get("agent_id")
            except (json.JSONDecodeError, IOError):
                pass

        return {
            "branch": branch.stdout.strip(),
            "agent_id": agent_id,
            "path": worktree_path.stdout.strip(),
            "is_claude_worktree": agent_id is not None,
        }
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


# ============================================================================
# Hook Execution Metrics
# ============================================================================

HOOK_METRICS_PATH = Path.home() / ".claude" / "hook-metrics.jsonl"


def emit_hook_metric(
    hook_name: str, duration_ms: float, status: str = "ok", **extra,
) -> None:
    """Write a structured metric entry to hook-metrics.jsonl (append)."""
    entry = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "hook": hook_name,
        "duration_ms": round(duration_ms, 1),
        "status": status,
    }
    entry.update(extra)
    try:
        HOOK_METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(HOOK_METRICS_PATH, "a") as f:
            f.write(json.dumps(entry, separators=(",", ":")) + "\n")
    except (IOError, OSError):
        pass


@contextmanager
def timed_hook(hook_name: str):
    """Context manager that times hook execution and emits metrics.

    Usage at script entry point:
        if __name__ == "__main__":
            with timed_hook("my-hook"):
                main()

    Handles SystemExit from sys.exit() gracefully.
    """
    metrics = {}
    start = time.monotonic()
    status = "ok"
    try:
        yield metrics
    except SystemExit as e:
        status = "ok" if e.code in (0, None) else "blocked"
        raise
    except Exception:
        status = "error"
        raise
    finally:
        duration_ms = (time.monotonic() - start) * 1000
        emit_hook_metric(hook_name, duration_ms, status, **metrics)
