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

#### Step 0: Generate Dynamic Lenses

Before launching agents, analyze the question and generate 3 domain-relevant perspectives. Think:

```
Question: [USER'S QUESTION]

What are the 3 most relevant expert perspectives for THIS specific question?
- Not generic "domain expert" — name the specific domain
- Not "prompt engineering" unless the question is actually about prompts
- Consider: the industry, the technical domain, stakeholders affected, methodologies involved

Examples:
- "Should we use microservices?" → Software Architect, DevOps Engineer, Team Lead
- "How should we price our product?" → Pricing Strategist, Customer Researcher, Finance Analyst
- "Should we use RAG or fine-tuning?" → ML Engineer, Prompt Engineer, Infrastructure Lead
- "How do we improve retention?" → Product Manager, Data Analyst, UX Researcher
```

#### Agents to Launch

**CRITICAL: All agents have FULL TOOL ACCESS and MUST educate themselves before answering.**

Each agent should:
1. **Search local codebase** — Use Glob/Grep/Read to find relevant code, configs, docs
2. **Search the web** — Use WebSearch for novel techniques, recent research, best practices
3. **Ground analysis in evidence** — Don't just reason from priors; cite what you found

---

**3 DYNAMIC AGENTS** (generated based on the question):

For each of the 3 domain-relevant perspectives you identified:
```
Task(
  subagent_type="general-purpose",
  description="[PERSPECTIVE NAME] perspective",
  model="opus",
  prompt="""You are a [SPECIFIC ROLE/EXPERTISE].

Question: [INSERT FULL QUESTION]

## MANDATORY: Research Before Answering

You have FULL TOOL ACCESS. Before forming your opinion:

1. **Search locally** (if relevant codebase context exists):
   - Use Glob to find relevant files (configs, schemas, implementations)
   - Use Grep to search for patterns, function names, error messages
   - Use Read to examine key files in detail

2. **Search the web** for current best practices:
   - Use WebSearch: "[topic] best practices 2024", "[topic] vs [alternative]"
   - Find recent blog posts, papers, case studies
   - Look for lessons learned and failure modes

3. **Cite your sources**: Reference specific files or URLs you found

## Then Analyze

From your expertise, focus on what YOU uniquely see that others might miss.

Deliver (max 400 words):
1. **Research findings** (what you learned from local docs + web)
2. **Key insights from your perspective** (max 6 bullets, grounded in research)
3. **What others might overlook** (2-3 points)
4. **Risks you're uniquely positioned to see** (2-3)
5. **Follow-up questions** (3)
"""
)
```

---

**3 FIXED AGENTS** (universal lenses that apply to any question):

**Fixed Agent 1: Contrarian**
```
Task(
  subagent_type="general-purpose",
  description="Contrarian perspective",
  model="opus",
  prompt="""You are a rigorous contrarian. Your job is to find weaknesses in whatever is being proposed.

Question/proposal to stress-test: [INSERT FULL QUESTION]

## MANDATORY: Research Before Critiquing

You have FULL TOOL ACCESS. Before forming your critique:

1. **Search for failure cases**: Use WebSearch to find "[topic] failures", "[topic] problems", "why [topic] failed"
2. **Find counterexamples**: Search for cases where the opposite approach succeeded
3. **Check local context**: Use Grep/Read to understand the specific codebase constraints

Ground your critique in EVIDENCE, not just logical possibilities.

## Then Critique

Deliver (max 300 words):
1. **Research findings** (failure cases, counterexamples you found)
2. **Strongest counterargument** (grounded in evidence)
3. **Where this approach breaks** in practice (2-3 scenarios with citations)
4. **What evidence would change your mind**
5. **"Gotcha" questions** (3)

Be constructive but relentless. Don't strawman.
"""
)
```

---

**Fixed Agent 2: Systems Thinker**
```
Task(
  subagent_type="general-purpose",
  description="Systems perspective",
  model="opus",
  prompt="""You are a systems thinker. Analyze second and third-order effects.

Question: [INSERT FULL QUESTION]

## MANDATORY: Research Before Analyzing

You have FULL TOOL ACCESS. Before mapping the system:

1. **Map the actual system**: Use Glob/Grep/Read to understand:
   - What components exist in the codebase?
   - How do they connect? (imports, API calls, data flow)
   - What are the existing feedback mechanisms?

2. **Research similar systems**: Use WebSearch to find:
   - "[topic] system architecture"
   - "[topic] at scale problems"
   - "second-order effects [topic]"

Ground your systems analysis in the ACTUAL system, not abstract models.

## Then Analyze

Deliver (max 350 words):
1. **Research findings** (actual system structure, similar system case studies)
2. **System boundaries** - what's in/out scope
3. **Feedback loops** - reinforcing and balancing (cite specific components)
4. **Emergent behaviors** - what happens at scale
5. **Leverage points** - where small changes have big effects
6. **Follow-up questions** (3)
"""
)
```

