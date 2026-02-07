#!/usr/bin/env python3
"""
Unified session state management for Claude Code hooks.

Replaces _state.py (670 lines, 8 state files, 13 mode checks) with a
single-file, task-agnostic state system:

- One state file: autonomous-state.json (replaces go/melt/appfix/burndown/
  episode/improve state files)
- Atomic writes via tempfile+fsync+rename (same pattern as _memory.py)
- PID-scoped for concurrent session isolation

Exports the same API surface consumed by surviving hooks (deploy-enforcer,
precompact-capture, doc-updater-async, skill-continuation-reminder).
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from _common import is_state_expired, is_pid_alive, log_debug


# State file name (replaces 8 per-skill files)
STATE_FILENAME = "autonomous-state.json"

# Legacy state files (for cleanup during transition)
LEGACY_STATE_FILES = [
    "go-state.json", "melt-state.json", "build-state.json",
    "forge-state.json", "appfix-state.json", "burndown-state.json",
    "episode-state.json", "improve-state.json",
]


# ============================================================================
# File Location
# ============================================================================


def _find_state_path(cwd: str) -> Path | None:
    """Find autonomous-state.json walking up the directory tree."""
    if not cwd:
        return None
    current = Path(cwd).resolve()
    home = Path.home()
    for _ in range(20):
        if current == home:
            break
        state_file = current / ".claude" / STATE_FILENAME
        if state_file.exists():
            return state_file
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None


def _load_state(path: Path) -> dict | None:
    """Load and parse a state JSON file."""
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, IOError, OSError):
        return None


def _atomic_write(path: Path, data: dict) -> bool:
    """Write JSON atomically via temp file + fsync + rename."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, str(path))
            return True
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            return False
    except (IOError, OSError):
        return False


# ============================================================================
# State Queries
# ============================================================================


def is_autonomous_mode_active(cwd: str, session_id: str = "") -> bool:
    """Check if any autonomous execution mode is active."""
    state, _ = get_autonomous_state(cwd, session_id)
    return state is not None


def get_autonomous_state(
    cwd: str, session_id: str = "",
) -> tuple[dict | None, str | None]:
    """Get the autonomous state and its mode type.

    Checks project-level first, then user-level.
    Filters expired states and validates session ownership.

    Returns (state_dict, mode_string) or (None, None).
    """
    # 1. Check project-level state
    project_state = _find_state_path(cwd)
    if project_state:
        state = _load_state(project_state)
        if state and not is_state_expired(state):
            return state, state.get("mode", "unknown")

    # 2. Check user-level state
    user_path = Path.home() / ".claude" / STATE_FILENAME
    if user_path.exists():
        state = _load_state(user_path)
        if state and not is_state_expired(state):
            # Validate session ownership
            if session_id:
                state_session = state.get("session_id", "")
                if state_session and state_session != session_id:
                    return None, None
            # Validate project origin
            origin = state.get("origin_project", "")
            if origin and cwd:
                try:
                    cwd_resolved = Path(cwd).resolve()
                    origin_resolved = Path(origin).resolve()
                    if not (
                        cwd_resolved == origin_resolved
                        or origin_resolved in cwd_resolved.parents
                    ):
                        return None, None
                except (ValueError, OSError):
                    return None, None
            return state, state.get("mode", "unknown")

    return None, None


def get_mode(cwd: str, session_id: str = "") -> str | None:
    """Get the current autonomous mode, or None if inactive."""
    _, mode = get_autonomous_state(cwd, session_id)
    return mode


# ============================================================================
# State Writes
# ============================================================================


