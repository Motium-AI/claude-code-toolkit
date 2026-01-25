#!/usr/bin/env python3
"""
Session Start Hook - Snapshot Git Diff State

Creates .claude/session-snapshot.json with the git diff hash at session start.
The stop hook compares against this to detect if THIS session made changes.

This solves the "pre-existing changes" loop:
- Session A makes changes but doesn't commit
- Session B (research-only) starts and saves the current diff hash
- Session B stops - diff hash unchanged, so no checkpoint required
- Without this, Session B would be blocked because git diff shows changes from A
"""
import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

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


def get_diff_hash(cwd: str) -> str:
    """
    Get hash of current git diff (excluding metadata files).

    Excludes lock files, IDE config, .claude/, and other non-code files
    that shouldn't affect version tracking.
    """
    try:
        result = subprocess.run(
            ["git", "diff", "HEAD", "--"] + VERSION_TRACKING_EXCLUSIONS,
            capture_output=True, text=True, timeout=5,
            cwd=cwd or None,
        )
        return hashlib.sha1(result.stdout.encode()).hexdigest()[:12]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return "unknown"


def main():
    input_data = json.loads(sys.stdin.read() or "{}")
    cwd = input_data.get("cwd", "")

    if not cwd:
        sys.exit(0)

    snapshot_path = Path(cwd) / ".claude" / "session-snapshot.json"
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)

    snapshot = {
        "diff_hash_at_start": get_diff_hash(cwd),
        "session_started_at": datetime.now().isoformat(),
    }

    snapshot_path.write_text(json.dumps(snapshot, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
