#!/usr/bin/env python3
"""
PostToolUse Hook - Proactive Checkpoint Invalidation

Fires after Edit/Write tools to detect code changes and proactively
reset version-dependent checkpoint fields. This prevents stale flags
from causing Claude to skip necessary steps (re-lint, re-deploy, re-test).

Exit codes:
  0 - Success (always exits 0, this is informational only)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Add hooks directory to path for shared imports
sys.path.insert(0, str(Path(__file__).parent))
from _common import (
    get_code_version,
    get_worktree_info,
    is_code_file,
    invalidate_stale_fields,
    load_checkpoint,
    save_checkpoint,
)


def main():
    try:
        input_data = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    cwd = input_data.get("cwd", "")

    if tool_name not in ["Edit", "Write"]:
        sys.exit(0)

    tool_input = input_data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    if not file_path:
        sys.exit(0)

    # Skip .claude/ internal files (checkpoint, state files)
    if ".claude/" in file_path or file_path.endswith(".claude"):
        sys.exit(0)

    checkpoint = load_checkpoint(cwd)
    if not checkpoint:
        sys.exit(0)

    current_version = get_code_version(cwd)
    if current_version == "unknown":
        sys.exit(0)

    checkpoint, invalidated = invalidate_stale_fields(checkpoint, current_version)

    if invalidated:
        save_checkpoint(cwd, checkpoint)

        file_type = "code" if is_code_file(file_path) else "config/other"

        worktree_info = get_worktree_info(cwd)
        agent_id = worktree_info.get("agent_id") if worktree_info else None
        worktree_note = (
            f"\nWorktree Agent: {agent_id} (isolated branch)" if agent_id else ""
        )

        fields_str = ", ".join(invalidated)
        print(f"""
⚠️ FILE CHANGE DETECTED - Checkpoint fields invalidated: {fields_str}

You edited ({file_type}): {file_path}
Current version: {current_version}{worktree_note}

These fields were reset to false because the code/config changed since they were set:
{chr(10).join(f"  • {f}: now requires re-verification" for f in invalidated)}

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