def write_autonomous_state(
    cwd: str, mode: str, session_id: str = "", **kwargs,
) -> bool:
    """Create autonomous-state.json for the current session.

    Args:
        cwd: Project directory
        mode: Execution mode (go, melt, repair, burndown, episode, improve)
        session_id: Current session ID
        **kwargs: Additional fields (coordinator, allowed_prompts, etc.)
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    state = {
        "mode": mode,
        "started_at": now,
        "last_activity_at": now,
        "session_id": session_id,
        "pid": os.getpid(),
        "iteration": 1,
        "plan_mode_completed": mode == "go",  # /go skips planning
        "origin_project": str(Path(cwd).resolve()) if cwd else "",
        **kwargs,
    }

    # Write project-level
    project_path = Path(cwd) / ".claude" / STATE_FILENAME
    if not _atomic_write(project_path, state):
        return False

    # Write user-level (for cross-directory detection)
    user_path = Path.home() / ".claude" / STATE_FILENAME
    return _atomic_write(user_path, state)


# ============================================================================
# Cleanup
# ============================================================================


def cleanup_autonomous_state(cwd: str) -> list[str]:
    """Remove all autonomous state files (project + user level)."""
    deleted = []

    if cwd:
        state_path = Path(cwd) / ".claude" / STATE_FILENAME
        if state_path.exists():
            try:
                state_path.unlink()
                deleted.append(str(state_path))
            except OSError:
                pass

    user_path = Path.home() / ".claude" / STATE_FILENAME
    if user_path.exists():
        try:
            user_path.unlink()
            deleted.append(str(user_path))
        except OSError:
            pass

    deleted.extend(_cleanup_legacy_state_files(cwd))
    return deleted


def cleanup_expired_state(cwd: str, session_id: str = "") -> list[str]:
    """Remove expired or foreign-session state files."""
    deleted = []

    for path in _all_state_paths(cwd):
        if not path.exists():
            continue
        state = _load_state(path)
        if state is None or is_state_expired(state):
            try:
                path.unlink()
                deleted.append(str(path))
            except OSError:
                pass
        elif session_id:
            state_session = state.get("session_id", "")
            if state_session and state_session != session_id:
                try:
                    path.unlink()
                    deleted.append(str(path))
                except OSError:
                    pass

    deleted.extend(_cleanup_legacy_state_files(cwd))
    return deleted


def cleanup_checkpoint_only(cwd: str) -> list[str]:
    """Remove completion checkpoint files (PID-aware)."""
    deleted = []
    if not cwd:
        return deleted

    claude_dir = Path(cwd) / ".claude"
    if not claude_dir.exists():
        return deleted

    for checkpoint_path in claude_dir.glob("completion-checkpoint*.json"):
        name = checkpoint_path.name
        if name != "completion-checkpoint.json":
            try:
                pid_str = name.replace("completion-checkpoint.", "").replace(
                    ".json", ""
                )
                pid = int(pid_str)
                if is_pid_alive(pid):
                    continue
            except ValueError:
                pass

        try:
            checkpoint_path.unlink()
            deleted.append(str(checkpoint_path))
        except OSError:
            pass

    return deleted


def _all_state_paths(cwd: str) -> list[Path]:
    """Get all state file paths to check (project + user, unified + legacy)."""
    paths = []
    if cwd:
        claude_dir = Path(cwd) / ".claude"
        paths.append(claude_dir / STATE_FILENAME)
        for legacy in LEGACY_STATE_FILES:
            paths.append(claude_dir / legacy)
    user_dir = Path.home() / ".claude"
    paths.append(user_dir / STATE_FILENAME)
    for legacy in LEGACY_STATE_FILES:
        paths.append(user_dir / legacy)
    return paths


def _cleanup_legacy_state_files(cwd: str) -> list[str]:
    """Remove old per-skill state files from both project and user level."""
    deleted = []
    dirs_to_check = [Path.home() / ".claude"]
    if cwd:
        dirs_to_check.append(Path(cwd) / ".claude")
    for dir_path in dirs_to_check:
        for legacy in LEGACY_STATE_FILES:
            legacy_path = dir_path / legacy
            if legacy_path.exists():
                try:
                    legacy_path.unlink()
                    deleted.append(str(legacy_path))
                except OSError:
                    pass
    return deleted


# ============================================================================
# Checkpoint (simple operations, moved from _checkpoint.py)
# ============================================================================


def load_checkpoint(cwd: str) -> dict | None:
    """Load completion checkpoint file."""
    if not cwd:
        return None
    checkpoint_path = Path(cwd) / ".claude" / "completion-checkpoint.json"
    if checkpoint_path.exists():
        try:
            return json.loads(checkpoint_path.read_text())
        except (json.JSONDecodeError, IOError):
            return None
    return None


def save_checkpoint(cwd: str, checkpoint: dict) -> bool:
    """Save completion checkpoint file (atomic)."""
    if not cwd:
        return False
    path = Path(cwd) / ".claude" / "completion-checkpoint.json"
    return _atomic_write(path, checkpoint)


# ============================================================================
# Task Reset (sticky sessions)
# ============================================================================


def reset_state_for_next_task(cwd: str) -> bool:
    """Reset per-task fields for the next task iteration."""
    state_path = _find_state_path(cwd)
    if not state_path:
        return False

    state = _load_state(state_path)
    if not state:
        return False

    state["iteration"] = state.get("iteration", 1) + 1
    state["last_activity_at"] = datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    # /go keeps plan_mode_completed=True (skips planning by design)
    if state.get("mode") != "go":
        state["plan_mode_completed"] = False

    if not _atomic_write(state_path, state):
        return False

    # Update user-level timestamp
    user_path = Path.home() / ".claude" / STATE_FILENAME
    if user_path.exists():
        user_state = _load_state(user_path)
        if user_state:
            user_state["last_activity_at"] = state["last_activity_at"]
            _atomic_write(user_path, user_state)

    return True
