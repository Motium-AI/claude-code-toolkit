#!/usr/bin/env python3
"""
Compound Context Loader - SessionStart Hook

Injects relevant solutions from docs/solutions/ at session start.
Gracefully exits if no solutions directory exists.

Part of the Compound Memory System that enables cross-session learning.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Add hooks directory to path for shared imports
sys.path.insert(0, str(Path(__file__).parent))

from _common import log_debug

MAX_SOLUTIONS = 2
MAX_CHARS = 2000


def main():
    input_data = json.loads(sys.stdin.read() or "{}")
    cwd = input_data.get("cwd", "")

    if not cwd:
        sys.exit(0)

    solutions_dir = Path(cwd) / "docs" / "solutions"
    if not solutions_dir.exists():
        sys.exit(0)

    # Find all solution markdown files
    solution_files = []
    for md_file in solutions_dir.rglob("*.md"):
        # Skip .gitkeep and other non-solution files
        if md_file.name.startswith(".") or md_file.name == ".gitkeep":
            continue
        try:
            mtime = md_file.stat().st_mtime
            solution_files.append((mtime, md_file))
        except OSError:
            continue

    if not solution_files:
        log_debug(
            "No solution files found",
            hook_name="compound-context-loader",
            parsed_data={"solutions_dir": str(solutions_dir)},
        )
        sys.exit(0)

    # Sort by mtime (most recent first), take top N
    solution_files.sort(reverse=True, key=lambda x: x[0])
    recent = solution_files[:MAX_SOLUTIONS]

    # Build context summary
    summaries = []
    for _, path in recent:
        try:
            content = path.read_text()
            # Extract title from frontmatter or first heading
            title = path.stem.replace("-", " ").title()
            for line in content.split("\n"):
                if line.startswith("title:"):
                    title = line.split(":", 1)[1].strip().strip("\"'")
                    break
                if line.startswith("# "):
                    title = line[2:].strip()
                    break

            category = path.parent.name
            summaries.append(f"- [{category}] {title}")
        except (IOError, OSError):
            continue

    if not summaries:
        sys.exit(0)

    # Format output (plain text, not JSON - SessionStart hooks use plain print)
    output = "[compound-context-loader] Recent solutions in docs/solutions/:\n"
    output += "\n".join(summaries)
    output += "\n\nRun `grep -riwl 'keyword' docs/solutions/` to find relevant fixes."

    if len(output) > MAX_CHARS:
        output = output[: MAX_CHARS - 3] + "..."

    log_debug(
        "Injecting solution context",
        hook_name="compound-context-loader",
        parsed_data={"solutions_count": len(summaries), "output_chars": len(output)},
    )

    print(output)
    sys.exit(0)


if __name__ == "__main__":
    main()
