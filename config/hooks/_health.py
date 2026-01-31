#!/usr/bin/env python3
"""
Health instrumentation for Claude Code toolkit.

Assesses memory system health, injection effectiveness (feedback loop),
and session diagnostics. Used by stop-validator (auto-capture), health-
aggregator (SessionStart summary), and /health skill (manual diagnostics).

Follows _memory.py patterns: atomic writes, safe reads, project isolation.
Pure stdlib — zero external dependencies.

Storage: ~/.claude/health/{project-hash}/snapshots/health_{timestamp}.json
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from _common import log_debug

# ============================================================================
# Constants
# ============================================================================

HEALTH_ROOT = Path.home() / ".claude" / "health"
HEALTH_TTL_DAYS = 30
MAX_SNAPSHOTS = 100
SCHEMA_VERSION = 1


# ============================================================================
# Storage
# ============================================================================


def _get_health_dir(cwd: str) -> Path:
    """Get the health snapshot directory for a project, creating if needed."""
    try:
        from _memory import get_project_hash
    except ImportError:
        import hashlib
        import subprocess

        # Inline fallback — avoid hard dependency on _memory
        try:
            remote = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True, text=True, timeout=5, cwd=cwd or None,
            )
            root = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True, text=True, timeout=5, cwd=cwd or None,
            )
            identity = f"{remote.stdout.strip()}|{root.stdout.strip()}"
            project_hash = hashlib.sha256(identity.encode()).hexdigest()[:16]
        except Exception:
            project_hash = hashlib.sha256(
                str(Path(cwd).resolve()).encode()
            ).hexdigest()[:16]

        health_dir = HEALTH_ROOT / project_hash / "snapshots"
        health_dir.mkdir(parents=True, exist_ok=True)
        return health_dir

    project_hash = get_project_hash(cwd)
    health_dir = HEALTH_ROOT / project_hash / "snapshots"
    health_dir.mkdir(parents=True, exist_ok=True)
    return health_dir


# ============================================================================
# Memory Health Assessment
# ============================================================================


def assess_memory_health(cwd: str) -> dict:
    """Snapshot memory system state.

    Reads from ~/.claude/memory/{hash}/events/ and manifest.json.
    Returns counts by category, average age, last cleanup stats.
    """
    result = {
        "total_events": 0,
        "by_category": {},
        "avg_age_days": 0.0,
        "oldest_event_age_days": 0.0,
        "last_cleanup_removed": 0,
    }

    try:
        from _memory import get_memory_dir, safe_read_event
    except ImportError:
        return result

    event_dir = get_memory_dir(cwd)
    now = time.time()
    ages = []

    for f in event_dir.glob("evt_*.json"):
        evt = safe_read_event(f)
        if not evt:
            continue

        result["total_events"] += 1

        cat = evt.get("category", "session")
        result["by_category"][cat] = result["by_category"].get(cat, 0) + 1

        try:
            age_days = (now - f.stat().st_mtime) / 86400
            ages.append(age_days)
        except OSError:
            pass

    if ages:
        result["avg_age_days"] = round(sum(ages) / len(ages), 1)
        result["oldest_event_age_days"] = round(max(ages), 1)

    return result


# ============================================================================
# Injection Health Assessment
# ============================================================================


def assess_injection_health(cwd: str) -> dict:
    """Measure injection effectiveness from manifest utility data.

    Returns citation rates, demoted event count, auto-tuned MIN_SCORE.
    """
    result = {
        "total_injected": 0,
        "total_cited": 0,
        "citation_rate": 0.0,
        "demoted_count": 0,
        "min_score_default": 0.12,
        "min_score_tuned": 0.12,
    }

    try:
        from _memory import (
            get_memory_dir,
            MANIFEST_NAME,
            get_tuned_min_score,
        )
    except ImportError:
        return result

    # Read utility data from manifest
    manifest_path = get_memory_dir(cwd).parent / MANIFEST_NAME
    try:
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text())
            utility = manifest.get("utility", {})

            result["total_injected"] = utility.get("total_injected", 0)
            result["total_cited"] = utility.get("total_cited", 0)

            if result["total_injected"] > 0:
                result["citation_rate"] = round(
                    result["total_cited"] / result["total_injected"], 3
                )

            # Count demoted events
            events_util = utility.get("events", {})
            for eid, entry in events_util.items():
                injected = entry.get("injected", 0)
                cited = entry.get("cited", 0)
                if injected >= 2 and cited == 0:
                    result["demoted_count"] += 1
    except (json.JSONDecodeError, IOError, OSError):
        pass

    # Get auto-tuned MIN_SCORE
    try:
        result["min_score_tuned"] = round(get_tuned_min_score(cwd), 3)
    except Exception:
        pass

    return result


# ============================================================================
# Session Health Assessment
# ============================================================================


def assess_session_health(cwd: str) -> dict:
    """Evaluate current session state.

    Reads session-snapshot.json, injection-log.json, and autonomous state.
    """
    result = {
        "session_id": "",
        "mode": "none",
        "code_changes": False,
        "events_injected": 0,
    }

    # Read session snapshot
    snap_path = Path(cwd) / ".claude" / "session-snapshot.json"
    if snap_path.exists():
        try:
            snap = json.loads(snap_path.read_text())
            result["session_id"] = snap.get("session_id", "")
        except (json.JSONDecodeError, IOError):
            pass

    # Check for code changes
    try:
        from _common import get_diff_hash

        if snap_path.exists():
            snap = json.loads(snap_path.read_text())
            start_hash = snap.get("diff_hash_at_start", "")
            current_hash = get_diff_hash(cwd)
            if start_hash and current_hash != "unknown":
                result["code_changes"] = start_hash != current_hash
    except Exception:
        pass

    # Read injection log
    log_path = Path(cwd) / ".claude" / "injection-log.json"
    if log_path.exists():
        try:
            log_data = json.loads(log_path.read_text())
            result["events_injected"] = len(log_data.get("events", []))
        except (json.JSONDecodeError, IOError):
            pass

    # Detect autonomous mode
    try:
        from _state import get_autonomous_state

        state, state_type = get_autonomous_state(cwd)
        if state_type:
            result["mode"] = state_type
    except ImportError:
        pass

    return result


# ============================================================================
# Sidecar Metrics (written by other hooks, read here)
# ============================================================================


def read_injection_metrics(cwd: str) -> dict:
    """Read injection metrics sidecar written by compound-context-loader."""
    metrics_path = Path(cwd) / ".claude" / "health-injection-metrics.json"
    if not metrics_path.exists():
        return {}
    try:
        return json.loads(metrics_path.read_text())
    except (json.JSONDecodeError, IOError, OSError):
        return {}


def read_cleanup_metrics(cwd: str) -> dict:
    """Read cleanup metrics sidecar written by session-snapshot."""
    metrics_path = Path(cwd) / ".claude" / "health-cleanup-metrics.json"
    if not metrics_path.exists():
        return {}
    try:
        return json.loads(metrics_path.read_text())
    except (json.JSONDecodeError, IOError, OSError):
        return {}


# ============================================================================
# Report Generation
# ============================================================================


def generate_health_report(cwd: str) -> dict:
    """Comprehensive health summary combining all assessments."""
    try:
        from _memory import get_project_hash

        project_hash = get_project_hash(cwd)
    except ImportError:
        import hashlib

        project_hash = hashlib.sha256(
            str(Path(cwd).resolve()).encode()
        ).hexdigest()[:16]

    return {
        "schema_version": SCHEMA_VERSION,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "project_hash": project_hash,
        "memory": assess_memory_health(cwd),
        "injection": assess_injection_health(cwd),
        "session": assess_session_health(cwd),
        "sidecar": {
            "injection_metrics": read_injection_metrics(cwd),
            "cleanup_metrics": read_cleanup_metrics(cwd),
        },
    }


# ============================================================================
# Snapshot Archival
# ============================================================================


def archive_health_snapshot(cwd: str, report: dict) -> Path | None:
    """Store health report as an append-only snapshot.

    Uses atomic_write_json from _memory.py for crash safety.
    Returns the snapshot file path, or None on failure.
    """
    try:
        from _memory import atomic_write_json
    except ImportError:
        return None

    health_dir = _get_health_dir(cwd)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    snapshot_path = health_dir / f"health_{ts}.json"

    try:
        atomic_write_json(snapshot_path, report)
        log_debug(
            f"Health snapshot archived: {snapshot_path.name}",
            hook_name="health",
        )
        return snapshot_path
    except Exception as e:
        log_debug(f"Health snapshot failed: {e}", hook_name="health")
        return None


# ============================================================================
# History & Trends
# ============================================================================


def get_health_history(cwd: str, limit: int = 10) -> list[dict]:
    """Read recent health snapshots for trend analysis.

    Returns list of report dicts, newest first.
    """
    health_dir = _get_health_dir(cwd)
    entries = []

    for f in health_dir.glob("health_*.json"):
        try:
            entries.append((f.stat().st_mtime, f))
        except OSError:
            continue

    entries.sort(reverse=True)
    results = []

    for _, f in entries[:limit]:
        try:
            raw = f.read_text(encoding="utf-8")
            data = json.loads(raw)
            if isinstance(data, dict):
                results.append(data)
        except (json.JSONDecodeError, IOError, OSError):
            continue

    return results


# ============================================================================
# Cleanup
# ============================================================================


def cleanup_old_snapshots(cwd: str) -> int:
    """Remove snapshots older than HEALTH_TTL_DAYS and enforce MAX_SNAPSHOTS.

    Called by health-aggregator at SessionStart. Returns count removed.
    """
    health_dir = _get_health_dir(cwd)
    now = time.time()
    cutoff = now - (HEALTH_TTL_DAYS * 86400)
    removed = 0

    entries = []
    for f in health_dir.glob("health_*.json"):
        try:
            mtime = f.stat().st_mtime
            entries.append((mtime, f))
        except OSError:
            continue

    # Remove expired
    for mtime, f in entries:
        if mtime < cutoff:
            try:
                f.unlink()
                removed += 1
            except OSError:
                pass

    # Enforce cap
    remaining = [(m, f) for m, f in entries if m >= cutoff]
    remaining.sort(reverse=True)
    if len(remaining) > MAX_SNAPSHOTS:
        for _, f in remaining[MAX_SNAPSHOTS:]:
            try:
                f.unlink()
                removed += 1
            except OSError:
                pass

    if removed:
        log_debug(
            f"Cleaned up {removed} old health snapshots",
            hook_name="health",
        )

    return removed
