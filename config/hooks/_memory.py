#!/usr/bin/env python3
"""
Memory primitives for Claude Code hooks.

Append-only event store with crash-safe writes, manifest-based fast reads,
and project-scoped isolation via git remote hash.

Used by:
- compound-context-loader.py (SessionStart: inject recent events)
- stop-validator.py (Stop: auto-capture checkpoint as event)
- /compound skill (manual: deep capture of solved problems)
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from _common import log_debug

# ============================================================================
# Constants
# ============================================================================

MEMORY_ROOT = Path.home() / ".claude" / "memory"
EVENT_TTL_DAYS = 90
MAX_EVENTS = 500
MANIFEST_NAME = "manifest.json"


# ============================================================================
# Atomic Write (P0 crash safety)
# ============================================================================


def atomic_write_json(path: Path, data: dict) -> None:
    """Write JSON atomically using write-temp-fsync-rename pattern.

    Guarantees: the file at `path` is either the old content or the
    new content, never a partial write. Uses F_FULLFSYNC on macOS
    for true durability.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(
        dir=str(path.parent),
        prefix=f".{path.stem}.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
            f.flush()
            # macOS fsync() doesn't flush disk write cache; F_FULLFSYNC does
            if hasattr(fcntl, "F_FULLFSYNC"):
                fcntl.fcntl(f.fileno(), fcntl.F_FULLFSYNC)
            else:
                os.fsync(f.fileno())
        os.replace(tmp_path, str(path))
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


# ============================================================================
# Safe Read
# ============================================================================


def safe_read_event(path: Path) -> dict | None:
    """Read a JSON event file with corruption detection.

    Returns None for corrupt/empty files. Does not quarantine —
    corrupt files are rare and cleanup handles them.
    """
    try:
        raw = path.read_text(encoding="utf-8")
        if not raw.strip():
            return None
        event = json.loads(raw)
        if not isinstance(event, dict):
            return None
        return event
    except (json.JSONDecodeError, IOError, OSError):
        return None


# ============================================================================
# Project Identity
# ============================================================================


def get_project_hash(cwd: str) -> str:
    """Generate a stable, collision-resistant project identifier.

    Uses SHA256(git_remote_url | repo_root)[:16]. Two repos on the
    same machine always get different hashes.
    """
    try:
        remote = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=5, cwd=cwd or None,
        )
        remote_url = remote.stdout.strip()

        root = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=5, cwd=cwd or None,
        )
        repo_root = root.stdout.strip()

        identity = f"{remote_url}|{repo_root}"
        return hashlib.sha256(identity.encode()).hexdigest()[:16]
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        # Fallback: hash the absolute path
        return hashlib.sha256(
            str(Path(cwd).resolve()).encode()
        ).hexdigest()[:16]


def get_memory_dir(cwd: str) -> Path:
    """Get the memory directory for a project, creating it if needed."""
    project_hash = get_project_hash(cwd)
    memory_dir = MEMORY_ROOT / project_hash / "events"
    memory_dir.mkdir(parents=True, exist_ok=True)
    return memory_dir


# ============================================================================
# Dedup Guard
# ============================================================================


def _is_duplicate(event_dir: Path, content: str, window: int = 8) -> bool:
    """Check if content duplicates a recent event (prefix hash + time window).

    Compares MD5 of first 200 chars against last `window` events.
    Only considers matches within a 60-minute time window to catch
    stop-retry duplicates and cross-session duplicates from sticky sessions.
    """
    prefix_hash = hashlib.md5(content[:200].encode()).hexdigest()
    manifest_path = event_dir.parent / MANIFEST_NAME
    try:
        manifest = json.loads(manifest_path.read_text())
        now = time.time()
        for eid in manifest.get("recent", [])[:window]:
            evt = safe_read_event(event_dir / f"{eid}.json")
            if not evt:
                continue
            # Check content prefix match
            if hashlib.md5(evt.get("content", "")[:200].encode()).hexdigest() != prefix_hash:
                continue
            # Check time window (60 minutes)
            evt_path = event_dir / f"{eid}.json"
            try:
                if now - evt_path.stat().st_mtime < 3600:
                    return True
            except OSError:
                continue
    except (json.JSONDecodeError, IOError, OSError):
        pass
    return False


# ============================================================================
# Event Operations
# ============================================================================


