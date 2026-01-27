#!/usr/bin/env python3
"""
SessionStart hook - outputs reminder to read project docs.
Outputs DIFFERENT messages based on event source:
- compact: Strong warning about incomplete memory
- startup/resume/clear: Standard doc reading reminder
"""
from __future__ import annotations

import json
import os
import sys


def find_existing_docs(cwd: str) -> list[tuple[str, str]]:
    """Find which standard doc files exist in the project."""
    from pathlib import Path

    candidates = [
        ("CLAUDE.md", "coding standards"),
        (".claude/MEMORIES.md", "session context"),
        ("docs/index.md", "documentation hub"),
        ("docs/TECHNICAL_OVERVIEW.md", "architecture and system design"),
    ]
    found = []
    base = Path(cwd) if cwd else Path.cwd()
    for path, desc in candidates:
        if (base / path).exists():
            found.append((path, desc))
    return found


def main():
    # Skip for automation roles
    fleet_role = os.environ.get("FLEET_ROLE", "")
    if fleet_role in ("knowledge_sync", "scheduled_job"):
        sys.exit(0)

    # Parse input to determine event source
    source = "startup"  # default
    cwd = ""
    try:
        input_data = json.load(sys.stdin)
        source = input_data.get("source", "startup")
        cwd = input_data.get("cwd", "")
    except (json.JSONDecodeError, EOFError):
        pass

    existing = find_existing_docs(cwd)

    if source == "compact":
        # STRONG message for compaction - this is when memory is actually lost
        if existing:
            file_list = "\n".join(
                f"{i}. {path} - {desc}" for i, (path, desc) in enumerate(existing, 1)
            )
            print(
                "\u26a0\ufe0f CONTEXT COMPACTION DETECTED - CRITICAL INSTRUCTION \u26a0\ufe0f\n\n"
                "You have just experienced context compaction. Your memory of this project is now INCOMPLETE.\n\n"
                "STOP. Do NOT respond to the user yet.\n\n"
                "You MUST read these files FIRST using the Read tool:\n"
                f"{file_list}\n\n"
                "This is NOT optional. Do NOT skip this step. Do NOT summarize from memory.\n"
                "The compacted summary is insufficient - you need the actual file contents.\n\n"
                "Read the docs NOW before doing anything else."
            )
        else:
            print(
                "\u26a0\ufe0f CONTEXT COMPACTION DETECTED \u26a0\ufe0f\n\n"
                "You have just experienced context compaction. Your memory of this project is now INCOMPLETE.\n\n"
                "No standard doc files (CLAUDE.md, docs/index.md, .claude/MEMORIES.md) were found in this project.\n"
                "Explore the codebase structure before responding to the user."
            )
    else:
        # Standard message for startup/resume/clear
        if existing:
            file_refs = " ".join(
                f"({i}) {path} - {desc}" for i, (path, desc) in enumerate(existing, 1)
            )
            print(
                "MANDATORY: Before executing ANY user request, you MUST use the Read tool to read these files IN ORDER: "
                f"{file_refs}. "
                "DO NOT skip this step. DO NOT summarize from memory. Actually READ the files. "
                "The user expects informed responses based on current project state, not generic assistance."
            )
        # If no docs exist, don't output anything - no point referencing missing files

    sys.exit(0)


if __name__ == "__main__":
    main()
