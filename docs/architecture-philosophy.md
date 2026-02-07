# Architecture Philosophy: One System, One Loop

This document captures the philosophical foundation of the namshub toolkit — the mental model that makes skills, hooks, memory, and health feel like ONE system rather than four bolted together.

## The Core Insight

**Namshub is a self-improving agent where every session both executes a task and trains the system to execute better, through a single closed loop.**

The system's identity is not in its components. It's in the loop:

```
ACT ──► ENFORCE ──► CAPTURE ──► STORE ──► INJECT ──► ACT (improved)
                                            │
                              MEASURE ◄─────┘
```

Everything in the toolkit either IS this loop or SERVES this loop.

## The Naming Problem

### What We Say (Wrong)
- "Skills are for intelligent work, hooks are for mechanistic work"
- "Memory is separate from health"
- "We have four systems that need integration"

### What's Actually True
We have **six loop functions** operating at different temporal horizons:

| Function | Implementation | Temporal Horizon |
|----------|---------------|------------------|
| **ACT** | Skills (`/melt`, `/heavy`, `/repair`) | Minutes to hours |
| **ENFORCE** | Validation hooks (`stop-validator`, `auto-approve`) | Sub-second |
| **CAPTURE** | `stop-validator::_auto_capture_memory()` | End of session |
| **STORE** | `_memory.py` event store | Days to months |
| **INJECT** | `compound-context-loader.py` | Start of session |
| **MEASURE** | `_health.py` + utility tracking | Continuous |

These aren't separate systems. They're **facets of the same feedback loop**.

## The Viable System Model

Stafford Beer proved mathematically that any viable system needs five functions. Namshub maps cleanly:

| VSM Function | Namshub Component | Purpose |
|--------------|-------------------|---------|
| **System 1: Operations** | Skills | Where value is created |
| **System 2: Coordination** | State tracking hooks | Prevent conflicts between modes |
| **System 3: Control** | Enforcement hooks | Ensure quality standards |
| **System 3*: Audit** | Health system | Deeper inspection of effectiveness |
| **System 4: Intelligence** | Memory injection | Connect present to accumulated wisdom |
| **System 5: Policy** | CLAUDE.md, this philosophy | Identity and governing principles |

These functions cannot be collapsed. The goal is not fewer functions — it's **tighter integration** between them.

## Temporal Horizons (Not Smart vs. Dumb)

The old framing of "intelligent skills vs. mechanistic hooks" creates a false hierarchy. The better framing is **temporal scope**:

| Layer | Time Scale | Characteristic |
|-------|------------|----------------|
| **Hooks** | Immediate (sub-second) | React to current event with local information |
| **Skills** | Extended (minutes-hours) | Pursue goals across multiple interactions |
| **Memory** | Trans-sessional (days-months) | Learning that persists beyond any session |
| **Health** | Evolutionary (continuous) | Track trends that inform system-level adaptation |

Each layer is essential. A reflex (hook) is not "dumber" than deliberation (skill) — it operates at a different time scale for a different purpose.

## The Self in Self-Improvement

Where does the system's identity reside?

**Not in memory** (passive archive). **Not in goals** (user-provided). **In the feedback loop itself.**

The "self" is the **trajectory** through configuration space:

```
Self(t) = (Memory(t), Weights(t), Health_History(t))
```

This trajectory has:
- **Continuity**: Each state derives from previous state + new events
- **Identity**: Project hash provides stable reference across sessions
- **Causation**: Past states influence future via retrieval and scoring

The system doesn't have phenomenal consciousness. But it has **functional selfhood** — a persistent, causally-connected trajectory that enables learning.

## Recursive Self-Improvement: Four Levels

| Level | What Improves | Status |
|-------|--------------|--------|
| **L0: Data** | Information available to the system | Active (event store) |
| **L1: Weights** | Selection/scoring of information | Active (utility tracking, MIN_SCORE tuning) |
| **L2: Architecture** | Structure of processing | Passive (hooks are static Python) |
| **L3: Goals** | What the system tries to achieve | Externalized (user prompts) |

Namshub achieves **L0 + L1 recursion**. This is substantial — most AI systems have no persistence. The architecture deliberately externalizes L3 (goals come from users, not the system).

## The Raptor Engine Principle

SpaceX evolved the Raptor engine by:
1. **Questioning every requirement** — Why does this exist?
2. **Deleting aggressively** — The best part is no part
3. **Simplifying** — Before optimizing
4. **Accelerating** — Only after simplifying
5. **Automating** — Last, not first

Applied to namshub:

