#!/usr/bin/env python3
"""
Activity-Based Stop Validator

Task-agnostic stop hook that validates based on what the session DID,
not what skill mode is active. Replaces the old mode-specific validation
(4 paths: /go, /improve, default-web, default-mobile) with a single
universal path.

Rules:
1. If session made no code changes -> allow stop (still capture memory)
2. If session made code changes -> require lightweight checkpoint:
   - is_job_complete: true
   - what_was_done: >20 chars
   - what_remains: "none"
   - key_insight: >50 chars (for cross-session memory)
   - search_terms: 2-7 keywords (for memory retrieval)
   - category: enum (for memory categorization)
3. No mode-specific paths - one schema fits all

Exit codes:
  0 - Allow stop
  2 - Block stop (stderr shown to Claude)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _common import get_diff_hash, get_code_version, log_debug, timed_hook, VERSION_TRACKING_EXCLUSIONS
from _session import (
    load_checkpoint,
    reset_state_for_next_task,
    is_autonomous_mode_active,
)


# Valid categories for memory events
VALID_CATEGORIES = frozenset({
    "bugfix", "gotcha", "architecture", "pattern", "config", "refactor",
})

CHECKPOINT_SCHEMA = """\
{
  "self_report": {
    "is_job_complete": false,
    "code_changes_made": false,
    "linters_pass": false,
    "category": ""
  },
  "reflection": {
    "what_was_done": "...",
    "what_remains": "none",
    "key_insight": "...",
    "search_terms": [],
    "memory_that_helped": []
  }
}"""


# ============================================================================
# Session Detection
# ============================================================================


def session_made_code_changes(cwd: str) -> bool:
    """Check if THIS session made code changes by comparing diff hashes."""
    snapshot_path = Path(cwd) / ".claude" / "session-snapshot.json"
    if not snapshot_path.exists():
        return False  # No snapshot = can't determine, allow stop

    try:
        snapshot = json.loads(snapshot_path.read_text())
        start_hash = snapshot.get("diff_hash_at_start", "")
    except (json.JSONDecodeError, IOError):
        return False

    if not start_hash or start_hash == "unknown":
        return False

    current_hash = get_diff_hash(cwd)
    return current_hash != "unknown" and start_hash != current_hash


def requires_checkpoint(cwd: str) -> bool:
    """Determine if this session requires a completion checkpoint.

    Checkpoint required when:
    - Autonomous mode active AND this session made code changes
    - Non-autonomous but this session made code changes

    Checkpoint NOT required for:
    - Read-only sessions (even in autonomous mode) <- THE KEY FIX
    - Sessions at HOME directory
    """
    if cwd:
        try:
            if Path(cwd).resolve() == Path.home().resolve():
                return False
        except (ValueError, OSError):
            pass

    if is_autonomous_mode_active(cwd):
        if not session_made_code_changes(cwd):
            log_debug(
                "Autonomous mode active but no code changes - skipping checkpoint",
                hook_name="stop-validator",
            )
            return False
        return True

    return session_made_code_changes(cwd)


# ============================================================================
# Validation
# ============================================================================


def validate_checkpoint(checkpoint: dict) -> tuple[bool, list[str]]:
    """Validate checkpoint - ONE universal path, no mode branching."""
    failures = []
    report = checkpoint.get("self_report", {})
    reflection = checkpoint.get("reflection", {})

    # 1. Core completion
    if not report.get("is_job_complete", False):
        failures.append("is_job_complete is false - you said the job isn't done")

    what_remains = reflection.get("what_remains", "")
    if what_remains and what_remains.lower() not in ("none", "nothing", "n/a", ""):
        failures.append(f"what_remains is not empty: '{what_remains}'")

    # 2. Work description
    what_done = reflection.get("what_was_done", "")
    if not what_done or len(what_done.strip()) < 20:
        failures.append("what_was_done is missing or too brief (need >20 chars)")

    # 3. Linters (only when code was changed)
    if report.get("code_changes_made", False):
        if not report.get("linters_pass", False):
            failures.append("linters_pass required - you changed code, run the linter")

    # 4. Memory quality fields
    key_insight = reflection.get("key_insight", "")
    if not key_insight or len(key_insight.strip()) < 50:
        failures.append(
            "key_insight is missing or too brief (need >50 chars) - "
            "what reusable lesson should FUTURE sessions know?"
        )
    elif what_done and key_insight.strip()[:40] == what_done.strip()[:40]:
        failures.append(
            "key_insight is a copy of what_was_done - "
            "key_insight should be the LESSON, not a repeat of what you did"
        )

    search_terms = reflection.get("search_terms", [])
    if not isinstance(search_terms, list) or len(search_terms) < 2:
        failures.append("search_terms needs 2-7 concept keywords for memory retrieval")
    elif len(search_terms) > 7:
        failures.append("search_terms has too many entries (max 7)")

    category = report.get("category", "")
    if not category or category.lower() not in VALID_CATEGORIES:
        failures.append(
            f"category must be one of: {', '.join(sorted(VALID_CATEGORIES))}"
        )

    return len(failures) == 0, failures


# ============================================================================
# Memory Capture
# ============================================================================


def _get_git_diff_files(cwd: str) -> list[str]:
    """Get list of modified files from git diff."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD", "--"] + VERSION_TRACKING_EXCLUSIONS,
            capture_output=True, text=True, timeout=5, cwd=cwd,
        )
        return [f for f in result.stdout.strip().split("\n") if f.strip()]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def auto_capture_memory(cwd: str, checkpoint: dict) -> None:
    """Archive checkpoint as a memory event for cross-session learning."""
    try:
        from _memory import append_event, append_assertion
    except ImportError:
        return

    reflection = checkpoint.get("reflection", {})
    report = checkpoint.get("self_report", {})

    what_done = reflection.get("what_was_done", "")
    if not what_done or len(what_done) < 20:
        return

    # Build LESSON-first content
    content_parts = []
    key_insight = reflection.get("key_insight", "")
    if key_insight and len(key_insight.strip()) > 10:
        content_parts.append(f"LESSON: {key_insight.strip()}")
    content_parts.append(f"DONE: {what_done[:200]}")
    content = "\n".join(content_parts)

    # Entity sourcing: model search_terms + git diff files
    entities = []
    search_terms = reflection.get("search_terms", [])
    if isinstance(search_terms, list):
        for term in search_terms[:7]:
            if isinstance(term, str) and len(term.strip()) >= 2:
                entities.append(term.strip().lower())

    for f in _get_git_diff_files(cwd)[:5]:
        parts = f.strip().split("/")
        entities.append(parts[-1])
        if len(parts) >= 2:
            entities.append("/".join(parts[-2:]))

    entities = list(dict.fromkeys(entities))  # dedup preserving order

    category = report.get("category", "session")
    problem_type = report.get("problem_type", "")
    valid_problem_types = {
        "race-condition", "config-mismatch", "api-change", "import-resolution",
        "state-management", "crash-safety", "data-integrity", "performance",
        "tooling", "dependency-management",
    }
    if problem_type and problem_type not in valid_problem_types:
        problem_type = ""

    try:
        append_event(
            cwd=cwd,
            content=content,
            entities=entities,
            event_type="session_end",
            source="auto-capture",
            category=category,
            problem_type=problem_type,
        )
        log_debug(
            "Auto-captured memory event",
            hook_name="stop-validator",
            parsed_data={"entities": entities[:5], "category": category},
        )
    except Exception as e:
        log_debug(f"Auto-capture failed: {e}", hook_name="stop-validator")

    # Core assertions
    try:
        core_assertions = reflection.get("core_assertions", [])
        if isinstance(core_assertions, list):
            for item in core_assertions[:5]:
                if isinstance(item, dict):
                    topic = item.get("topic", "")
                    assertion = item.get("assertion", "")
                    if topic and assertion:
                        append_assertion(cwd, topic, assertion)
    except Exception:
        pass


