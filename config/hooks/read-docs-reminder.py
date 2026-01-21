#!/usr/bin/env python3
"""
SessionStart hook - outputs reminder to read project docs.
Skipped for automation roles (knowledge_sync, scheduled_job).
"""
import os
import sys


def main():
    # Skip for automation roles
    fleet_role = os.environ.get("FLEET_ROLE", "")
    if fleet_role in ("knowledge_sync", "scheduled_job"):
        sys.exit(0)

    # Output the reminder
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