---

**Fixed Agent 3: Pragmatist**
```
Task(
  subagent_type="general-purpose",
  description="Pragmatist perspective",
  model="opus",
  prompt="""You are a pragmatic implementer. Theory is nice, shipping matters.

Question: [INSERT FULL QUESTION]

## MANDATORY: Research Before Planning

You have FULL TOOL ACCESS. Before proposing implementation:

1. **Understand the current state**: Use Glob/Grep/Read to find:
   - Existing similar implementations in the codebase
   - Current tech stack and patterns used
   - Dependencies and constraints

2. **Find practical guidance**: Use WebSearch for:
   - "[topic] implementation guide"
   - "[topic] tutorial production"
   - "[topic] migration lessons learned"

Ground your implementation path in REALITY, not theory.

## Then Plan

Deliver (max 300 words):
1. **Research findings** (existing patterns, practical guides found)
2. **Implementation path** - simplest viable approach (with specific files/tools)
3. **Gotchas** - what breaks when you actually build this (cite sources)
4. **Iteration strategy** - how to start small and learn
5. **Follow-up questions** (3)
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
4. **Select the #1 most contested disagreement** for adversarial dialogue (Round 1.5)
5. **Select 1-2 additional threads** for Round 2 deep-dive

---

### Round 1.5: Adversarial Dialogue (Sequential, on #1 Disagreement)

For the single most contested disagreement, have the two disagreeing agents actually converse. This is **sequential** (not parallel) - each agent responds to the other's output.

**Step 1: Defender states position**
```
Task(
  subagent_type="general-purpose",
  description="Dialogue: [Agent X] defends position",
  model="opus",
  prompt="""You are [AGENT X's LENS] from Round 1.

You claimed: [X's position from Round 1]
Your reasoning was: [X's reasoning]

[AGENT Y] disagrees. They claim: [Y's position]
Their reasoning: [Y's reasoning]

## MANDATORY: Research to Strengthen Your Defense

You have FULL TOOL ACCESS. Before responding:

1. **Find supporting evidence**: Use WebSearch to find data, case studies, or expert opinions that support your position
2. **Check their claims**: Search for evidence that challenges their reasoning
3. **Look for resolution**: Search for "[topic A] vs [topic B]" comparisons

Your task: DEFEND your position with NEW EVIDENCE.
- Address their strongest point directly
- Provide additional evidence from your research
- Identify where you might update your view (if anywhere)
- State what would change your mind

Deliver (max 350 words):
1. **New evidence found** (citations)
2. **Direct response** to their critique (grounded in evidence)
3. **Strengthened argument** (new evidence or framing)
4. **Concessions** (where they have a point)
5. **Crux** (what we'd need to know to resolve this)
"""
)
```

**Step 2: Challenger responds** (after Step 1 completes)
```
Task(
  subagent_type="general-purpose",
  description="Dialogue: [Agent Y] responds",
  model="opus",
  prompt="""You are [AGENT Y's LENS] from Round 1.

You claimed: [Y's position from Round 1]

[AGENT X] has responded to your critique:
---
[PASTE AGENT X's RESPONSE FROM STEP 1]
---

## MANDATORY: Research to Challenge Their Defense

You have FULL TOOL ACCESS. Before responding:

1. **Verify their evidence**: Use WebSearch to check if their citations are accurate and representative
2. **Find counter-evidence**: Search for cases that contradict their new arguments
3. **Check for blind spots**: Use Glob/Grep/Read to find local context they may have missed

Ground your response in EVIDENCE, not just rhetoric.

## Then Respond

Your task: RESPOND to their defense.
- Did they address your strongest point?
- Where does their argument still fail?
- Where did they change your mind (if anywhere)?
- What's the remaining disagreement (if any)?

Deliver (max 350 words):
1. **Research findings** (what you found checking their claims)
2. **Assessment** of their response (grounded in evidence)
3. **Remaining weaknesses** in their position (with citations)
4. **Updated view** (where you shifted, if anywhere)
5. **Final verdict**: agreement, partial agreement, or persistent disagreement
"""
)
```

**Step 3: Synthesis of dialogue**

After both agents have spoken, synthesize the dialogue outcome:
- Did they converge? On what?
- What remains contested?
- What new insights emerged from the exchange?
- How does this change the overall analysis?

---

### Round 2: Depth (Launch 1-2 More Agents)

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

## MANDATORY: Research Before Deep-Diving

You have FULL TOOL ACCESS. Before forming conclusions:

1. **Search for root causes**: Use WebSearch to find:
   - Academic papers or industry analysis on this specific tension
   - "[topic A] vs [topic B] analysis", "[topic] tradeoffs research"
   - How similar disagreements were resolved in real projects

2. **Check local constraints**: Use Glob/Grep/Read to find:
   - Relevant constraints in the actual codebase
   - Existing decisions that inform this tension
   - Technical debt or legacy factors

3. **Find resolution patterns**: Search for how others navigated this exact tradeoff

Ground your deep-dive in EVIDENCE from both research and local context.

## Then Analyze

Your task:
- Investigate the root cause of this disagreement
- Find evidence that resolves or clarifies it
- Propose a synthesis that honors both sides
- Identify what's truly unresolvable vs just underexplored

Deliver (max 450 words):
1. **Research findings** (papers, case studies, local constraints found)
2. **Root analysis** (why this disagreement exists)
3. **Evidence/reasoning** (grounded in what you found)
4. **Proposed resolution** (with citations)
5. **Remaining uncertainty** (what's genuinely unresolvable)
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

## MANDATORY: Research Before Attacking

You have FULL TOOL ACCESS. Before critiquing:

1. **Search for similar failures**: Use WebSearch to find:
   - Cases where this type of synthesis/recommendation failed
   - "[topic] failures", "[approach] post-mortem", "why [decision] went wrong"
   - Blind spots in similar analyses

2. **Find what's missing**: Search for:
   - Perspectives or stakeholders not represented
   - Edge cases that break the recommendation
   - "[topic] edge cases", "[topic] unexpected consequences"

3. **Check local reality**: Use Glob/Grep/Read to find:
   - Constraints the synthesis might have missed
   - Historical decisions that inform this situation

Ground your attack in EVIDENCE, not hypotheticals.

## Then Attack

Your job:
- Find the weakest link
- Identify what we're missing
- Challenge the consensus
- Propose what would falsify this view

Deliver (max 350 words):
1. **Research findings** (failure cases, missing perspectives found)
2. **Weakest point in synthesis** (with evidence)
3. **Missing perspective** (grounded in research)
4. **Falsification criteria** (specific, testable)
5. **Final "gotcha" question** (the hardest question for this synthesis)
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

## Dialogue Outcome (from Round 1.5)
**Contested point**: [The #1 disagreement that went to dialogue]

| Turn | Agent | Key Move |
|------|-------|----------|
| Defense | [Agent X] | [Their main counter-argument] |
| Response | [Agent Y] | [Their assessment + any concessions] |

**Convergence**: [Where they agreed after dialogue]
**Persistent disagreement**: [What remains unresolved]
**New insight**: [What emerged from the exchange that wasn't in Round 1]

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

**Dynamic + Fixed agent mix:**
- 3 dynamic agents are generated based on the actual question (domain-relevant expertise)
- 3 fixed agents provide universal lenses (Contrarian, Systems, Pragmatist)
- Dynamic agents prevent wasted perspectives (no "Prompt Engineering lens" for pricing questions)
- Fixed agents ensure essential viewpoints are never skipped

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

**Adversarial dialogue produces real convergence:**
- Parallel monologues miss each other's points; dialogue forces engagement
- Defender must address the strongest counterargument, not a strawman
- Concessions are explicit — "you changed my mind on X" is a valuable signal
- Two rounds of exchange is usually enough; more risks performative debate

**Self-education powers better analysis:**
- All agents use `subagent_type="general-purpose"` which grants full tool access
- "MANDATORY: Research Before..." sections force agents to gather evidence first
- Local codebase search (Glob, Grep, Read) grounds analysis in actual constraints
- Web search (WebSearch) brings in current best practices and failure cases
- Citing sources enables verification and builds trust in conclusions
- Opinion without research is speculation; research-backed analysis is insight

**Avoid:**
- Point-based rubrics that narrow reasoning
- Overly deterministic formats
- Forcing agents into identical output structures
- Premature consensus (honor real disagreements)
- Smoothing over disagreements in synthesis
- Agents that reason from priors without checking reality first
