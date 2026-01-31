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
)
from _checkpoint import load_checkpoint
from _state import (
    cleanup_checkpoint_only,
    reset_state_for_next_task,
    is_autonomous_mode_active,
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
    - Autonomous mode is active (build-state.json or appfix-state.json exists)
    - THIS SESSION made code changes (diff hash changed since session start)
    - A plan file exists for this project

    Checkpoint skipped for:
    - Research/exploration sessions (no code changes in THIS session)
    - Sessions with only pre-existing uncommitted changes from previous sessions
    - Simple file reads, documentation queries
    - Sessions where cwd is HOME (not a project directory)
    """
    # HOME directory is not a project — checkpoint path would be ~/.claude/
    # which contains toolkit symlinks, not project checkpoints. Any checkpoint
    # there is stale from a different session. Skip validation entirely.
    if cwd:
        try:
            if Path(cwd).resolve() == Path.home().resolve():
                log_debug(
                    "SKIPPING: cwd is HOME directory, not a project",
                    hook_name="stop-validator",
                )
                return False
        except (ValueError, OSError):
            pass

    # CRITICAL: If autonomous mode active (build or appfix), checkpoint is ALWAYS required
    # This ensures all changes are validated before stopping
    if is_autonomous_mode_active(cwd):
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
            parsed_data={"fleet_role": fleet_role},
        )
        sys.exit(0)

    # Read and parse stdin
    raw_input = sys.stdin.read()
    log_debug("Stop hook invoked", hook_name="stop-validator", raw_input=raw_input)

    try:
        input_data = json.loads(raw_input) if raw_input else {}
    except json.JSONDecodeError as e:
        log_debug(
            f"JSON parse error: {e}", hook_name="stop-validator", raw_input=raw_input
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
            hook_name="stop-validator",
        )
        sys.exit(0)

    # Load checkpoint
    checkpoint = load_checkpoint(cwd)

    # =========================================================================
    # FIRST STOP: Require checkpoint file
    # =========================================================================
    if not stop_hook_active:
        if checkpoint is None:
            log_debug(
                "BLOCKING STOP: checkpoint file missing", hook_name="stop-validator"
            )
            block_no_checkpoint(cwd)

        # Checkpoint exists but first stop - validate and block with checklist
        is_valid, failures = validate_checkpoint(checkpoint, modified_files, cwd)
        if not is_valid:
            log_debug(
                "BLOCKING STOP: checkpoint validation failed",
                hook_name="stop-validator",
                parsed_data={"failures": failures},
            )
            block_with_continuation(failures, cwd)

        # Checkpoint valid - allow stop on first try if everything is complete
        log_debug(
            "ALLOWING STOP: checkpoint valid on first stop", hook_name="stop-validator"
        )

        # Auto-capture: archive checkpoint as memory event
        _auto_capture_memory(cwd, checkpoint)

        # Sticky session: clean only checkpoint, keep mode state for next task
        deleted = cleanup_checkpoint_only(cwd)
        if deleted:
            log_debug(
                "Cleaned up checkpoint (sticky session: mode state preserved)",
                hook_name="stop-validator",
                parsed_data={"deleted": deleted},
            )
        # Reset per-task fields for the next task iteration
        if reset_state_for_next_task(cwd):
            log_debug(
                "Reset state for next task (iteration incremented)",
                hook_name="stop-validator",
            )
        sys.exit(0)

    # =========================================================================
    # SECOND STOP (stop_hook_active=True): Re-validate checkpoint
    # =========================================================================
    if checkpoint is None:
        log_debug(
            "BLOCKING STOP: second stop but checkpoint file still missing",
            hook_name="stop-validator",
        )
        block_no_checkpoint(cwd)

    is_valid, failures = validate_checkpoint(checkpoint, modified_files, cwd)
    if not is_valid:
        log_debug(
            "BLOCKING STOP: second stop but checkpoint still invalid",
            hook_name="stop-validator",
            parsed_data={"failures": failures},
        )
        block_with_continuation(failures, cwd)

    # All checks pass
    log_debug(
        "ALLOWING STOP: checkpoint valid",
        hook_name="stop-validator",
        parsed_data={"checkpoint": checkpoint},
    )

    # Auto-capture: archive checkpoint as memory event
    _auto_capture_memory(cwd, checkpoint)

    # Sticky session: clean only checkpoint, keep mode state for next task
    deleted = cleanup_checkpoint_only(cwd)
    if deleted:
        log_debug(
            "Cleaned up checkpoint (sticky session: mode state preserved)",
            hook_name="stop-validator",
            parsed_data={"deleted": deleted},
        )
    # Reset per-task fields for the next task iteration
    if reset_state_for_next_task(cwd):
        log_debug(
            "Reset state for next task (iteration incremented)",
            hook_name="stop-validator",
        )
    sys.exit(0)


def _auto_capture_memory(cwd: str, checkpoint: dict) -> None:
    """Archive completion checkpoint as a memory event.

    This is the PRIMARY capture path — zero user effort.
    Runs on every successful stop with code changes.

    v3: Model-provided search_terms as primary entities, lesson-first
    content with truncated context, top-level category, quality metadata.
    """
    try:
        from _memory import append_event
    except ImportError:
        return

    self_report = checkpoint.get("self_report", {})
    reflection = checkpoint.get("reflection", {})

    # Quality gate: skip if no meaningful content
    what_was_done = reflection.get("what_was_done", "")
    if not what_was_done or len(what_was_done) < 20:
        return

    # Skip if no code changes
    if not self_report.get("code_changes_made", False):
        return

    # Build LESSON-first content (lesson IS the memory; done is context)
    content_parts = []
    key_insight = reflection.get("key_insight", "")
    if key_insight and len(key_insight.strip()) > 10:
        content_parts.append(f"LESSON: {key_insight.strip()}")
    content_parts.append(f"DONE: {what_was_done[:200]}")
    content = "\n".join(content_parts)

    # Entity sourcing: model-provided search_terms FIRST, git diff SECOND
    entities = []

    # PRIMARY: model-declared concept keywords (highest retrieval value)
    search_terms = reflection.get("search_terms", [])
    if isinstance(search_terms, list):
        for term in search_terms[:7]:
            if isinstance(term, str) and len(term.strip()) >= 2:
                entities.append(term.strip().lower())

    # SECONDARY: git diff file paths (basename + parent/base enrichment)
    files_changed = self_report.get("files_changed", [])
    if not files_changed:
        files_changed = get_git_diff_files()
    for f in files_changed[:5]:
        parts = f.split("/")
        entities.append(parts[-1])                  # "_memory.py"
        if len(parts) >= 2:
            entities.append("/".join(parts[-2:]))   # "hooks/_memory.py"

    entities = list(dict.fromkeys(entities))        # dedup preserving order

    # Category from checkpoint (validated upstream by _sv_validators)
    category = self_report.get("category", "")
    if not category or category.lower() in ("session", ""):
        category = "session"

    # Quality tier for scoring
    has_lesson = bool(key_insight and len(key_insight.strip()) > 10)
    has_terms = bool(search_terms and len(search_terms) >= 2)
    quality = "rich" if (has_lesson and has_terms) else "standard"

    try:
        append_event(
            cwd=cwd,
            content=content,
            entities=entities,
            event_type="session_end",
            source="auto-capture",
            category=category,
            meta={
                "quality": quality,
                "files_changed": files_changed[:5],
            },
        )
        log_debug(
            "Auto-captured memory event from checkpoint",
            hook_name="stop-validator",
            parsed_data={
                "entities": entities[:5],
                "quality": quality,
                "category": category,
            },
        )
    except Exception as e:
        log_debug(
            f"Auto-capture failed: {e}",
            hook_name="stop-validator",
        )

    # Record injection utility (feedback loop)
    _record_injection_utility(cwd, checkpoint)


def _record_injection_utility(cwd: str, checkpoint: dict) -> None:
    """Record which injected memories were cited by the model.

    Reads memory_that_helped from checkpoint, validates IDs against
    injection-log.json, and updates manifest utility counters.
    """
    reflection = checkpoint.get("reflection", {})
    helped = reflection.get("memory_that_helped", [])
    if not isinstance(helped, list):
        helped = []

    # Read injection log
    log_path = Path(cwd) / ".claude" / "injection-log.json"
    if not log_path.exists():
        return
    try:
        log_data = json.loads(log_path.read_text())
    except (json.JSONDecodeError, IOError, OSError):
        return

    # Staleness guard: cross-check session_id
    snap_path = Path(cwd) / ".claude" / "session-snapshot.json"
    if snap_path.exists():
        try:
            snap = json.loads(snap_path.read_text())
            if log_data.get("session_id") and snap.get("session_id"):
                if log_data["session_id"] != snap["session_id"]:
                    return  # Stale log from a different session
        except (json.JSONDecodeError, IOError):
            pass

    injected_ids = [e["id"] for e in log_data.get("events", []) if e.get("id")]
    if not injected_ids:
        return

    # Validate helped IDs against injected IDs (drop hallucinated IDs)
    valid_helped = set(str(h) for h in helped if h) & set(injected_ids)

    try:
        from _memory import record_utility
        record_utility(cwd, injected_ids, valid_helped)
        log_debug(
            "Recorded injection utility",
            hook_name="stop-validator",
            parsed_data={
                "injected": len(injected_ids),
                "cited": len(valid_helped),
            },
        )
    except (ImportError, Exception) as e:
        log_debug(f"Utility recording failed: {e}", hook_name="stop-validator")


if __name__ == "__main__":
    main()
