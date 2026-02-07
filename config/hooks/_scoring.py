#!/usr/bin/env python3
"""
Unified scoring module for memory event ranking.

Shared by compound-context-loader.py (SessionStart) and memory-recall.py (PostToolUse).
Provides consistent scoring across all retrieval paths.

Weights: entity overlap (45%) + recency (35%) + quality (20%)

Entity gate: zero-overlap events older than ENTITY_GATE_BYPASS_HOURS are rejected.
Fresh events bypass the gate to let recency compensate.
"""

from __future__ import annotations

from datetime import datetime, timezone


# ============================================================================
# Constants
# ============================================================================

MIN_SCORE_SESSION_START = 0.12
MIN_SCORE_RECALL = 0.25
ENTITY_GATE_BYPASS_HOURS = 4


# ============================================================================
# Component Scores
# ============================================================================


def event_age_hours(event: dict) -> float:
    """Calculate event age in hours from its timestamp."""
    ts = event.get("ts", "")
    try:
        event_time = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        age = (datetime.now(timezone.utc) - event_time).total_seconds() / 3600
        return max(0.0, age)
    except (ValueError, TypeError):
        return 999.0  # Unknown age treated as old


def recency_score(event: dict) -> float:
    """Gradual freshness curve: linear 1.0->0.5 over 48h, then exponential decay.

    Anchored at 0.5 at the 48h boundary for continuity.
    Half-life 7 days in the exponential portion.
    """
    age = event_age_hours(event)
    if age < 48:
        return 1.0 - (age / 96.0)
    age_days_past_48h = (age - 48) / 24.0
    return 0.5 * (0.5 ** (age_days_past_48h / 7.0))


def entity_overlap_score(
    event: dict, basenames: set, stems: set, dirs: set,
) -> float:
    """Multi-tier entity matching. Uses max() not average().

    Tiers:
    - Exact basename match (1.0): "stop-validator.py" in basenames
    - Stem match (0.6): "stop-validator" in stems
    - Concept match (0.5): keyword in stems or dirs
    - Substring match (0.35): keyword substring of stem/dir
    - Directory match (0.3): path component in dirs
    """
    entities = event.get("entities", [])
    if not entities or not (basenames or stems or dirs):
        return 0.0
    best = 0.0
    for e in entities:
        is_file_entity = "/" in e or "." in e
        if is_file_entity:
            e_base = e.split("/")[-1]
            if e_base in basenames:
                best = max(best, 1.0)
            elif (e_base.rsplit(".", 1)[0] if "." in e_base else e_base) in stems:
                best = max(best, 0.6)
            elif e in dirs or e_base in dirs:
                best = max(best, 0.3)
        else:
            e_lower = e.lower()
            if e_lower in stems or e_lower in dirs:
                best = max(best, 0.5)
            elif any(e_lower in s.lower() for s in stems) or any(
                e_lower in d.lower() for d in dirs
            ):
                best = max(best, 0.35)
        if best >= 1.0:
            break
    return best


def quality_score(event: dict) -> float:
    """Continuous 0-1 quality score.

    Uses meta.quality_score (float) if available from stop-validator.
    Falls back to content analysis for old events without it.
    """
    qs = event.get("meta", {}).get("quality_score")
    if isinstance(qs, (int, float)):
        return max(0.0, min(1.0, float(qs)))
    return _content_quality_fallback(event)


def _content_quality_fallback(event: dict) -> float:
    """Content-based quality score for backward compat with old events."""
    content = event.get("content", "")
    entities = event.get("entities", [])
    has_lesson = (
        content.startswith("LESSON:") or content.startswith("SCHEMA:")
    ) and len(content.split("\n")[0]) > 35
    has_terms = len(entities) >= 3
    if has_lesson and has_terms:
        return 1.0
    if has_lesson:
        return 0.6
    if has_terms:
        return 0.4
    return 0.2


# ============================================================================
# File Components
# ============================================================================


def build_file_components(changed_files: set[str]) -> tuple[set, set, set]:
    """Pre-compute file component sets for O(1) entity matching."""
    basenames = set()
    stems = set()
    dirs = set()
    for f in changed_files:
        parts = f.split("/")
        basename = parts[-1]
        basenames.add(basename)
        stem = basename.rsplit(".", 1)[0] if "." in basename else basename
        stems.add(stem)
        dirs.update(p for p in parts[:-1] if p)
    return basenames, stems, dirs


# ============================================================================
# Composite Score
# ============================================================================


def score_event(
    event: dict,
    basenames: set,
    stems: set,
    dirs: set,
    utility_map: dict | None = None,
) -> float:
    """Unified scoring: entity (45%) + recency (35%) + quality (20%) + utility bonus.

    Optional utility_map adds a weak +0.05 bonus for events with proven
    citation history (cited/injected >= 0.3 with >= 3 injections).
    """
    entity = entity_overlap_score(event, basenames, stems, dirs)
    recency = recency_score(event)
    qual = quality_score(event)
    score = 0.45 * entity + 0.35 * recency + 0.20 * qual
    if utility_map:
        score += _utility_bonus(event, utility_map)
    return min(score, 1.0)


def _utility_bonus(event: dict, utility_map: dict) -> float:
    """Weak bonus for events with proven citation history."""
    eid = event.get("id", "")
    if not eid or not utility_map:
        return 0.0
    stats = utility_map.get(eid)
    if not stats:
        return 0.0
    injected = stats.get("injected", 0)
    cited = stats.get("cited", 0)
    if injected >= 3 and cited / max(injected, 1) >= 0.3:
        return 0.05
    return 0.0
