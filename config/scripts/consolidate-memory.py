#!/usr/bin/env python3
"""
Memory Consolidation — Episodic to Semantic Compression

Clusters memory events by entity Jaccard similarity, generates schema
events (consolidated knowledge) for clusters of 3+, and marks source
events as archived.

Schema events are more compact and higher-signal than the raw episodic
events they replace. They get BUDGET_HIGH treatment in injection.

Usage:
    python3 consolidate-memory.py [--dry-run] [--cwd /path/to/repo]

Run periodically (e.g., weekly) or when event count exceeds threshold.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

# Add hooks directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))

from _common import log_debug
from _memory import (
    MEMORY_ROOT,
    atomic_write_json,
    get_memory_dir,
    get_project_hash,
    safe_read_event,
)


MIN_CLUSTER_SIZE = 3
JACCARD_THRESHOLD = 0.25  # Minimum entity overlap to consider events related
MAX_SCHEMA_CONTENT_LEN = 500


def _entity_set(event: dict) -> set[str]:
    """Extract normalized entity set from an event."""
    entities = set()
    for e in event.get("entities", []):
        # Normalize: lowercase, basename for files
        if "/" in e or "." in e:
            entities.add(e.split("/")[-1].lower())
        else:
            entities.add(e.lower())
    return entities


def _jaccard(a: set, b: set) -> float:
    """Jaccard similarity between two sets."""
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _cluster_events(events: list[dict]) -> list[list[dict]]:
    """Cluster events by entity Jaccard similarity (greedy single-linkage).

    Returns clusters of size >= MIN_CLUSTER_SIZE.
    """
    # Pre-compute entity sets
    entity_sets = [(evt, _entity_set(evt)) for evt in events]

    # Build adjacency: events with Jaccard >= threshold
    n = len(entity_sets)
    adjacency: dict[int, set[int]] = defaultdict(set)
    for i in range(n):
        for j in range(i + 1, n):
            if _jaccard(entity_sets[i][1], entity_sets[j][1]) >= JACCARD_THRESHOLD:
                adjacency[i].add(j)
                adjacency[j].add(i)

    # Connected components via BFS
    visited = set()
    clusters: list[list[dict]] = []
    for i in range(n):
        if i in visited:
            continue
        # BFS
        queue = [i]
        component = []
        while queue:
            node = queue.pop(0)
            if node in visited:
                continue
            visited.add(node)
            component.append(entity_sets[node][0])
            for neighbor in adjacency.get(node, set()):
                if neighbor not in visited:
                    queue.append(neighbor)
        if len(component) >= MIN_CLUSTER_SIZE:
            clusters.append(component)

    return clusters


def _generate_schema(cluster: list[dict]) -> dict:
    """Generate a schema event from a cluster of related events.

    Extracts shared entities, combines lessons, and creates a
    consolidated knowledge event.
    """
    # Collect all entities with frequency
    entity_freq: dict[str, int] = defaultdict(int)
    for evt in cluster:
        for e in evt.get("entities", []):
            key = e.split("/")[-1].lower() if "/" in e or "." in e else e.lower()
            entity_freq[key] += 1

    # Keep entities that appear in at least 2 events
    shared_entities = [e for e, count in entity_freq.items() if count >= 2]
    # Also keep high-frequency unique entities
    shared_entities += [e for e, count in entity_freq.items() if count == 1 and len(e) > 5]
    shared_entities = list(dict.fromkeys(shared_entities))[:15]  # dedup, cap

    # Extract lessons from all events
    lessons = []
    for evt in cluster:
        content = evt.get("content", "")
        # Extract LESSON: prefix if present
        for line in content.split("\n"):
            if line.startswith("LESSON:"):
                lesson = line[7:].strip()
                if lesson and len(lesson) > 20:
                    lessons.append(lesson)
                break

    # Build schema content
    if lessons:
        # Deduplicate similar lessons (prefix match)
        unique_lessons = []
        seen_prefixes = set()
        for lesson in lessons:
            prefix = lesson[:40].lower()
            if prefix not in seen_prefixes:
                unique_lessons.append(lesson)
                seen_prefixes.add(prefix)
        content = "SCHEMA: " + " | ".join(unique_lessons[:5])
    else:
        # Fall back to combining content summaries
        summaries = []
        for evt in cluster[:5]:
            c = evt.get("content", "").strip()
            if c:
                summaries.append(c[:100])
        content = "SCHEMA: " + " | ".join(summaries)

    if len(content) > MAX_SCHEMA_CONTENT_LEN:
        content = content[:MAX_SCHEMA_CONTENT_LEN - 3] + "..."

    # Collect categories
    categories = [evt.get("category", "") for evt in cluster if evt.get("category")]
    category = max(set(categories), key=categories.count) if categories else "architecture"

    return {
        "content": content,
        "entities": shared_entities,
        "category": category,
        "source_count": len(cluster),
        "source_ids": [evt.get("id", "") for evt in cluster if evt.get("id")],
    }


def consolidate(cwd: str, dry_run: bool = False) -> dict:
    """Run consolidation on a project's memory events.

    Returns stats dict with cluster_count, schema_count, archived_count.
    """
    event_dir = get_memory_dir(cwd)
    stats = {"cluster_count": 0, "schema_count": 0, "archived_count": 0, "clusters": []}

    # Load all non-archived, non-bootstrap events
    events = []
    for f in event_dir.glob("*.json"):
        if f.name.startswith("."):
            continue
        evt = safe_read_event(f)
        if not evt:
            continue
        if evt.get("type") == "schema":
            continue  # Don't re-consolidate schemas
        if evt.get("meta", {}).get("archived_by"):
            continue  # Already archived
        if evt.get("source") in {"async-task-bootstrap", "bootstrap"}:
            continue
        events.append(evt)

    if len(events) < MIN_CLUSTER_SIZE:
        return stats

    # Cluster by entity similarity
    clusters = _cluster_events(events)
    stats["cluster_count"] = len(clusters)

    for cluster in clusters:
        schema_data = _generate_schema(cluster)
        stats["clusters"].append({
            "size": len(cluster),
            "entities": schema_data["entities"][:5],
            "content_preview": schema_data["content"][:100],
        })

        if dry_run:
            stats["schema_count"] += 1
            stats["archived_count"] += len(cluster)
            continue

        # Create schema event
        from _memory import append_event
        schema_path = append_event(
            cwd=cwd,
            content=schema_data["content"],
            entities=schema_data["entities"],
            event_type="schema",
            source="consolidation",
            category=schema_data["category"],
            meta={"source_ids": schema_data["source_ids"]},
        )

        if not schema_path:
            continue

        schema_id = schema_path.stem
        stats["schema_count"] += 1

        # Mark source events as archived
        for source_id in schema_data["source_ids"]:
            source_path = event_dir / f"{source_id}.json"
            if not source_path.exists():
                continue
            try:
                evt = json.loads(source_path.read_text())
                meta = evt.get("meta", {})
                meta["archived_by"] = schema_id
                evt["meta"] = meta
                atomic_write_json(source_path, evt)
                stats["archived_count"] += 1
            except (json.JSONDecodeError, IOError):
                continue

    return stats


def main():
    parser = argparse.ArgumentParser(description="Consolidate memory events")
    parser.add_argument("--dry-run", action="store_true", help="Show what would happen without changes")
    parser.add_argument("--cwd", default=".", help="Working directory (for project hash)")
    args = parser.parse_args()

    stats = consolidate(args.cwd, dry_run=args.dry_run)

    prefix = "[DRY RUN] " if args.dry_run else ""
    print(f"{prefix}Consolidation complete:")
    print(f"  Clusters found: {stats['cluster_count']}")
    print(f"  Schema events created: {stats['schema_count']}")
    print(f"  Source events archived: {stats['archived_count']}")

    if stats["clusters"]:
        print("\nClusters:")
        for i, cluster in enumerate(stats["clusters"], 1):
            print(f"  {i}. {cluster['size']} events — entities: {', '.join(cluster['entities'][:5])}")
            print(f"     {cluster['content_preview']}")


if __name__ == "__main__":
    main()
