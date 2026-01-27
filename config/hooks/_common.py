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
from datetime import datetime
from pathlib import Path


# Files/patterns excluded from version tracking (dirty calculation)
# These don't represent code changes requiring re-deployment
# IMPORTANT: Use both root and nested patterns for directories like .claude/
# because :(exclude).claude/ only matches at root, not nested paths
VERSION_TRACKING_EXCLUSIONS = [
    # Base path required for exclude patterns to work correctly
    ".",
    # .claude directory at any depth (checkpoint files, state files)
    ":(exclude).claude",
    ":(exclude).claude/*",
    ":(exclude)*/.claude",
    ":(exclude)*/.claude/*",
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
            capture_output=True, text=True, timeout=5,
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
            capture_output=True, text=True, timeout=5,
            cwd=cwd or None,
        )
        head_hash = head.stdout.strip()
        if not head_hash:
            return "unknown"

        diff = subprocess.run(
            ["git", "diff", "HEAD", "--"] + VERSION_TRACKING_EXCLUSIONS,
            capture_output=True, text=True, timeout=5,
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
            f.write(f"\n{'='*60}\n")
            f.write(f"Timestamp: {datetime.now().isoformat()}\n")
            f.write(f"Hook: {hook_name}\n")
            f.write(f"Message: {message}\n")
            if error:
                f.write(f"Error: {type(error).__name__}: {error}\n")
            if raw_input:
                f.write(f"Raw stdin ({len(raw_input)} bytes): {repr(raw_input[:500])}\n")
            if parsed_data is not None:
                f.write(f"Parsed data: {json.dumps(parsed_data, indent=2)}\n")
            f.write(f"{'='*60}\n")
    except Exception:
        pass  # Never fail on logging


def _check_state_file(cwd: str, filename: str) -> bool:
    """Check if a state file exists in .claude/ directory tree.

    Walks up the directory tree to find the state file,
    similar to how git finds the .git directory.

    Args:
        cwd: Current working directory path
        filename: Name of the state file (e.g., 'appfix-state.json')

    Returns:
        True if state file exists, False otherwise
    """
    if cwd:
        current = Path(cwd).resolve()
        # Walk up to filesystem root (max 20 levels to prevent infinite loops)
        for _ in range(20):
            state_file = current / ".claude" / filename
            if state_file.exists():
                return True
            parent = current.parent
            if parent == current:  # Reached filesystem root
                break
            current = parent
    return False


def is_appfix_active(cwd: str) -> bool:
    """Check if appfix mode is active via state file or env var.

    Args:
        cwd: Current working directory path

    Returns:
        True if appfix mode is active, False otherwise
    """
    if _check_state_file(cwd, "appfix-state.json"):
        return True

    # Fallback: Check environment variable
    if os.environ.get("APPFIX_ACTIVE", "").lower() in ("true", "1", "yes"):
        return True

    return False


def is_godo_active(cwd: str) -> bool:
    """Check if godo mode is active via state file or env var.

    Args:
        cwd: Current working directory path

    Returns:
        True if godo mode is active, False otherwise
    """
    if _check_state_file(cwd, "godo-state.json"):
        return True

    # Fallback: Check environment variable
    if os.environ.get("GODO_ACTIVE", "").lower() in ("true", "1", "yes"):
        return True

    return False


def is_autonomous_mode_active(cwd: str) -> bool:
    """Check if any autonomous execution mode is active (godo or appfix).

    This is the unified check for enabling auto-approval hooks.

    Args:
        cwd: Current working directory path

    Returns:
        True if godo OR appfix mode is active, False otherwise
    """
    return is_godo_active(cwd) or is_appfix_active(cwd)


def _find_state_file_path(cwd: str, filename: str) -> Path | None:
    """Find the path to a state file in .claude/ directory tree.

    Walks up the directory tree to find the state file,
    similar to how git finds the .git directory.

    Args:
        cwd: Current working directory path
        filename: Name of the state file (e.g., 'godo-state.json')

    Returns:
        Path to state file if found, None otherwise
    """
    if cwd:
        current = Path(cwd).resolve()
        # Walk up to filesystem root (max 20 levels to prevent infinite loops)
        for _ in range(20):
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


def get_autonomous_state(cwd: str) -> tuple[dict | None, str | None]:
    """Get the autonomous mode state file and its type.

    Checks for godo-state.json first, then appfix-state.json.

    Args:
        cwd: Current working directory path

    Returns:
        Tuple of (state_dict, state_type) where state_type is 'godo' or 'appfix'
        Returns (None, None) if no state file found
    """
    godo_state = load_state_file(cwd, "godo-state.json")
    if godo_state:
        return godo_state, "godo"

    appfix_state = load_state_file(cwd, "appfix-state.json")
    if appfix_state:
        return appfix_state, "appfix"

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
            capture_output=True, text=True, timeout=5,
            cwd=cwd or None,
        )
        git_common = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            capture_output=True, text=True, timeout=5,
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
            capture_output=True, text=True, timeout=5,
            cwd=cwd or None,
        )
        branch_name = branch.stdout.strip()

        # Get worktree path
        worktree_path = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=5,
            cwd=cwd or None,
        )

        # Check for agent state file
        state_file = Path(worktree_path.stdout.strip()) / ".claude" / "worktree-agent-state.json"
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
        checkpoint_path.write_text(json.dumps(checkpoint, indent=2))
        return True
    except IOError:
        return False
