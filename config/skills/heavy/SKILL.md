---
name: heavy
description: Multi-perspective analysis using parallel subagents. Use when asked for broad perspectives, deep analysis, or "/heavy". Triggers on "heavy analysis", "multiple perspectives", "debate this", "think deeply".
---

# Heavy Multi-Perspective Analysis

Multi-agent analysis system that produces **shared synthesis of diverse information** — not diverse opinions on identical information.

## Input Question

$ARGUMENTS

---

## Phase 0: Triage + Memory

Before spawning agents, do three things:

### 0.1 Determine Mode

| Signal | Mode | Agent Behavior |
|--------|------|----------------|
| "Should we...", "Is it a good idea...", "Evaluate whether..." | EVALUATION | Challenge assumptions, explore both sides |
| "How can we improve...", "Help me design...", "I want to..." | IMPLEMENTATION | Accept goal as given, debate HOW not WHETHER |

### 0.2 Assess Complexity + Bind Architecture

| Complexity | Signal | Agents | Architecture | Rationale |
|------------|--------|--------|-------------|-----------|
| **Quick** | Binary decision, single concern | 2-3 | `Task()` parallel calls | No cross-pollination needed |
| **Standard** | Multi-faceted but bounded | 3-4 | `Task()` parallel calls | Coordinator synthesizes |
| **Deep** | Architectural, strategic, high-stakes | 4-5 | `TeamCreate` with peer messaging | Cross-pollination via SendMessage |

Default to **Standard** unless the question clearly warrants Quick or Deep.

**MANDATORY**: The complexity assessment BINDS the architecture choice. If you assess Deep, you MUST use TeamCreate — do not fall back to Task() for cost savings. The cross-pollination quality gain justifies the cost for Deep questions.

Output your triage result explicitly before proceeding:

> TRIAGE: [MODE] / [COMPLEXITY] → [ARCHITECTURE]

### 0.3 Prime with Memory

Check if the memory system has relevant context. Scan the `<memories>` and `<core-assertions>` blocks injected at session start. If any are relevant to the question:
- Note them as "known context" for agent prompts
- Agents should build on these, not rediscover them
- Include the specific assertion or memory ref in each agent's prompt

---

## Phase 1: Divergent Discovery

### 1.1 Generate Agent Roster

**ALL agents are dynamic.** Generate 3-5 agents specifically for THIS question. Each agent gets:
1. A **perspective** (how they think)
2. A **research territory** (where they look)
3. A **key question** (what they must answer)

The perspective determines the analytical lens. The research territory ensures agents discover DIFFERENT facts — this is how information diversity emerges. Without territories, all agents grep the same files and search the same queries.

**To generate agents, think:** *What distinct bodies of evidence exist for this question? Who would each body of evidence be most visible to?*

Example roster for "Should we replace our REST API with GraphQL?":

| Agent | Perspective | Research Territory | Key Question |
|-------|-------------|-------------------|--------------|
| Internal Archaeologist | What does our code actually do? | Codebase: grep API patterns, read route handlers, check client usage | How entangled is REST in our architecture? |
| External Scout | What does the industry know? | Web: migration case studies, GraphQL at scale postmortems | Where has this transition succeeded/failed and why? |
| Reductive Analyst | What's the simplest path? | Codebase + web: identify what can be deleted, what's unnecessary | What problem are we actually solving? Is GraphQL the answer or a symptom? |
| Adversarial Reviewer | What will break? | Codebase: find edge cases, coupling, implicit contracts | What's the migration cost nobody is counting? |

### 1.2 Agent Template Library

Use these as starting points when generating agents — pick, adapt, or ignore:

**Reductive Analyst** (via negativa):
```
Question every requirement. Delete what doesn't need to exist.
Simplify what remains. Only then accelerate. Only then automate.
Output: What can be removed? Name specific things to delete.
```

**Capability Maximizer** (AGI-pilled):
```
Assume maximally capable AI and reason from that assumption.
If you're constraining the model with rules, you're probably doing it wrong.
Output: The ambitious, capability-maximizing approach. Don't hedge.
```

**Adversarial Reviewer** (mode-sensitive):
```
EVALUATION: Find what will break. "It might not work" is weak.
"Here's where it failed: [citation]" is strong.
IMPLEMENTATION: Critique HOW, not WHETHER. Find risks in execution.
Output: What would make you mass-revert this at 2am?
```

**Domain Expert** (generated per question):
```
You are a [SPECIFIC ROLE]. From YOUR expertise, what do you see
that others will miss? Ground every claim in evidence.
Output: Your distinct insight that others are blind to.
```

### 1.3 Agent Prompt Structure

Every agent prompt MUST include:

```
Task(
  subagent_type="general-purpose",
  description="[Perspective]: [key question in 5 words]",
  model="opus",
  prompt="""[PERSPECTIVE FRAMING - 2-3 sentences]

Question: [THE QUESTION]

[KNOWN CONTEXT from memory/assertions if relevant]

YOUR RESEARCH TERRITORY: [WHERE to look, not just WHAT to think]
- [Specific codebase searches to run]
- [Specific web queries to make]
- [Specific files/systems to examine]

You have FULL TOOL ACCESS. You MUST research before forming opinions.
Research your territory FIRST, then form your position.

Output format:
## Discoveries
[What you FOUND that others likely didn't — specific facts, evidence, data]

## Position
[Your claim, grounded in your discoveries]

## Key Evidence
[The 2-3 strongest pieces of evidence supporting your position]

## Uncertainties
[What you're NOT sure about — honest gaps]"""
)
```

