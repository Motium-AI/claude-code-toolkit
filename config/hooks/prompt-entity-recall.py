#!/usr/bin/env python3
"""
UserPromptSubmit Memory Recall — Intent-Based Retrieval

Extracts entities (file names, technical concepts) from the user's prompt
and queries the inverted entity index for relevant memories BEFORE the
model starts working. Complements PostToolUse recall (which fires after
file access) by surfacing memories based on user intent.

Lightweight: targets <100ms via manifest-only reads (no event file I/O
unless matches found).
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _common import log_debug, timed_hook

# Minimum entity length to avoid noise
MIN_ENTITY_LEN = 3
MAX_RECALL_EVENTS = 2
MAX_RECALL_CHARS = 800


def _extract_entities_from_prompt(message: str) -> set[str]:
    """Extract potential entities from user message text.

    Finds:
    - File paths and filenames (e.g., "stop-validator.py", "src/hooks/memory.py")
    - Backtick-quoted terms (e.g., `score_event`)
    - Technical hyphenated terms (e.g., "race-condition", "entity-gate")
    - CamelCase/snake_case identifiers
    """
    entities = set()

    # File paths: anything with a dot-extension or slash
    for match in re.findall(r'[\w./-]+\.(?:py|ts|tsx|js|jsx|json|md|yaml|yml|sh|sql|css|html)\b', message):
        entities.add(match)

    # Backtick-quoted terms
    for match in re.findall(r'`([^`]{3,50})`', message):
        entities.add(match.strip())

    # Technical hyphenated terms (3+ chars each side)
    for match in re.findall(r'\b([a-z][a-z0-9]+-[a-z][a-z0-9-]+)\b', message.lower()):
        if len(match) >= MIN_ENTITY_LEN:
            entities.add(match)

    # snake_case identifiers
    for match in re.findall(r'\b([a-z][a-z0-9]*(?:_[a-z][a-z0-9]*)+)\b', message.lower()):
        if len(match) >= MIN_ENTITY_LEN:
            entities.add(match)

    # Significant standalone words (6+ chars, likely technical)
    for word in re.findall(r'\b([a-zA-Z]{6,})\b', message):
        lower = word.lower()
        if lower not in _COMMON_WORDS:
            entities.add(lower)

    return entities


# Common English words to skip (not technical concepts)
_COMMON_WORDS = frozenset({
    "please", "should", "would", "could", "before", "after", "between",
    "through", "during", "without", "within", "another", "because",
    "change", "changes", "create", "delete", "update", "implement",
    "function", "method", "return", "import", "module", "system",
    "really", "actually", "currently", "already", "working", "looking",
    "making", "getting", "having", "trying", "something", "anything",
    "everything", "nothing", "always", "never", "sometimes", "problem",
    "issues", "things", "right", "about", "think", "there", "where",
    "which", "their", "these", "those", "other", "first", "second",
})


def main():
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    message = input_data.get("message", "")
    cwd = input_data.get("cwd", "")

    if not cwd or len(message) < 10:
        sys.exit(0)

    # Extract entities from the user's prompt
    entities = _extract_entities_from_prompt(message)
    if not entities:
        sys.exit(0)

    # Throttle: check injection log for recent prompt recalls
    try:
        log_path = Path(cwd) / ".claude" / "injection-log.json"
        if log_path.exists():
            log_data = json.loads(log_path.read_text())
            prompt_recalls = [
                r for r in log_data.get("recalled_events", [])
                if r.get("trigger") == "prompt"
            ]
            # Max 3 prompt-based recalls per session
            if len(prompt_recalls) >= 3 * MAX_RECALL_EVENTS:
                sys.exit(0)
            # Cooldown: 60s between prompt recalls
            if prompt_recalls:
                last_ts = prompt_recalls[-1].get("ts", 0)
                if isinstance(last_ts, (int, float)) and time.time() - last_ts < 60:
                    sys.exit(0)
    except (json.JSONDecodeError, IOError):
        pass

    # Query inverted index
    try:
        from _memory import get_events_by_entities
    except ImportError:
        sys.exit(0)

    events = get_events_by_entities(cwd, entities, recent_limit=3)
    if not events:
        sys.exit(0)

    # Get already-injected IDs to avoid duplicates
    injected_ids = set()
    try:
        log_path = Path(cwd) / ".claude" / "injection-log.json"
        if log_path.exists():
            log_data = json.loads(log_path.read_text())
            for entry in log_data.get("events", []):
                injected_ids.add(entry.get("id", ""))
            for entry in log_data.get("recalled_events", []):
                injected_ids.add(entry.get("id", ""))
    except (json.JSONDecodeError, IOError):
        pass

    # Score and filter
    try:
        from _scoring import build_file_components, score_event, MIN_SCORE_RECALL
    except ImportError:
        sys.exit(0)

    basenames, stems, dirs = build_file_components(entities)

    scored = []
    for event in events:
        eid = event.get("id", "")
        if eid in injected_ids:
            continue
        if event.get("source") in {"async-task-bootstrap", "bootstrap"}:
            continue
        if event.get("meta", {}).get("archived_by"):
            continue
        score = score_event(event, basenames, stems, dirs)
        if score >= MIN_SCORE_RECALL:
            scored.append((event, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    top = scored[:MAX_RECALL_EVENTS]

    if not top:
        sys.exit(0)

    # Format recalled memories
    parts = []
    total_chars = 0
    for event, _score in top:
        content = event.get("content", "").strip()
        if not content:
            continue
        if len(content) > 400:
            cut = content[:400].rfind(". ")
            if cut > 200:
                content = content[:cut + 1]
            else:
                content = content[:400] + "..."
        eid = event.get("id", "")
        entry = f'<recalled id="{eid}" trigger="prompt">\n{content}\n</recalled>'
        if total_chars + len(entry) > MAX_RECALL_CHARS:
            break
        parts.append(entry)
        total_chars += len(entry)

    if not parts:
        sys.exit(0)

    # Update injection log
    try:
        import fcntl
        from _memory import atomic_write_json
        log_path = Path(cwd) / ".claude" / "injection-log.json"
        lock_path = Path(cwd) / ".claude" / ".injection-log.lock"
        with open(lock_path, "w") as lock_file:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except (IOError, OSError):
                pass
            else:
                try:
                    log_data = {}
                    if log_path.exists():
                        log_data = json.loads(log_path.read_text())
                    recalled = log_data.get("recalled_events", [])
                    for event, score in top:
                        recalled.append({
                            "id": event.get("id", ""),
                            "score": round(score, 3),
                            "trigger": "prompt",
                            "ts": time.time(),
                        })
                    log_data["recalled_events"] = recalled
                    atomic_write_json(log_path, log_data)
                finally:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
    except Exception:
        pass

    context = "INTENT RECALL (relevant to your request):\n" + "\n".join(parts)
    output = json.dumps(context)

    log_debug(
        f"Prompt recall: {len(parts)} memories from {len(entities)} entities",
        hook_name="prompt-entity-recall",
        parsed_data={
            "entities": sorted(entities)[:10],
            "event_ids": [e.get("id", "") for e, _ in top],
        },
    )

    print(output)
    sys.exit(0)


if __name__ == "__main__":
    with timed_hook("prompt-entity-recall"):
        main()
