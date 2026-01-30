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
        # Walk up to home directory (max 20 levels to prevent infinite loops)
        for _ in range(20):
            # Stop at home directory - ~/.claude/ is for global config, not project state
            if current == home:
                break
            state_file = current / ".claude" / filename
            if state_file.exists():
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

    Args:
        cwd: Current working directory path
        user_state: Parsed user-level state file dict
        session_id: Current session ID (optional, for cross-directory trust)

    Returns:
        True if cwd is under origin_project (or origin_project not set), False otherwise
    """
    # Trust matching session - same session can work anywhere
    # This enables cross-directory workflows (e.g., appfix navigating to test dirs)
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


def is_appfix_active(cwd: str, session_id: str = "") -> bool:
    """Check if appfix mode is active via non-expired state file or env var.

    Loads the state file and checks TTL expiry. Expired state files are
    treated as inactive (cleaned up at next SessionStart).

    Args:
        cwd: Current working directory path
        session_id: Current session ID (optional, for cross-directory trust)

    Returns:
        True if appfix mode is active and not expired, False otherwise
    """
    # Check project-level state with TTL
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


def is_godo_active(cwd: str, session_id: str = "") -> bool:
    """Check if godo mode is active via non-expired state file or env var.

    Loads the state file and checks TTL expiry. Expired state files are
    treated as inactive (cleaned up at next SessionStart).

    Args:
        cwd: Current working directory path
        session_id: Current session ID (optional, for cross-directory trust)

    Returns:
        True if godo mode is active and not expired, False otherwise
    """
    # Check project-level state with TTL
    state = load_state_file(cwd, "godo-state.json")
    if state and not is_state_expired(state):
        return True

    # Check user-level state with TTL and origin/session check
    user_state_path = Path.home() / ".claude" / "godo-state.json"
    if user_state_path.exists():
        try:
            user_state = json.loads(user_state_path.read_text())
            if not is_state_expired(user_state) and _is_cwd_under_origin(cwd, user_state, session_id):
                return True
        except (json.JSONDecodeError, IOError):
            pass

    # Fallback: Check environment variable (no TTL for env vars)
    if os.environ.get("GODO_ACTIVE", "").lower() in ("true", "1", "yes"):
        return True

    return False


def is_autonomous_mode_active(cwd: str, session_id: str = "") -> bool:
    """Check if any autonomous execution mode is active (godo or appfix).

    This is the unified check for enabling auto-approval hooks.

    Args:
        cwd: Current working directory path
        session_id: Current session ID (optional, for cross-directory trust)

    Returns:
        True if godo OR appfix mode is active, False otherwise
    """
    return is_godo_active(cwd, session_id) or is_appfix_active(cwd, session_id)


def _find_state_file_path(cwd: str, filename: str) -> Path | None:
    """Find the path to a state file in .claude/ directory tree.

    Walks up the directory tree to find the state file,
    similar to how git finds the .git directory.

    IMPORTANT: Stops at the home directory to avoid picking up unrelated
    state files from ~/.claude/ which is meant for global config, not
    project-specific state.

    Args:
        cwd: Current working directory path
        filename: Name of the state file (e.g., 'godo-state.json')

    Returns:
        Path to state file if found, None otherwise
    """
    if cwd:
        current = Path(cwd).resolve()
        home = Path.home()
        # Walk up to home directory (max 20 levels to prevent infinite loops)
        for _ in range(20):
            # Stop at home directory - ~/.claude/ is for global config, not project state
            if current == home:
                break
            state_file = current / ".claude" / filename
            if state_file.exists():
                return state_file
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
        filename: Name of the state file (e.g., 'godo-state.json')

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
        filename: Name of the state file (e.g., 'godo-state.json')
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

    Checks for godo-state.json first, then appfix-state.json.
    Checks both project-level AND user-level state files.
    Returns None for expired state files.

    Args:
        cwd: Current working directory path
        session_id: Current session ID (optional, for cross-directory trust)

    Returns:
        Tuple of (state_dict, state_type) where state_type is 'godo' or 'appfix'
        Returns (None, None) if no state file found or all expired
    """
    # Check project-level godo state
    godo_state = load_state_file(cwd, "godo-state.json")
    if godo_state and not is_state_expired(godo_state):
        return godo_state, "godo"

    # Check project-level appfix state
    appfix_state = load_state_file(cwd, "appfix-state.json")
    if appfix_state and not is_state_expired(appfix_state):
        return appfix_state, "appfix"

    # Check user-level state files (for cross-directory support)
    # This matches the behavior of is_appfix_active() and is_godo_active()
    user_godo_path = Path.home() / ".claude" / "godo-state.json"
    if user_godo_path.exists():
        try:
            user_godo_state = json.loads(user_godo_path.read_text())
            if not is_state_expired(user_godo_state) and _is_cwd_under_origin(cwd, user_godo_state, session_id):
                return user_godo_state, "godo"
        except (json.JSONDecodeError, IOError):
            pass

    user_appfix_path = Path.home() / ".claude" / "appfix-state.json"
    if user_appfix_path.exists():
        try:
            user_appfix_state = json.loads(user_appfix_path.read_text())
            if not is_state_expired(user_appfix_state) and _is_cwd_under_origin(cwd, user_appfix_state, session_id):
                return user_appfix_state, "appfix"
        except (json.JSONDecodeError, IOError):
            pass

    return None, None


