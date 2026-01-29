#!/usr/bin/env python3
"""
SessionStart Hook - Toolkit Auto-Update

Checks for toolkit updates on session start (rate-limited to once per 24 hours).
If updates available, performs git pull and detects settings.json changes.

Flow:
1. Fast path: If recently checked and up-to-date, exit immediately
2. Slow path: Compare local HEAD vs remote origin/main
3. If outdated: git pull, detect settings.json changes
4. If settings.json changed: Output strong restart warning

Exit codes:
  0 - Success (always non-blocking for SessionStart hooks)

Output (stdout):
  - Nothing if up-to-date
  - Update notification if pulled
  - STRONG restart warning if settings.json changed
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ============================================================================
# Configuration
# ============================================================================

CHECK_INTERVAL_MINUTES = 5
STATE_FILE = Path.home() / ".claude" / "toolkit-update-state.json"
DEBUG_LOG = Path(tempfile.gettempdir()) / "claude-hooks-debug.log"


def log_debug(message: str) -> None:
    """Append debug message to log file."""
    try:
        with open(DEBUG_LOG, "a") as f:
            timestamp = datetime.now().isoformat()
            f.write(f"[{timestamp}] [auto-update] {message}\n")
    except Exception:
        pass


# ============================================================================
# Toolkit Path Resolution
# ============================================================================


def get_toolkit_repo_path() -> Path | None:
    """
    Get the toolkit repository path by resolving the hooks symlink.

    Returns None if not installed via symlink (manual install or not installed).
    """
    hooks_path = Path.home() / ".claude" / "hooks"

    if not hooks_path.exists():
        log_debug("hooks path does not exist")
        return None

    if not hooks_path.is_symlink():
        log_debug("hooks path is not a symlink (manual install?)")
        return None

    try:
        # Resolve symlink: ~/.claude/hooks -> /path/to/repo/config/hooks
        resolved = hooks_path.resolve()
        # Go up to repo root: config/hooks -> config -> repo_root
        repo_path = resolved.parent.parent

        # Verify it's a git repo
        git_dir = repo_path / ".git"
        if not git_dir.exists():
            log_debug(f"resolved path {repo_path} is not a git repo")
            return None

        log_debug(f"found toolkit repo at {repo_path}")
        return repo_path
    except Exception as e:
        log_debug(f"error resolving toolkit path: {e}")
        return None


# ============================================================================
# State Management
# ============================================================================


def load_state() -> dict:
    """Load update state file, return empty dict if missing/invalid."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except (json.JSONDecodeError, IOError) as e:
            log_debug(f"error loading state file: {e}")
    return {}


def save_state(state: dict) -> None:
    """Save state file back to disk."""
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(state, indent=2))
    except Exception as e:
        log_debug(f"error saving state file: {e}")


def get_settings_hash() -> str:
    """Get SHA256 hash of settings.json content."""
    settings_path = Path.home() / ".claude" / "settings.json"
    try:
        if settings_path.exists():
            # Resolve symlink to get actual file
            actual_path = settings_path.resolve()
            content = actual_path.read_text()
            return f"sha256:{hashlib.sha256(content.encode()).hexdigest()[:16]}"
    except Exception as e:
        log_debug(f"error hashing settings.json: {e}")
    return "unknown"


def should_check_for_updates(state: dict) -> bool:
    """Determine if enough time has passed since last check."""
    last_check = state.get("last_check_timestamp")
    if not last_check:
        return True

    try:
        # Handle both Z suffix and +00:00 formats
        last_check_str = last_check.replace("Z", "+00:00")
        last_check_time = datetime.fromisoformat(last_check_str)
        now = datetime.now(timezone.utc)
        elapsed = now - last_check_time
        should_check = elapsed > timedelta(minutes=CHECK_INTERVAL_MINUTES)
        log_debug(
            f"last check: {last_check}, elapsed: {elapsed}, should_check: {should_check}"
        )
        return should_check
    except (ValueError, TypeError) as e:
        log_debug(f"error parsing last_check_timestamp: {e}")
        return True


# ============================================================================
# Git Operations
# ============================================================================


