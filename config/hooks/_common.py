#!/usr/bin/env python3
"""
Shared utilities for Claude Code hooks.

This module contains common functions used across multiple hooks to avoid duplication.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path


# TTL for autonomous mode state files (hours).
# State older than this is considered expired and cleaned up.
SESSION_TTL_HOURS = 8


# Files/patterns excluded from version tracking (dirty calculation)
# These don't represent code changes requiring re-deployment
# IMPORTANT: Use both root and nested patterns for directories like .claude/
# because :(exclude).claude/ only matches at root, not nested paths
VERSION_TRACKING_EXCLUSIONS = [
    # Base path required for exclude patterns to work correctly
    ".",
    # .claude directory at any depth (checkpoint files, state files)
    # Use ** for recursive matching across directory boundaries
    # (single * only matches one path component, missing nested paths like config/hooks/.claude/)
    ":(exclude).claude",
    ":(exclude).claude/**",
    ":(exclude)**/.claude",
    ":(exclude)**/.claude/**",
    # Lock files
    ":(exclude)*.lock",
    ":(exclude)package-lock.json",
    ":(exclude)yarn.lock",
    ":(exclude)pnpm-lock.yaml",
    ":(exclude)poetry.lock",
    ":(exclude)Pipfile.lock",
    ":(exclude)Cargo.lock",
    # Git metadata
    ":(exclude).gitmodules",
    # Python artifacts
    ":(exclude)*.pyc",
    ":(exclude)__pycache__",
    ":(exclude)*/__pycache__",
    # Environment and logs
    ":(exclude).env*",
    ":(exclude)*.log",
    # OS and editor artifacts
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
# PID-Based Session Scoping
# ============================================================================


def get_session_pid() -> int:
    """Get the Claude Code ancestor PID for this session.

    PID is the key for session-scoped state files because it:
    - Is unique across parallel Claude agents (OS guarantee)
    - Persists through context compaction (same process)
    - Is discoverable from any hook via process tree walking

    Returns:
        Claude Code process PID
    """
    return _get_ancestor_pid()


def _scoped_filename(filename: str, pid: int | None = None) -> str:
    """Convert a state filename to its PID-scoped version.

    Examples:
        'build-state.json' → 'build-state.12345.json'
        'completion-checkpoint.json' → 'completion-checkpoint.12345.json'

    Args:
        filename: Original filename (e.g., 'build-state.json')
        pid: PID to scope to (default: current session PID)

    Returns:
        PID-scoped filename
    """
    if pid is None:
        pid = get_session_pid()
    base, ext = os.path.splitext(filename)
    return f"{base}.{pid}{ext}"


def _extract_pid_from_filename(filename: str) -> int | None:
    """Extract PID from a PID-scoped filename.

    Examples:
        'build-state.12345.json' → 12345
        'build-state.json' → None (legacy, no PID)

    Args:
        filename: Filename (stem or full name)

    Returns:
        PID if found, None otherwise
    """
    stem = Path(filename).stem
    parts = stem.rsplit(".", 1)
    if len(parts) == 2:
        try:
            return int(parts[1])
        except ValueError:
            return None
    return None


def _find_any_scoped_state_files(cwd: str, base_name: str) -> list[Path]:
    """Find all PID-scoped state files matching a base name pattern.

    Used for session-agnostic checks (e.g., "is ANY build session active?").

    Args:
        cwd: Directory containing .claude/
        base_name: Base name without extension (e.g., 'build-state')

    Returns:
        List of matching Path objects, sorted by modification time (newest first)
    """
    results = []
    if not cwd:
        return results

    claude_dir = Path(cwd) / ".claude"
    if not claude_dir.exists():
        return results

    # Match pattern: {base_name}.{digits}.json
    for f in claude_dir.glob(f"{base_name}.*.json"):
        pid = _extract_pid_from_filename(f.name)
        if pid is not None:
            results.append(f)

    # Sort by modification time, newest first
    results.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return results


def get_diff_hash(cwd: str = "") -> str:
    """
    Get hash of current git diff (excluding metadata files).

    Used to detect if THIS session made changes by comparing against
    the snapshot taken at session start.

    Excludes lock files, IDE config, .claude/, and other non-code files
    that shouldn't affect version tracking.

    Args:
        cwd: Working directory for git command

    Returns:
        12-character hash of the diff, or "unknown" on error
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
    """
    Get current code version (git HEAD + dirty indicator).

    Returns format:
    - "abc1234" - clean commit
    - "abc1234-dirty" - commit with uncommitted changes (no hash suffix)
    - "unknown" - not a git repo or error

    NOTE: The dirty indicator is boolean, NOT a hash. This ensures version
    stability during development - version only changes at commit boundaries,
    not on every file edit. This prevents checkpoint invalidation loops.

    Excludes metadata files (lock files, IDE config, .claude/, etc.) from
    dirty calculation.

    Args:
        cwd: Working directory for git command

    Returns:
        Version string
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
        # Return stable version - no hash suffix for dirty state
        # This prevents version from changing on every edit
        if diff.stdout.strip():
            return f"{head_hash}-dirty"

        return head_hash
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return "unknown"


def log_debug(
    message: str,
    hook_name: str = "unknown",
    raw_input: str = "",
    parsed_data: dict | None = None,
    error: Exception | None = None,
) -> None:
    """Log diagnostic info for debugging hook issues.

    Args:
        message: Description of what happened
        hook_name: Name of the calling hook
        raw_input: Raw stdin content (optional)
        parsed_data: Parsed JSON data (optional)
        error: Exception that occurred (optional)
    """
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


def _check_state_file(cwd: str, filename: str) -> bool:
    """Check if a state file exists in .claude/ directory tree.

    Walks up the directory tree to find the state file,
    similar to how git finds the .git directory.

    Checks PID-scoped filename first, then falls back to legacy unscoped name.
    Also checks for ANY PID-scoped file matching the base name (for multi-agent).

    IMPORTANT: Stops at the home directory to avoid picking up unrelated
    state files from ~/.claude/ which is meant for global config, not
    project-specific state.

    Args:
        cwd: Current working directory path
        filename: Name of the state file (e.g., 'appfix-state.json')

    Returns:
        True if state file exists, False otherwise
    """
    if cwd:
        current = Path(cwd).resolve()
        home = Path.home()
        base_name = Path(filename).stem  # e.g., 'build-state'
        # Walk up to home directory (max 20 levels to prevent infinite loops)
        for _ in range(20):
            # Stop at home directory - ~/.claude/ is for global config, not project state
            if current == home:
                break
            claude_dir = current / ".claude"
            if claude_dir.exists():
                # 1. Check PID-scoped file for this session
                scoped = claude_dir / _scoped_filename(filename)
                if scoped.exists():
                    return True
                # 2. Check any PID-scoped file (another active agent)
                if _find_any_scoped_state_files(str(current), base_name):
                    return True
                # 3. Fall back to legacy unscoped file
                legacy = claude_dir / filename
                if legacy.exists():
                    return True
            parent = current.parent
            if parent == current:  # Reached filesystem root
                break
            current = parent
    return False



def _is_cwd_under_origin(cwd: str, user_state: dict, session_id: str = "") -> bool:
    """Check if cwd is under the origin_project directory from user-level state.

    User-level state files store an origin_project field indicating which project
    created the state. This function checks if the current working directory is
    the same as or a subdirectory of that origin project.

    This prevents user-level state from one project affecting unrelated projects.

    EXCEPTION: If session_id is provided and matches the state's session_id,
    trust the session regardless of directory. This allows a session to work
    across directories (e.g., navigating to a test directory during appfix).

    MULTI-SESSION SUPPORT: User-level state may have a "sessions" dict that maps
    session_id to session info. If session_id is found in sessions, trust it.

    Args:
        cwd: Current working directory path
        user_state: Parsed user-level state file dict
        session_id: Current session ID (optional, for cross-directory trust)

    Returns:
        True if cwd is under origin_project (or origin_project not set), False otherwise
    """
    # MULTI-SESSION: Check if session_id exists in sessions dict
    # This is the new format that supports multiple parallel sessions
    sessions = user_state.get("sessions", {})
    if session_id and session_id in sessions:
        session_info = sessions[session_id]
        # Check TTL for this specific session
        # If session is found but expired, return False immediately
        # (don't fall through to legacy checks)
        return not is_state_expired(session_info)

    # LEGACY: Trust matching session - same session can work anywhere
    # This enables cross-directory workflows (e.g., appfix navigating to test dirs)
    # Only applies if session_id was NOT found in the new sessions dict
    if session_id and user_state.get("session_id") == session_id:
        return True

    origin = user_state.get("origin_project")
    if not origin:
        # No origin recorded - backward compatibility, allow it
        return True

    try:
        cwd_resolved = Path(cwd).resolve()
        origin_resolved = Path(origin).resolve()
        # Check if cwd is origin or a subdirectory of origin
        return cwd_resolved == origin_resolved or origin_resolved in cwd_resolved.parents
    except (ValueError, OSError):
        return False


def is_repair_active(cwd: str, session_id: str = "") -> bool:
    """Check if repair mode is active (unified debugging - web or mobile).

    This is the PRIMARY function to check for debugging mode.
    Internally uses appfix-state.json for backwards compatibility.

    For web vs mobile distinction, use is_mobileappfix_active().

    Args:
        cwd: Current working directory path
        session_id: Current session ID (optional, for cross-directory trust)

    Returns:
        True if repair mode is active (web OR mobile), False otherwise
    """
    return is_appfix_active(cwd, session_id)


def is_appfix_active(cwd: str, session_id: str = "") -> bool:
    """Check if appfix mode is active via non-expired state file or env var.

    NOTE: Prefer using is_repair_active() for new code. This function exists
    for backwards compatibility.

    Loads the state file and checks TTL expiry. Expired state files are
    treated as inactive (cleaned up at next SessionStart).

    Checks PID-scoped files first (via load_state_file → _find_state_file_path),
    then user-level, then env var.

    Args:
        cwd: Current working directory path
        session_id: Current session ID (optional, for cross-directory trust)

    Returns:
        True if appfix mode is active and not expired, False otherwise
    """
    # Check project-level state with TTL (handles PID-scoped + legacy)
    state = load_state_file(cwd, "appfix-state.json")
    if state and not is_state_expired(state):
        return True

    # Check user-level state with TTL and origin/session check
    user_state_path = Path.home() / ".claude" / "appfix-state.json"
    if user_state_path.exists():
        try:
            user_state = json.loads(user_state_path.read_text())
            if not is_state_expired(user_state) and _is_cwd_under_origin(cwd, user_state, session_id):
                return True
        except (json.JSONDecodeError, IOError):
            pass

    # Fallback: Check environment variable (no TTL for env vars)
    if os.environ.get("APPFIX_ACTIVE", "").lower() in ("true", "1", "yes"):
        return True

    return False


def is_mobileappfix_active(cwd: str, session_id: str = "") -> bool:
    """Check if mobileappfix mode is active (mobile variant of appfix).

    Checks if appfix mode is active AND the skill_type is 'mobile'.

    Args:
        cwd: Current working directory path
        session_id: Current session ID (optional, for cross-directory trust)

    Returns:
        True if mobileappfix mode is active, False otherwise
    """
    if not is_appfix_active(cwd, session_id):
        return False

    # Check project-level state for skill_type
    state = load_state_file(cwd, "appfix-state.json")
    if state and state.get("skill_type") == "mobile":
        return True

    # Check user-level state
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
    """Check if build mode is active via non-expired state file or env var.

    Loads the state file and checks TTL expiry. Expired state files are
    treated as inactive (cleaned up at next SessionStart).

    Checks PID-scoped files first (via load_state_file → _find_state_file_path),
    then user-level, then env var.

    Args:
        cwd: Current working directory path
        session_id: Current session ID (optional, for cross-directory trust)

    Returns:
        True if build mode is active and not expired, False otherwise
    """
    # Check project-level state with TTL (handles PID-scoped + legacy)
    # Check build-state.json first, fall back to forge-state.json for backward compat
    for state_filename in ("build-state.json", "forge-state.json"):
        state = load_state_file(cwd, state_filename)
        if state and not is_state_expired(state):
            return True

    # Check user-level state with TTL and origin/session check
    for state_filename in ("build-state.json", "forge-state.json"):
        user_state_path = Path.home() / ".claude" / state_filename
        if user_state_path.exists():
            try:
                user_state = json.loads(user_state_path.read_text())
                if not is_state_expired(user_state) and _is_cwd_under_origin(cwd, user_state, session_id):
                    return True
            except (json.JSONDecodeError, IOError):
                pass

    # Fallback: Check environment variable (no TTL for env vars)
    if os.environ.get("BUILD_ACTIVE", "").lower() in ("true", "1", "yes"):
        return True
    # Legacy env var fallback
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
    """Check if burndown mode is active via non-expired state file or env var.

    Loads the state file and checks TTL expiry. Expired state files are
    treated as inactive (cleaned up at next SessionStart).

    Args:
        cwd: Current working directory path
        session_id: Current session ID (optional, for cross-directory trust)

    Returns:
        True if burndown mode is active and not expired, False otherwise
    """
    # Check project-level state with TTL (handles PID-scoped + legacy)
    state = load_state_file(cwd, "burndown-state.json")
    if state and not is_state_expired(state):
        return True

    # Check user-level state with TTL and origin/session check
    user_state_path = Path.home() / ".claude" / "burndown-state.json"
    if user_state_path.exists():
        try:
            user_state = json.loads(user_state_path.read_text())
            if not is_state_expired(user_state) and _is_cwd_under_origin(cwd, user_state, session_id):
                return True
        except (json.JSONDecodeError, IOError):
            pass

    # Fallback: Check environment variable (no TTL for env vars)
    if os.environ.get("BURNDOWN_ACTIVE", "").lower() in ("true", "1", "yes"):
        return True

    return False


def is_autonomous_mode_active(cwd: str, session_id: str = "") -> bool:
    """Check if any autonomous execution mode is active (build, repair, or burndown).

    This is the unified check for enabling auto-approval hooks.
    Recognizes /build, /repair (/appfix, /mobileappfix), and /burndown modes.

    Args:
        cwd: Current working directory path
        session_id: Current session ID (optional, for cross-directory trust)

    Returns:
        True if build OR repair OR burndown mode is active, False otherwise
    """
    return is_build_active(cwd, session_id) or is_repair_active(cwd, session_id) or is_burndown_active(cwd, session_id)


def _find_state_file_path(cwd: str, filename: str) -> Path | None:
    """Find the path to a state file in .claude/ directory tree.

    Walks up the directory tree to find the state file,
    similar to how git finds the .git directory.

    Checks in this order at each directory level:
    1. PID-scoped file for this session (e.g., build-state.12345.json)
    2. Any PID-scoped file with a live PID (another active agent)
    3. Legacy unscoped file (e.g., build-state.json)

    IMPORTANT: Stops at the home directory to avoid picking up unrelated
    state files from ~/.claude/ which is meant for global config, not
    project-specific state.

    Args:
        cwd: Current working directory path
        filename: Name of the state file (e.g., 'build-state.json')

    Returns:
        Path to state file if found, None otherwise
    """
    if cwd:
        current = Path(cwd).resolve()
        home = Path.home()
        base_name = Path(filename).stem  # e.g., 'build-state'
        # Walk up to home directory (max 20 levels to prevent infinite loops)
        for _ in range(20):
            # Stop at home directory - ~/.claude/ is for global config, not project state
            if current == home:
                break
            claude_dir = current / ".claude"
            if claude_dir.exists():
                # 1. Check PID-scoped file for this session
                scoped = claude_dir / _scoped_filename(filename)
                if scoped.exists():
                    return scoped
                # 2. Check any PID-scoped file with live PID
                scoped_files = _find_any_scoped_state_files(str(current), base_name)
                for sf in scoped_files:
                    pid = _extract_pid_from_filename(sf.name)
                    if pid is not None and is_pid_alive(pid):
                        return sf
                # 3. Fall back to legacy unscoped file
                legacy = claude_dir / filename
                if legacy.exists():
                    return legacy
            parent = current.parent
            if parent == current:  # Reached filesystem root
                break
            current = parent
    return None


def load_state_file(cwd: str, filename: str) -> dict | None:
    """Load and parse a state file from .claude/ directory tree.

    Walks up the directory tree to find the state file and parse its JSON contents.

    Args:
        cwd: Current working directory path
        filename: Name of the state file (e.g., 'build-state.json')

    Returns:
        Parsed JSON contents as dict if found, None otherwise
    """
    state_path = _find_state_file_path(cwd, filename)
    if state_path:
        try:
            return json.loads(state_path.read_text())
        except (json.JSONDecodeError, IOError):
            return None
    return None


def update_state_file(cwd: str, filename: str, updates: dict) -> bool:
    """Update a state file with new values (merge, not replace).

    Finds the state file, loads it, merges updates, and writes back.

    Args:
        cwd: Current working directory path
        filename: Name of the state file (e.g., 'build-state.json')
        updates: Dictionary of key-value pairs to merge into state

    Returns:
        True if update succeeded, False otherwise
    """
    state_path = _find_state_file_path(cwd, filename)
    if not state_path:
        return False

    try:
        # Load existing state
        state = json.loads(state_path.read_text())
        # Merge updates
        state.update(updates)
        # Write back
        state_path.write_text(json.dumps(state, indent=2))
        return True
    except (json.JSONDecodeError, IOError):
        return False


def get_autonomous_state(cwd: str, session_id: str = "") -> tuple[dict | None, str | None]:
    """Get the autonomous mode state file and its type, filtering expired.

    Checks for build-state.json first (with forge-state.json fallback),
    then appfix-state.json (used by /repair), then burndown-state.json.
    Checks both project-level AND user-level state files.
    Returns None for expired state files.

    Args:
        cwd: Current working directory path
        session_id: Current session ID (optional, for cross-directory trust)

    Returns:
        Tuple of (state_dict, state_type) where state_type is 'build', 'repair', or 'burndown'
        Returns (None, None) if no state file found or all expired
    """
    # Check project-level build state (new name first, legacy fallback)
    for build_filename in ("build-state.json", "forge-state.json"):
        build_state = load_state_file(cwd, build_filename)
        if build_state and not is_state_expired(build_state):
            return build_state, "build"

    # Check project-level appfix state (used by /repair)
    appfix_state = load_state_file(cwd, "appfix-state.json")
    if appfix_state and not is_state_expired(appfix_state):
        return appfix_state, "repair"

    # Check project-level burndown state
    burndown_state = load_state_file(cwd, "burndown-state.json")
    if burndown_state and not is_state_expired(burndown_state):
        return burndown_state, "burndown"

    # Check user-level state files (for cross-directory support)
    for filename, state_type in [
        ("build-state.json", "build"),
        ("forge-state.json", "build"),  # Legacy fallback
        ("appfix-state.json", "repair"),
        ("burndown-state.json", "burndown"),
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


def cleanup_autonomous_state(cwd: str) -> list[str]:
    """Clean up ALL autonomous mode state files.

    Removes state files from:
    1. User-level (~/.claude/)
    2. ALL .claude/ directories walking UP from cwd
    Handles both PID-scoped and legacy unscoped filenames.

    This function should be called after a successful stop to prevent
    stale state files from affecting subsequent sessions.

    Args:
        cwd: Current working directory to start walk-up from

    Returns:
        List of file paths that were deleted
    """
    deleted = []
    state_files = ["appfix-state.json", "build-state.json", "forge-state.json", "burndown-state.json"]
    state_bases = ["appfix-state", "build-state", "forge-state", "burndown-state"]

    # 1. Clean user-level state
    user_claude_dir = Path.home() / ".claude"
    for filename in state_files:
        user_state = user_claude_dir / filename
        if user_state.exists():
            try:
                user_state.unlink()
                deleted.append(str(user_state))
            except (IOError, OSError):
                pass  # Best effort cleanup

    # 2. Walk UP directory tree and clean ALL project-level state files
    if cwd:
        current = Path(cwd).resolve()
        for _ in range(20):  # Max depth to prevent infinite loops
            claude_dir = current / ".claude"
            if claude_dir.exists():
                for filename in state_files:
                    # Legacy unscoped file
                    state_file = claude_dir / filename
                    if state_file.exists():
                        try:
                            state_file.unlink()
                            deleted.append(str(state_file))
                        except (IOError, OSError):
                            pass  # Best effort cleanup
                # PID-scoped files
                for base_name in state_bases:
                    for scoped_file in claude_dir.glob(f"{base_name}.*.json"):
                        if _extract_pid_from_filename(scoped_file.name) is not None:
                            try:
                                scoped_file.unlink()
                                deleted.append(str(scoped_file))
                            except (IOError, OSError):
                                pass
            parent = current.parent
            if parent == current:  # Reached filesystem root
                break
            current = parent

    return deleted


# ============================================================================
# Session & TTL Utilities
# ============================================================================


def is_state_expired(state: dict, ttl_hours: int = SESSION_TTL_HOURS) -> bool:
    """Check if a state file has exceeded its TTL.

    Uses last_activity_at if present, falls back to started_at.
    Missing or malformed timestamps are treated as expired.

    Args:
        state: Parsed state file dict
        ttl_hours: Hours before state expires (default: SESSION_TTL_HOURS)

    Returns:
        True if expired, False if still valid
    """
    timestamp_str = state.get("last_activity_at") or state.get("started_at")
    if not timestamp_str:
        return True  # No timestamp = expired

    try:
        # Parse ISO format timestamp
        if timestamp_str.endswith("Z"):
            timestamp_str = timestamp_str[:-1] + "+00:00"
        ts = datetime.fromisoformat(timestamp_str)
        # Ensure timezone-aware comparison
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        return (now - ts) > timedelta(hours=ttl_hours)
    except (ValueError, TypeError):
        return True  # Malformed timestamp = expired


def is_state_for_session(state: dict, session_id: str) -> bool:
    """Check if a state file belongs to the given session.

    No session_id in state = True (backward compatibility with old state files).
    Empty session_id argument = True (caller doesn't have session info).

    Args:
        state: Parsed state file dict
        session_id: Session ID to match against

    Returns:
        True if state belongs to this session (or can't determine)
    """
    if not session_id:
        return True  # Caller has no session info - accept
    state_session = state.get("session_id")
    if not state_session:
        return True  # Old format state - backward compatible
    return state_session == session_id


def cleanup_checkpoint_only(cwd: str) -> list[str]:
    """Delete ONLY the completion checkpoint file. Leave mode state intact.

    This is the sticky session replacement for cleanup_autonomous_state
    at task boundaries. The mode state (appfix-state.json, build-state.json)
    persists for the next task in the same session.

    Handles both PID-scoped and legacy checkpoint filenames.

    Args:
        cwd: Working directory containing .claude/

    Returns:
        List of file paths that were deleted
    """
    deleted = []
    if not cwd:
        return deleted

    claude_dir = Path(cwd) / ".claude"
    if not claude_dir.exists():
        return deleted

    # PID-scoped checkpoint
    scoped_path = claude_dir / _scoped_filename("completion-checkpoint.json")
    if scoped_path.exists():
        try:
            scoped_path.unlink()
            deleted.append(str(scoped_path))
        except (IOError, OSError):
            pass

    # Legacy unscoped checkpoint
    legacy_path = claude_dir / "completion-checkpoint.json"
    if legacy_path.exists():
        try:
            legacy_path.unlink()
            deleted.append(str(legacy_path))
        except (IOError, OSError):
            pass

    return deleted


def reset_state_for_next_task(cwd: str) -> bool:
    """Reset per-task fields in the autonomous state file for the next task.

    Increments iteration, resets plan_mode_completed, updates last_activity_at,
    clears per-task fields (verification_evidence, services).
    Does NOT delete the state file - that's the sticky session behavior.

    Operates on whichever state file exists (forge, appfix, or burndown).
    Finds PID-scoped files first, falls back to legacy.

    Args:
        cwd: Working directory containing .claude/

    Returns:
        True if state was reset, False if no state file found
    """
    for filename in ("build-state.json", "forge-state.json", "appfix-state.json", "burndown-state.json"):
        state_path = _find_state_file_path(cwd, filename)
        if state_path:
            try:
                state = json.loads(state_path.read_text())
                # Increment iteration
                state["iteration"] = state.get("iteration", 1) + 1
                # Reset per-task fields
                state["plan_mode_completed"] = False
                state["verification_evidence"] = None
                state["services"] = {}
                # Update activity timestamp
                state["last_activity_at"] = datetime.now(timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                )
                state_path.write_text(json.dumps(state, indent=2))

                # Also update user-level state timestamp (both legacy and sessions dict)
                session_id = state.get("session_id", "")
                user_state_path = Path.home() / ".claude" / filename
                if user_state_path.exists():
                    try:
                        user_state = json.loads(user_state_path.read_text())
                        # Update legacy root-level fields
                        user_state["last_activity_at"] = state["last_activity_at"]
                        user_state["plan_mode_completed"] = False

                        # Update session in sessions dict (multi-session support)
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


def _cleanup_user_level_sessions(state_path: Path) -> bool:
    """Clean up expired sessions from user-level state file.

    MULTI-SESSION SUPPORT: Instead of deleting the whole file, remove
    individual expired sessions from the sessions dict.

    Args:
        state_path: Path to the user-level state file

    Returns:
        True if file was deleted (all sessions expired), False otherwise
    """
    try:
        state = json.loads(state_path.read_text())
    except (json.JSONDecodeError, IOError):
        # Corrupt file - delete it
        try:
            state_path.unlink()
            return True
        except (IOError, OSError):
            return False

    # Handle multi-session format
    sessions = state.get("sessions", {})
    if sessions:
        # Remove expired sessions
        valid_sessions = {}
        for session_id, session_info in sessions.items():
            if not is_state_expired(session_info):
                valid_sessions[session_id] = session_info

        if not valid_sessions:
            # All sessions expired - delete the file
            try:
                state_path.unlink()
                return True
            except (IOError, OSError):
                return False
        elif len(valid_sessions) < len(sessions):
            # Some sessions expired - update the file
            state["sessions"] = valid_sessions
            try:
                state_path.write_text(json.dumps(state, indent=2))
            except (IOError, OSError):
                pass
        return False

    # Legacy format (no sessions dict) - check root-level TTL
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

    Keeps state that:
    - Belongs to the current session AND is not expired
    - Has no session_id (old format) AND is not expired

    Cleans both project-level and user-level state files.

    MULTI-SESSION SUPPORT: User-level state files have a "sessions" dict
    that maps session_id to session info. Expired sessions are removed
    from the dict rather than deleting the whole file.

    Args:
        cwd: Working directory to start walk-up from
        current_session_id: Current session's ID (empty = clean only expired)

    Returns:
        List of file paths that were deleted
    """
    deleted = []
    state_files = ["appfix-state.json", "build-state.json", "forge-state.json", "burndown-state.json"]

    def _should_clean_project_level(state_path: Path) -> bool:
        """Check if a project-level state file should be cleaned up.

        Project-level state is cleaned if:
        1. Expired (TTL-based), OR
        2. Belongs to a different session (session_id mismatch)
        """
        try:
            state = json.loads(state_path.read_text())
        except (json.JSONDecodeError, IOError):
            return True  # Corrupt file = clean up

        # Expired state is always cleaned
        if is_state_expired(state):
            return True

        # Different session's state is cleaned (if we know the session)
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
        state_bases = [Path(f).stem for f in state_files]  # e.g., ['appfix-state', 'build-state', 'forge-state']
        for _ in range(20):
            if current == home:
                break
            claude_dir = current / ".claude"
            if claude_dir.exists():
                # Clean legacy unscoped files
                for filename in state_files:
                    state_file = claude_dir / filename
                    if state_file.exists() and _should_clean_project_level(state_file):
                        try:
                            state_file.unlink()
                            deleted.append(str(state_file))
                        except (IOError, OSError):
                            pass
                # Clean PID-scoped files with dead PIDs or expired TTL
                for base_name in state_bases:
                    for scoped_file in claude_dir.glob(f"{base_name}.*.json"):
                        pid = _extract_pid_from_filename(scoped_file.name)
                        if pid is None:
                            continue
                        # Dead PID → always clean
                        if not is_pid_alive(pid):
                            try:
                                scoped_file.unlink()
                                deleted.append(str(scoped_file))
                            except (IOError, OSError):
                                pass
                        # Live PID but should clean based on content
                        elif _should_clean_project_level(scoped_file):
                            try:
                                scoped_file.unlink()
                                deleted.append(str(scoped_file))
                            except (IOError, OSError):
                                pass
            parent = current.parent
            if parent == current:
                break
            current = parent

    return deleted


def is_pid_alive(pid: int) -> bool:
    """Check if a process with the given PID is still running.

    Uses os.kill(pid, 0) which doesn't actually send a signal,
    just checks if the process exists.

    Args:
        pid: Process ID to check

    Returns:
        True if process exists, False if not
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


def _get_ancestor_pid() -> int:
    """Get the ancestor PID that represents the Claude Code process.

    Walks up the process tree past shell intermediaries (sh, bash, zsh,
    python3) to find the actual Claude Code PID. Falls back to os.getppid().

    Returns:
        Best-guess PID for the Claude Code process
    """
    try:
        pid = os.getppid()
        # Walk up past shell intermediaries (max 5 levels)
        for _ in range(5):
            if pid <= 1:
                break
            try:
                result = subprocess.run(
                    ["ps", "-p", str(pid), "-o", "comm="],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
                comm = result.stdout.strip().lower()
                # Stop at node/claude (the actual Claude Code process)
                if "node" in comm or "claude" in comm:
                    return pid
                # Skip shell intermediaries
                if comm in ("sh", "bash", "zsh", "fish", "python3", "python"):
                    # Get parent of this intermediate process
                    ppid_result = subprocess.run(
                        ["ps", "-p", str(pid), "-o", "ppid="],
                        capture_output=True,
                        text=True,
                        timeout=2,
                    )
                    parent_pid = int(ppid_result.stdout.strip())
                    if parent_pid <= 1:
                        break
                    pid = parent_pid
                else:
                    break  # Unknown process, stop here
            except (subprocess.TimeoutExpired, ValueError, FileNotFoundError):
                break
        return pid
    except Exception:
        return os.getppid()


# ============================================================================
# Worktree Detection
# ============================================================================


def is_worktree(cwd: str = "") -> bool:
    """Check if the current directory is a git worktree (not the main repo).

    A worktree is a linked working directory managed by git worktree commands.
    This is used to detect if we're in a parallel agent isolation directory.

    Args:
        cwd: Working directory to check

    Returns:
        True if in a worktree, False if in main repo or error
    """
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
        # If git-dir != git-common-dir, this is a linked worktree
        return git_dir.stdout.strip() != git_common.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def get_worktree_info(cwd: str = "") -> dict | None:
    """Get information about the current worktree if in one.

    Args:
        cwd: Working directory to check

    Returns:
        Dict with worktree info if in a worktree:
        - branch: current branch name
        - agent_id: agent ID if this is a Claude worktree
        - path: worktree root path
        - is_claude_worktree: True if has agent state file
        Returns None if not in a worktree
    """
    if not is_worktree(cwd):
        return None
    try:
        # Get the branch name
        branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=cwd or None,
        )
        branch_name = branch.stdout.strip()

        # Get worktree path
        worktree_path = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=cwd or None,
        )

        # Check for agent state file
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
            "branch": branch_name,
            "agent_id": agent_id,
            "path": worktree_path.stdout.strip(),
            "is_claude_worktree": agent_id is not None,
        }
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


# ============================================================================
# Checkpoint File Operations
# ============================================================================


def load_checkpoint(cwd: str) -> dict | None:
    """Load completion checkpoint file from .claude directory.

    Checks PID-scoped checkpoint first, falls back to legacy unscoped.

    Args:
        cwd: Working directory containing .claude/

    Returns:
        Parsed checkpoint dict if exists and valid, None otherwise
    """
    if not cwd:
        return None

    claude_dir = Path(cwd) / ".claude"
    if not claude_dir.exists():
        return None

    # 1. Check PID-scoped checkpoint
    scoped_path = claude_dir / _scoped_filename("completion-checkpoint.json")
    if scoped_path.exists():
        try:
            return json.loads(scoped_path.read_text())
        except (json.JSONDecodeError, IOError):
            return None

    # 2. Fall back to legacy unscoped checkpoint
    legacy_path = claude_dir / "completion-checkpoint.json"
    if legacy_path.exists():
        try:
            return json.loads(legacy_path.read_text())
        except (json.JSONDecodeError, IOError):
            return None

    return None


def save_checkpoint(cwd: str, checkpoint: dict) -> bool:
    """Save checkpoint file back to disk.

    Uses PID-scoped filename for session isolation.

    Args:
        cwd: Working directory containing .claude/
        checkpoint: Checkpoint dict to save

    Returns:
        True if save succeeded, False otherwise
    """
    if not cwd:
        return False
    checkpoint_path = Path(cwd) / ".claude" / _scoped_filename("completion-checkpoint.json")
    try:
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        checkpoint_path.write_text(json.dumps(checkpoint, indent=2))
        return True
    except IOError:
        return False


# ============================================================================
# Checkpoint Invalidation (shared by checkpoint-invalidator, bash-version-tracker, stop-validator)
# ============================================================================

# Code file extensions that trigger checkpoint invalidation
CODE_EXTENSIONS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java", ".rb", ".php",
    ".vue", ".svelte",
    ".tf", ".tfvars", ".bicep",
    ".yaml", ".yml",
    ".sql", ".sh", ".bash",
}

# Fields invalidated when code changes (in dependency order)
# When a field is invalidated, all fields that depend on it are also invalidated
FIELD_DEPENDENCIES = {
    "linters_pass": [],
    "deployed": ["linters_pass"],
    "web_testing_done": ["deployed"],
}

# All version-dependent fields
VERSION_DEPENDENT_FIELDS = list(FIELD_DEPENDENCIES.keys())


def is_code_file(file_path: str) -> bool:
    """Check if file is a code file based on extension."""
    return Path(file_path).suffix.lower() in CODE_EXTENSIONS


def get_fields_to_invalidate(primary_field: str) -> set[str]:
    """Get all fields that should be invalidated when primary_field changes.

    Uses dependency graph to cascade invalidations.
    """
    to_invalidate = {primary_field}
    changed = True
    while changed:
        changed = False
        for field, deps in FIELD_DEPENDENCIES.items():
            if field not in to_invalidate:
                if any(dep in to_invalidate for dep in deps):
                    to_invalidate.add(field)
                    changed = True
    return to_invalidate


def normalize_version(version: str) -> str:
    """Normalize version by stripping the -dirty suffix.

    Prevents invalidation loops where "abc1234" and "abc1234-dirty"
    are treated as different versions. Only actual commit changes
    should trigger invalidation.
    """
    if version.endswith("-dirty"):
        return version[:-6]
    return version


def invalidate_stale_fields(
    checkpoint: dict, current_version: str
) -> tuple[dict, list[str]]:
    """Check all version-dependent fields and invalidate stale ones.

    Versions are normalized before comparison to prevent loops.
    "abc1234" and "abc1234-dirty" are considered the same version.

    Returns (modified_checkpoint, list_of_invalidated_fields).
    """
    report = checkpoint.get("self_report", {})
    invalidated = []

    current_normalized = normalize_version(current_version)

    for field in VERSION_DEPENDENT_FIELDS:
        if report.get(field, False):
            field_version = report.get(f"{field}_at_version", "")
            if field_version:
                field_normalized = normalize_version(field_version)
                if field_normalized != current_normalized:
                    fields_to_reset = get_fields_to_invalidate(field)
                    for f in fields_to_reset:
                        if report.get(f, False):
                            report[f] = False
                            report[f"{f}_at_version"] = ""
                            if f not in invalidated:
                                invalidated.append(f)

    return checkpoint, invalidated