def cleanup_autonomous_state(cwd: str) -> list[str]:
    """Clean up ALL autonomous mode state files.

    Removes state files from:
    1. User-level (~/.claude/)
    2. ALL .claude/ directories walking UP from cwd

    This function should be called after a successful stop to prevent
    stale state files from affecting subsequent sessions.

    Args:
        cwd: Current working directory to start walk-up from

    Returns:
        List of file paths that were deleted
    """
    deleted = []
    state_files = ["appfix-state.json", "godo-state.json"]

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
                    state_file = claude_dir / filename
                    if state_file.exists():
                        try:
                            state_file.unlink()
                            deleted.append(str(state_file))
                        except (IOError, OSError):
                            pass  # Best effort cleanup
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
    at task boundaries. The mode state (appfix-state.json, godo-state.json)
    persists for the next task in the same session.

    Args:
        cwd: Working directory containing .claude/

    Returns:
        List of file paths that were deleted
    """
    deleted = []
    if not cwd:
        return deleted

    checkpoint_path = Path(cwd) / ".claude" / "completion-checkpoint.json"
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
    clears per-task fields (verification_evidence, services).
    Does NOT delete the state file - that's the sticky session behavior.

    Operates on whichever state file exists (godo or appfix).

    Args:
        cwd: Working directory containing .claude/

    Returns:
        True if state was reset, False if no state file found
    """
    for filename in ("godo-state.json", "appfix-state.json"):
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

                # Also update user-level state timestamp
                user_state_path = Path.home() / ".claude" / filename
                if user_state_path.exists():
                    try:
                        user_state = json.loads(user_state_path.read_text())
                        user_state["last_activity_at"] = state["last_activity_at"]
                        user_state_path.write_text(json.dumps(user_state, indent=2))
                    except (json.JSONDecodeError, IOError):
                        pass

                return True
            except (json.JSONDecodeError, IOError):
                return False
    return False


def cleanup_expired_state(cwd: str, current_session_id: str = "") -> list[str]:
    """Delete state files that are expired OR belong to a different session.

    Called at SessionStart to clean up stale state from previous sessions.

    Keeps state that:
    - Belongs to the current session AND is not expired
    - Has no session_id (old format) AND is not expired

    Cleans both project-level and user-level state files.

    Args:
        cwd: Working directory to start walk-up from
        current_session_id: Current session's ID (empty = clean only expired)

    Returns:
        List of file paths that were deleted
    """
    deleted = []
    state_files = ["appfix-state.json", "godo-state.json"]

    def _should_clean_user_level(state_path: Path) -> bool:
        """Check if a user-level state file should be cleaned up.

        User-level state is ONLY cleaned based on TTL expiration.
        We do NOT clean based on session_id mismatch because user-level state
        is meant to persist across sessions for cross-directory autonomous mode.
        """
        try:
            state = json.loads(state_path.read_text())
        except (json.JSONDecodeError, IOError):
            return True  # Corrupt file = clean up

        # Only clean if expired (TTL-based)
        return is_state_expired(state)

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

    # 1. Clean user-level state (TTL-based only, preserves cross-session state)
    user_claude_dir = Path.home() / ".claude"
    for filename in state_files:
        user_state = user_claude_dir / filename
        if user_state.exists() and _should_clean_user_level(user_state):
            try:
                user_state.unlink()
                deleted.append(str(user_state))
            except (IOError, OSError):
                pass

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
                    if state_file.exists() and _should_clean_project_level(state_file):
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

    Args:
        cwd: Working directory containing .claude/

    Returns:
        Parsed checkpoint dict if exists and valid, None otherwise
    """
    if not cwd:
        return None
    checkpoint_path = Path(cwd) / ".claude" / "completion-checkpoint.json"
    if not checkpoint_path.exists():
        return None
    try:
        return json.loads(checkpoint_path.read_text())
    except (json.JSONDecodeError, IOError):
        return None


def save_checkpoint(cwd: str, checkpoint: dict) -> bool:
    """Save checkpoint file back to disk.

    Args:
        cwd: Working directory containing .claude/
        checkpoint: Checkpoint dict to save

    Returns:
        True if save succeeded, False otherwise
    """
    if not cwd:
        return False
    checkpoint_path = Path(cwd) / ".claude" / "completion-checkpoint.json"
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