def get_local_head(repo_path: Path) -> str | None:
    """Get local HEAD commit hash."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        log_debug(f"git rev-parse failed: {result.stderr}")
        return None
    except subprocess.TimeoutExpired:
        log_debug("git rev-parse timed out")
        return None
    except FileNotFoundError:
        log_debug("git not found")
        return None


def get_remote_head(repo_path: Path) -> str | None:
    """Get remote origin/main HEAD without full fetch."""
    try:
        result = subprocess.run(
            ["git", "ls-remote", "origin", "main"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0 and result.stdout:
            # Output format: "abc123def456...\trefs/heads/main"
            commit_hash = result.stdout.split()[0]
            log_debug(f"remote HEAD: {commit_hash[:7]}")
            return commit_hash
        log_debug(f"git ls-remote failed: {result.stderr}")
        return None
    except subprocess.TimeoutExpired:
        log_debug("git ls-remote timed out")
        return None
    except FileNotFoundError:
        log_debug("git not found")
        return None


def perform_git_pull(repo_path: Path) -> tuple[bool, str]:
    """Perform git pull and return (success, message)."""
    try:
        # First, fetch to ensure we have latest refs
        fetch_result = subprocess.run(
            ["git", "fetch", "origin", "main"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if fetch_result.returncode != 0:
            return False, f"Fetch failed: {fetch_result.stderr.strip()}"

        # Then pull (fast-forward only to avoid conflicts)
        pull_result = subprocess.run(
            ["git", "pull", "--ff-only", "origin", "main"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if pull_result.returncode == 0:
            return True, pull_result.stdout.strip()
        else:
            return False, f"Pull failed: {pull_result.stderr.strip()}"
    except subprocess.TimeoutExpired:
        return False, "Git operation timed out"
    except FileNotFoundError:
        return False, "Git not found"


def get_commit_summary(repo_path: Path, from_commit: str, to_commit: str) -> str:
    """Get one-line summary of commits between two hashes."""
    try:
        result = subprocess.run(
            ["git", "log", "--oneline", f"{from_commit}..{to_commit}"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            lines = result.stdout.strip().split("\n")
            if len(lines) <= 3:
                return result.stdout.strip()
            else:
                return f"{lines[0]}\n{lines[1]}\n... and {len(lines) - 2} more commits"
        return ""
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


# ============================================================================
# Main Logic
# ============================================================================


def main():
    # Check for disable flag
    if os.environ.get("CLAUDE_TOOLKIT_AUTO_UPDATE", "").lower() == "false":
        log_debug("auto-update disabled via environment variable")
        sys.exit(0)

    # Parse input (SessionStart provides session_id, cwd, source)
    try:
        input_data = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        input_data = {}

    source = input_data.get("source", "startup")
    log_debug(f"SessionStart source: {source}")

    # Get toolkit repo path
    repo_path = get_toolkit_repo_path()
    if not repo_path:
        # Not installed via symlink, skip auto-update
        sys.exit(0)

    # Load state
    state = load_state()

    # Record current settings hash (for change detection)
    current_settings_hash = get_settings_hash()

    # Check for pending restart requirement from previous update
    pending_restart = state.get("pending_restart_reason")
    if pending_restart:
        # Settings changed in a previous session but user didn't restart
        stored_hash = state.get("settings_hash_at_session_start")
        if stored_hash and stored_hash != current_settings_hash:
            # Hash changed - user restarted (or settings changed manually), clear pending
            log_debug("pending restart cleared - settings hash changed")
            state["pending_restart_reason"] = None
            state["settings_hash_at_session_start"] = current_settings_hash
            save_state(state)
        else:
            # Still needs restart - show warning
            print(f"""
⚠️ TOOLKIT RESTART REQUIRED ⚠️

The Claude Code Toolkit was updated but settings.json changed.
Hooks are captured at session startup and require restart to reload.

Reason: {pending_restart}

ACTION REQUIRED: Exit this session and start a new one.

