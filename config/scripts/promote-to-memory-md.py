#!/usr/bin/env python3
"""
Promote high-utility compound memory events to native MEMORY.md.

Standalone script (not a hook). Reads utility data from manifest.json,
identifies events with high citation-to-injection ratios, and appends
their LESSON content to MEMORY.md under the "## Promoted Lessons" heading.

Usage:
    python3 config/scripts/promote-to-memory-md.py [--dry-run]
"""

from __future__ import annotations

import argparse
import glob
import json
import subprocess
import sys
from pathlib import Path

# Add hooks dir for shared imports
HOOKS_DIR = Path(__file__).resolve().parent.parent / "hooks"
sys.path.insert(0, str(HOOKS_DIR))

from _memory import get_project_hash, safe_read_event, atomic_write_json, MEMORY_ROOT

# Promotion thresholds
MIN_RATIO = 0.3       # cited / injected >= 0.3
MIN_INJECTIONS = 5    # Must have been injected at least 5 times
MAX_PROMOTIONS = 3    # Max promotions per run


def _find_native_memory_md(cwd: str) -> Path | None:
    """Locate the native MEMORY.md file for this project."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=5, cwd=cwd,
        )
        repo_root = result.stdout.strip()
        if not repo_root:
            return None

        # Claude Code encodes paths: replace / and _ with -
        encoded = repo_root.replace("/", "-").replace("_", "-").lstrip("-")
        memory_path = (
            Path.home() / ".claude" / "projects"
            / f"-{encoded}" / "memory" / "MEMORY.md"
        )
        if memory_path.exists():
            return memory_path

        # Glob fallback
        pattern = str(
            Path.home() / ".claude" / "projects"
            / "*-claude-code-toolkit" / "memory" / "MEMORY.md"
        )
        for match in glob.glob(pattern):
            p = Path(match)
            if p.exists():
                return p
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return None


def _load_sidecar(sidecar_path: Path) -> dict:
    """Load promoted-events.json sidecar (tracks already-promoted events)."""
    if not sidecar_path.exists():
        return {"promoted": []}
    try:
        return json.loads(sidecar_path.read_text())
    except (json.JSONDecodeError, IOError):
        return {"promoted": []}


def _find_candidates(cwd: str, already_promoted: set[str]) -> list[dict]:
    """Find events qualifying for promotion based on utility data.

    Criteria: cited/injected >= MIN_RATIO AND injected >= MIN_INJECTIONS.
    Sorted by ratio descending.
    """
    project_hash = get_project_hash(cwd)
    manifest_path = MEMORY_ROOT / project_hash / "manifest.json"

    if not manifest_path.exists():
        return []

    try:
        manifest = json.loads(manifest_path.read_text())
    except (json.JSONDecodeError, IOError):
        return []

    utility = manifest.get("utility", {}).get("events", {})
    if not utility:
        return []

    event_dir = MEMORY_ROOT / project_hash / "events"
    candidates = []

    for event_id, stats in utility.items():
        if event_id in already_promoted:
            continue

        injected = stats.get("injected", 0)
        cited = stats.get("cited", 0)

        if injected < MIN_INJECTIONS:
            continue

        ratio = cited / injected
        if ratio < MIN_RATIO:
            continue

        # Load the actual event to get LESSON content
        event = safe_read_event(event_dir / f"{event_id}.json")
        if not event:
            continue

        content = event.get("content", "").strip()
        if not content:
            continue

        # Extract just the LESSON line (first line starting with LESSON:)
        lesson = ""
        for line in content.split("\n"):
            if line.startswith("LESSON:"):
                lesson = line
                break
        if not lesson:
            # Use full content if no LESSON prefix, but truncate
            lesson = content.split("\n")[0][:200]

        candidates.append({
            "event_id": event_id,
            "injected": injected,
            "cited": cited,
            "ratio": round(ratio, 2),
            "lesson": lesson,
            "category": event.get("category", "session"),
        })

    # Sort by ratio descending, then by cited count
    candidates.sort(key=lambda c: (c["ratio"], c["cited"]), reverse=True)
    return candidates


def main():
    parser = argparse.ArgumentParser(description="Promote high-utility memory events to MEMORY.md")
    parser.add_argument("--dry-run", action="store_true", help="Show candidates without writing")
    args = parser.parse_args()

    cwd = str(Path(__file__).resolve().parent.parent.parent)

    # Find MEMORY.md
    memory_md = _find_native_memory_md(cwd)
    if not memory_md:
        print("ERROR: Native MEMORY.md not found. Create it first.")
        sys.exit(1)

    # Load sidecar
    project_hash = get_project_hash(cwd)
    sidecar_path = MEMORY_ROOT / project_hash / "promoted-events.json"
    sidecar = _load_sidecar(sidecar_path)
    already_promoted = set(sidecar.get("promoted", []))

    # Find candidates
    candidates = _find_candidates(cwd, already_promoted)

    if not candidates:
        print("No events qualify for promotion.")
        print(f"  Criteria: cited/injected >= {MIN_RATIO}, injected >= {MIN_INJECTIONS}")
        sys.exit(0)

    # Show candidates
    print(f"Found {len(candidates)} candidate(s):\n")
    for i, c in enumerate(candidates):
        marker = " *" if i < MAX_PROMOTIONS else ""
        print(f"  [{c['ratio']:.0%}] {c['event_id']} (injected={c['injected']}, cited={c['cited']}){marker}")
        print(f"         {c['lesson'][:120]}")
        print()

    to_promote = candidates[:MAX_PROMOTIONS]
    print(f"Will promote top {len(to_promote)} event(s).")

    if args.dry_run:
        print("\n--dry-run: No changes made.")
        sys.exit(0)

    # Append to MEMORY.md under ## Promoted Lessons
    current_content = memory_md.read_text(encoding="utf-8")

    new_lines = []
    for c in to_promote:
        # Format: - **[category]** lesson text (event_id, ratio)
        new_lines.append(
            f"- **[{c['category']}]** {c['lesson']} "
            f"_({c['event_id']}, {c['ratio']:.0%} cite rate)_"
        )

    append_text = "\n".join(new_lines) + "\n"

    # Insert after "## Promoted Lessons" heading if it exists
    if "## Promoted Lessons" in current_content:
        # Append after the heading
        idx = current_content.index("## Promoted Lessons") + len("## Promoted Lessons")
        # Find the end of that line
        newline_idx = current_content.index("\n", idx)
        updated = current_content[:newline_idx + 1] + "\n" + append_text + current_content[newline_idx + 1:]
    else:
        # Append section at end
        updated = current_content.rstrip() + "\n\n## Promoted Lessons\n\n" + append_text

    memory_md.write_text(updated, encoding="utf-8")
    print(f"\nAppended {len(to_promote)} lesson(s) to {memory_md}")

    # Update sidecar
    promoted_ids = sidecar.get("promoted", [])
    for c in to_promote:
        promoted_ids.append(c["event_id"])
    sidecar["promoted"] = promoted_ids
    atomic_write_json(sidecar_path, sidecar)
    print(f"Updated sidecar: {sidecar_path}")


if __name__ == "__main__":
    main()
