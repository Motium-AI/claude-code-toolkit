#!/usr/bin/env python3
"""
PostToolUse Hook - Bash Command Version Tracker

Fires after Bash tool to detect version-changing operations and invalidate
stale checkpoint fields. Catches scenarios that Edit/Write hooks miss:

1. git commit → version changes from "abc-dirty-xxx" to "def"
2. git push → code is now on remote (affects deployed state)
3. az CLI commands → infrastructure changed, testing/deployment invalid

This hook complements checkpoint-invalidator.py (which handles Edit/Write).

Worktree Support:
- Detects if running in a git worktree (for parallel agent isolation)
- Uses worktree-local checkpoint files for isolation
- Each agent's worktree has independent version tracking

Exit codes:
  0 - Success (always exits 0, this is informational only)
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


# ============================================================================
# Worktree Detection
# ============================================================================


def is_worktree(cwd: str = "") -> bool:
    """Check if the current directory is a git worktree (not the main repo)."""
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


def get_worktree_agent_id(cwd: str = "") -> str | None:
    """Get the agent ID if running in a Claude agent worktree."""
    if not is_worktree(cwd):
        return None
    try:
        # Check for agent state file
        worktree_root = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=cwd or None,
        )
        state_file = (
            Path(worktree_root.stdout.strip()) / ".claude" / "worktree-agent-state.json"
        )
        if state_file.exists():
            state = json.loads(state_file.read_text())
            return state.get("agent_id")
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
        pass
    return None


# ============================================================================
# Configuration
# ============================================================================

# Version tracking exclusions (same as stop-validator.py)
VERSION_TRACKING_EXCLUSIONS = [
    ".",
    ":(exclude).claude",
    ":(exclude).claude/*",
    ":(exclude)*/.claude",
    ":(exclude)*/.claude/*",
    ":(exclude)*.lock",
    ":(exclude)package-lock.json",
    ":(exclude)yarn.lock",
    ":(exclude)pnpm-lock.yaml",
    ":(exclude)poetry.lock",
    ":(exclude)Pipfile.lock",
    ":(exclude)Cargo.lock",
    ":(exclude).gitmodules",
    ":(exclude)*.pyc",
    ":(exclude)__pycache__",
    ":(exclude)*/__pycache__",
    ":(exclude).env*",
    ":(exclude)*.log",
    ":(exclude).DS_Store",
    ":(exclude)*.swp",
    ":(exclude)*.swo",
    ":(exclude)*.orig",
    ":(exclude).idea",
    ":(exclude).idea/*",
    ":(exclude).vscode",
    ":(exclude).vscode/*",
]

# Fields invalidated when code changes (in dependency order)
FIELD_DEPENDENCIES = {
    "linters_pass": [],
    "deployed": ["linters_pass"],
    "web_testing_done": ["deployed"],
    "console_errors_checked": ["deployed"],
    "api_testing_done": ["deployed"],
}

VERSION_DEPENDENT_FIELDS = list(FIELD_DEPENDENCIES.keys())

# Patterns that indicate version-changing commands
GIT_COMMIT_PATTERNS = [
    r"\bgit\s+commit\b",
    r"\bgit\s+cherry-pick\b",
    r"\bgit\s+revert\b",
    r"\bgit\s+merge\b",
    r"\bgit\s+rebase\b",
]

# Patterns that indicate infrastructure changes (require re-testing)
AZ_CLI_PATTERNS = [
    r"\baz\s+containerapp\b",
    r"\baz\s+webapp\b",
    r"\baz\s+functionapp\b",
    r"\baz\s+keyvault\b",
    r"\baz\s+storage\b",
]


def get_code_version(cwd: str = "") -> str:
    """
    Get current code version (git HEAD + dirty indicator).

    Returns format:
    - "abc1234" - clean commit
    - "abc1234-dirty" - commit with uncommitted changes (no hash suffix)
    - "unknown" - not a git repo

    NOTE: The dirty indicator is boolean, NOT a hash. This ensures version
    stability during development - version only changes at commit boundaries.
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
        if diff.stdout.strip():
            return f"{head_hash}-dirty"

        return head_hash
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return "unknown"


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


