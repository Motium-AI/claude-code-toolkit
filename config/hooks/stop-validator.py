#!/usr/bin/env python3
"""
Global Stop Hook Validator - Deterministic Boolean Checkpoints

Two-phase stop flow with completion checkpoint validation:
1. First stop (stop_hook_active=false): Block + require checkpoint file
2. Second stop (stop_hook_active=true): Validate checkpoint booleans

The model MUST fill out .claude/completion-checkpoint.json with honest
boolean answers. The hook deterministically checks these booleans.

Exit codes:
  0 - Allow stop
  2 - Block stop (stderr shown to Claude)
"""
import json
import os
import sys
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

# Debug logging
DEBUG_LOG = Path(tempfile.gettempdir()) / "stop-hook-debug.log"


def log_debug(message: str, raw_input: str = "", parsed_data: dict | None = None) -> None:
    """Log diagnostic info for debugging."""
    try:
        with open(DEBUG_LOG, "a") as f:
            f.write(f"\n{'='*60}\n")
            f.write(f"Timestamp: {datetime.now().isoformat()}\n")
            f.write(f"Message: {message}\n")
            if raw_input:
                f.write(f"Raw stdin ({len(raw_input)} bytes): {repr(raw_input)}\n")
            if parsed_data is not None:
                f.write(f"Parsed data: {json.dumps(parsed_data, indent=2)}\n")
            f.write(f"{'='*60}\n")
    except Exception:
        pass


def get_git_diff_files() -> list[str]:
    """Get list of modified files (staged + unstaged)."""
    try:
        staged = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True, text=True, timeout=5,
        )
        unstaged = subprocess.run(
            ["git", "diff", "--name-only"],
            capture_output=True, text=True, timeout=5,
        )
        staged_files = [f for f in staged.stdout.strip().split("\n") if f]
        unstaged_files = [f for f in unstaged.stdout.strip().split("\n") if f]
        return list(set(staged_files + unstaged_files))
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def has_code_changes(files: list[str]) -> bool:
    """Check if any code files were modified (not just docs/config)."""
    code_extensions = {'.py', '.ts', '.tsx', '.js', '.jsx', '.go', '.rs', '.java', '.rb', '.php'}
    for f in files:
        ext = Path(f).suffix.lower()
        if ext in code_extensions:
            return True
    return False


def has_frontend_changes(files: list[str]) -> bool:
    """Check if any frontend files were modified."""
    frontend_patterns = ['.tsx', '.jsx', 'components/', 'app/', 'pages/', 'hooks/']
    for f in files:
        for pattern in frontend_patterns:
            if pattern in f or f.endswith(pattern.rstrip('/')):
                return True
    return False


def load_checkpoint(cwd: str) -> dict | None:
    """Load completion checkpoint file."""
    if not cwd:
        return None
    checkpoint_path = Path(cwd) / ".claude" / "completion-checkpoint.json"
    if not checkpoint_path.exists():
        return None
    try:
        return json.loads(checkpoint_path.read_text())
    except (json.JSONDecodeError, IOError):
        return None


def validate_checkpoint(checkpoint: dict, modified_files: list[str]) -> tuple[bool, list[str]]:
    """
    Validate checkpoint booleans deterministically.

    Returns (is_valid, list_of_failures)
    """
    failures = []
    report = checkpoint.get("self_report", {})
    reflection = checkpoint.get("reflection", {})

    # Check: is_job_complete must be true
    if not report.get("is_job_complete", False):
        failures.append("is_job_complete is false - YOU said the job isn't done")

    # Get code_changes_made from checkpoint - this is the source of truth for THIS session
    # Even if git diff shows changes, the model might be doing research/audit only
    code_changed = report.get("code_changes_made", False)

    # Only require web_testing, deployment, etc. if code was actually changed
    if code_changed:
        # Check: web_testing_done required if frontend changes
        has_frontend = has_frontend_changes(modified_files)
        if has_frontend and not report.get("web_testing_done", False):
            failures.append("web_testing_done is false - frontend changes require browser testing")

        # Check: if code changes made, should be deployed
        if not report.get("deployed", False):
            # Only fail if there are actual code changes in git
            if has_code_changes(modified_files):
                failures.append("deployed is false - you made code changes but didn't deploy")

        # Check: console_errors_checked should be true if frontend changes
        if has_frontend and not report.get("console_errors_checked", False):
            failures.append("console_errors_checked is false - check browser console for errors")

    # Check: what_remains should be empty or "none"
    what_remains = reflection.get("what_remains", "")
    if what_remains and what_remains.lower() not in ["none", "nothing", "n/a", ""]:
        failures.append(f"what_remains is not empty: '{what_remains}'")

    return len(failures) == 0, failures