# ============================================================================
# Blocking Messages
# ============================================================================


def has_uncommitted_changes(cwd: str) -> bool:
    """Check if there are uncommitted code changes in the working tree."""
    version = get_code_version(cwd)
    return version.endswith("-dirty")


def block_uncommitted_changes(cwd: str) -> None:
    """Block stop - uncommitted changes in autonomous mode."""
    print(
        """
╔═══════════════════════════════════════════════════════════════╗
║  UNCOMMITTED CHANGES — COMMIT BEFORE STOPPING                 ║
╚═══════════════════════════════════════════════════════════════╝

You have uncommitted code changes. In autonomous mode, commit your work
before stopping:

  git add <files> && git commit -m "feat/fix/refactor: [description]"

Then try stopping again.
""",
        file=sys.stderr,
    )
    sys.exit(2)


def block_no_checkpoint(cwd: str) -> None:
    """Block stop - no checkpoint file exists."""
    checkpoint_path = (
        Path(cwd) / ".claude" / "completion-checkpoint.json"
        if cwd else ".claude/completion-checkpoint.json"
    )
    categories = ", ".join(sorted(VALID_CATEGORIES))
    print(
        f"""
╔═══════════════════════════════════════════════════════════════╗
║  COMPLETION CHECKPOINT REQUIRED                               ║
╚═══════════════════════════════════════════════════════════════╝

Create {checkpoint_path} before stopping:

{CHECKPOINT_SCHEMA}

RULES:
- is_job_complete must be true
- what_was_done must be >20 chars
- what_remains must be "none"
- linters_pass required only if code_changes_made is true
- key_insight: >50 chars, what you LEARNED (not what you did)
- search_terms: 2-7 concept keywords
- category: {categories}

Create this file, answer honestly, then stop again.
""",
        file=sys.stderr,
    )
    sys.exit(2)