def save_checkpoint(cwd: str, checkpoint: dict) -> bool:
    """Save checkpoint file back to disk."""
    if not cwd:
        return False
    checkpoint_path = Path(cwd) / ".claude" / "completion-checkpoint.json"
    try:
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        checkpoint_path.write_text(json.dumps(checkpoint, indent=2))
        return True
    except IOError:
        return False


def get_fields_to_invalidate(primary_field: str) -> set[str]:
    """Get all fields that should be invalidated (cascading dependencies)."""
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
    """
    Normalize version by stripping the -dirty suffix.

    This prevents invalidation loops where "abc1234" and "abc1234-dirty"
    are treated as different versions. Only actual commit changes should
    trigger invalidation.
    """
    if version.endswith("-dirty"):
        return version[:-6]
    return version


def invalidate_stale_fields(
    checkpoint: dict, current_version: str
) -> tuple[dict, list[str]]:
    """
    Check all version-dependent fields and invalidate stale ones.

    Versions are normalized before comparison to prevent loops.
    "abc1234" and "abc1234-dirty" are considered the same version.
    """
    report = checkpoint.get("self_report", {})
    invalidated = []

    # Normalize current version for comparison
    current_normalized = normalize_version(current_version)

    for field in VERSION_DEPENDENT_FIELDS:
        if report.get(field, False):
            field_version = report.get(f"{field}_at_version", "")
            if field_version:
                # Normalize field version for comparison
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


def matches_any_pattern(command: str, patterns: list[str]) -> bool:
    """Check if command matches any of the given regex patterns."""
    for pattern in patterns:
        if re.search(pattern, command, re.IGNORECASE):
            return True
    return False


def main():
    try:
        input_data = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    cwd = input_data.get("cwd", "")

    # Only process Bash tool
    if tool_name != "Bash":
        sys.exit(0)

    # Get the command that was executed
    tool_input = input_data.get("tool_input", {})
    command = tool_input.get("command", "")

    if not command:
        sys.exit(0)

    # Check if this was a version-changing or infrastructure command
    is_git_commit = matches_any_pattern(command, GIT_COMMIT_PATTERNS)
    is_az_cli = matches_any_pattern(command, AZ_CLI_PATTERNS)

    if not is_git_commit and not is_az_cli:
        sys.exit(0)

    # Load checkpoint
    checkpoint = load_checkpoint(cwd)
    if not checkpoint:
        sys.exit(0)

    # Get current version
    current_version = get_code_version(cwd)
    if current_version == "unknown":
        sys.exit(0)

    # Invalidate stale fields
    checkpoint, invalidated = invalidate_stale_fields(checkpoint, current_version)

    # For az CLI commands, also mark that testing needs to be re-done
    # (even if version hasn't changed, infrastructure has)
    if is_az_cli:
        report = checkpoint.get("self_report", {})
        az_invalidated = []
        for field in ["web_testing_done", "console_errors_checked", "api_testing_done"]:
            if report.get(field, False) and field not in invalidated:
                report[field] = False
                report[f"{field}_at_version"] = ""
                az_invalidated.append(field)
        invalidated.extend(az_invalidated)
        # Mark that az CLI changes were made
        report["az_cli_changes_made"] = True

    if invalidated:
        # Save updated checkpoint
        save_checkpoint(cwd, checkpoint)

        # Determine reason for invalidation
        if is_git_commit:
            reason = "Git commit changed code version"
        else:
            reason = "Azure CLI command changed infrastructure"

        # Check for worktree context
        agent_id = get_worktree_agent_id(cwd)
        worktree_note = (
            f"\nWorktree Agent: {agent_id} (isolated branch)" if agent_id else ""
        )

        # Output reminder to Claude
        fields_str = ", ".join(invalidated)
        print(f"""
⚠️ {reason.upper()} - Checkpoint fields invalidated: {fields_str}

Command: {command[:100]}{"..." if len(command) > 100 else ""}
Current version: {current_version}{worktree_note}

These fields were reset to false because they're now stale:
{chr(10).join(f"  • {f}: now requires re-verification" for f in invalidated)}

Before stopping, you must:
1. Re-run linters (if linters_pass was reset)
2. Re-deploy (if deployed was reset)
3. Re-test in browser (if web_testing_done was reset)
4. Update checkpoint with new version
""")

    sys.exit(0)


if __name__ == "__main__":
    main()
