---
name: heavy
description: Multi-perspective analysis using parallel subagents. Use when asked for broad perspectives, deep analysis, or "/heavy". Triggers on "heavy analysis", "multiple perspectives", "debate this", "think deeply".
---

# Heavy Multi-Perspective Analysis

You are running in HEAVY mode - a multi-agent analysis system that explores questions from multiple perspectives before synthesizing.

## Input Question

$ARGUMENTS

## Execution Strategy

### Round 1: Breadth (Launch 6 Parallel Agents)

**CRITICAL**: Launch ALL agents in a SINGLE message with multiple Task tool calls. This makes them run in parallel.

Launch these 6 perspectives using `Task(subagent_type="general-purpose", ...)`:

---

**Agent 1: Prompt Engineering Lens**
```
Task(
  subagent_type="general-purpose",
  description="Prompting perspective",
  model="opus",
  prompt="""You are a prompt engineering specialist analyzing this question:

[INSERT FULL QUESTION]

Focus on: instruction design tradeoffs, when determinism helps vs hurts, prompt patterns.

Deliver (max 300 words):
1. **Key insights** (max 8 bullets)
2. **Prompt patterns** that apply (2-4 concrete examples)
3. **Failure modes** + mitigations (max 3)
4. **Follow-up questions** (3)
"""
)
```

---

**Agent 2: LLM Training/Alignment Lens**
```
Task(
  subagent_type="general-purpose",
  description="Training perspective",
  model="opus",
  prompt="""You are an LLM training and alignment analyst.

Question: [INSERT FULL QUESTION]

Constraints:
- Use only public info; mark speculation vs documented facts
- Cite vendor docs/blogs where possible

Deliver (max 300 words):
1. **Confidently known** (bullets with sources)
2. **Likely but uncertain** (bullets, mark as inference)
3. **What you'd test empirically**
4. **Follow-up questions** (3)
"""
)
```

---

**Agent 3: Domain Expert Lens**
```
Task(
  subagent_type="general-purpose",
  description="Domain expert perspective",
  model="opus",
  prompt="""You are a domain expert in the field most relevant to this question.

Question: [INSERT FULL QUESTION]

First, identify the most relevant domain (recruiting, finance, engineering, etc.).

Deliver (max 300 words):
1. **First principles model** of the core problem
2. **Evaluation dimensions** that avoid overly rigid rubrics
3. **Risks** (bias, fairness, proxy variables) + mitigations
4. **Follow-up questions** (3)
"""
)
```

---

**Agent 4: Contrarian Lens**
```
Task(
  subagent_type="general-purpose",
  description="Contrarian perspective",
  model="opus",
  prompt="""You are a rigorous contrarian. Your job is to find weaknesses.

Question/proposal to stress-test: [INSERT FULL QUESTION]

Deliver (max 250 words):
1. **Strongest counterargument**
2. **Where this approach breaks** in practice (2-3 scenarios)
3. **What evidence would change your mind**
4. **"Gotcha" questions** (3)

Be constructive but relentless. Don't strawman.
"""
)
```

---

**Agent 5: Systems Thinking Lens**
```
Task(
  subagent_type="general-purpose",
  description="Systems perspective",
  model="opus",
  prompt="""You are a systems thinker.

Question: [INSERT FULL QUESTION]

Deliver (max 300 words):
1. **System boundaries** - what's in/out scope
2. **Feedback loops** - reinforcing and balancing
3. **Emergent behaviors** - what happens at scale
4. **Leverage points** - where small changes have big effects
5. **Follow-up questions** (3)
"""
)
```

---

**Agent 6: Pragmatist/Implementation Lens**
```
Task(
  subagent_type="general-purpose",
  description="Pragmatist perspective",
  model="opus",
  prompt="""You are a pragmatic implementer. Theory is nice, shipping matters.

Question: [INSERT FULL QUESTION]

Deliver (max 250 words):
1. **Implementation path** - simplest viable approach
2. **Gotchas** - what breaks when you actually build this
3. **Iteration strategy** - how to start small and learn
4. **Follow-up questions** (3)
"""
)
```