def append_event(
    cwd: str,
    content: str,
    entities: list[str],
    event_type: str = "compound",
    source: str = "compound",
    category: str = "session",
    meta: dict | None = None,
) -> Path | None:
    """Append a new event to the store. Returns the event file path.

    Returns None if the event is a duplicate of a recent event.
    Filename includes timestamp + PID + random suffix for uniqueness
    without locking.
    """
    event_dir = get_memory_dir(cwd)

    # Dedup guard: skip if content matches a recent event within 60 minutes
    if _is_duplicate(event_dir, content):
        log_debug(
            "Skipping duplicate event (content prefix matches recent event)",
            hook_name="memory",
            parsed_data={"content_prefix": content[:50]},
        )
        return None

    now = datetime.now(timezone.utc)
    ts = now.strftime("%Y%m%dT%H%M%S")
    suffix = uuid4().hex[:6]
    event_id = f"evt_{ts}-{os.getpid()}-{suffix}"

    event = {
        "id": event_id,
        "ts": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "type": event_type,
        "content": content,
        "entities": entities,
        "source": source,
        "category": category,
        "meta": meta or {},
    }

    event_path = event_dir / f"{event_id}.json"
    atomic_write_json(event_path, event)

    # Update manifest
    _update_manifest(event_dir, event_id)

    log_debug(
        f"Event appended: {event_id}",
        hook_name="memory",
        parsed_data={"type": event_type, "entities": entities[:5]},
    )

    return event_path


def _update_manifest(event_dir: Path, new_event_id: str) -> None:
    """Update manifest with new event ID. Best-effort, non-blocking."""
    manifest_path = event_dir.parent / MANIFEST_NAME
    try:
        manifest = {}
        if manifest_path.exists():
            raw = manifest_path.read_text()
            if raw.strip():
                manifest = json.loads(raw)

        recent = manifest.get("recent", [])
        recent.insert(0, new_event_id)
        recent = recent[:50]  # Keep top 50

        manifest["recent"] = recent
        manifest["total_count"] = manifest.get("total_count", 0) + 1
        manifest["updated_at"] = datetime.now(timezone.utc).isoformat()

        atomic_write_json(manifest_path, manifest)
    except (json.JSONDecodeError, IOError, OSError):
        pass  # Manifest is a cache — will be rebuilt on read miss


# ============================================================================
# Read Operations
# ============================================================================


def get_recent_events(cwd: str, limit: int = 5) -> list[dict]:
    """Get recent events using manifest fast-path.

    Falls back to directory scan if manifest is missing/corrupt.
    """
    event_dir = get_memory_dir(cwd)
    manifest_path = event_dir.parent / MANIFEST_NAME

    # Fast path: read from manifest
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text())
            recent_ids = manifest.get("recent", [])[:limit]
            events = []
            for event_id in recent_ids:
                event = safe_read_event(event_dir / f"{event_id}.json")
                if event:
                    events.append(event)
            if events:
                return events
        except (json.JSONDecodeError, IOError):
            pass  # Fall through to slow path

    # Slow path: scan directory, rebuild manifest
    return _rebuild_and_return(event_dir, limit)


def _rebuild_and_return(event_dir: Path, limit: int) -> list[dict]:
    """Scan directory, rebuild manifest, return recent events."""
    entries = []
    for f in event_dir.glob("*.json"):
        if f.name.startswith("."):
            continue
        try:
            entries.append((f.stat().st_mtime, f.stem))
        except OSError:
            continue

    entries.sort(reverse=True)

    # Rebuild manifest
    manifest = {
        "recent": [eid for _, eid in entries[:50]],
        "total_count": len(entries),
        "rebuilt_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        atomic_write_json(event_dir.parent / MANIFEST_NAME, manifest)
    except OSError:
        pass

    # Return requested events
    events = []
    for _, event_id in entries[:limit]:
        event = safe_read_event(event_dir / f"{event_id}.json")
        if event:
            events.append(event)
    return events


# ============================================================================
# Cleanup
# ============================================================================


def cleanup_old_events(cwd: str) -> int:
    """Remove events older than EVENT_TTL_DAYS and enforce MAX_EVENTS cap.

    Called at SessionStart. Returns number of files removed.
    """
    event_dir = get_memory_dir(cwd)
    now = time.time()
    cutoff = now - (EVENT_TTL_DAYS * 24 * 3600)
    removed = 0

    # Collect all events with mtime
    entries = []
    for f in event_dir.glob("*.json"):
        if f.name.startswith("."):
            continue
        try:
            mtime = f.stat().st_mtime
            entries.append((mtime, f))
        except OSError:
            continue

    # Remove expired events
    for mtime, f in entries:
        if mtime < cutoff:
            try:
                f.unlink()
                removed += 1
            except OSError:
                pass

    # Enforce hard cap (keep newest)
    remaining = [(m, f) for m, f in entries if m >= cutoff]
    remaining.sort(reverse=True)
    if len(remaining) > MAX_EVENTS:
        for _, f in remaining[MAX_EVENTS:]:
            try:
                f.unlink()
                removed += 1
            except OSError:
                pass

    if removed:
        # Rebuild manifest after cleanup
        _rebuild_and_return(event_dir, 5)
        log_debug(
            f"Cleaned up {removed} old events",
            hook_name="memory",
        )

    # Prune stale utility entries for deleted events
    _cleanup_stale_utility(event_dir)

    return removed


# ============================================================================
# Utility Tracking (Feedback Loop)
# ============================================================================


def _get_utility_from_manifest(cwd: str) -> dict:
    """Read utility data from manifest. Returns empty dict if missing."""
    event_dir = get_memory_dir(cwd)
    manifest_path = event_dir.parent / MANIFEST_NAME
    try:
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text())
            return manifest.get("utility", {})
    except (json.JSONDecodeError, IOError, OSError):
        pass
    return {}


