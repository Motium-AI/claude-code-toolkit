# Memory Integration Analysis for Harness System

> **HISTORICAL DOCUMENT**: This analysis from 2026-01-30 proposed a hybrid push/pull memory architecture with briefing.md, episodes, and skill profiles. The actual implementation (Memory System v3, 2026-01-31) took a different approach: append-only event store with auto-capture from checkpoints, 4-signal scoring, and concept entity matching. See [docs/index.md](index.md#memory-system-v3) for the current implementation.

> `/heavy` analysis — 7 Opus agents across 3 rounds (2026-01-30)

## Executive Summary

The harness system already implements ~70% of the memory concepts from the analyzed articles through MEMORIES.md, completion checkpoints, and hook-driven context injection. The critical gap: **zero session outcomes persist across sessions**. Checkpoints are deleted on stop, MEMORIES.md is manually curated, and 452KB of async-tasks prove that file-based accumulation without cleanup rots. The opportunity is real but bounded — the articles describe systems with LLM-powered extraction and vector stores, neither of which work inside 5-second Python hooks with stdlib only.

All 7 agents converge on a **hybrid push/pull file-based memory system** delivered in 4 phases, with Phase 0 proving the GC pattern works before building on it.

---

## Recommended Architecture: Hybrid Push/Pull Memory

**Storage**: `~/.claude/memory/{project-hash}/` — project-scoped, file-based, no external services.

**Three memory tiers**:

| Tier | File | Size | Injection | Update Frequency |
|------|------|------|-----------|-----------------|
| **Briefing** | `briefing.md` | ≤80 lines (~1,950 tokens) | Push at SessionStart | Manual via `/memory consolidate` |
| **Skill Profiles** | `profiles/{skill}.md` | ≤30 lines each (~400 tokens) | Push when skill activates | Manual or at consolidation |
| **Episodes** | `episodes/session-{id}.json` | ~500B each | Pull via INDEX.md | Auto-archived at Stop/SessionStart |

**Push layers** (briefing + active skill profile) inject ~2,350 tokens automatically — well within budget alongside existing skill prompts (8-9K tokens).

**Pull layer** (episodes) uses an `INDEX.md` manifest that hooks inject as a "menu" — Claude reads specific episode files only when relevant, matching the existing `read-docs-trigger.py` pattern.

---

## Implementation Phases

### Phase 0: Prove GC Works (prerequisite)

Fix the async-tasks accumulation leak. 27 unprocessed files (452KB) prove that append-only file patterns rot without cleanup. Add cleanup logic to `session-snapshot.py` (already runs at SessionStart, already does cleanup). This is a ~15-line change that validates the entire memory GC approach.

Also fix: `cleanup_checkpoint_only()` in `_state.py` uses hardcoded `completion-checkpoint.json` but PID-scoped variants (`completion-checkpoint.{pid}.json`) are never cleaned. Change to glob pattern `completion-checkpoint*.json`.

### Phase 1: Archive Checkpoints to Episodes

**What**: Before deleting checkpoints at stop, archive them to `~/.claude/memory/{project-hash}/episodes/session-{timestamp}.json`.

**Where**: Fold into existing `stop-validator.py` (10s timeout, already reads checkpoints). No new hook = no added stop latency.

**Schema**:

```json
{
  "session_id": "2026-01-30T14:22:00",
  "project": {"cwd": "/path/to/project", "git_remote": "github.com/org/repo"},
  "skill_used": "melt",
  "what_was_done": "Added logout button to navbar",
  "files_changed": ["src/components/Navbar.tsx"],
  "outcome": "completed",
  "duration_minutes": 12
}
```

**Critical addition** (from red-team): Add retroactive archival at SessionStart via `session-snapshot.py` — if orphaned checkpoints exist (crash, SIGHUP, Ctrl+C), archive them before cleanup. Stop hook is NOT guaranteed to fire.

**Pruning**: Delete episodes older than 90 days at SessionStart. Keep max 200 episodes per project.

### Phase 2: Memory Injection

**New hook**: `memory-injector.py` (SessionStart, ~60 lines Python).

- Reads `briefing.md` (≤80 lines), injects via stdout
- Reads `INDEX.md` (episode manifest), injects as "available memory" menu
- Token cap: if briefing exceeds 80 lines, truncate with warning

**Modified hook**: `skill-state-initializer.py` gains ~20 lines.

- When skill detected, also reads `profiles/{skill}.md` if it exists
- Injects skill-specific context (e.g., "Last 5 /heavy analyses in this project covered: X, Y, Z")

**INDEX.md format** (auto-generated):

```markdown
# Session Memory Index
## Recent Episodes (newest first)
- `episodes/session-2026-01-30T14.json` - /melt: Added logout button [Navbar.tsx]
- `episodes/session-2026-01-29T09.json` - /heavy: Memory system analysis [7 agents]
- `episodes/session-2026-01-28T16.json` - /burndown: Fixed 12 slop issues [src/hooks/]
```

Claude sees this menu and can `Read` specific episode files when relevant — selective retrieval without vector search.

### Phase 3: Consolidation

**NOT a separate hook.** Consolidation is too complex for 5-second hooks (requires intelligence to summarize). Instead:

- **Manual command**: `/memory consolidate` — a new skill (~100 lines markdown) that reads all episodes + current briefing, synthesizes a new briefing.md, updates skill profiles, prunes stale episodes.
- **Folded into stop-validator**: After archiving episode, append one-line entry to INDEX.md (simple string formatting, no intelligence needed, <1s).
- **Briefing versioning**: Keep `briefing.md`, `briefing.md.1`, `briefing.md.2` (3 versions for rollback). Red-team identified briefing quality as the actual hard problem — versioning provides safety net.

### Phase 4: Deferred

- Decision journal entries (no clear extraction path without LLM in hooks)
- Agent personality files (need more data on what's useful)
- Automatic briefing regeneration (quality problem unsolved)
- Cross-project memory (low value for single-developer toolkit)

---

## Technical Details

### Project Scoping

Hash of `git_remote_url` or `cwd` as directory name. Prevents cross-pollination (red-team CRITICAL finding).

```
~/.claude/memory/
  {project-hash-1}/
    briefing.md          # Curated project context
    briefing.md.1        # Previous version (rollback)
    INDEX.md             # Episode manifest
    episodes/            # Archived sessions
      session-2026-01-30T14.json
      ...
    profiles/            # Per-skill memory
      melt.md
      heavy.md
      burndown.md
  {project-hash-2}/
    ...
```

### Concurrency Safety

Per-session JSON files (not shared JSONL). Red-team found concurrent JSONL writes corrupt. Each session writes only its own episode file — no contention.

### Token Budget (Corrected)

Red-team correction: 80 lines of markdown ~ 1,950 tokens (not 800). Skill profiles at 30 lines ~ 400 tokens. INDEX.md at 20 entries ~ 300 tokens. Total push injection: ~2,650 tokens. Combined with skill prompts (8-9K), total context load: ~11.5K tokens. Acceptable for 200K context window but must be monitored.

### Hook Timeout Compliance

All new logic is file I/O only (read JSON, write JSON, read/write markdown). No LLM calls, no network, no subprocess. Well within 5-second budget.

### Push vs Pull Pattern

The existing codebase already implements a two-tier retrieval pattern:

- **Push (Tier 1)**: Hooks inject context into Claude's context window (`read-docs-reminder`, `skill-continuation-reminder`, `plan-execution-reminder`)
- **Pull (Tier 2)**: Hooks tell Claude what files exist, and Claude reads them (`read-docs-trigger` suggests docs, `doc-updater-async` creates task files)

The memory store maps cleanly onto this:

- **Push layers** (1, 2): Briefing, skill profiles — always injected, low token cost
- **Pull layers** (3): Episodes — indexed via INDEX.md, Claude reads selectively
- **Write-only layer** (4): Activity captured during session, consumed at consolidation

---

## Execution Risks and Mitigations

| Risk | Severity | Mitigation |
|------|----------|------------|
| Stop hook doesn't fire (crash/SIGHUP) | CRITICAL | Retroactive archival at SessionStart catches orphans |
| Briefing quality degrades over time | SERIOUS | 3-version rollback + manual `/memory consolidate` command |
| Token budget exceeds estimates | SERIOUS | Hard cap (80 lines briefing, 30 lines profiles), monitoring in injector |
| File accumulation without cleanup | SERIOUS | Phase 0 proves GC pattern first; 90-day prune + 200 episode cap |
| Cross-project memory pollution | CRITICAL | Project-hash scoping from day 1 |
| Concurrent session writes | SERIOUS | Per-session files (not shared JSONL), no contention by design |
| Memory becomes stale/wrong | MODERATE | Episodes are append-only facts; briefing is manually curated |
| Second Stop hook doubles latency | MODERATE | Fold consolidation into stop-validator, not separate hook |
| No briefing quality circuit breaker | MODERATE | Keep 3 briefing versions for rollback |

---

## What NOT to Build

All 7 agents agreed to DELETE these from the articles:

| Component | Why DELETE |
|-----------|-----------|
| Knowledge graph | Codebase IS the graph. Glob/Grep/Read are better. |
| Vector store / embeddings | Overkill for single-developer toolkit. |
| SQLite | Adds dependency; file-based sufficient at this scale. |
| LLM calls in hooks | 5-second timeout makes this impossible. |
| Cron jobs | SessionStart hooks already provide lifecycle points. |
| Time-decay scoring | 90-day prune is simpler and sufficient. |
| Conflict resolution system | Single-user, single-project scope eliminates conflicts. |
| MCP memory server | Adds infrastructure for marginal gain. |
| Embedding pipeline | No vectors = no embeddings = no pipeline. |
| Automatic fact extraction in hooks | Hooks cannot run LLMs; delegate to Claude at session end. |
| Multi-layer context graph | LLM's own understanding of summaries is sufficient at this scale. |

---

## Red-Team Findings Summary

12 findings ordered by severity:

| # | Finding | Severity | Fix |
|---|---------|----------|-----|
| 1 | `cleanup_checkpoint_only()` misses PID-scoped checkpoints | CRITICAL | Glob for `completion-checkpoint*.json` |
| 2 | Stop hook not guaranteed (crashes, SIGHUP, Ctrl+C) | CRITICAL | Retroactive archive at SessionStart |
| 3 | No project context in checkpoints — cross-pollination guaranteed | CRITICAL | Add `cwd` + `git_remote_url` to archive |
| 4 | Token budget underestimated by 2-3x | SERIOUS | Cap briefing at 80 lines, fix budget claims |
| 5 | Concurrent JSONL writes can corrupt | SERIOUS | Per-session JSON files, not shared JSONL |
| 6 | async-tasks proves GC doesn't happen unless forced | SERIOUS | Fix async-tasks first as proof (Phase 0) |
| 7 | Briefing regeneration requires intelligence hooks can't provide | SERIOUS | Manual `/memory consolidate` command |
| 8 | Second Stop hook doubles stop latency | MODERATE | Fold into stop-validator, not separate hook |
| 9 | No briefing quality circuit breaker | MODERATE | Keep 3 briefing versions for rollback |
| 10 | Layers 3 and 5 have no implementation path | MODERATE | Defer to Phase 4 |
| 11 | Briefing quality is the actual hard problem | LOW | Accept; versioning provides safety net |
| 12 | Limited testability for multi-session scenarios | LOW | pytest integration tests |

---

## Agent Perspectives Summary

### First Principles (Elon Musk Algorithm)
Harness already implements 70% of article concepts. Only 2 changes needed (~50 lines): append checkpoint summary to MEMORIES.md on stop, inline MEMORIES.md on compaction. DELETE everything else.

### AGI-Pilled (Maximally Capable AI)
6-layer file-based memory stack. Per-skill memory transforms each harness. Compounding effect over 100 sessions. No vector store, no MCP server, no rigid schema. Let Opus compress its own sessions.

### Data Architect
Progressive compression schema (Session Log ~500B -> Facts ~200B -> Context ~2KB -> MEMORIES.md ~1KB). JSONL + markdown, no SQLite/vector store. User-level storage. Supersession model for conflict resolution.

### Context Engineering Architect
Detailed lifecycle mapping with 3 new hooks. ISOLATE pattern: different skills get different memory slices. Token budgets: 800 normal, 1200 compaction, 400 per subagent. Maps to existing push/pull patterns.

### Critical Reviewer
10 pitfalls: 5s hook timeout kills LLM extraction, context budget collision (skills already 8-9K tokens), HaluMem hallucination risk (62% accuracy), async-tasks proves files rot, MEMORIES.md already solves core problem.

### Deep-Dive (Selective Retrieval)
Recommended Option D: Hybrid (pre-compute + model-driven). Push layers (1,2): always injected. Pull layers (3,5): indexed via INDEX.md. Write-only layer (6): captured during session. Maps directly to existing patterns.

### Red-Team
12 findings. Critical: glob for PID-scoped checkpoints, retroactive archive at SessionStart, project-hash scoping. Serious: token budget 2-3x underestimated, per-session JSON files not JSONL, fix async-tasks first.

---

## Implementation Summary

Total implementation: ~310 lines of Python + ~100 lines of skill markdown. No new dependencies. No external services. Ships incrementally — each phase provides standalone value.

| Phase | Scope | Lines | Risk |
|-------|-------|-------|------|
| 0 | Fix async-tasks + checkpoint glob | ~30 | Low |
| 1 | Archive checkpoints + retroactive archival | ~80 | Low |
| 2 | Memory injection + skill profiles | ~80 | Medium |
| 3 | Consolidation command + INDEX.md | ~120 | Medium |
| 4 | Decision journal, agent personality (deferred) | TBD | TBD |

**Next step**: `/melt` Phase 0 (fix async-tasks cleanup + checkpoint glob pattern).
