#!/usr/bin/env python3
"""
PostToolUse Hook - Proactive Checkpoint Invalidation

Fires after Edit/Write tools to detect code changes and proactively
reset version-dependent checkpoint fields. This prevents stale flags
from causing Claude to skip necessary steps (re-lint, re-deploy, re-test).

Problem this solves:
1. Deploy at version A → checkpoint: deployed=true
2. Test finds error → write fix → version becomes B
3. WITHOUT this hook: Claude sees deployed=true, skips re-deploy
4. WITH this hook: deployed is reset to false immediately after edit

Worktree Support:
- Detects if running in a git worktree (for parallel agent isolation)
- Uses worktree-local checkpoint files for isolation
- Each agent's worktree has independent checkpoint state

Exit codes:
  0 - Success (always exits 0, this is informational only)
"""
from __future__ import annotations

import json
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


def get_worktree_agent_id(cwd: str = "") -> str | None:
    """Get the agent ID if running in a Claude agent worktree."""
    if not is_worktree(cwd):
        return None
    try:
        # Check for agent state file
        worktree_root = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=5,
            cwd=cwd or None,
        )
        state_file = Path(worktree_root.stdout.strip()) / ".claude" / "worktree-agent-state.json"
        if state_file.exists():
            state = json.loads(state_file.read_text())
            return state.get("agent_id")
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
        pass
    return None


# ============================================================================
# Configuration
# ============================================================================

# Code file extensions that trigger checkpoint invalidation
CODE_EXTENSIONS = {
    # Application code
    '.py', '.ts', '.tsx', '.js', '.jsx', '.go', '.rs',
    '.java', '.rb', '.php', '.vue', '.svelte',
    # Infrastructure as Code
    '.tf', '.tfvars',       # Terraform
    '.bicep',               # Azure Bicep
    '.yaml', '.yml',        # K8s, CI/CD, CloudFormation
    # Database and scripts
    '.sql',                 # Database migrations/changes
    '.sh', '.bash',         # Shell scripts
}

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

# Fields invalidated when code changes (in dependency order)
# When a field is invalidated, all fields that depend on it are also invalidated
FIELD_DEPENDENCIES = {
    # linters_pass depends on code not changing
    "linters_pass": [],
    # deployed depends on linters passing
    "deployed": ["linters_pass"],
    # testing depends on deployment
    "web_testing_done": ["deployed"],
    "console_errors_checked": ["deployed"],
    "api_testing_done": ["deployed"],
}

# All version-dependent fields
VERSION_DEPENDENT_FIELDS = list(FIELD_DEPENDENCIES.keys())


def get_code_version(cwd: str = "") -> str:
    """
    Get current code version (git HEAD + dirty indicator).

    Returns format:
    - "abc1234" - clean commit
    - "abc1234-dirty" - commit with uncommitted changes (no hash suffix)
    - "unknown" - not a git repo

    NOTE: The dirty indicator is boolean, NOT a hash. This ensures version
    stability during development - version only changes at commit boundaries,
    not on every file edit. This prevents checkpoint invalidation loops.

    Excludes metadata files (lock files, IDE config, .claude/, etc.) from
    dirty calculation.
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


def is_code_file(file_path: str) -> bool:
    """Check if file is a code file based on extension."""
    return Path(file_path).suffix.lower() in CODE_EXTENSIONS


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
    """
    Get all fields that should be invalidated when primary_field changes.
    Uses dependency graph to cascade invalidations.
    """
    to_invalidate = {primary_field}

    # Find all fields that depend on the primary field (directly or transitively)
    changed = True
    while changed:
        changed = False
        for field, deps in FIELD_DEPENDENCIES.items():
            if field not in to_invalidate:
                # If any dependency is invalidated, this field is too
                if any(dep in to_invalidate for dep in deps):
                    to_invalidate.add(field)
                    changed = True

    return to_invalidate


def invalidate_stale_fields(checkpoint: dict, current_version: str) -> tuple[dict, list[str]]:
    """
    Check all version-dependent fields and invalidate stale ones.
    Returns (modified_checkpoint, list_of_invalidated_fields).
    """
    report = checkpoint.get("self_report", {})
    invalidated = []

    for field in VERSION_DEPENDENT_FIELDS:
        if report.get(field, False):
            field_version = report.get(f"{field}_at_version", "")
            if field_version and field_version != current_version:
                # Field is stale - invalidate it and all dependents
                fields_to_reset = get_fields_to_invalidate(field)
                for f in fields_to_reset:
                    if report.get(f, False):
                        report[f] = False
                        report[f"{f}_at_version"] = ""
                        if f not in invalidated:
                            invalidated.append(f)

    return checkpoint, invalidated


def main():
    try:
        input_data = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    cwd = input_data.get("cwd", "")

    # Only process Edit and Write tools
    if tool_name not in ["Edit", "Write"]:
        sys.exit(0)

    # Get the file that was edited
    tool_input = input_data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    if not file_path:
        sys.exit(0)

    # Skip .claude/ internal files (checkpoint, state files)
    # These don't represent code changes
    if ".claude/" in file_path or file_path.endswith(".claude"):
        sys.exit(0)

    # Load checkpoint
    checkpoint = load_checkpoint(cwd)
    if not checkpoint:
        sys.exit(0)

    # Get current version and check for stale fields
    current_version = get_code_version(cwd)
    if current_version == "unknown":
        sys.exit(0)

    # Invalidate stale fields
    checkpoint, invalidated = invalidate_stale_fields(checkpoint, current_version)

    if invalidated:
        # Save updated checkpoint
        save_checkpoint(cwd, checkpoint)

        # Determine if this was a code file or other file
        is_code = is_code_file(file_path)
        file_type = "code" if is_code else "config/other"

        # Check for worktree context
        agent_id = get_worktree_agent_id(cwd)
        worktree_note = f"\nWorktree Agent: {agent_id} (isolated branch)" if agent_id else ""

        # Output reminder to Claude
        fields_str = ", ".join(invalidated)
        print(f"""
⚠️ FILE CHANGE DETECTED - Checkpoint fields invalidated: {fields_str}

You edited ({file_type}): {file_path}
Current version: {current_version}{worktree_note}

These fields were reset to false because the code/config changed since they were set:
{chr(10).join(f'  • {f}: now requires re-verification' for f in invalidated)}

IMPORTANT: These fields are now FALSE in the checkpoint file. You MUST:
1. Re-run linters if linters_pass was reset
2. Re-deploy if deployed was reset
3. Re-test in browser if web_testing_done was reset
4. Update checkpoint with new *_at_version fields

DO NOT set these fields to true without actually performing the actions!
""")

    sys.exit(0)


if __name__ == "__main__":
    main()
