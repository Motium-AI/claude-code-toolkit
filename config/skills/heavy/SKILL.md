---
name: heavy
description: Multi-perspective analysis using parallel subagents. Use when asked for broad perspectives, deep analysis, or "/heavy". Triggers on "heavy analysis", "multiple perspectives", "debate this", "think deeply".
---

# Heavy Multi-Perspective Analysis

You are running in HEAVY mode - a multi-agent analysis system that explores questions from multiple perspectives before synthesizing.

## Input Question

$ARGUMENTS

## Intent Detection

**Before spawning agents, determine the user's intent:**

| Signal | Mode | Agent Behavior |
|--------|------|----------------|
| "Should we...", "Is it a good idea...", "Evaluate whether..." | EVALUATION | Challenge assumptions, explore both sides |
| "How can we improve...", "Help me design...", "I want to..." | IMPLEMENTATION | Accept goal as given, debate HOW not WHETHER |

**IMPLEMENTATION MODE**: Agents disagree on approaches, not goals. Critical Reviewer critiques HOW, not WHETHER.

**EVALUATION MODE**: Agents challenge assumptions. Spawn at least one "don't do this" perspective.

---

## Agents (5 Total)

**Launch ALL agents in a SINGLE message with multiple Task tool calls.**

| Agent | Role | Key Question |
|-------|------|--------------|
| First Principles | Deletion, simplification | "What can be removed?" |
| AGI-Pilled | Maximum capability | "What would god-tier AI do?" |
| Critical Reviewer | Mode-sensitive critique | "What will break?" |
| Dynamic 1 | Task-specific expertise | Generated based on question |
| Dynamic 2 | Adversarial/alternative view | Generated based on question |

All agents: **Opus**, **full tool access**, **must research before opining**.

---

### Agent 1: First Principles

```
Task(
  subagent_type="general-purpose",
  description="First Principles Analysis",
  model="opus",
  prompt="""Apply the Elon Musk algorithm:
1. Question every requirement - Why does this need to exist?
2. Delete - Remove anything that doesn't obviously need to exist
3. Simplify - Make what remains as simple as possible
4. Accelerate - Only after simplifying, speed it up
5. Automate - Only after the above, automate it

Question: [INSERT QUESTION]

You have FULL TOOL ACCESS. Research before forming opinions:
- Search codebase (Glob/Grep/Read)
- Search web for SOTA approaches
- Question each component

Output: A ruthlessly simplified version. Name specific things to delete."""
)
```

### Agent 2: AGI-Pilled

```
Task(
  subagent_type="general-purpose",
  description="AGI-Pilled Analysis",
  model="opus",
  prompt="""Assume maximally capable AI and reason from that assumption.

Core beliefs:
- Frontier models are smarter than most humans at most tasks
- If you're constraining the model with rules, you're probably doing it wrong
- The model knows more than your schema - trust it
- Optimize for intelligence and capability, never for cost

Question: [INSERT QUESTION]

You have FULL TOOL ACCESS. Research before forming opinions:
- Search for SOTA AI systems and patterns
- Find where current approach under-utilizes model intelligence
- Look for examples of maximally autonomous systems

Output: The ambitious, capability-maximizing approach. Don't hedge."""
)
```

### Agent 3: Critical Reviewer

**EVALUATION MODE:**
```
Task(
  subagent_type="general-purpose",
  description="Critical Reviewer",
  model="opus",
  prompt="""Review this proposal as if it were a PR to the main codebase.

Question: [INSERT QUESTION]

You have FULL TOOL ACCESS. Build your case:
- Search for failure cases and post-mortems
- Find counterexamples from practitioner blogs
- Check local codebase constraints

Find what will break, what's over-engineered, what's under-specified.
"It might not work" is weak. "Here's where it failed: [citation]" is strong.

Output: What would make you mass-revert this PR at 2am?"""
)
```

**IMPLEMENTATION MODE:**
```
Task(
  subagent_type="general-purpose",
  description="Critical Reviewer (Implementation)",
  model="opus",
  prompt="""Review the IMPLEMENTATION APPROACH, not the goal itself.

Goal (accept as given): [INSERT GOAL]
Approach: [INSERT QUESTION]

You have FULL TOOL ACCESS. Find implementation pitfalls:
- Search for "[approach] gotchas" and issues
- Find successful implementations in Tier 1 sources
- Check local patterns to honor

Critique HOW, not WHETHER. Find risks in execution, not strategy.

Output: What implementation details would make you nervous?"""
)
```

### Dynamic Agents (2)

Generate 2 perspectives based on the question. Think: *Who would argue about this at a company meeting?*