def block_no_checkpoint(cwd: str) -> None:
    """Block stop - no checkpoint file exists."""
    checkpoint_path = Path(cwd) / ".claude" / "completion-checkpoint.json" if cwd else ".claude/completion-checkpoint.json"

    print(f"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║  ❌ COMPLETION CHECKPOINT REQUIRED                                            ║
╚═══════════════════════════════════════════════════════════════════════════════╝

You must create {checkpoint_path} before stopping.

This file requires HONEST self-reporting of what you've done:

{{
  "self_report": {{
    "code_changes_made": true,       // Did you modify any code files?
    "web_testing_done": false,       // Did you verify in browser/Surf?
    "api_testing_done": false,       // Did you test API endpoints?
    "deployed": false,               // Did you deploy the changes?
    "console_errors_checked": false, // Did you check browser console?
    "docs_updated": false,           // Did you update relevant docs?
    "is_job_complete": false         // Is the job ACTUALLY done?
  }},
  "reflection": {{
    "what_was_done": "...",          // Honest summary of work completed
    "what_remains": "none",          // Must be empty to allow stop
    "blockers": null                 // Any genuine blockers
  }},
  "evidence": {{
    "urls_tested": [],               // URLs you actually tested
    "console_clean": false           // Was browser console clean?
  }}
}}

DOCUMENTATION REQUIREMENTS (docs_updated):
- docs/TECHNICAL_OVERVIEW.md - Update for architectural changes
- Module docs in docs/ directory - Update for feature changes
- .claude/skills/*/references/ - Update service topology, patterns
- .claude/MEMORIES.md - Significant learnings only (not changelog)

If you answer "false" to required fields and try to stop, you'll be blocked.
The only way to stop is to actually do the work OR have a genuine blocker.

Create this file, answer honestly, then stop again.
""", file=sys.stderr)
    sys.exit(2)


def block_with_continuation(failures: list[str]) -> None:
    """Block stop with specific continuation instructions."""
    failure_list = "\n".join(f"  • {f}" for f in failures)

    print(f"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║  ❌ COMPLETION CHECKPOINT FAILED - CONTINUE WORKING                           ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Your self-report indicates incomplete work:

{failure_list}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
REQUIRED ACTION: Complete the remaining work.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

If web_testing_done is false:
  → Run /webtest or use Chrome MCP to verify in browser
  → Check browser console for errors
  → Update checkpoint with results

If deployed is false (and code was changed):
  → Commit and push: git add <files> && git commit -m "fix: ..." && git push
  → Deploy: gh workflow run deploy.yml && gh run watch --exit-status

If is_job_complete is false:
  → You honestly answered that the job isn't done
  → Complete the remaining work, then update checkpoint

If what_remains is not empty:
  → You listed remaining work: do it!

Update .claude/completion-checkpoint.json, then stop again.
""", file=sys.stderr)
    sys.exit(2)


def requires_checkpoint(cwd: str, modified_files: list[str]) -> bool:
    """
    Determine if this session requires a completion checkpoint.

    Checkpoint required when:
    - Code files were modified
    - A plan file exists for this project

    Checkpoint skipped for:
    - Research/exploration sessions (no code changes)
    - Simple file reads, documentation queries
    """
    # If code files modified, checkpoint required
    if has_code_changes(modified_files):
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


def main():
    # Skip for automation roles
    fleet_role = os.environ.get("FLEET_ROLE", "")
    if fleet_role in ("knowledge_sync", "scheduled_job"):
        log_debug("Skipping: automation role", parsed_data={"fleet_role": fleet_role})
        sys.exit(0)

    # Read and parse stdin
    raw_input = sys.stdin.read()
    log_debug("Stop hook invoked", raw_input=raw_input)

    try:
        input_data = json.loads(raw_input) if raw_input else {}
    except json.JSONDecodeError as e:
        log_debug(f"JSON parse error: {e}", raw_input=raw_input)
        sys.exit(0)

    log_debug("Parsed successfully", parsed_data=input_data)

    cwd = input_data.get("cwd", "")
    session_id = input_data.get("session_id", "")
    stop_hook_active = input_data.get("stop_hook_active", False)

    # Get modified files
    modified_files = get_git_diff_files()

    # Check if checkpoint is required for this session
    if not requires_checkpoint(cwd, modified_files):
        log_debug("ALLOWING STOP: no checkpoint required (no code changes, no active plan)")
        sys.exit(0)

    # Load checkpoint
    checkpoint = load_checkpoint(cwd)

    # =========================================================================
    # FIRST STOP: Require checkpoint file
    # =========================================================================
    if not stop_hook_active:
        if checkpoint is None:
            log_debug("BLOCKING STOP: checkpoint file missing")
            block_no_checkpoint(cwd)

        # Checkpoint exists but first stop - validate and block with checklist
        is_valid, failures = validate_checkpoint(checkpoint, modified_files)
        if not is_valid:
            log_debug("BLOCKING STOP: checkpoint validation failed", parsed_data={"failures": failures})
            block_with_continuation(failures)

        # Checkpoint valid - allow stop on first try if everything is complete
        log_debug("ALLOWING STOP: checkpoint valid on first stop")
        sys.exit(0)

    # =========================================================================
    # SECOND STOP (stop_hook_active=True): Re-validate checkpoint
    # =========================================================================
    if checkpoint is None:
        log_debug("BLOCKING STOP: second stop but checkpoint file still missing")
        block_no_checkpoint(cwd)

    is_valid, failures = validate_checkpoint(checkpoint, modified_files)
    if not is_valid:
        log_debug("BLOCKING STOP: second stop but checkpoint still invalid", parsed_data={"failures": failures})
        block_with_continuation(failures)

    # All checks pass
    log_debug("ALLOWING STOP: checkpoint valid", parsed_data={"checkpoint": checkpoint})
    sys.exit(0)


if __name__ == "__main__":
    main()
