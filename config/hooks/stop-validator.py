#!/usr/bin/env python3
"""
Global Stop Hook Validator - Deterministic Boolean Checkpoints

Two-phase stop flow with completion checkpoint validation:
1. First stop (stop_hook_active=false): Block + require checkpoint file
2. Second stop (stop_hook_active=true): Validate checkpoint booleans

The model MUST fill out .claude/completion-checkpoint.json with honest
boolean answers. The hook deterministically checks these booleans.

Worktree Support:
- Detects if running in a git worktree (for parallel agent isolation)
- Uses worktree-local checkpoint files for isolation
- Reports worktree context in validation messages

Exit codes:
  0 - Allow stop
  2 - Block stop (stderr shown to Claude)

Module Structure:
- _common.py: Shared utilities (git, state files, logging)
- _sv_validators.py: Validation logic (sub-validators, artifact checks)
- _sv_templates.py: Blocking message templates
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Add hooks directory to path for sibling imports
sys.path.insert(0, str(Path(__file__).parent))

from _common import (
    log_debug,
    get_diff_hash,
    load_checkpoint,
    cleanup_autonomous_state,
)
from _sv_validators import (
    validate_checkpoint,
    get_git_diff_files,
    has_code_changes,
)
from _sv_templates import (
    block_no_checkpoint,
    block_with_continuation,
)


# ============================================================================
# Mode Detection
# ============================================================================

def is_appfix_mode(cwd: str = "") -> bool:
    """Check if appfix mode is active.

    Checks user-level state first (~/.claude/appfix-state.json) to handle
    cross-repo scenarios where appfix was started in one repo but work
    is being done in another (e.g., Terraform infra repo).

    Falls back to project-level state for backward compatibility.
    """
    # User-level state takes precedence (cross-repo compatible)
    user_state = Path.home() / ".claude" / "appfix-state.json"
    if user_state.exists():
        return True

    # Fall back to project-level state (backward compatibility)
    if cwd:
        project_state = Path(cwd) / ".claude" / "appfix-state.json"
        if project_state.exists():
            return True

    return False


def is_godo_mode(cwd: str = "") -> bool:
    """Check if godo mode is active.

    Checks user-level state first (~/.claude/godo-state.json) to handle
    cross-repo scenarios.

    Falls back to project-level state for backward compatibility.
    """
    # User-level state takes precedence (cross-repo compatible)
    user_state = Path.home() / ".claude" / "godo-state.json"
    if user_state.exists():
        return True

    # Fall back to project-level state (backward compatibility)
    if cwd:
        project_state = Path(cwd) / ".claude" / "godo-state.json"
        if project_state.exists():
            return True

    return False


def is_autonomous_mode(cwd: str = "") -> bool:
    """Check if any autonomous execution mode is active (godo or appfix).

    This unified check determines if strict completion validation applies.
    """
    return is_godo_mode(cwd) or is_appfix_mode(cwd)


# ============================================================================
# Session Detection
# ============================================================================

def session_made_code_changes(cwd: str) -> bool:
    """Check if THIS session made code changes (not pre-existing changes).

    Compares the current diff hash against the snapshot taken at session start.
    This prevents research-only sessions from being blocked by pre-existing
    uncommitted changes from previous sessions.

    Falls back to git diff check if no snapshot exists (old session format).
    """
    snapshot_path = Path(cwd) / ".claude" / "session-snapshot.json"
    if not snapshot_path.exists():
        # No snapshot = old session format, fall back to git diff check
        return has_code_changes(get_git_diff_files())

    try:
        snapshot = json.loads(snapshot_path.read_text())
        start_hash = snapshot.get("diff_hash_at_start", "")
    except (json.JSONDecodeError, IOError):
        return has_code_changes(get_git_diff_files())

    if not start_hash or start_hash == "unknown":
        # Invalid snapshot, fall back to git diff check
        return has_code_changes(get_git_diff_files())

    current_hash = get_diff_hash(cwd)
    if current_hash == "unknown":
        # Can't determine current state, fall back to git diff check
        return has_code_changes(get_git_diff_files())

    # True if diff changed during this session
    return start_hash != current_hash


def requires_checkpoint(cwd: str, modified_files: list[str]) -> bool:
    """Determine if this session requires a completion checkpoint.

    Checkpoint required when:
    - Autonomous mode is active (godo-state.json or appfix-state.json exists)
    - THIS SESSION made code changes (diff hash changed since session start)
    - A plan file exists for this project

    Checkpoint skipped for:
    - Research/exploration sessions (no code changes in THIS session)
    - Sessions with only pre-existing uncommitted changes from previous sessions
    - Simple file reads, documentation queries
    """
    # CRITICAL: If autonomous mode active (godo or appfix), checkpoint is ALWAYS required
    # This ensures all changes are validated before stopping
    if is_autonomous_mode(cwd):
        return True

    # Check if THIS SESSION made code changes (not pre-existing changes)
    # This is the key fix: don't block sessions that inherited uncommitted changes
    if session_made_code_changes(cwd):
        return True

    # If plan file exists in ~/.claude/plans/, checkpoint required
    plans_dir = Path.home() / ".claude" / "plans"
    if plans_dir.exists() and list(plans_dir.glob("*.md")):
        # Check if any plan matches current project
        cwd_path = str(Path(cwd).resolve()) if cwd else ""
        for plan_file in plans_dir.glob("*.md"):
            try:
                content = plan_file.read_text()
                if cwd_path and cwd_path in content:
                    return True
            except IOError:
                continue

    return False


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    """Main stop hook entry point."""
    # Skip for automation roles
    fleet_role = os.environ.get("FLEET_ROLE", "")
    if fleet_role in ("knowledge_sync", "scheduled_job"):
        log_debug(
            "Skipping: automation role",
            hook_name="stop-validator",
            parsed_data={"fleet_role": fleet_role}
        )
        sys.exit(0)

    # Read and parse stdin
    raw_input = sys.stdin.read()
    log_debug("Stop hook invoked", hook_name="stop-validator", raw_input=raw_input)

    try:
        input_data = json.loads(raw_input) if raw_input else {}
    except json.JSONDecodeError as e:
        log_debug(
            f"JSON parse error: {e}",
            hook_name="stop-validator",
            raw_input=raw_input
        )
        sys.exit(0)

    log_debug("Parsed successfully", hook_name="stop-validator", parsed_data=input_data)

    cwd = input_data.get("cwd", "")
    stop_hook_active = input_data.get("stop_hook_active", False)

    # Get modified files
    modified_files = get_git_diff_files()

    # Check if checkpoint is required for this session
    if not requires_checkpoint(cwd, modified_files):
        log_debug(
            "ALLOWING STOP: no checkpoint required (no code changes, no active plan)",
            hook_name="stop-validator"
        )
        sys.exit(0)

    # Load checkpoint
    checkpoint = load_checkpoint(cwd)

    # =========================================================================
    # FIRST STOP: Require checkpoint file
    # =========================================================================
    if not stop_hook_active:
        if checkpoint is None:
            log_debug("BLOCKING STOP: checkpoint file missing", hook_name="stop-validator")
            block_no_checkpoint(cwd)

        # Checkpoint exists but first stop - validate and block with checklist
        is_valid, failures = validate_checkpoint(checkpoint, modified_files, cwd)
        if not is_valid:
            log_debug(
                "BLOCKING STOP: checkpoint validation failed",
                hook_name="stop-validator",
                parsed_data={"failures": failures}
            )
            block_with_continuation(failures, cwd)

        # Checkpoint valid - allow stop on first try if everything is complete
        log_debug("ALLOWING STOP: checkpoint valid on first stop", hook_name="stop-validator")
        # Clean up state files to prevent stale state affecting future sessions
        deleted = cleanup_autonomous_state(cwd)
        if deleted:
            log_debug(
                "Cleaned up state files on successful stop",
                hook_name="stop-validator",
                parsed_data={"deleted": deleted}
            )
        sys.exit(0)

    # =========================================================================
    # SECOND STOP (stop_hook_active=True): Re-validate checkpoint
    # =========================================================================
    if checkpoint is None:
        log_debug(
            "BLOCKING STOP: second stop but checkpoint file still missing",
            hook_name="stop-validator"
        )
        block_no_checkpoint(cwd)

    is_valid, failures = validate_checkpoint(checkpoint, modified_files, cwd)
    if not is_valid:
        log_debug(
            "BLOCKING STOP: second stop but checkpoint still invalid",
            hook_name="stop-validator",
            parsed_data={"failures": failures}
        )
        block_with_continuation(failures, cwd)

    # All checks pass
    log_debug(
        "ALLOWING STOP: checkpoint valid",
        hook_name="stop-validator",
        parsed_data={"checkpoint": checkpoint}
    )
    # Clean up state files to prevent stale state affecting future sessions
    deleted = cleanup_autonomous_state(cwd)
    if deleted:
        log_debug(
            "Cleaned up state files on successful stop",
            hook_name="stop-validator",
            parsed_data={"deleted": deleted}
        )
    sys.exit(0)


if __name__ == "__main__":
    main()
