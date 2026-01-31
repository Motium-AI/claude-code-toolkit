#!/usr/bin/env python3
"""
Health Aggregator - SessionStart Hook

Runs after session-snapshot, before compound-context-loader.
Reads the previous session's health snapshot and prints a 1-2 line
summary if any warnings exist. Also cleans up old health snapshots.

Exit codes:
  0 - Always (never blocks session start)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Add hooks directory to path for sibling imports
sys.path.insert(0, str(Path(__file__).parent))

from _common import log_debug


def main():
    input_data = json.loads(sys.stdin.read() or "{}")
    cwd = input_data.get("cwd", "")

    if not cwd:
        sys.exit(0)

    # Import health module — fail silently if broken
    try:
        from _health import get_health_history, cleanup_old_snapshots
    except ImportError:
        log_debug(
            "Cannot import _health module",
            hook_name="health-aggregator",
        )
        sys.exit(0)

    # Cleanup old snapshots (>30 days, >100 cap)
    try:
        removed = cleanup_old_snapshots(cwd)
        if removed:
            log_debug(
                f"Cleaned up {removed} old health snapshots",
                hook_name="health-aggregator",
            )
    except Exception:
        pass

    # Read most recent health snapshot
    try:
        history = get_health_history(cwd, limit=1)
    except Exception:
        sys.exit(0)

    if not history:
        sys.exit(0)

    latest = history[0]
    warnings = []

    # Check injection effectiveness
    injection = latest.get("injection", {})
    total_injected = injection.get("total_injected", 0)
    citation_rate = injection.get("citation_rate", 0.0)
    demoted_count = injection.get("demoted_count", 0)

    if total_injected >= 20 and citation_rate < 0.10:
        warnings.append(
            f"citation rate {citation_rate:.0%} (below 10% target)"
        )

    if demoted_count > 5:
        warnings.append(f"{demoted_count} demoted events")

    # Check memory health
    memory = latest.get("memory", {})
    total_events = memory.get("total_events", 0)
    avg_age = memory.get("avg_age_days", 0)

    if total_events > 0 and avg_age > 30:
        warnings.append(f"avg event age {avg_age:.0f}d (stale)")

    # Print summary if warnings exist
    if warnings:
        summary = ", ".join(warnings)
        print(f"[health] {summary}")
        log_debug(
            "Health warnings detected",
            hook_name="health-aggregator",
            parsed_data={"warnings": warnings},
        )

    sys.exit(0)


if __name__ == "__main__":
    main()
