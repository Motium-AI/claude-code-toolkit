#!/usr/bin/env python3
"""
PostToolUse Hook - Doc Debt Tracker

Fires after Bash to detect git commits. Tracks documentation debt in
.claude/doc-debt.json — a lightweight registry of commits that may
require documentation updates.

Debt is surfaced at next session start by compound-context-loader.py.
Debt is cleared when a commit touches documentation files.

Replaces the old async task file approach (task files accumulated
without a processor). This design works because:
- Detection happens at commit time (PostToolUse)
- Surfacing happens at session start (compound-context-loader)
- No async agents needed — the model sees the debt and decides

Exit codes:
  0 - Always (informational only)
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import log_debug, timed_hook

# Patterns that indicate a commit was made
GIT_COMMIT_PATTERNS = [
    r"\bgit\s+commit\b",
    r"\bgit\s+cherry-pick\b",
    r"\bgit\s+merge\b",
]

# Updating these files clears doc debt (debt is paid)
DOC_PATTERNS = {"docs/", "README.md", ".claude/MEMORIES.md", "CLAUDE.md"}

MAX_DEBT_ENTRIES = 10


def has_actual_git_command(command: str, patterns: list[str]) -> bool:
    """Check if any command segment is actually a git operation.

    Splits by shell operators and only matches segments starting with 'git'.
    Prevents false positives from echo/pipe arguments containing git strings.
    """
    segments = re.split(r'\s*(?:&&|\|\||;|\|)\s*', command)
    for segment in segments:
        segment = segment.strip()
        if segment.startswith("git ") or segment == "git":
            for pattern in patterns:
                if re.search(pattern, segment, re.IGNORECASE):
                    return True
    return False


def get_last_commit_info(cwd: str) -> tuple[str, str, list[str]]:
    """Get commit hash, message, and changed files from HEAD."""
    try:
        hash_r = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5, cwd=cwd,
        )
        msg_r = subprocess.run(
            ["git", "log", "-1", "--format=%s"],
            capture_output=True, text=True, timeout=5, cwd=cwd,
        )
        files_r = subprocess.run(
            ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"],
            capture_output=True, text=True, timeout=5, cwd=cwd,
        )
        commit_hash = hash_r.stdout.strip()
        message = msg_r.stdout.strip()
        files = [f for f in files_r.stdout.strip().split("\n") if f.strip()]
        return commit_hash, message, files
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return "", "", []


def touches_docs(changed_files: list[str]) -> bool:
    """Check if any changed files are documentation."""
    for f in changed_files:
        for pattern in DOC_PATTERNS:
            if pattern.endswith("/"):
                if f.startswith(pattern):
                    return True
            elif f == pattern or f.endswith("/" + pattern):
                return True
    return False


def main():
    try:
        input_data = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        sys.exit(0)

    if input_data.get("tool_name") != "Bash":
        sys.exit(0)

    cwd = input_data.get("cwd", "")
    command = input_data.get("tool_input", {}).get("command", "")
    if not cwd or not command:
        sys.exit(0)

    if not has_actual_git_command(command, GIT_COMMIT_PATTERNS):
        sys.exit(0)

    commit_hash, message, changed_files = get_last_commit_info(cwd)
    if not commit_hash:
        sys.exit(0)

    debt_path = Path(cwd) / ".claude" / "doc-debt.json"
    debt_path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing debt
    debt = {"entries": []}
    try:
        if debt_path.exists():
            debt = json.loads(debt_path.read_text())
    except (json.JSONDecodeError, IOError):
        pass

    # If this commit touches docs, clear all debt (debt is paid)
    if touches_docs(changed_files):
        debt = {
            "entries": [],
            "last_doc_update": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        debt_path.write_text(json.dumps(debt, indent=2))
        log_debug(
            f"Doc debt cleared by commit {commit_hash}",
            hook_name="doc-debt-tracker",
        )
        sys.exit(0)

    # Skip non-code files (lock files, config, etc.)
    code_extensions = {".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".rb", ".sh"}
    code_files = [
        f for f in changed_files
        if any(f.endswith(ext) for ext in code_extensions)
    ]
    if not code_files:
        sys.exit(0)

    # Dedup: skip if this commit is already tracked
    tracked_hashes = {e.get("commit", "") for e in debt.get("entries", [])}
    if commit_hash in tracked_hashes:
        sys.exit(0)

    # Append debt entry
    entries = debt.get("entries", [])
    entries.append({
        "commit": commit_hash,
        "message": message[:120],
        "changed_files": code_files[:10],
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    })

    # FIFO eviction
    debt["entries"] = entries[-MAX_DEBT_ENTRIES:]
    debt_path.write_text(json.dumps(debt, indent=2))

    log_debug(
        f"Doc debt recorded: {commit_hash} ({message[:60]})",
        hook_name="doc-debt-tracker",
        parsed_data={"files": code_files[:5], "total_debt": len(debt["entries"])},
    )
    sys.exit(0)


if __name__ == "__main__":
    with timed_hook("doc-debt-tracker"):
        main()