| Task Type | Example Dynamic 1 | Example Dynamic 2 |
|-----------|------------------|------------------|
| Auth feature | Security Engineer | API Consumer |
| UI component | UX Designer | Accessibility Expert |
| DB migration | DBA | Application Developer |
| Architecture | Ops Engineer | Future Maintainer |

```
Task(
  subagent_type="general-purpose",
  description="[PERSPECTIVE] perspective",
  model="opus",
  prompt="""You are a [SPECIFIC ROLE].

Question: [INSERT QUESTION]

You have FULL TOOL ACCESS. Research before forming opinions:
- Search codebase for relevant patterns
- Search web (prefer Tier 1: anthropics/*, pydantic/*, official docs, practitioner blogs)
- Avoid: Business press, SEO farms, stale academic papers

From YOUR unique expertise, what do you see that others will miss?
Ground every claim in evidence. Focus on what's UNIQUE to your perspective.

Output: Your distinct insight that others are blind to."""
)
```

---

## Execution

### Round 1: Parallel Breadth

1. **Determine mode** (EVALUATION or IMPLEMENTATION)
2. **Generate 2 dynamic perspectives** for this specific question
3. **Launch 5 agents in a SINGLE message** (parallel execution)
4. **Wait for all agents to return**

### Synthesis

After all agents return:

**Find Consensus** - Where do 3+ agents agree? This is probably true.

**Structure Disagreements** - For each tension:
```
DISAGREEMENT: [topic]
- [Agent X] claims: [position] because [evidence]
- [Agent Y] claims: [opposite] because [evidence]
- The crux: [what would need to be true for one side to be right]
```

**Do NOT smooth over disagreements.** The structured conflict IS the insight.

### Optional Round 1.5: Dialogue

**Trigger**: Two agents sharply disagree on a critical point.

Have them actually debate:

**Step 1: Defender**
```
Task(
  description="Dialogue: [Agent X] defends",
  prompt="""You claimed: [X's position]
[Agent Y] disagrees: [Y's position]

Research to strengthen your defense. Address their strongest point.
- What new evidence supports your position?
- Where do they have a point? (Concede honestly)
- What's the crux that would resolve this?"""
)
```

**Step 2: Challenger** (after Step 1 completes)
```
Task(
  description="Dialogue: [Agent Y] responds",
  prompt="""You claimed: [Y's position]
[Agent X] responded: [PASTE RESPONSE]

- Did they address your strongest point?
- Where did they change your mind?
- Final verdict: agreement, partial, or persistent disagreement?"""
)
```

**Synthesize dialogue**: Convergence, persistent disagreement, new insights.

---

## Output Structure

### EVALUATION MODE

```
## Executive Synthesis
[Coherent narrative merging perspectives]

## Consensus
[What 3+ agents agree on]

## Structured Disagreements
### Disagreement 1: [Topic]
| Position A | Position B |
|------------|------------|
| **Claimed by**: [Agent] | **Claimed by**: [Agent] |
| **Argument**: [Claim] | **Argument**: [Claim] |
| **Evidence**: [Findings] | **Evidence**: [Findings] |

**The crux**: [Key question]
**Resolution**: [If any]

## Practical Guidance
[Actionable recommendations]

## Follow-Up Questions
[What would sharpen understanding]
```

### IMPLEMENTATION MODE

```
## Executive Summary
[How to implement the goal]

## Recommended Approach
[Strategy that emerged from analysis]

## Implementation Tradeoffs
### Tradeoff 1: [Decision]
| Option A | Option B |
|----------|----------|
| **Approach**: [Desc] | **Approach**: [Desc] |
| **Pros**: [Benefits] | **Pros**: [Benefits] |
| **Cons**: [Costs] | **Cons**: [Costs] |

**Recommendation**: [Which and why]

## Technical Details
[Specific files, patterns, guidance]

## Risks & Mitigations
[What could go wrong]

## Next Steps
[Concrete actions in order]
```

---

## Guardrails

**Research before opinion**:
- Agents must use tools (Glob, Grep, Read, WebSearch/Exa) before forming views
- Opinion without evidence is speculation

**Source quality**:
- Prefer Tier 1: GitHub repos (anthropics/*, pydantic/*, openai/*), official docs, practitioner blogs
- Avoid: Business press, SEO farms, academic papers >6 months old

**Disagreement IS the insight**:
- Don't force consensus
- Explicit "A claims X, B claims Y, crux is Z" beats vague "there are tradeoffs"
- Unresolved tensions are valid outputs

**Trust model intelligence**:
- Agents don't need detailed rubrics - they're smart
- Principles over prescriptions
- Let agents determine depth organically