The current session is using stale hook definitions.
""")
            sys.exit(0)

    # Fast path: Recently checked and up-to-date
    if not should_check_for_updates(state):
        # Update settings hash for this session
        state["settings_hash_at_session_start"] = current_settings_hash
        save_state(state)
        sys.exit(0)

    # Slow path: Check for updates
    log_debug("checking for updates...")
    local_head = get_local_head(repo_path)
    remote_head = get_remote_head(repo_path)

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    if not local_head or not remote_head:
        # Network error or git issue - don't block, just skip
        log_debug(f"version check failed: local={local_head}, remote={remote_head}")
        state["last_check_timestamp"] = now
        state["last_check_result"] = "check_failed"
        state["settings_hash_at_session_start"] = current_settings_hash
        save_state(state)
        sys.exit(0)

    # Compare versions
    if local_head == remote_head:
        # Up to date
        log_debug(f"up to date at {local_head[:7]}")
        state["last_check_timestamp"] = now
        state["last_check_result"] = "up_to_date"
        state["local_commit_at_check"] = local_head[:7]
        state["remote_commit_at_check"] = remote_head[:7]
        state["settings_hash_at_session_start"] = current_settings_hash
        save_state(state)
        sys.exit(0)

    # Updates available - record settings hash before pull
    log_debug(f"updates available: {local_head[:7]} -> {remote_head[:7]}")
    settings_hash_before = current_settings_hash

    # Perform git pull
    success, message = perform_git_pull(repo_path)

    if not success:
        # Pull failed - notify but don't block
        log_debug(f"pull failed: {message}")
        state["last_check_timestamp"] = now
        state["last_check_result"] = "update_failed"
        state["settings_hash_at_session_start"] = current_settings_hash
        save_state(state)
        print(f"""
⚠️ TOOLKIT UPDATE FAILED

Could not auto-update the Claude Code Toolkit.
Error: {message}

Manual update: cd {repo_path} && git pull
""")
        sys.exit(0)

    # Verify HEAD actually changed to the expected commit
    new_local_head = get_local_head(repo_path)
    if new_local_head and new_local_head != remote_head:
        # Pull "succeeded" but HEAD didn't move - likely local is ahead of remote
        # This happens when local has unpushed commits that include the remote commits
        log_debug(
            f"pull completed but HEAD unchanged: "
            f"expected {remote_head[:7]}, got {new_local_head[:7]}"
        )
        state["last_check_timestamp"] = now
        state["last_check_result"] = "local_ahead"
        state["local_commit_at_check"] = new_local_head[:7]
        state["remote_commit_at_check"] = remote_head[:7]
        state["settings_hash_at_session_start"] = current_settings_hash
        save_state(state)
        print(f"""
⚠️ TOOLKIT LOCAL CHANGES DETECTED

Your local toolkit has unpushed commits ahead of origin/main.

Local:  {new_local_head[:7]}
Remote: {remote_head[:7]}

The auto-update cannot fast-forward. Options:
1. Push your local changes: cd {repo_path} && git push
2. Reset to remote: cd {repo_path} && git reset --hard origin/main
3. Rebase on remote: cd {repo_path} && git rebase origin/main

Auto-update will resume once local matches or is behind remote.
""")
        sys.exit(0)

    # Pull succeeded and HEAD moved - check if settings.json changed
    settings_hash_after = get_settings_hash()
    settings_changed = settings_hash_before != settings_hash_after

    log_debug(
        f"pull succeeded: {local_head[:7]} -> {new_local_head[:7] if new_local_head else remote_head[:7]}, "
        f"settings_changed: {settings_changed}"
    )

    # Get commit summary
    commit_summary = get_commit_summary(repo_path, local_head[:7], remote_head[:7])

    # Update history
    history = state.get("update_history", [])
    history.insert(
        0,
        {
            "timestamp": now,
            "from_commit": local_head[:7],
            "to_commit": remote_head[:7],
            "settings_changed": settings_changed,
        },
    )
    state["update_history"] = history[:5]  # Keep last 5

    # Update state
    state["last_check_timestamp"] = now
    state["last_check_result"] = "updated"
    state["local_commit_at_check"] = remote_head[:7]
    state["remote_commit_at_check"] = remote_head[:7]
    state["settings_hash_at_session_start"] = settings_hash_after

    if settings_changed:
        # Settings changed - require restart
        state["pending_restart_reason"] = (
            f"settings.json changed in update {local_head[:7]} -> {remote_head[:7]}"
        )
        save_state(state)

        print(f"""
⚠️ TOOLKIT UPDATED - RESTART REQUIRED ⚠️

The Claude Code Toolkit was updated from {local_head[:7]} to {remote_head[:7]}.

{commit_summary}

CRITICAL: settings.json changed in this update.
Hooks are captured at session startup and require restart to reload.

ACTION REQUIRED: Exit this session and start a new one.

The update has been applied to disk, but this session is using stale hooks.
Continue at your own risk - new hook behavior will not work correctly.
""")
    else:
        # Update complete, no restart needed
        save_state(state)
        print(f"""
✓ TOOLKIT UPDATED

The Claude Code Toolkit was updated from {local_head[:7]} to {remote_head[:7]}.

{commit_summary}

No restart required - hook scripts updated in place.
""")

    sys.exit(0)


if __name__ == "__main__":
    main()