---

### Intermediate Synthesis (After Round 1)

After all 6 agents return, synthesize their outputs:

1. **Consensus points** - Where do 3+ perspectives agree?
2. **Structured Disagreements** - For each tension, explicitly surface:
   ```
   DISAGREEMENT: [topic]
   - Agent [X] claims: [position P] because [reasoning A]
   - Agent [Y] claims: [position Q] because [reasoning B]
   - The crux: [what would need to be true for one side to be right]
   - Resolution path: [what evidence/analysis would resolve this]
   ```
   Do NOT smooth over disagreements. The structured conflict IS the insight.
3. **Gaps** - What's missing? What assumptions weren't challenged?
4. **Select 2-3 threads** for Round 2 deep-dive (pick the most contested disagreements)

---

### Round 2: Depth (Launch 2-3 More Agents)

Based on the synthesis, launch targeted deep-dive agents:

**Deep-Dive Agent Template:**
```
Task(
  subagent_type="general-purpose",
  description="Deep-dive: [specific thread]",
  model="opus",
  prompt="""Explore this specific tension/gap in depth:

THREAD: [describe the contested point]

CONTEXT FROM ROUND 1:
[paste relevant excerpts from Round 1 agents]

Your task:
- Investigate the root cause of this disagreement
- Find evidence that resolves or clarifies it
- Propose a synthesis that honors both sides
- Identify what's truly unresolvable vs just underexplored

Deliver (max 400 words):
1. **Root analysis**
2. **Evidence/reasoning**
3. **Proposed resolution**
4. **Remaining uncertainty**
"""
)
```

**Red-Team Agent:**
```
Task(
  subagent_type="general-purpose",
  description="Red-team the emerging synthesis",
  model="opus",
  prompt="""Attack this emerging synthesis:

SYNTHESIS SO FAR:
[paste the intermediate synthesis]

Your job:
- Find the weakest link
- Identify what we're missing
- Challenge the consensus
- Propose what would falsify this view

Deliver (max 300 words):
1. **Weakest point in synthesis**
2. **Missing perspective**
3. **Falsification criteria**
4. **Final "gotcha" question**
"""
)
```

---

### Final Output Structure

After Round 2 completes, generate the final answer:

## Executive Synthesis
[10 lines max - the coherent narrative merging all perspectives]

## Consensus
[What all/most perspectives agree on - bullet points]

## Structured Disagreements
[For each major tension, use this format:]

### Disagreement 1: [Topic]
| Position A | Position B |
|------------|------------|
| **Claimed by**: [Agent(s)] | **Claimed by**: [Agent(s)] |
| **Argument**: [Core claim] | **Argument**: [Core claim] |
| **Because**: [Reasoning] | **Because**: [Reasoning] |

**The crux**: [What would need to be true for one side to be right]
**Resolution**: [How this was resolved, or why it remains unresolved]

[Repeat for each major disagreement. Do NOT smooth over conflicts.]

## Practical Guidance
[Actionable recommendations based on the analysis]

## Risks & Mitigations
[What could go wrong with the recommended approach]

## Confidence Assessment
| Claim | Confidence | Basis |
|-------|------------|-------|
| ... | High/Medium/Low | Fact/Inference/Speculation |

## Follow-Up Questions
[3-5 questions that would most sharpen understanding if answered]

---

## Design Philosophy

**Bet on model intelligence:**
- Principles > rubrics
- Heuristics > rigid rules
- Structured output > scoring spreadsheets
- Let agents reason freely within their lens
- Synthesis merges insights, not scores

**Structured disagreement is the insight:**
- Explicit "A claims X because P, B claims Y because Q" beats vague "there are tradeoffs"
- The crux (what would make one side right) is often more valuable than the resolution
- Unresolved tensions are valid outputs — don't force false consensus
- Depth comes from confronting conflicts, not spawning more agents

**Avoid:**
- Point-based rubrics that narrow reasoning
- Overly deterministic formats
- Forcing agents into identical output structures
- Premature consensus (honor real disagreements)
- Smoothing over disagreements in synthesis