def record_utility(cwd: str, injected_ids: list[str], helped_ids: set[str]) -> None:
    """Record injection/citation counts for utility tracking.

    Called by stop-validator after validating memory_that_helped against
    the injection log. Updates manifest.utility with per-event and
    aggregate counters.
    """
    event_dir = get_memory_dir(cwd)
    manifest_path = event_dir.parent / MANIFEST_NAME
    try:
        manifest = {}
        if manifest_path.exists():
            raw = manifest_path.read_text()
            if raw.strip():
                manifest = json.loads(raw)

        utility = manifest.get("utility", {})
        events_util = utility.get("events", {})

        for eid in injected_ids:
            entry = events_util.get(eid, {"injected": 0, "cited": 0})
            entry["injected"] = entry.get("injected", 0) + 1
            if eid in helped_ids:
                entry["cited"] = entry.get("cited", 0) + 1
            events_util[eid] = entry

        utility["events"] = events_util
        utility["total_injected"] = utility.get("total_injected", 0) + len(injected_ids)
        utility["total_cited"] = utility.get("total_cited", 0) + len(helped_ids)
        manifest["utility"] = utility

        atomic_write_json(manifest_path, manifest)
    except (json.JSONDecodeError, IOError, OSError) as e:
        log_debug(f"record_utility failed: {e}", hook_name="memory")


def get_event_demotion(cwd: str, event_id: str) -> float:
    """Return demotion factor (0.0-0.5) for events injected often with no citations.

    Events injected 3+ times with 0 citations get a 0.5 demotion (50% score penalty).
    Events injected 2 times with 0 citations get 0.25.
    Otherwise returns 0.0 (no demotion).
    """
    if not event_id:
        return 0.0
    utility = _get_utility_from_manifest(cwd)
    entry = utility.get("events", {}).get(event_id)
    if not entry:
        return 0.0
    injected = entry.get("injected", 0)
    cited = entry.get("cited", 0)
    if cited > 0 or injected < 2:
        return 0.0
    if injected >= 3:
        return 0.5
    return 0.25  # injected == 2, cited == 0


def get_tuned_min_score(cwd: str, default: float = 0.12) -> float:
    """Auto-tune MIN_SCORE based on aggregate citation rate.

    Proportional controller: if citation rate is high, lower the threshold
    (inject more). If citation rate is low, raise the threshold (be pickier).

    Requires 20+ total injections before activating. Clamped to [0.05, 0.25].
    """
    utility = _get_utility_from_manifest(cwd)
    total_injected = utility.get("total_injected", 0)
    if total_injected < 20:
        return default

    total_cited = utility.get("total_cited", 0)
    citation_rate = total_cited / total_injected  # 0.0 to ~1.0

    # Target citation rate: 0.15 (15% of injected memories are cited)
    # If actual rate > target: lower threshold (inject more)
    # If actual rate < target: raise threshold (be pickier)
    target_rate = 0.15
    adjustment = (target_rate - citation_rate) * 0.3  # Gentle proportional control
    tuned = default + adjustment

    return max(0.05, min(0.25, tuned))


def _cleanup_stale_utility(event_dir: Path) -> None:
    """Prune utility entries for events that no longer exist.

    Called during cleanup_old_events to keep utility data bounded.
    """
    manifest_path = event_dir.parent / MANIFEST_NAME
    try:
        if not manifest_path.exists():
            return
        manifest = json.loads(manifest_path.read_text())
        utility = manifest.get("utility", {})
        events_util = utility.get("events", {})
        if not events_util:
            return

        # Check which event IDs still have files
        existing_ids = {f.stem for f in event_dir.glob("evt_*.json")}
        pruned = {eid: data for eid, data in events_util.items() if eid in existing_ids}

        if len(pruned) < len(events_util):
            utility["events"] = pruned
            manifest["utility"] = utility
            atomic_write_json(manifest_path, manifest)
            log_debug(
                f"Pruned {len(events_util) - len(pruned)} stale utility entries",
                hook_name="memory",
            )
    except (json.JSONDecodeError, IOError, OSError):
        pass
