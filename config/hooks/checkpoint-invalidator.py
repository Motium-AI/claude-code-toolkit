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

Exit codes:
  0 - Success (always exits 0, this is informational only)
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

# Code file extensions that trigger checkpoint invalidation
CODE_EXTENSIONS = {
    '.py', '.ts', '.tsx', '.js', '.jsx', '.go', '.rs',
    '.java', '.rb', '.php', '.vue', '.svelte'
}

# Files/patterns excluded from version tracking (dirty calculation)
# These don't represent code changes requiring re-deployment
VERSION_TRACKING_EXCLUSIONS = [
    ":(exclude).claude/",
    ":(exclude)*.lock",
    ":(exclude)package-lock.json",
    ":(exclude)yarn.lock",
    ":(exclude)pnpm-lock.yaml",
    ":(exclude)poetry.lock",
    ":(exclude)Pipfile.lock",
    ":(exclude)Cargo.lock",
    ":(exclude).gitmodules",
    ":(exclude)*.pyc",
    ":(exclude)__pycache__/",
    ":(exclude).env*",
    ":(exclude)*.log",
    ":(exclude).DS_Store",
    ":(exclude)*.swp",
    ":(exclude)*.swo",
    ":(exclude)*.orig",
    ":(exclude).idea/",
    ":(exclude).vscode/",
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
    Get current code version (git HEAD + dirty state hash).

    Excludes metadata files (lock files, IDE config, .claude/, etc.) from
    dirty calculation. This prevents version-dependent checkpoint fields
    from becoming stale when only metadata changes (not actual code).
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
        if diff.stdout:
            dirty_hash = hashlib.sha1(diff.stdout.encode()).hexdigest()[:7]
            return f"{head_hash}-dirty-{dirty_hash}"

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

    # Only invalidate for code files
    if not file_path or not is_code_file(file_path):
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

        # Output reminder to Claude
        fields_str = ", ".join(invalidated)
        print(f"""
⚠️ CODE CHANGE DETECTED - Checkpoint fields invalidated: {fields_str}

You edited: {file_path}
Current version: {current_version}

These fields were reset to false because the code changed since they were set:
{chr(10).join(f'  • {f}: now requires re-verification' for f in invalidated)}

Before stopping, you must:
1. Re-run linters (if linters_pass was reset)
2. Re-deploy (if deployed was reset)
3. Re-test in browser (if web_testing_done was reset)
4. Update checkpoint with new version
""")

    sys.exit(0)


if __name__ == "__main__":
    main()
