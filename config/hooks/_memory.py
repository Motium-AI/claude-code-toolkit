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
    problem_type: str = "",
) -> Path | None:
    """Append a new event to the store. Returns the event file path.

    Returns None if the event is a duplicate of a recent event.
    Filename includes timestamp + PID + random suffix for uniqueness
    without locking.

    problem_type: optional controlled vocabulary tag for the type of problem
    solved (e.g., "race-condition", "config-mismatch"). Auto-injected as
    a concept entity for retrieval matching.
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

    # Auto-inject problem_type as concept entity for retrieval matching
    if problem_type and problem_type not in entities:
        entities = list(entities) + [problem_type]

    now = datetime.now(timezone.utc)
    ts = now.strftime("%Y%m%dT%H%M%S")
    suffix = uuid4().hex[:6]
    event_id = f"evt_{ts}-{os.getpid()}-{suffix}"

    event = {
        "v": 1,
        "id": event_id,
        "ts": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "type": event_type,
        "content": content,
        "entities": entities,
        "source": source,
        "category": category,
        "meta": meta or {},
    }
    if problem_type:
        event["problem_type"] = problem_type

    event_path = event_dir / f"{event_id}.json"
    atomic_write_json(event_path, event)

    # Update manifest (with entity index)
    _update_manifest(event_dir, event_id, entities)

    log_debug(
        f"Event appended: {event_id}",
        hook_name="memory",
        parsed_data={"type": event_type, "entities": entities[:5]},
    )

    return event_path


def _normalize_entity_key(entity: str) -> str:
    """Normalize an entity string for index keys.

    File entities: lowercase basename (e.g., "src/hooks/stop-validator.py" -> "stop-validator.py")
    Concept entities: lowercase (e.g., "race-condition" -> "race-condition")
    """
    if "/" in entity or "." in entity.split("/")[-1]:
        return entity.split("/")[-1].lower()
    return entity.lower().strip()


def _update_manifest(
    event_dir: Path, new_event_id: str, entities: list[str] | None = None,
) -> None:
    """Update manifest with new event ID and entity index.

    Maintains an inverted index: entity_key -> [event_ids] for O(1) lookup
    at retrieval time. File locking prevents concurrent corruption.
    """
    manifest_path = event_dir.parent / MANIFEST_NAME
    lock_path = event_dir.parent / ".manifest.lock"

    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with open(lock_path, "w") as lock_file:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except (IOError, OSError):
                return

            try:
                manifest = {}
                if manifest_path.exists():
                    raw = manifest_path.read_text()
                    if raw.strip():
                        manifest = json.loads(raw)

                recent = manifest.get("recent", [])
                recent.insert(0, new_event_id)
                recent = recent[:50]

                manifest["recent"] = recent
                manifest["total_count"] = manifest.get("total_count", 0) + 1
                manifest["updated_at"] = datetime.now(timezone.utc).isoformat()

                # Update inverted entity index
                if entities:
                    entity_index = manifest.get("entity_index", {})
                    for entity in entities:
                        key = _normalize_entity_key(entity)
                        if not key:
                            continue
                        ids = entity_index.get(key, [])
                        if new_event_id not in ids:
                            ids.insert(0, new_event_id)
                            ids = ids[:30]  # Cap per-entity list
                        entity_index[key] = ids
                        # Also index stem for file entities
                        if "." in key:
                            stem = key.rsplit(".", 1)[0]
                            stem_ids = entity_index.get(stem, [])
                            if new_event_id not in stem_ids:
                                stem_ids.insert(0, new_event_id)
                                stem_ids = stem_ids[:30]
                            entity_index[stem] = stem_ids
                    manifest["entity_index"] = entity_index

                atomic_write_json(manifest_path, manifest)
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
    except (json.JSONDecodeError, IOError, OSError):
        pass


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
    """Scan directory, rebuild manifest with entity index, return recent events."""
    entries = []
    all_events = []
    for f in event_dir.glob("*.json"):
        if f.name.startswith("."):
            continue
        try:
            mtime = f.stat().st_mtime
            event = safe_read_event(f)
            if event:
                entries.append((mtime, f.stem))
                all_events.append(event)
        except OSError:
            continue

    entries.sort(reverse=True)

    # Build entity index from all events
    entity_index: dict[str, list[str]] = {}
    for event in all_events:
        eid = event.get("id", "")
        if not eid:
            continue
        for entity in event.get("entities", []):
            key = _normalize_entity_key(entity)
            if not key:
                continue
            ids = entity_index.get(key, [])
            if eid not in ids:
                ids.append(eid)
            entity_index[key] = ids
            if "." in key:
                stem = key.rsplit(".", 1)[0]
                stem_ids = entity_index.get(stem, [])
                if eid not in stem_ids:
                    stem_ids.append(eid)
                entity_index[stem] = stem_ids

    # Rebuild manifest
    manifest = {
        "recent": [eid for _, eid in entries[:50]],
        "total_count": len(entries),
        "entity_index": entity_index,
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


def get_events_by_entities(
    cwd: str, query_entities: set[str], recent_limit: int = 10,
) -> list[dict]:
    """Retrieve events matching query entities via inverted index.

    Combines index-based retrieval (entity match across full corpus) with
    recent events (freshness guarantee). Expands queries with concept
    synonyms for semantic reach. Deduplicates by event ID.

    Returns events sorted by number of entity matches (descending),
    with recent events appended.
    """
    event_dir = get_memory_dir(cwd)
    manifest_path = event_dir.parent / MANIFEST_NAME

    try:
        if not manifest_path.exists():
            return _rebuild_and_return(event_dir, recent_limit)
        manifest = json.loads(manifest_path.read_text())
    except (json.JSONDecodeError, IOError, OSError):
        return _rebuild_and_return(event_dir, recent_limit)

    entity_index = manifest.get("entity_index", {})
    recent_ids = manifest.get("recent", [])[:recent_limit]

    # Expand query entities with synonyms
    try:
        from _scoring import get_synonyms
        expanded = set()
        for entity in query_entities:
            expanded.update(get_synonyms(entity.lower()))
        query_entities = query_entities | expanded
    except ImportError:
        pass

    # Query the inverted index: collect event IDs with match counts
    match_counts: dict[str, int] = {}
    for entity in query_entities:
        key = entity.lower().strip()
        # Try exact key
        for eid in entity_index.get(key, []):
            match_counts[eid] = match_counts.get(eid, 0) + 1
        # Try basename if it looks like a path
        if "/" in entity:
            basename_key = entity.split("/")[-1].lower()
            for eid in entity_index.get(basename_key, []):
                match_counts[eid] = match_counts.get(eid, 0) + 1
        # Try stem
        if "." in key:
            stem = key.rsplit(".", 1)[0]
            for eid in entity_index.get(stem, []):
                match_counts[eid] = match_counts.get(eid, 0) + 1

    # Merge with recent IDs (guaranteed freshness)
    all_ids = set(match_counts.keys())
    for rid in recent_ids:
        all_ids.add(rid)

    # Load events
    seen = set()
    events = []
    # First: index-matched events sorted by match count (most matches first)
    sorted_matches = sorted(match_counts.items(), key=lambda x: x[1], reverse=True)
    for eid, _ in sorted_matches:
        if eid in seen:
            continue
        event = safe_read_event(event_dir / f"{eid}.json")
        if event:
            events.append(event)
            seen.add(eid)

    # Then: recent events not already included
    for eid in recent_ids:
        if eid in seen:
            continue
        event = safe_read_event(event_dir / f"{eid}.json")
        if event:
            events.append(event)
            seen.add(eid)

    return events


# ============================================================================
# Utility Tracking (citation feedback loop)
# ============================================================================


def record_injection(cwd: str, event_ids: list[str]) -> None:
    """Record that events were injected into a session (for citation rate tracking)."""
    _update_utility(cwd, event_ids, field="injected")


def record_citation(cwd: str, event_ids: list[str]) -> None:
    """Record that events were cited as helpful (memory_that_helped feedback)."""
    _update_utility(cwd, event_ids, field="cited")


def get_utility_data(cwd: str) -> dict:
    """Get utility tracking data: {event_id: {injected: N, cited: N}}."""
    event_dir = get_memory_dir(cwd)
    manifest_path = event_dir.parent / MANIFEST_NAME
    try:
        if not manifest_path.exists():
            return {}
        manifest = json.loads(manifest_path.read_text())
        return manifest.get("utility", {})
    except (json.JSONDecodeError, IOError, OSError):
        return {}


def _update_utility(cwd: str, event_ids: list[str], field: str) -> None:
    """Increment utility counters for events in the manifest."""
    if not event_ids:
        return
    event_dir = get_memory_dir(cwd)
    manifest_path = event_dir.parent / MANIFEST_NAME
    lock_path = event_dir.parent / ".manifest.lock"

    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with open(lock_path, "w") as lock_file:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except (IOError, OSError):
                return

            try:
                manifest = {}
                if manifest_path.exists():
                    raw = manifest_path.read_text()
                    if raw.strip():
                        manifest = json.loads(raw)

                utility = manifest.get("utility", {})
                for eid in event_ids:
                    if not eid:
                        continue
                    if eid not in utility:
                        utility[eid] = {"injected": 0, "cited": 0}
                    utility[eid][field] = utility[eid].get(field, 0) + 1
                manifest["utility"] = utility

                atomic_write_json(manifest_path, manifest)
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
    except (json.JSONDecodeError, IOError, OSError):
        pass


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

    return removed


# ============================================================================
# Core Assertions
# ============================================================================

ASSERTIONS_FILENAME = "core-assertions.jsonl"
MAX_ASSERTIONS = 20


def _normalize_topic(topic: str) -> str:
    """Normalize topic for dedup: lowercase, strip, spaces→hyphens, truncate 50."""
    return topic.lower().strip().replace(" ", "-").replace("_", "-")[:50]


def _get_assertions_path(cwd: str) -> Path:
    """Get path to core-assertions.jsonl for this project."""
    project_hash = get_project_hash(cwd)
    return MEMORY_ROOT / project_hash / ASSERTIONS_FILENAME


def append_assertion(cwd: str, topic: str, assertion: str) -> bool:
    """Append one assertion to core-assertions.jsonl.

    Uses flock + F_FULLFSYNC for crash safety. Topic is normalized
    for dedup (last-write-wins during compaction).

    Returns True if successfully written.
    """
    topic = _normalize_topic(topic)
    if not topic or not assertion.strip():
        return False

    path = _get_assertions_path(cwd)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.parent / ".assertions.lock"

    entry = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "topic": topic,
        "assertion": assertion.strip(),
    }
    line = json.dumps(entry, separators=(",", ":")) + "\n"

    try:
        with open(lock_path, "w") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                with open(path, "a") as f:
                    f.write(line)
                    f.flush()
                    if hasattr(fcntl, "F_FULLFSYNC"):
                        fcntl.fcntl(f.fileno(), fcntl.F_FULLFSYNC)
                    else:
                        os.fsync(f.fileno())
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        return True
    except (IOError, OSError) as e:
        log_debug(f"append_assertion failed: {e}", hook_name="memory")
        return False


def read_assertions(cwd: str) -> list[dict]:
    """Read assertions, dedup by topic (last-write-wins), return max 20.

    Returns list of dicts sorted by ts descending.
    """
    path = _get_assertions_path(cwd)
    if not path.exists():
        return []

    try:
        raw = path.read_text(encoding="utf-8")
    except (IOError, OSError):
        return []

    # Parse JSONL, dedup by topic (last-write-wins)
    by_topic: dict[str, dict] = {}
    for line in raw.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
            topic = entry.get("topic", "")
            if topic:
                by_topic[topic] = entry
        except json.JSONDecodeError:
            continue

    # Sort by ts descending, take max 20
    entries = sorted(by_topic.values(), key=lambda e: e.get("ts", ""), reverse=True)
    return entries[:MAX_ASSERTIONS]


def compact_assertions(cwd: str) -> int:
    """Rewrite assertions file atomically: dedup + LRU eviction.

    Called at SessionStart for housekeeping. Returns number of
    entries removed during compaction.
    """
    path = _get_assertions_path(cwd)
    if not path.exists():
        return 0

    try:
        raw = path.read_text(encoding="utf-8")
    except (IOError, OSError):
        return 0

    # Parse all entries
    all_entries: list[dict] = []
    for line in raw.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        try:
            all_entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    if not all_entries:
        return 0

    # Dedup by topic (last-write-wins)
    by_topic: dict[str, dict] = {}
    for entry in all_entries:
        topic = entry.get("topic", "")
        if topic:
            by_topic[topic] = entry

    # Sort by ts descending, evict beyond MAX_ASSERTIONS
    entries = sorted(by_topic.values(), key=lambda e: e.get("ts", ""), reverse=True)
    kept = entries[:MAX_ASSERTIONS]

    removed = len(all_entries) - len(kept)
    if removed <= 0:
        return 0

    # Rewrite atomically
    lock_path = path.parent / ".assertions.lock"
    try:
        with open(lock_path, "w") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                fd, tmp_path = tempfile.mkstemp(
                    dir=str(path.parent), prefix=".assertions.", suffix=".tmp",
                )
                with os.fdopen(fd, "w") as f:
                    for entry in kept:
                        f.write(json.dumps(entry, separators=(",", ":")) + "\n")
                    f.flush()
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
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
    except (IOError, OSError) as e:
        log_debug(f"compact_assertions failed: {e}", hook_name="memory")
        return 0

    log_debug(
        f"Compacted assertions: {removed} removed, {len(kept)} kept",
        hook_name="memory",
    )
    return removed


