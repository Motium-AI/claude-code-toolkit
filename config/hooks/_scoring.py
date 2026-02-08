#!/usr/bin/env python3
"""
Unified scoring module for memory event ranking.

Shared by compound-context-loader.py (SessionStart) and memory-recall.py (PostToolUse).
Provides consistent scoring across all retrieval paths.

2-signal scoring: entity overlap (60%) + recency (40%).
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
# Concept Synonym Map
# ============================================================================

# Bidirectional synonym groups for semantic recall boost.
# Each group is a frozenset of equivalent terms. When an event entity matches
# a synonym of a query stem/dir, it scores 0.45 (between concept 0.5 and
# substring 0.35).
_SYNONYM_GROUPS: list[frozenset[str]] = [
    # Concurrency
    frozenset({"race-condition", "concurrency", "mutex", "deadlock", "lock", "thread-safety", "atomic"}),
    # State management
    frozenset({"state-management", "redux", "zustand", "context", "store", "state"}),
    # Authentication
    frozenset({"auth", "authentication", "login", "session", "jwt", "oauth", "sso"}),
    # API patterns
    frozenset({"api", "endpoint", "route", "handler", "controller", "rest", "graphql"}),
    # Database
    frozenset({"database", "db", "sql", "query", "migration", "schema", "orm", "sqlite", "postgres"}),
    # Testing
    frozenset({"test", "testing", "spec", "jest", "pytest", "vitest", "e2e", "unit-test"}),
    # Error handling
    frozenset({"error", "exception", "crash", "failure", "retry", "fallback", "error-handling"}),
    # Configuration
    frozenset({"config", "configuration", "env", "environment", "settings", "dotenv"}),
    # Caching
    frozenset({"cache", "caching", "memoize", "memoization", "redis", "invalidation"}),
    # Deployment
    frozenset({"deploy", "deployment", "ci-cd", "pipeline", "staging", "production", "release"}),
    # Performance
    frozenset({"performance", "optimization", "perf", "latency", "throughput", "profiling", "benchmark"}),
    # Frontend
    frozenset({"component", "react", "nextjs", "ui", "frontend", "render", "jsx", "tsx"}),
    # Styling
    frozenset({"css", "tailwind", "style", "styling", "theme", "design-system"}),
    # Build tools
    frozenset({"build", "webpack", "vite", "bundler", "compile", "transpile", "esbuild"}),
    # Package management
    frozenset({"dependency", "package", "npm", "pip", "yarn", "pnpm", "version"}),
    # Type system
    frozenset({"type", "typing", "typecheck", "typescript", "mypy", "pydantic", "zod", "schema"}),
    # Async
    frozenset({"async", "await", "promise", "asyncio", "concurrent", "parallel", "non-blocking"}),
    # File system
    frozenset({"file", "filesystem", "path", "directory", "io", "read", "write", "stream"}),
    # Git / VCS
    frozenset({"git", "commit", "branch", "merge", "rebase", "diff", "vcs"}),
    # Hooks / middleware
    frozenset({"hook", "hooks", "middleware", "interceptor", "plugin", "extension"}),
    # Memory / context
    frozenset({"memory", "context", "injection", "recall", "retrieval", "scoring", "entity"}),
    # Validation
    frozenset({"validation", "validator", "sanitize", "parse", "schema", "constraint"}),
    # Logging / monitoring
    frozenset({"logging", "log", "monitor", "telemetry", "metrics", "observability", "debug"}),
    # Security
    frozenset({"security", "xss", "csrf", "injection", "sanitize", "escape", "vulnerability"}),
    # Mobile
    frozenset({"mobile", "ios", "android", "react-native", "expo", "app", "native"}),
]

# Build lookup: term -> set of all synonyms (excluding self)
_SYNONYM_LOOKUP: dict[str, frozenset[str]] = {}
for _group in _SYNONYM_GROUPS:
    for _term in _group:
        _SYNONYM_LOOKUP[_term] = _group - {_term}


def get_synonyms(term: str) -> frozenset[str]:
    """Get synonyms for a term. Returns empty frozenset if none."""
    return _SYNONYM_LOOKUP.get(term.lower(), frozenset())


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
            else:
                # Synonym expansion: check if entity synonyms match stems/dirs
                syns = get_synonyms(e_lower)
                if syns and (syns & stems or syns & dirs):
                    best = max(best, 0.45)
        if best >= 1.0:
            break
    return best


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


def utility_bonus(event: dict, utility_data: dict | None = None) -> float:
    """Citation-rate bonus for events that have proven helpful.

    Events with citation rate >= 30% (min 3 injections) get +0.05.
    This closes the feedback loop: memory_that_helped refs are tracked
    in the manifest's utility field, and events that consistently help
    get boosted in future scoring.

    Returns 0.0 if no utility data or insufficient evidence.
    """
    if not utility_data:
        return 0.0
    eid = event.get("id", "")
    if not eid:
        return 0.0
    stats = utility_data.get(eid)
    if not stats:
        return 0.0
    injected = stats.get("injected", 0)
    cited = stats.get("cited", 0)
    if injected >= 3 and cited / injected >= 0.30:
        return 0.05
    return 0.0


def score_event(
    event: dict,
    basenames: set,
    stems: set,
    dirs: set,
    utility_data: dict | None = None,
) -> float:
    """2-signal scoring + utility bonus: entity overlap (60%) + recency (40%) + citation bonus.

    Wider dynamic range than 3-signal — entity overlap provides the
    relevance gate, recency provides the freshness tiebreaker.
    Utility bonus rewards events that have been cited as helpful.
    """
    entity = entity_overlap_score(event, basenames, stems, dirs)
    recency = recency_score(event)
    bonus = utility_bonus(event, utility_data)
    return 0.60 * entity + 0.40 * recency + bonus