def block_with_failures(failures: list[str]) -> None:
    """Block stop - checkpoint validation failed."""
    failure_list = "\n".join(f"  * {f}" for f in failures)
    print(
        f"""
╔═══════════════════════════════════════════════════════════════╗
║  CHECKPOINT FAILED - CONTINUE WORKING                         ║
╚═══════════════════════════════════════════════════════════════╝

{failure_list}

Fix these issues, update .claude/completion-checkpoint.json, then stop again.
""",
        file=sys.stderr,
    )
    sys.exit(2)


# ============================================================================
# Main
# ============================================================================


def main():
    """Main stop hook entry point."""
    fleet_role = os.environ.get("FLEET_ROLE", "")
    if fleet_role in ("knowledge_sync", "scheduled_job"):
        sys.exit(0)

    raw_input = sys.stdin.read()
    log_debug("Stop hook invoked", hook_name="stop-validator", raw_input=raw_input)

    try:
        input_data = json.loads(raw_input) if raw_input else {}
    except json.JSONDecodeError:
        sys.exit(0)

    cwd = input_data.get("cwd", "")
    stop_hook_active = input_data.get("stop_hook_active", False)

    # Check if checkpoint is required for this session
    if not requires_checkpoint(cwd):
        log_debug(
            "ALLOWING STOP: no checkpoint required",
            hook_name="stop-validator",
        )
        # Still capture memory if checkpoint exists
        checkpoint = load_checkpoint(cwd)
        if checkpoint:
            auto_capture_memory(cwd, checkpoint)
        sys.exit(0)

    checkpoint = load_checkpoint(cwd)

    is_autonomous = is_autonomous_mode_active(cwd)

    # FIRST STOP: require checkpoint file
    if not stop_hook_active:
        if checkpoint is None:
            block_no_checkpoint(cwd)

        is_valid, failures = validate_checkpoint(checkpoint)
        if not is_valid:
            block_with_failures(failures)

        # Gate: uncommitted changes in autonomous mode
        if is_autonomous and has_uncommitted_changes(cwd):
            log_debug(
                "BLOCKING STOP: uncommitted changes in autonomous mode",
                hook_name="stop-validator",
            )
            block_uncommitted_changes(cwd)

        # Valid - capture memory and allow stop
        log_debug("ALLOWING STOP: checkpoint valid", hook_name="stop-validator")
        auto_capture_memory(cwd, checkpoint)
        reset_state_for_next_task(cwd)
        sys.exit(0)

    # SECOND STOP (stop_hook_active=True): re-validate
    if checkpoint is None:
        block_no_checkpoint(cwd)

    is_valid, failures = validate_checkpoint(checkpoint)
    if not is_valid:
        block_with_failures(failures)

    # Gate: uncommitted changes in autonomous mode (re-check)
    if is_autonomous and has_uncommitted_changes(cwd):
        log_debug(
            "BLOCKING STOP: uncommitted changes in autonomous mode (2nd stop)",
            hook_name="stop-validator",
        )
        block_uncommitted_changes(cwd)

    log_debug("ALLOWING STOP: checkpoint valid", hook_name="stop-validator")
    auto_capture_memory(cwd, checkpoint)
    reset_state_for_next_task(cwd)
    sys.exit(0)


if __name__ == "__main__":
    with timed_hook("stop-validator"):
        main()
