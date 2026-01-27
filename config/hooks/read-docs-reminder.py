#!/usr/bin/env python3
"""
SessionStart hook - outputs reminder to read project docs.
Outputs DIFFERENT messages based on event source:
- compact: Strong warning about incomplete memory
- startup/resume/clear: Standard doc reading reminder
"""
import json
import os
import sys


def main():
    # Skip for automation roles
    fleet_role = os.environ.get("FLEET_ROLE", "")
    if fleet_role in ("knowledge_sync", "scheduled_job"):
        sys.exit(0)

    # Parse input to determine event source
    source = "startup"  # default
    try:
        input_data = json.load(sys.stdin)
        source = input_data.get("source", "startup")
    except (json.JSONDecodeError, EOFError):
        pass

    if source == "compact":
        # STRONG message for compaction - this is when memory is actually lost
        print(
            "⚠️ CONTEXT COMPACTION DETECTED - CRITICAL INSTRUCTION ⚠️\n\n"
            "You have just experienced context compaction. Your memory of this project is now INCOMPLETE.\n\n"
            "STOP. Do NOT respond to the user yet.\n\n"
            "You MUST read these files FIRST using the Read tool:\n"
            "1. CLAUDE.md - coding standards (REQUIRED)\n"
            "2. .claude/MEMORIES.md - session context (REQUIRED)\n"
            "3. docs/index.md - documentation hub (REQUIRED)\n"
            "4. docs/TECHNICAL_OVERVIEW.md - architecture (if exists)\n\n"
            "This is NOT optional. Do NOT skip this step. Do NOT summarize from memory.\n"
            "The compacted summary is insufficient - you need the actual file contents.\n\n"
            "Read the docs NOW before doing anything else."
        )
    else:
        # Standard message for startup/resume/clear - less urgent, builds good habit
        print(
            "MANDATORY: Before executing ANY user request, you MUST use the Read tool to read these files IN ORDER: "
            "(1) docs/index.md - project documentation hub with architecture links "
            "(2) CLAUDE.md - coding standards you MUST follow "
            "(3) .claude/MEMORIES.md - prior session context "
            "(4) docs/TECHNICAL_OVERVIEW.md - architecture and system design (if exists). "
            "DO NOT skip this step. DO NOT summarize from memory. Actually READ the files. "
            "The user expects informed responses based on current project state, not generic assistance."
        )

    sys.exit(0)


if __name__ == "__main__":
    main()
