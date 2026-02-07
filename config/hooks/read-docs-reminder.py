#!/usr/bin/env python3
"""
SessionStart hook - outputs reminder to use QMD for documentation lookup.
Outputs DIFFERENT messages based on event source:
- compact: Strong warning about incomplete memory + QMD recovery
- startup/resume/clear: QMD-first doc lookup reminder
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def check_qmd_available(cwd: str) -> bool:
    """Check if QMD MCP server is configured."""
    mcp_paths = [
        Path(cwd) / ".mcp.json" if cwd else Path.cwd() / ".mcp.json",
        Path.home() / ".claude" / "settings.json",
    ]
    for mcp_path in mcp_paths:
        if mcp_path.exists():
            try:
                with open(mcp_path) as f:
                    config = json.load(f)
                    servers = config.get("mcpServers", {})
                    if "qmd" in servers:
                        return True
            except (json.JSONDecodeError, OSError):
                continue
    return False


def find_essential_docs(cwd: str) -> list[tuple[str, str]]:
    """Find which essential docs exist (only CLAUDE.md and MEMORIES.md)."""
    candidates = [
        ("CLAUDE.md", "coding standards"),
        (".claude/MEMORIES.md", "session context"),
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

    qmd_available = check_qmd_available(cwd)
    essential_docs = find_essential_docs(cwd)

    if source == "compact":
        # STRONG message for compaction - this is when memory is actually lost
        if qmd_available:
            print(
                "\u26a0\ufe0f CONTEXT COMPACTION DETECTED - CRITICAL INSTRUCTION \u26a0\ufe0f\n\n"
                "You have just experienced context compaction. Your memory of this project is now INCOMPLETE.\n\n"
                "STOP. Do NOT respond to the user yet.\n\n"
                "Recovery steps:\n"
                "1. Read CLAUDE.md (root) for project overview and coding standards\n"
                "2. Read .claude/MEMORIES.md for session context and prior decisions\n"
                "3. Use QMD search for any deeper context your task needs:\n"
                '   qmd_search "your task topic"  — finds relevant docs across all indexed projects\n\n'
                "Do NOT manually read docs/index.md, TECHNICAL_OVERVIEW.md, or subdirectory CLAUDE.md files.\n"
                "QMD searches all indexed documentation — search, don't browse."
            )
        else:
            if essential_docs:
                file_list = "\n".join(
                    f"{i}. {path} - {desc}"
                    for i, (path, desc) in enumerate(essential_docs, 1)
                )
                print(
                    "\u26a0\ufe0f CONTEXT COMPACTION DETECTED \u26a0\ufe0f\n\n"
                    "You have just experienced context compaction. Your memory of this project is now INCOMPLETE.\n\n"
                    "STOP. Do NOT respond to the user yet.\n\n"
                    "You MUST read these files FIRST using the Read tool:\n"
                    f"{file_list}\n\n"
                    "Then read docs/index.md to find task-relevant documentation."
                )
            else:
                print(
                    "\u26a0\ufe0f CONTEXT COMPACTION DETECTED \u26a0\ufe0f\n\n"
                    "You have just experienced context compaction. Your memory of this project is now INCOMPLETE.\n\n"
                    "Explore the codebase structure before responding to the user."
                )
    else:
        # Standard message for startup/resume/clear
        if qmd_available:
            print(
                "MANDATORY: Before executing ANY user request, you MUST:\n"
                "1. Read CLAUDE.md — project overview and coding standards (always read this)\n"
                "2. Read .claude/MEMORIES.md — session context and prior decisions\n"
                "3. For ANY deeper documentation needs, use QMD search instead of manual file reads:\n"
                '   qmd_search "topic"  — fast semantic search across all indexed documentation\n'
                '   qmd_get "path"      — retrieve a specific document by path\n\n'
                "Do NOT manually read docs/index.md, TECHNICAL_OVERVIEW.md, or subdirectory CLAUDE.md files.\n"
                "QMD replaces manual doc browsing — search for what you need, when you need it."
            )
        elif essential_docs:
            file_refs = " ".join(
                f"({i}) {path} - {desc}"
                for i, (path, desc) in enumerate(essential_docs, 1)
            )
            print(
                "MANDATORY: Before executing ANY user request, you MUST use the Read tool to read these files IN ORDER: "
                f"{file_refs}. "
                "Then read docs/index.md to find task-relevant documentation. "
                "DO NOT skip this step. DO NOT summarize from memory."
            )

    sys.exit(0)


if __name__ == "__main__":
    main()
