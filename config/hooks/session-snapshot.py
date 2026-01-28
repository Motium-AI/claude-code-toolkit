#!/usr/bin/env python3
"""
Session Start Hook - Snapshot Git Diff State + Session Guard

Creates .claude/session-snapshot.json with the git diff hash at session start.
The stop hook compares against this to detect if THIS session made changes.

Session Guard:
- Claims session ownership via .claude/session-owner.json
- Detects concurrent Claude instances in the same directory
- Warns (but doesn't block) if another live session is detected
- Takes over from dead sessions silently

Expired State Cleanup:
- At session start, cleans up expired or foreign-session autonomous state files
- This is the session boundary cleanup for sticky session mode

This solves the "pre-existing changes" loop:
- Session A makes changes but doesn't commit
- Session B (research-only) starts and saves the current diff hash
- Session B stops - diff hash unchanged, so no checkpoint required
- Without this, Session B would be blocked because git diff shows changes from A
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add hooks directory to path for shared imports
sys.path.insert(0, str(Path(__file__).parent))

from _common import (
    get_diff_hash,
    cleanup_expired_state,
    is_pid_alive,
    _get_ancestor_pid,
    log_debug,
)


def _check_and_claim_session_ownership(cwd: str, session_id: str) -> None:
    """Check for concurrent sessions and claim ownership.

    Loads .claude/session-owner.json and checks:
    - Same session_id → no action (resuming)
    - Different session_id + PID alive → print warning to stdout
    - Different session_id + PID dead → take over silently
    - No file → claim ownership

    Writes new owner data: {session_id, pid, started_at}

    Args:
        cwd: Working directory containing .claude/
        session_id: Current session's ID
    """
    if not cwd or not session_id:
        return

    owner_path = Path(cwd) / ".claude" / "session-owner.json"
    owner_path.parent.mkdir(parents=True, exist_ok=True)

    # Check existing owner
    if owner_path.exists():
        try:
            existing = json.loads(owner_path.read_text())
            existing_session = existing.get("session_id", "")
            existing_pid = existing.get("pid", 0)

            if existing_session == session_id:
                # Same session resuming - just update PID
                pass
            elif existing_pid and is_pid_alive(existing_pid):
                # Different session, still alive - warn
                print(
                    f"[session-guard] WARNING: Another Claude session is active "
                    f"in this directory (PID {existing_pid}, session "
                    f"{existing_session[:8]}...). State files may conflict."
                )
                log_debug(
                    f"Concurrent session detected: PID {existing_pid} alive",
                    hook_name="session-snapshot",
                    parsed_data={
                        "existing_session": existing_session,
                        "existing_pid": existing_pid,
                        "new_session": session_id,
                    },
                )
            else:
                # Previous session died - take over silently
                log_debug(
                    f"Taking over from dead session (PID {existing_pid})",
                    hook_name="session-snapshot",
                    parsed_data={
                        "dead_session": existing_session,
                        "dead_pid": existing_pid,
                        "new_session": session_id,
                    },
                )
        except (json.JSONDecodeError, IOError):
            pass  # Corrupt file - overwrite

    # Claim ownership
    owner_data = {
        "session_id": session_id,
        "pid": _get_ancestor_pid(),
        "started_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    try:
        owner_path.write_text(json.dumps(owner_data, indent=2))
    except IOError as e:
        log_debug(
            f"Failed to write session-owner.json: {e}",
            hook_name="session-snapshot",
        )


def main():
    input_data = json.loads(sys.stdin.read() or "{}")
    cwd = input_data.get("cwd", "")
    session_id = input_data.get("session_id", "")

    if not cwd:
        sys.exit(0)

    # 1. Create session snapshot
    snapshot_path = Path(cwd) / ".claude" / "session-snapshot.json"
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)

    snapshot = {
        "diff_hash_at_start": get_diff_hash(cwd),
        "session_started_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "session_id": session_id,
    }

    snapshot_path.write_text(json.dumps(snapshot, indent=2))

    # 2. Session guard - check and claim ownership
    _check_and_claim_session_ownership(cwd, session_id)

    # 3. Clean up expired/foreign-session autonomous state files
    deleted = cleanup_expired_state(cwd, session_id)
    if deleted:
        log_debug(
            "Cleaned up expired/foreign state at session start",
            hook_name="session-snapshot",
            parsed_data={"deleted": deleted},
        )
        print(
            f"[session-snapshot] Cleaned up {len(deleted)} expired state file(s) "
            f"from previous session."
        )

    # 4. Garbage collect stale worktrees (from crashed coordinators)
    try:
        from worktree_manager import gc_worktrees

        gc_cleaned = gc_worktrees(ttl_hours=8)
        if gc_cleaned:
            log_debug(
                "Garbage collected stale worktrees",
                hook_name="session-snapshot",
                parsed_data={"cleaned": gc_cleaned},
            )
            print(f"[session-snapshot] Cleaned up {len(gc_cleaned)} stale worktree(s).")
    except ImportError:
        pass  # worktree-manager not available

    sys.exit(0)


if __name__ == "__main__":
    main()
