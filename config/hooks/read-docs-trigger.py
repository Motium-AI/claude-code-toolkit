#!/usr/bin/env python3
"""
UserPromptSubmit hook - triggers documentation reading when user says "read the docs".
Suggests QMD search when available, falls back to keyword-based doc suggestions.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def check_qmd_available() -> bool:
    """Check if QMD MCP server is configured in .mcp.json."""
    mcp_paths = [
        Path.cwd() / ".mcp.json",
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


# Fallback: discover docs dynamically from project structure (no QMD)
# Used only when QMD is not available — scans for docs/ directories and index files.
def _discover_doc_paths(cwd: str) -> list[str]:
    """Find documentation files in the project (max depth 3, limit 10)."""
    base = Path(cwd) if cwd else Path.cwd()
    found = []
    # Priority: docs/index.md, then any docs/*.md, then README.md
    for pattern in ["docs/index.md", "docs/*.md", "**/docs/index.md", "README.md"]:
        for p in base.glob(pattern):
            rel = str(p.relative_to(base))
            if rel not in found and "node_modules" not in rel:
                found.append(rel)
            if len(found) >= 10:
                return found
    return found


def suggest_relevant_docs(message: str, cwd: str = "") -> list[str]:
    """Return list of docs relevant to the user's message (fallback for non-QMD).

    Uses dynamic file discovery instead of hardcoded paths.
    """
    doc_paths = _discover_doc_paths(cwd)
    if not doc_paths:
        return []
    # Match message keywords against doc filenames/paths
    message_lower = message.lower()
    scored = []
    for path in doc_paths:
        path_lower = path.lower()
        # Score by keyword overlap with path components
        parts = path_lower.replace("/", " ").replace("-", " ").replace("_", " ").replace(".md", "").split()
        overlap = sum(1 for part in parts if part in message_lower and len(part) > 2)
        scored.append((path, overlap))
    # Sort by relevance, then return top 3 (always include docs/index.md if it exists)
    scored.sort(key=lambda x: x[1], reverse=True)
    return [p for p, _ in scored[:3]]


def main():
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    message = input_data.get("message", "").lower()
    cwd = input_data.get("cwd", "")
    qmd_available = check_qmd_available()

    # Check for keyword-based doc suggestions (fallback for non-QMD repos)
    suggested_docs = suggest_relevant_docs(message, cwd)

    # Only show full reminder when user explicitly requests doc reading
    if "read the docs" in message:
        if qmd_available:
            reminder = """Consider using the Skill tool for this task. Relevant skills:
  - /docs-navigator (matched: 'read the docs')

**QMD is available.** Use semantic search for documentation:

1. Search for relevant docs:
   qmd_search "your task description"

2. Read the top 1-3 matches:
   qmd_get "qmd://collection/path/to/doc.md"

3. Apply the patterns and conventions documented there

Do NOT read all docs. Use QMD to find only what's relevant."""
        else:
            reminder = """Consider using the Skill tool for this task. Relevant skills:
  - /docs-navigator (matched: 'read the docs')

Before starting this task, you MUST:

1. Read docs/index.md to understand the documentation structure
2. Read docs/TECHNICAL_OVERVIEW.md for mid-level system understanding
3. Use the docs-navigator skill pattern to identify relevant docs
4. Match your task keywords to the index keywords
5. Read ONLY the 1-3 most relevant docs (not all)
6. Apply the patterns and conventions documented there

Do NOT skip this step. Do NOT read all docs. Read smart, not everything."""
        print(reminder)
    elif qmd_available and suggested_docs:
        # QMD available + keywords detected - suggest QMD search
        hint = f"""Consider using the Skill tool for this task. Relevant skills:
  - /docs-navigator (matched keywords in message)

**QMD is available.** For documentation related to your task, use:

qmd_search "{message[:50]}..."

This will find relevant docs via semantic search."""
        print(hint)
    elif suggested_docs:
        # Fallback: suggest specific docs based on keywords detected
        docs_list = "\n  - ".join(suggested_docs)
        hint = f"""Consider using the Skill tool for this task. Relevant skills:
  - /docs-navigator (matched: 'read the docs')

Based on your task, these docs may be relevant:
  - {docs_list}

Read these BEFORE starting work to understand existing patterns."""
        print(hint)

    sys.exit(0)


if __name__ == "__main__":
    main()
