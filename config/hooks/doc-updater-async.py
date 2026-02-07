#!/usr/bin/env python3
"""
PostToolUse Hook - Async Documentation Updater

Fires after Bash tool to detect git commits during repair/build sessions.
When a commit is detected, spawns an async Sonnet agent to update relevant
documentation based on the diff.

This hook is designed to:
1. Detect git commit commands in Bash tool output
2. Only fire during autonomous mode (repair/build)
3. Launch an async agent with the /heavy skill for multi-perspective doc analysis
4. Allow the main session to continue while docs are updated in background

Exit codes:
  0 - Success (always exits 0, this is informational only)
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add hooks directory to path for shared imports
sys.path.insert(0, str(Path(__file__).parent))
from _common import log_debug
from _session import is_autonomous_mode_active


# Patterns that indicate a commit was made
GIT_COMMIT_PATTERNS = [
    r"\bgit\s+commit\b",
    r"\bgit\s+cherry-pick\b",
    r"\bgit\s+merge\b",
]

# Documentation directories to check for relevance
DOC_DIRECTORIES = [
    "docs/",
    "README.md",
    "CLAUDE.md",
    ".claude/MEMORIES.md",
    ".claude/skills/*/references/",
]


def matches_any_pattern(command: str, patterns: list[str]) -> bool:
    """Check if command matches any of the given regex patterns."""
    for pattern in patterns:
        if re.search(pattern, command, re.IGNORECASE):
            return True
    return False


def has_actual_git_command(command: str, patterns: list[str]) -> bool:
    """Check if any command segment is actually a git operation matching patterns.

    Splits the command by shell operators (&&, ||, ;, |) and only matches
    segments that start with 'git'. This prevents false positives from
    commands like: echo '...git commit...' | python3 hook.py
    """
    segments = re.split(r'\s*(?:&&|\|\||;|\|)\s*', command)
    for segment in segments:
        segment = segment.strip()
        if segment.startswith("git ") or segment == "git":
            if matches_any_pattern(segment, patterns):
                return True
    return False


def get_recent_commit_diff(cwd: str) -> tuple[str, str]:
    """Get the diff from the most recent commit.

    Returns: (commit_message, diff_content)
    """
    try:
        # Get the commit message
        msg_result = subprocess.run(
            ["git", "log", "-1", "--format=%B"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=cwd or None,
        )
        commit_message = msg_result.stdout.strip()

        # Get the diff (stat + patch for context)
        diff_result = subprocess.run(
            ["git", "show", "--stat", "--patch", "HEAD"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=cwd or None,
        )
        diff_content = diff_result.stdout.strip()

        # Truncate if too long (keep first 8000 chars)
        if len(diff_content) > 8000:
            diff_content = diff_content[:8000] + "\n\n... [truncated - diff too long]"

        return commit_message, diff_content
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        log_debug(f"Error getting commit diff: {e}")
        return "", ""


def get_existing_docs(cwd: str) -> list[str]:
    """Get list of existing documentation files."""
    docs = []
    try:
        for pattern in DOC_DIRECTORIES:
            if pattern.endswith(".md"):
                # Specific file
                path = Path(cwd) / pattern
                if path.exists():
                    docs.append(pattern)
            else:
                # Directory pattern
                base_pattern = pattern.rstrip("/")
                glob_pattern = f"{base_pattern}/**/*.md" if "**" not in base_pattern else base_pattern
                for match in Path(cwd).glob(glob_pattern.replace("**/", "")):
                    rel_path = str(match.relative_to(cwd))
                    if rel_path not in docs:
                        docs.append(rel_path)
    except Exception as e:
        log_debug(f"Error finding docs: {e}")
    return docs


def create_doc_update_task_file(cwd: str, commit_message: str, diff_content: str, existing_docs: list[str]) -> str:
    """Create a task file for the async agent.

    Returns: path to the task file
    """
    task_dir = Path(cwd) / ".claude" / "async-tasks"
    task_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    task_file = task_dir / f"doc-update-{timestamp}.json"

    task = {
        "type": "doc-update",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "pending",
        "commit_message": commit_message,
        "diff_content": diff_content,
        "existing_docs": existing_docs,
        "instructions": f"""
DOCUMENTATION UPDATE TASK

A commit was just made in an repair/build session. Your job is to:

1. Analyze the diff to understand what changed
2. Determine which documentation files need updating
3. Update the relevant docs to reflect the changes

COMMIT MESSAGE:
{commit_message}

EXISTING DOCUMENTATION FILES:
{chr(10).join(f"- {doc}" for doc in existing_docs)}

DIFF CONTENT:
{diff_content}

INSTRUCTIONS:
- Only update docs that are actually affected by this change
- Keep updates concise and accurate
- Don't add unnecessary documentation
- If the change is purely code (no architectural/API changes), you may skip doc updates
- Focus on: API changes, new features, architectural decisions, configuration changes

Use the /heavy skill if you need multiple perspectives on what to document.
""",
    }

    task_file.write_text(json.dumps(task, indent=2))
    return str(task_file)



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

    # Only fire during autonomous mode
    if not is_autonomous_mode_active(cwd):
        sys.exit(0)

    # Get the command that was executed
    tool_input = input_data.get("tool_input", {})
    command = tool_input.get("command", "")

    if not command:
        sys.exit(0)

    # Check if this was a git commit (must be an actual git command segment,
    # not just the string "git commit" inside echo/pipe arguments)
    if not has_actual_git_command(command, GIT_COMMIT_PATTERNS):
        sys.exit(0)

    log_debug(f"[doc-updater-async] Git commit detected: {command[:80]}")

    # Get commit info
    commit_message, diff_content = get_recent_commit_diff(cwd)
    if not diff_content:
        log_debug("[doc-updater-async] No diff content, skipping")
        sys.exit(0)

    # Get existing docs
    existing_docs = get_existing_docs(cwd)
    if not existing_docs:
        log_debug("[doc-updater-async] No docs found, skipping")
        sys.exit(0)

    # Create task file
    task_file = create_doc_update_task_file(cwd, commit_message, diff_content, existing_docs)
    log_debug(f"[doc-updater-async] Task file created: {task_file}")

    # Output suggestion for spawning async agent
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": f"""
ASYNC DOC UPDATE TASK CREATED

A commit was detected during this repair/build session.
Task file: {task_file}

After completing the fix-verify loop, you may spawn a background agent to update docs:

Task(
    description="Update docs from commit",
    subagent_type="general-purpose",
    model="sonnet",
    run_in_background=true,
    prompt="Read the task file at {task_file} and update relevant documentation. Commit message: {commit_message[:100]}"
)
""",
        }
    }

    print(json.dumps(output))
    sys.exit(0)


if __name__ == "__main__":
    main()