### 1.4 Launch (Architecture-Bound)

**Follow the architecture selected in Phase 0.2.** Do not override the triage.

#### Quick / Standard → Parallel Task() Calls

Launch ALL agents in a SINGLE message with multiple Task tool calls. Coordinator synthesizes after all return.

#### Deep → TeamCreate with Peer Messaging

Create a team, assign tasks, spawn teammates, and let them share findings via SendMessage. This replaces the manual coordinator bottleneck with real-time peer discovery sharing.

```
# Step 1: Create team
TeamCreate(team_name="heavy-analysis", description="Deep analysis: [QUESTION]")

# Step 2: Create tasks (one per agent)
TaskCreate(
  subject="[Agent perspective]: [key question]",
  description="""[PERSPECTIVE FRAMING]
  Research territory: [WHERE to look]
  Key question: [WHAT to answer]
  After completing initial research, use SendMessage to share your top 3 discoveries
  with other teammates. Then react to their findings.""",
  activeForm="Researching [territory]"
)
# Repeat TaskCreate for each agent...

# Step 3: Spawn teammates (one per task)
Task(
  subagent_type="general-purpose",
  team_name="heavy-analysis",
  name="archaeologist",
  model="sonnet",
  prompt="""You are a teammate on the heavy-analysis team.
  1. Call TaskList to find available tasks
  2. Claim a task matching your expertise via TaskUpdate(taskId, status="in_progress", owner="archaeologist")
  3. Research your territory using all available tools
  4. Share your top 3 discoveries via SendMessage(type="message", recipient="[other-agent]", content="...", summary="Key findings from [territory]")
  5. React to findings shared with you — update your position
  6. Mark your task completed via TaskUpdate(taskId, status="completed")
  7. Wait for shutdown request"""
)
# Launch all teammates in a SINGLE message with multiple Task calls

# Step 4: Monitor and synthesize
# Teammates share findings via SendMessage peer-to-peer
# Coordinator receives idle notifications and synthesizes when all complete

# Step 5: Shutdown
SendMessage(type="shutdown_request", recipient="archaeologist", content="Analysis complete")
# Wait for shutdown_response from each teammate
TeamDelete()
```

**Architecture binding (from Phase 0.2):**
- Quick/Standard → parallel `Task()` calls above (Phase 1 only, coordinator synthesizes)
- Deep → `TeamCreate` above (real-time cross-pollination via SendMessage, skip Phase 2)

---

## Phase 2: Cross-Pollination (Deep complexity only)

**If using TeamCreate (Deep)**: Cross-pollination happens automatically via SendMessage during Phase 1. Agents share findings peer-to-peer as they research. Skip this phase — proceed directly to Phase 3 Synthesis when all teammates complete.

**If using Task() (Standard, upgraded to Deep after Round 1 divergence)**: Launch follow-up agents with summaries of Round 1 discoveries.

**Trigger for upgrade**: Round 1 results sharply diverge on critical points.

After Round 1 agents return, create a brief summary of each agent's key discoveries (not their full output — just claims + evidence). Then launch follow-up agents:

```
Task(
  subagent_type="general-purpose",
  description="Cross-pollination: [Agent X] reacts",
  model="opus",
  prompt="""You originally researched [TERRITORY] and found [SUMMARY].

Other agents discovered:
- [Agent A] found: [key discovery]
- [Agent B] found: [key discovery]
- [Agent C] found: [key discovery]

Given these new facts:
1. What changes about your position?
2. What new research does this suggest? (Run it)
3. Where do you now AGREE with another agent you initially wouldn't have?
4. Where do you DISAGREE more strongly given the new evidence?

Output: Updated position with rationale for what changed and what held."""
)
```

Launch cross-pollination agents in parallel. This is where the highest-value insights emerge — at the intersection of discoveries.

---

## Phase 3: Synthesis

This is the hardest and most important phase. Do NOT rush it.

### 3.1 Catalog Discoveries

Before forming opinions, list every distinct fact/discovery agents surfaced:

```
DISCOVERY LOG:
1. [Agent X] found: [specific fact] (source: [codebase/web/both])
2. [Agent Y] found: [specific fact] (source: [codebase/web/both])
...
```

### 3.2 Identify Genuine Tensions

Not every disagreement is real. Classify each:

| Type | Test | Action |
|------|------|--------|
| **Surface framing** | Agents say the same thing in different words | Merge into consensus |
| **Different evidence** | Agents found different facts that appear to conflict | Check if both facts can be true simultaneously |
| **Genuine tension** | Agents disagree even given the same facts | Structure as disagreement with crux |

### 3.3 Find the Crux

For each genuine tension, identify the **crux** — the single empirical question that, if answered, would resolve the disagreement:

```
TENSION: [topic]
- [Agent X] claims: [position] because [evidence]
- [Agent Y] claims: [opposite] because [evidence]
- THE CRUX: [If we knew ___, this would be resolved]
- RESOLUTION: [If one emerged] or UNRESOLVED [if genuinely open]
```

**Do NOT smooth over disagreements.** Structured conflict IS the insight. An unresolved crux with clearly stated positions is more valuable than a forced consensus.

### 3.4 Produce Actionable Output

Use the appropriate mode template:

#### EVALUATION MODE

```markdown
## Executive Synthesis
[Coherent narrative that tells a story — not a list of bullet points]

## Consensus
[What 3+ agents agree on, with the evidence that convinced them]

## Structured Disagreements
### [Tension 1 Title]
| Position A | Position B |
|------------|------------|
| **Agent**: [who] | **Agent**: [who] |
| **Claim**: [what] | **Claim**: [what] |
| **Evidence**: [findings] | **Evidence**: [findings] |

**The crux**: [single question that would resolve this]

## Practical Guidance
[What to do given the current state of knowledge, including uncertainty]

## Follow-Up Questions
[What research or experiments would sharpen the analysis]
```

#### IMPLEMENTATION MODE

```markdown
## Recommended Approach
[The strategy that emerged — not a compromise, the BEST approach given all evidence]

## Why This Approach
[What evidence from which agents drove this recommendation]

## Implementation Tradeoffs
### [Decision Point 1]
| Option A | Option B |
|----------|----------|
| **Approach**: [desc] | **Approach**: [desc] |
| **Evidence for**: [findings] | **Evidence for**: [findings] |
| **Risk**: [what could go wrong] | **Risk**: [what could go wrong] |

**Recommendation**: [which and why, with crux if unresolved]

## Technical Details
[Specific files, patterns, APIs — actionable, not abstract]

## Risks & Mitigations
[Honest assessment, not boilerplate]

## Next Steps
[Concrete actions in order, with the first step being immediately executable]
```

---

## Phase 4: Quality Gate

Before presenting output, self-check:

| Check | Pass Condition |
|-------|---------------|
| **Information diversity** | Agents discovered DIFFERENT facts, not just opined differently on the same facts |
| **Evidence grounding** | Every claim traces to codebase evidence or cited external source |
| **Preserved disagreements** | At least one genuine tension is explicitly structured (unless true consensus) |
| **Surprise test** | Output contains at least one insight the questioner didn't already have |
| **Actionability** | Reader knows what to DO next, not just what to THINK |

If any check fails:
- Missing information diversity → Note it honestly: "All agents converged; this may not warrant heavy analysis"
- Missing evidence → Flag ungrounded claims as speculation
- No surprises → The question may have been too simple for heavy; acknowledge this

---

## Guardrails

**Research before opinion**: Agents must use tools (Glob, Grep, Read, Exa) before forming views. Opinion without evidence is speculation.

**Source quality**: Prefer Tier 1 (GitHub repos: anthropics/*, pydantic/*, openai/*), official docs, practitioner blogs. Avoid business press, SEO farms, academic papers >6 months old.

**Disagreement IS the insight**: Don't force consensus. "A claims X because [evidence], B claims Y because [evidence], crux is Z" beats "there are tradeoffs."

**Trust model intelligence**: Agents don't need rubrics. Principles over prescriptions. Let agents determine depth organically.

**Minimum viable context transfer**: When passing Agent A's output to Agent B (cross-pollination), pass claims + evidence, not the full analysis.

---

## Agent Template Quick Reference

For other skills that reference heavy templates (e.g., /burndown, /melt):

| Template | When to Use | Key Prompt Fragment |
|----------|-------------|-------------------|
| **Reductive Analyst** | Simplification, deletion, debt | "Question every requirement. Delete what doesn't need to exist." |
| **Capability Maximizer** | AI-first design, removing constraints | "Assume maximally capable AI. Trust the model." |
| **Adversarial Reviewer** | Risk assessment, PR review | "What would make you mass-revert this at 2am?" |
| **Domain Expert** | Specialized knowledge needed | "From YOUR expertise, what do others miss?" |
| **Internal Archaeologist** | Codebase-focused discovery | "What does the code actually do today?" |
| **External Scout** | Industry patterns, SOTA research | "How have others solved this? Where did it fail?" |

---

## Why This Works

Multi-agent analysis exploits **information asymmetry**, not just opinion diversity.

**The mechanism:**
1. Research territories force agents to discover different facts
2. Parallel execution prevents serial drift toward consensus
3. Cross-pollination produces insights at the intersection of discoveries
4. Crux identification transforms vague "tradeoffs" into testable questions

**The 4-layer stack:**
```
Layer 4: Persistent Memory (cross-session learnings via memory system)
Layer 3: Session State (agent outputs, synthesis, quality gate)
Layer 2: Deterministic Scaffolding (triage, parallel launch, synthesis template)
Layer 1: Model Intelligence (each agent's reasoning within its territory)
```

Heavy operates at Layers 1-3. Layer 4 is handled by the memory system that captures insights for future sessions.
