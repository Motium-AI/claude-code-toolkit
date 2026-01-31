#!/usr/bin/env python3
"""
State file management for Claude Code hooks.

Handles loading, saving, and cleanup of autonomous mode state files,
mode detection (is_appfix_active, is_build_active, etc.), and
state file lifecycle operations.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from _common import is_state_expired, is_state_for_session


# ============================================================================
# State File Location
# ============================================================================


def _find_state_file_path(cwd: str, filename: str) -> Path | None:
    """Find the path to a state file in .claude/ directory tree.

    Walks up the directory tree to find the state file,
    similar to how git finds the .git directory.

    Stops at the home directory to avoid picking up unrelated
    state files from ~/.claude/.

    Args:
        cwd: Current working directory path
        filename: Name of the state file (e.g., 'build-state.json')

    Returns:
        Path to state file if found, None otherwise
    """
    if cwd:
        current = Path(cwd).resolve()
        home = Path.home()
        for _ in range(20):
            if current == home:
                break
            claude_dir = current / ".claude"
            if claude_dir.exists():
                state_file = claude_dir / filename
                if state_file.exists():
                    return state_file
            parent = current.parent
            if parent == current:
                break
            current = parent
    return None


def _is_cwd_under_origin(cwd: str, user_state: dict, session_id: str = "") -> bool:
    """Check if cwd is under the origin_project from user-level state.

    Prevents user-level state from one project affecting unrelated projects.

    EXCEPTION: If session_id matches, trust the session regardless of directory.
    """
    # MULTI-SESSION: Check if session_id exists in sessions dict
    sessions = user_state.get("sessions", {})
    if session_id and session_id in sessions:
        session_info = sessions[session_id]
        return not is_state_expired(session_info)

    # LEGACY: Trust matching session
    if session_id and user_state.get("session_id") == session_id:
        return True

    origin = user_state.get("origin_project")
    if not origin:
        return True

    try:
        cwd_resolved = Path(cwd).resolve()
        origin_resolved = Path(origin).resolve()
        return cwd_resolved == origin_resolved or origin_resolved in cwd_resolved.parents
    except (ValueError, OSError):
        return False


# ============================================================================
# State File Operations
# ============================================================================


def load_state_file(cwd: str, filename: str) -> dict | None:
    """Load and parse a state file from .claude/ directory tree."""
    state_path = _find_state_file_path(cwd, filename)
    if state_path:
        try:
            return json.loads(state_path.read_text())
        except (json.JSONDecodeError, IOError):
            return None
    return None


def update_state_file(cwd: str, filename: str, updates: dict) -> bool:
    """Update a state file with new values (merge, not replace)."""
    state_path = _find_state_file_path(cwd, filename)
    if not state_path:
        return False

    try:
        state = json.loads(state_path.read_text())
        state.update(updates)
        state_path.write_text(json.dumps(state, indent=2))
        return True
    except (json.JSONDecodeError, IOError):
        return False


# ============================================================================
# Mode Status Checks
# ============================================================================


def is_repair_active(cwd: str, session_id: str = "") -> bool:
    """Check if repair mode is active (unified debugging - web or mobile).

    This is the PRIMARY function to check for debugging mode.
    Internally uses appfix-state.json for backwards compatibility.
    """
    return is_appfix_active(cwd, session_id)


def is_appfix_active(cwd: str, session_id: str = "") -> bool:
    """Check if appfix mode is active via state file or env var."""
    state = load_state_file(cwd, "appfix-state.json")
    if state and not is_state_expired(state):
        return True

    user_state_path = Path.home() / ".claude" / "appfix-state.json"
    if user_state_path.exists():
        try:
            user_state = json.loads(user_state_path.read_text())
            if not is_state_expired(user_state) and _is_cwd_under_origin(cwd, user_state, session_id):
                return True
        except (json.JSONDecodeError, IOError):
            pass

    if os.environ.get("APPFIX_ACTIVE", "").lower() in ("true", "1", "yes"):
        return True

    return False


def is_mobileappfix_active(cwd: str, session_id: str = "") -> bool:
    """Check if mobileappfix mode is active (mobile variant)."""
    if not is_appfix_active(cwd, session_id):
        return False

    state = load_state_file(cwd, "appfix-state.json")
    if state and state.get("skill_type") == "mobile":
        return True

    user_state_path = Path.home() / ".claude" / "appfix-state.json"
    if user_state_path.exists():
        try:
            user_state = json.loads(user_state_path.read_text())
            if user_state.get("skill_type") == "mobile" and _is_cwd_under_origin(cwd, user_state, session_id):
                return True
        except (json.JSONDecodeError, IOError):
            pass

    return False


def is_build_active(cwd: str, session_id: str = "") -> bool:
    """Check if build mode is active via state file or env var."""
    for state_filename in ("build-state.json", "forge-state.json"):
        state = load_state_file(cwd, state_filename)
        if state and not is_state_expired(state):
            return True

    for state_filename in ("build-state.json", "forge-state.json"):
        user_state_path = Path.home() / ".claude" / state_filename
        if user_state_path.exists():
            try:
                user_state = json.loads(user_state_path.read_text())
                if not is_state_expired(user_state) and _is_cwd_under_origin(cwd, user_state, session_id):
                    return True
            except (json.JSONDecodeError, IOError):
                pass

    if os.environ.get("BUILD_ACTIVE", "").lower() in ("true", "1", "yes"):
        return True
    if os.environ.get("FORGE_ACTIVE", "").lower() in ("true", "1", "yes"):
        return True

    return False


# Backward compatibility aliases
def is_forge_active(cwd: str, session_id: str = "") -> bool:
    """Deprecated: Use is_build_active() instead."""
    return is_build_active(cwd, session_id)


def is_godo_active(cwd: str, session_id: str = "") -> bool:
    """Deprecated: Use is_build_active() instead."""
    return is_build_active(cwd, session_id)


def is_burndown_active(cwd: str, session_id: str = "") -> bool:
    """Check if burndown mode is active via state file or env var."""
    state = load_state_file(cwd, "burndown-state.json")
    if state and not is_state_expired(state):
        return True

    user_state_path = Path.home() / ".claude" / "burndown-state.json"
    if user_state_path.exists():
        try:
            user_state = json.loads(user_state_path.read_text())
            if not is_state_expired(user_state) and _is_cwd_under_origin(cwd, user_state, session_id):
                return True
        except (json.JSONDecodeError, IOError):
            pass

    if os.environ.get("BURNDOWN_ACTIVE", "").lower() in ("true", "1", "yes"):
        return True

    return False


def is_episode_active(cwd: str, session_id: str = "") -> bool:
    """Check if episode generation mode is active via state file or env var."""
    state = load_state_file(cwd, "episode-state.json")
    if state and not is_state_expired(state):
        return True

    user_state_path = Path.home() / ".claude" / "episode-state.json"
    if user_state_path.exists():
        try:
            user_state = json.loads(user_state_path.read_text())
            if not is_state_expired(user_state) and _is_cwd_under_origin(cwd, user_state, session_id):
                return True
        except (json.JSONDecodeError, IOError):
            pass

    if os.environ.get("EPISODE_ACTIVE", "").lower() in ("true", "1", "yes"):
        return True

    return False


def is_go_active(cwd: str, session_id: str = "") -> bool:
    """Check if /go fast execution mode is active via state file or env var.

    /go is a lightweight, speed-optimized version of /build that skips
    the mandatory Lite Heavy planning phase.
    """
    state = load_state_file(cwd, "go-state.json")
    if state and not is_state_expired(state):
        return True

    user_state_path = Path.home() / ".claude" / "go-state.json"
    if user_state_path.exists():
        try:
            user_state = json.loads(user_state_path.read_text())
            if not is_state_expired(user_state) and _is_cwd_under_origin(cwd, user_state, session_id):
                return True
        except (json.JSONDecodeError, IOError):
            pass

    if os.environ.get("GO_ACTIVE", "").lower() in ("true", "1", "yes"):
        return True

    return False


def is_autonomous_mode_active(cwd: str, session_id: str = "") -> bool:
    """Check if any autonomous execution mode is active (go, build, repair, burndown, or episode).

    This is the unified check for enabling auto-approval hooks.
    """
    return (
        is_go_active(cwd, session_id)
        or is_build_active(cwd, session_id)
        or is_repair_active(cwd, session_id)
        or is_burndown_active(cwd, session_id)
        or is_episode_active(cwd, session_id)
    )


def get_autonomous_state(cwd: str, session_id: str = "") -> tuple[dict | None, str | None]:
    """Get the autonomous mode state file and its type, filtering expired.

    Checks go-state first (fast mode), then build-state, appfix-state (repair), burndown-state, episode-state.
    Checks both project-level AND user-level state files.

    Returns:
        Tuple of (state_dict, state_type) where state_type is 'go', 'build', 'repair', 'burndown', or 'episode'
        Returns (None, None) if no state file found or all expired
    """
    # Check /go first (takes precedence as fast mode)
    go_state = load_state_file(cwd, "go-state.json")
    if go_state and not is_state_expired(go_state):
        return go_state, "go"

    for build_filename in ("build-state.json", "forge-state.json"):
        build_state = load_state_file(cwd, build_filename)
        if build_state and not is_state_expired(build_state):
            return build_state, "build"

    appfix_state = load_state_file(cwd, "appfix-state.json")
    if appfix_state and not is_state_expired(appfix_state):
        return appfix_state, "repair"

    burndown_state = load_state_file(cwd, "burndown-state.json")
    if burndown_state and not is_state_expired(burndown_state):
        return burndown_state, "burndown"

    episode_state = load_state_file(cwd, "episode-state.json")
    if episode_state and not is_state_expired(episode_state):
        return episode_state, "episode"

    for filename, state_type in [
        ("go-state.json", "go"),
        ("build-state.json", "build"),
        ("forge-state.json", "build"),
        ("appfix-state.json", "repair"),
        ("burndown-state.json", "burndown"),
        ("episode-state.json", "episode"),
    ]:
        user_path = Path.home() / ".claude" / filename
        if user_path.exists():
            try:
                user_state = json.loads(user_path.read_text())
                if not is_state_expired(user_state) and _is_cwd_under_origin(cwd, user_state, session_id):
                    return user_state, state_type
            except (json.JSONDecodeError, IOError):
                pass

    return None, None


# ============================================================================
# Cleanup Operations
# ============================================================================


def cleanup_autonomous_state(cwd: str) -> list[str]:
    """Clean up ALL autonomous mode state files.

    Removes state files from:
    1. User-level (~/.claude/)
    2. ALL .claude/ directories walking UP from cwd
    """
    deleted = []
    state_files = ["go-state.json", "appfix-state.json", "build-state.json", "forge-state.json", "burndown-state.json", "episode-state.json"]

    # 1. Clean user-level state
    user_claude_dir = Path.home() / ".claude"
    for filename in state_files:
        user_state = user_claude_dir / filename
        if user_state.exists():
            try:
                user_state.unlink()
                deleted.append(str(user_state))
            except (IOError, OSError):
                pass

    # 2. Walk UP directory tree and clean project-level state files
    if cwd:
        current = Path(cwd).resolve()
        for _ in range(20):
            claude_dir = current / ".claude"
            if claude_dir.exists():
                for filename in state_files:
                    state_file = claude_dir / filename
                    if state_file.exists():
                        try:
                            state_file.unlink()
                            deleted.append(str(state_file))
                        except (IOError, OSError):
                            pass
            parent = current.parent
            if parent == current:
                break
            current = parent

    return deleted


def _cleanup_user_level_sessions(state_path: Path) -> bool:
    """Clean up expired sessions from user-level state file.

    MULTI-SESSION SUPPORT: Instead of deleting the whole file, remove
    individual expired sessions from the sessions dict.

    Returns:
        True if file was deleted (all sessions expired), False otherwise
    """
    try:
        state = json.loads(state_path.read_text())
    except (json.JSONDecodeError, IOError):
        try:
            state_path.unlink()
            return True
        except (IOError, OSError):
            return False

    sessions = state.get("sessions", {})
    if sessions:
        valid_sessions = {}
        for session_id, session_info in sessions.items():
            if not is_state_expired(session_info):
                valid_sessions[session_id] = session_info

        if not valid_sessions:
            try:
                state_path.unlink()
                return True
            except (IOError, OSError):
                return False
        elif len(valid_sessions) < len(sessions):
            state["sessions"] = valid_sessions
            try:
                state_path.write_text(json.dumps(state, indent=2))
            except (IOError, OSError):
                pass
        return False

    if is_state_expired(state):
        try:
            state_path.unlink()
            return True
        except (IOError, OSError):
            return False

    return False


def cleanup_expired_state(cwd: str, current_session_id: str = "") -> list[str]:
    """Delete state files that are expired OR belong to a different session.

    Called at SessionStart to clean up stale state from previous sessions.
    """
    deleted = []
    state_files = ["go-state.json", "appfix-state.json", "build-state.json", "forge-state.json", "burndown-state.json", "episode-state.json"]

    def _should_clean(state_path: Path) -> bool:
        try:
            state = json.loads(state_path.read_text())
        except (json.JSONDecodeError, IOError):
            return True
        if is_state_expired(state):
            return True
        if current_session_id and not is_state_for_session(state, current_session_id):
            return True
        return False

    # 1. Clean user-level state (multi-session aware)
    user_claude_dir = Path.home() / ".claude"
    for filename in state_files:
        user_state = user_claude_dir / filename
        if user_state.exists():
            if _cleanup_user_level_sessions(user_state):
                deleted.append(str(user_state))

    # 2. Walk UP directory tree and clean project-level state files
    if cwd:
        current = Path(cwd).resolve()
        home = Path.home()
        for _ in range(20):
            if current == home:
                break
            claude_dir = current / ".claude"
            if claude_dir.exists():
                for filename in state_files:
                    state_file = claude_dir / filename
                    if state_file.exists() and _should_clean(state_file):
                        try:
                            state_file.unlink()
                            deleted.append(str(state_file))
                        except (IOError, OSError):
                            pass
            parent = current.parent
            if parent == current:
                break
            current = parent

    return deleted


def cleanup_checkpoint_only(cwd: str) -> list[str]:
    """Delete ONLY the completion checkpoint file. Leave mode state intact.

    This is the sticky session replacement for cleanup_autonomous_state
    at task boundaries.
    """
    deleted = []
    if not cwd:
        return deleted

    claude_dir = Path(cwd) / ".claude"
    if not claude_dir.exists():
        return deleted

    checkpoint_path = claude_dir / "completion-checkpoint.json"
    if checkpoint_path.exists():
        try:
            checkpoint_path.unlink()
            deleted.append(str(checkpoint_path))
        except (IOError, OSError):
            pass

    return deleted


def reset_state_for_next_task(cwd: str) -> bool:
    """Reset per-task fields in the autonomous state file for the next task.

    Increments iteration, resets plan_mode_completed, updates last_activity_at,
    clears per-task fields. Does NOT delete the state file (sticky session behavior).

    NOTE: For /go mode, plan_mode_completed is NOT reset (it stays true)
    because /go skips the planning phase by design.
    """
    for filename in ("go-state.json", "build-state.json", "forge-state.json", "appfix-state.json", "burndown-state.json", "episode-state.json"):
        state_path = _find_state_file_path(cwd, filename)
        if state_path:
            try:
                state = json.loads(state_path.read_text())
                state["iteration"] = state.get("iteration", 1) + 1
                # /go mode keeps plan_mode_completed=True (skips planning by design)
                if filename != "go-state.json":
                    state["plan_mode_completed"] = False
                state["verification_evidence"] = None
                state["services"] = {}
                state["last_activity_at"] = datetime.now(timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                )
                state_path.write_text(json.dumps(state, indent=2))

                # Also update user-level state timestamp
                session_id = state.get("session_id", "")
                user_state_path = Path.home() / ".claude" / filename
                if user_state_path.exists():
                    try:
                        user_state = json.loads(user_state_path.read_text())
                        user_state["last_activity_at"] = state["last_activity_at"]
                        user_state["plan_mode_completed"] = False

                        if session_id and "sessions" in user_state:
                            sessions = user_state.get("sessions", {})
                            if session_id in sessions:
                                sessions[session_id]["last_activity_at"] = state["last_activity_at"]
                                sessions[session_id]["plan_mode_completed"] = False

                        user_state_path.write_text(json.dumps(user_state, indent=2))
                    except (json.JSONDecodeError, IOError):
                        pass

                return True
            except (json.JSONDecodeError, IOError):
                return False
    return False
