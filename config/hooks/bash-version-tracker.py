#!/usr/bin/env python3
"""
PostToolUse Hook - Bash Command Version Tracker

Fires after Bash tool to detect version-changing operations and invalidate
stale checkpoint fields. Catches scenarios that Edit/Write hooks miss:

1. git commit → version changes from "abc-dirty" to "def"
2. git push → code is now on remote
3. az CLI commands → infrastructure changed, testing/deployment invalid

Exit codes:
  0 - Success (always exits 0, this is informational only)
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# Add hooks directory to path for shared imports
sys.path.insert(0, str(Path(__file__).parent))
from _common import get_code_version, get_worktree_info
from _session import load_checkpoint, save_checkpoint


def invalidate_stale_fields(checkpoint: dict, current_version: str) -> tuple:
    """No-op stub — new checkpoint schema has no version-stamped fields."""
    return checkpoint, []

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


def matches_any_pattern(command: str, patterns: list[str]) -> bool:
    """Check if command matches any of the given regex patterns."""
    return any(re.search(p, command, re.IGNORECASE) for p in patterns)


def main():
    try:
        input_data = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    cwd = input_data.get("cwd", "")

    if tool_name != "Bash":
        sys.exit(0)

    tool_input = input_data.get("tool_input", {})
    command = tool_input.get("command", "")

    if not command:
        sys.exit(0)

    is_git_commit = matches_any_pattern(command, GIT_COMMIT_PATTERNS)
    is_az_cli = matches_any_pattern(command, AZ_CLI_PATTERNS)

    if not is_git_commit and not is_az_cli:
        sys.exit(0)

    checkpoint = load_checkpoint(cwd)
    if not checkpoint:
        sys.exit(0)

    current_version = get_code_version(cwd)
    if current_version == "unknown":
        sys.exit(0)

    checkpoint, invalidated = invalidate_stale_fields(checkpoint, current_version)

    # For az CLI commands, also mark that testing needs to be re-done
    # (even if version hasn't changed, infrastructure has)
    if is_az_cli:
        report = checkpoint.get("self_report", {})
        for field in ["web_testing_done", "console_errors_checked", "api_testing_done"]:
            if report.get(field, False) and field not in invalidated:
                report[field] = False
                report[f"{field}_at_version"] = ""
                invalidated.append(field)
        report["az_cli_changes_made"] = True

    if invalidated:
        save_checkpoint(cwd, checkpoint)

        reason = "Git commit changed code version" if is_git_commit else "Azure CLI command changed infrastructure"

        worktree_info = get_worktree_info(cwd)
        agent_id = worktree_info.get("agent_id") if worktree_info else None
        worktree_note = (
            f"\nWorktree Agent: {agent_id} (isolated branch)" if agent_id else ""
        )

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
