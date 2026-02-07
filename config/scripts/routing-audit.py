#!/usr/bin/env python3
"""
Post-session routing audit — detects behavioral patterns from tool usage logs.

Reads .claude/tool-usage-log.json and runs pattern detectors to identify
sessions where the agent may have been in the wrong skill mode.

Usage:
    python3 routing-audit.py [project-dir]

Detectors:
    edit_test_loop  — same file edited 3+ times with same bash command between
    grep_storm      — 5+ search operations in 60s with no edit
    file_thrash     — 3+ edits to same file with no test between
    debug_in_build  — debug-pattern bash commands while in melt/burndown mode
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path


# Pattern detection thresholds
EDIT_TEST_LOOP_MIN = 3
GREP_STORM_WINDOW_S = 60
GREP_STORM_MIN = 5
FILE_THRASH_MIN = 3

# Debug command patterns (substrings)
DEBUG_PATTERNS = [
    "curl -sf", "curl --fail", "/health",
    "docker logs", "az containerapp logs",
    "console.log", "print(", "pdb",
    "LOGFIRE", "logfire",
]

SEARCH_TOOLS = {"Grep", "Glob", "Read"}
EDIT_TOOLS = {"Edit", "Write"}
TEST_TOOLS = {"Bash"}


def load_log(project_dir: str) -> list[dict]:
    """Load tool usage log from project directory."""
    log_path = Path(project_dir) / ".claude" / "tool-usage-log.json"
    if not log_path.exists():
        return []
    try:
        entries = json.loads(log_path.read_text())
        return entries if isinstance(entries, list) else []
    except (json.JSONDecodeError, IOError):
        return []


def load_mode(project_dir: str) -> str | None:
    """Load the autonomous mode from state file."""
    state_path = Path(project_dir) / ".claude" / "autonomous-state.json"
    if not state_path.exists():
        return None
    try:
        state = json.loads(state_path.read_text())
        return state.get("mode")
    except (json.JSONDecodeError, IOError):
        return None


def detect_edit_test_loop(entries: list[dict]) -> list[dict]:
    """Detect same file edited 3+ times with same bash command between edits."""
    findings = []
    file_edit_counts: dict[str, list[float]] = defaultdict(list)
    bash_between: dict[str, set[str]] = defaultdict(set)

    for entry in entries:
        tool = entry.get("tool", "")
        sig = entry.get("sig", "")
        t = entry.get("t", 0)

        if tool in EDIT_TOOLS and sig:
            file_edit_counts[sig].append(t)
            # Check for bash commands between this edit and the last
            if len(file_edit_counts[sig]) >= EDIT_TEST_LOOP_MIN:
                # Look for repeated bash commands between edits of this file
                bash_cmds = bash_between.get(sig, set())
                if bash_cmds:
                    findings.append({
                        "pattern": "edit_test_loop",
                        "file": sig,
                        "edit_count": len(file_edit_counts[sig]),
                        "bash_commands": list(bash_cmds)[:3],
                    })
        elif tool == "Bash" and sig:
            # Track bash commands for all files being edited
            for f in file_edit_counts:
                bash_between[f].add(sig[:60])

    return findings


def detect_grep_storm(entries: list[dict]) -> list[dict]:
    """Detect 5+ search operations within 60s with no edit in between."""
    findings = []
    search_window: list[float] = []
    last_edit_t = 0.0

    for entry in entries:
        tool = entry.get("tool", "")
        t = entry.get("t", 0)

        if tool in EDIT_TOOLS:
            last_edit_t = t
            search_window = []
        elif tool in SEARCH_TOOLS:
            # Only count searches after last edit
            if t > last_edit_t:
                search_window.append(t)
                # Trim window
                search_window = [s for s in search_window if t - s <= GREP_STORM_WINDOW_S]
                if len(search_window) >= GREP_STORM_MIN:
                    findings.append({
                        "pattern": "grep_storm",
                        "search_count": len(search_window),
                        "window_seconds": round(search_window[-1] - search_window[0], 1),
                        "since_last_edit_seconds": round(t - last_edit_t, 1),
                    })
                    search_window = []  # Reset after detection

    return findings


def detect_file_thrash(entries: list[dict]) -> list[dict]:
    """Detect 3+ edits to same file with no test/bash between them."""
    findings = []
    consecutive_edits: dict[str, int] = Counter()

    for entry in entries:
        tool = entry.get("tool", "")
        sig = entry.get("sig", "")

        if tool in EDIT_TOOLS and sig:
            consecutive_edits[sig] += 1
            if consecutive_edits[sig] >= FILE_THRASH_MIN:
                findings.append({
                    "pattern": "file_thrash",
                    "file": sig,
                    "consecutive_edits": consecutive_edits[sig],
                })
                consecutive_edits[sig] = 0
        elif tool in TEST_TOOLS:
            consecutive_edits.clear()

    return findings


def detect_debug_in_build(entries: list[dict], mode: str | None) -> list[dict]:
    """Detect debug-pattern commands while in a non-debug mode."""
    if mode not in ("melt", "burndown", "improve"):
        return []

    findings = []
    debug_commands = []

    for entry in entries:
        if entry.get("tool") != "Bash":
            continue
        sig = entry.get("sig", "")
        for pattern in DEBUG_PATTERNS:
            if pattern in sig:
                debug_commands.append(sig)
                break

    if len(debug_commands) >= 2:
        findings.append({
            "pattern": "debug_in_build",
            "mode": mode,
            "debug_command_count": len(debug_commands),
            "examples": debug_commands[:3],
        })

    return findings


def run_audit(project_dir: str) -> dict:
    """Run all pattern detectors and return audit report."""
    entries = load_log(project_dir)
    mode = load_mode(project_dir)

    if not entries:
        return {"status": "no_data", "entry_count": 0, "findings": []}

    findings = []
    findings.extend(detect_edit_test_loop(entries))
    findings.extend(detect_grep_storm(entries))
    findings.extend(detect_file_thrash(entries))
    findings.extend(detect_debug_in_build(entries, mode))

    return {
        "status": "clean" if not findings else "patterns_detected",
        "entry_count": len(entries),
        "mode": mode,
        "finding_count": len(findings),
        "findings": findings,
    }


def main():
    project_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    report = run_audit(project_dir)

    print(json.dumps(report, indent=2))

    if report["findings"]:
        print(f"\n--- {report['finding_count']} pattern(s) detected ---")
        for f in report["findings"]:
            pattern = f["pattern"]
            if pattern == "edit_test_loop":
                print(f"  EDIT-TEST-LOOP: {f['file']} edited {f['edit_count']}x")
            elif pattern == "grep_storm":
                print(f"  GREP-STORM: {f['search_count']} searches in {f['window_seconds']}s")
            elif pattern == "file_thrash":
                print(f"  FILE-THRASH: {f['file']} edited {f['consecutive_edits']}x without testing")
            elif pattern == "debug_in_build":
                print(f"  DEBUG-IN-BUILD: {f['debug_command_count']} debug commands in {f['mode']} mode")
    else:
        print("\n--- No behavioral anti-patterns detected ---")


if __name__ == "__main__":
    main()