| Raptor Move | Namshub Application |
|-------------|---------------------|
| Fewer part boundaries | Skills and hooks share `_common.py`, `_memory.py`, `_health.py` |
| Full-flow combustion | Every successful stop feeds memory; every start consumes it |
| Reusability | Same toolkit works across projects (via project hash isolation) |

The goal is not to add integration layers. It's to **reduce conceptual complexity** while **tightening the feedback loop**.

## Everything Is an Event

The unifying abstraction is **events**. Everything the system does is already an event:

| Current Name | Event Type |
|--------------|------------|
| Memory event | `lesson` — a captured insight |
| Health snapshot | `health_sample` — point-in-time measurement |
| State file | `mode_change` — a transition |
| Checkpoint | `task_boundary` — completion marker |
| Injection log | `injection` — what context was provided |

These aren't separate data stores. They're **views on the same event stream**.

## The 13-Commit Test

The benchmark for recursive self-improvement:

> If the same edge case could be discovered 13 times across sessions, the system has failed.

Session #4 should already know what sessions #1-3 learned. The compounding loop means each session benefits from all previous sessions, not just the immediately prior one.

## Design Principles

### 1. The Loop Is Primary
Every design decision should be evaluated by: **Does this tighten the feedback loop?**

- Adding a new hook? It should either capture learning or enforce quality.
- Adding a new skill? It should generate learnings worth capturing.
- Adding instrumentation? It should measure loop effectiveness.

### 2. Trust the Model
Hard-coded rules are human assumptions. The model often knows better.

| Constrained (Current) | Trusting (Future) |
|-----------------------|-------------------|
| Fixed scoring weights (35/30/20/15) | Model-judged relevance |
| Fixed 10-event injection | Dynamic budget based on task |
| Time-based decay (90-day TTL) | Utility-based forgetting |
| Category enum (6 values) | Emergent clustering |

### 3. Tighter Coupling Over Modularity
The goal is not clean separation. It's **shared understanding**.

- Information flow (systems share context) over data passing (systems exchange JSON files)
- Common primitives (`atomic_write_json`, `get_project_hash`, `SessionContext`) over scattered implementations
- Unified identity (one session context) over fragmented state (7 state files)

### 4. Temporal Coherence
Each layer should operate at its appropriate time scale:

- Don't make hooks do planning (that's skills' job)
- Don't make skills manage state files (that's hooks' job)
- Don't make memory track real-time metrics (that's health's job)

### 5. Fail Toward Learning
When something goes wrong, the system should learn from it:

- Failed validations should inform future checkpoints
- Low citation rates should adjust retrieval
- Health warnings should trigger corrective actions

## What Components Serve the Loop?

### Core (ARE the Loop)
- `_memory.py` — Store + retrieve knowledge
- `compound-context-loader.py` — Inject past knowledge
- `stop-validator::_auto_capture_memory()` — Capture new knowledge
- `stop-validator::_record_injection_utility()` — Measure effectiveness
- `_memory::get_tuned_min_score()` — Self-tune based on measurement

### Enforcement (Make Input Better)
- Checkpoint validation — Ensures high-quality captures
- Plan-mode enforcement — Ensures thoughtful execution
- State management — Prevents mode conflicts

### Features (Applications on Top)
- `/audiobook`, `/episode`, `/essay` — Content creation
- Domain knowledge skills — Frozen memories
- Convenience hooks — Context loading, reminders

Features are valuable but should not be confused with core architecture. They ride on top of the loop; they don't constitute it.

## The Path Forward

### Do
1. **Name by function**: ACT/ENFORCE/CAPTURE/STORE/INJECT/MEASURE, not skills/hooks/memory/health
2. **Consolidate primitives**: One session context, one event stream
3. **Trust the model more**: Replace fixed heuristics with model judgment
4. **Delete conceptual complexity**: Merge redundant state representations
5. **Tighten the loop**: Every session should leave the system smarter

### Don't
- Add integration layers (the loop IS the integration)
- Create new abstractions (use the event primitive)
- Separate concerns that should be unified (memory and health are both views on events)
- Optimize for modularity (optimize for loop tightness)

## Summary

Namshub is not four systems that need integration. It's **one closed feedback loop** where every session both executes work and trains the system to do better work.

The components exist at different temporal horizons — immediate (hooks), extended (skills), trans-sessional (memory), continuous (health) — but they all serve the same purpose: **recursive self-improvement**.

The philosophical alignment you're seeking already exists. The work is not to add integration. It's to **name things correctly** and **tighten the loop**.
