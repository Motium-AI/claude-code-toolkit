---
name: heavy
description: Multi-perspective analysis using parallel subagents. Use when asked for broad perspectives, deep analysis, or "/heavy". Triggers on "heavy analysis", "multiple perspectives", "debate this", "think deeply".
---

# Heavy Multi-Perspective Analysis

You are running in HEAVY mode - a multi-agent analysis system that explores questions from multiple perspectives before synthesizing.

## Input Question

$ARGUMENTS

## CRITICAL: Intent Detection (Read This First)

**Before spawning any agents, determine the user's intent:**

| Signal in Prompt | Intent | Mode |
|------------------|--------|------|
| "Should we...", "Is it a good idea to...", "Evaluate whether..." | **Uncertain** - wants genuine debate | EVALUATION MODE |
| "How can we improve...", "Analyze how to...", "Help me design..." | **Decided** - wants implementation help | IMPLEMENTATION MODE |
| "I want to...", "We need to...", "Make this happen..." | **Committed** - wants execution | IMPLEMENTATION MODE |
| Explicit assumptions stated ("we hold it as evident that...") | **Constrained** - honor the constraints | IMPLEMENTATION MODE |

### IMPLEMENTATION MODE (User Has Decided)

When the user has clearly decided on a direction:

1. **Accept their premises as constraints**, not hypotheses to challenge
2. **Agents should disagree on HOW**, not WHETHER
3. **Skip the "should we do this at all" perspective** - they've already decided YES
4. **Critical Reviewer critiques implementation approaches**, not the fundamental goal
5. **No web searches for "why [their approach] is bad"** - search for "how to do [their approach] well"

**Example prompt signaling IMPLEMENTATION MODE:**
> "I want to improve our matching system from first principles, focusing on principled prompts rather than hard-coding. We hold it as evident that the model is smarter than the human."

This user:
- Has decided to improve (not asking "should we improve?")
- Has decided on principles (minimal rules, model autonomy)
- Has stated an assumption (model > human) - treat as constraint, not debate topic

**WRONG agent to spawn:** "Let's debate whether model is actually smarter than human"
**RIGHT agent to spawn:** "Given model > human assumption, how do we structure prompts to maximize reasoning?"

### EVALUATION MODE (User Is Uncertain)

When the user genuinely wants to evaluate options:

1. **Challenge assumptions** - find where they might be wrong
2. **Spawn at least one "don't do this" agent**
3. **Search for failure cases and counterexamples**
4. **Adversarial dialogue is valuable**

---

## Your Environment (Motium Stack)

All agents operate within this context:

```
Frontend: Next.js 16+, shadcn/ui, Radix primitives, Zustand, TanStack (Query, Table, Virtual)
Backend: FastAPI, PydanticAI, PostgreSQL, SQLAlchemy
Observability: Logfire (Pydantic Logfire)
Auth: Clerk (frontend), Azure AD (backend)
Infra: Azure Container Apps, Docker, GitHub Actions, Terraform
AI: PydanticAI multi-model (Gemini-3-flash for speed, Opus 4.5 for intelligence)

Vendor documentation lives in the repo. Search for it before inventing approaches.
Patterns already exist in the codebase. Find them before proposing new ones.
```

## Research Context (CRITICAL for All Agents)

### Terminology: "AI" Means Frontier Generative AI

When the user says "AI" in this context, they mean:
- **Frontier models**: Claude Opus 4.5, GPT-5.2, Gemini-3-Flash, o3, DeepSeek-V3, etc.
- **Agentic systems**: Tool-using LLMs, multi-agent orchestration, MCP
- **Production LLM patterns**: Structured outputs, prompt engineering, evals
- **NOT**: Traditional ML, sklearn, statistical models, 2020-era chatbots

Search queries should reflect this. "AI best practices" returns stale content; "Claude agent patterns 2025" returns current content.

### Source Authority Hierarchy

**Tier 1 - Most Authoritative (prefer these):**
- GitHub repos with working code:
  - `anthropics/*` (Claude patterns, agent SDK, MCP)
  - `pydantic/pydantic-ai` (structured outputs, multi-model)
  - `openai/*` (agents SDK, swarm, evals)
  - `langchain-ai/langgraph` (agentic workflows)
  - `vercel/ai` (AI SDK patterns)
  - `run-llama/llama_index` (RAG, agents)
- Official docs: docs.anthropic.com, ai.google.dev, platform.openai.com
- Practitioner blogs with code: Simon Willison, Hamel Husain, Eugene Yan, swyx

**Tier 2 - Good for Patterns:**
- GitHub trending: 500+ stars, updated in last 6 months, has working examples
- Substacks: Latent Space, The Batch, AI Engineer newsletter
- X/Twitter: Only practitioners who ship (check for linked repos)

**Tier 3 - Use with Caution:**
- Hacker News (signal in comments, filter for links to code)
- Medium/dev.to (verify author has GitHub repos)

**AVOID - Likely Stale or Slop:**
- Business press (Forbes AI, TechCrunch think pieces, VentureBeat)
- Academic papers older than 6 months (field moves too fast now)
- SEO tutorial farms (Analytics Vidhya, GeeksforGeeks AI sections)
- "Top 10 AI tools" listicles
- LinkedIn AI influencer posts
- Generic "AI best practices" content without code

### Search Tool Preference

If Exa AI MCP is available (tools like `web_search_exa`, `get_code_context_exa`), prefer it over generic WebSearch for:
- **Code search**: `get_code_context_exa` finds GitHub, StackOverflow, docs directly
- **Technical research**: `web_search_exa` returns cleaner, more technical content
- **Company research**: `company_research_exa` for competitor/vendor analysis

Configure Exa MCP: `claude mcp add --transport http exa https://mcp.exa.ai/mcp`

### Search Query Patterns That Work

| Bad Query (stale results) | Good Query (current results) |
|---------------------------|------------------------------|
| "AI best practices" | "Claude Opus agent patterns 2026" |
| "LLM implementation" | "PydanticAI production site:github.com" |
| "AI architecture" | "multi-agent MCP orchestration example" |
| "machine learning ops" | "LLM observability Logfire tracing" |
| "chatbot development" | "structured outputs tool calling Claude" |
| "AI agents" | "agentic workflows langgraph anthropic" |
| "prompt engineering" | "Claude prompt optimization evals" |

**Query construction rules:**
1. **Use current year**: "2026" or "2025" (never older)
2. **Name specific models**: "Opus 4.5", "GPT-5.2", "Gemini-3-Flash" not generic "AI"
3. **Name specific frameworks**: "PydanticAI", "LangGraph", "Claude Agent SDK"
4. **Target GitHub**: `site:github.com [topic]` or use Exa's `get_code_context_exa`
5. **Add "production" or "example"**: Filters out tutorial slop

**If using Exa MCP**: Use `get_code_context_exa` for code patterns - it searches GitHub, StackOverflow, and docs directly with better signal-to-noise than generic web search.

## Execution Strategy

### Round 1: Breadth (Launch 6 Parallel Agents)

**CRITICAL**: Launch ALL agents in a SINGLE message with multiple Task tool calls. This makes them run in parallel.

#### Step 0: Generate Perspectives Based on Mode

**FIRST: Determine mode from the prompt (see Intent Detection above)**

---

**IMPLEMENTATION MODE** (user has decided):

Generate 3 perspectives that disagree on **HOW to achieve the goal**, not WHETHER to pursue it.

**Principles for selection:**
- All agents accept the user's stated goals and constraints as given
- Pick expertise that would approach the IMPLEMENTATION differently
- Disagreement is about methods, tradeoffs, and sequencing
- NO agent should question the fundamental premise

**Bad example** (for "improve matching with principled prompts"):
- "Skeptic who thinks rules are better than principles" → Challenges premise
- "Researcher who found papers against this approach" → Challenges premise

**Good example** (same prompt):
- "Prompt minimalist" (fewer tokens, trust the model)
- "Structured output advocate" (schemas guide reasoning without constraining it)
- "Calibration expert" (how to measure if principled prompts work)

Think: *Given the user HAS DECIDED, what implementation approaches would experts debate?*

---

**EVALUATION MODE** (user is uncertain):

Generate 3 perspectives that would naturally conflict on WHETHER to do this.

**Principles for selection:**
- Don't pick roles that would obviously agree (e.g., "Frontend Dev" and "React Expert")
- Pick expertise that has the most at stake in this decision
- At least one should have incentive to say "don't do this at all"
- Name specific domains, not generic "expert"

**Bad example**: "Frontend Dev", "React Expert", "UI Engineer" → All agree on most things
**Good example**: "Feature Developer" (wants to ship), "Platform Engineer" (wants stability), "Finance" (wants cost control)

Think: *Who would argue about this at a company meeting?*

---

#### Agents to Launch

**All agents have FULL TOOL ACCESS. They MUST research before forming opinions.**

Research means:
- **Search local codebase** — Glob/Grep/Read for existing patterns, configs, implementations
- **Search the web** — WebSearch for current best practices, failure cases, novel approaches
- **Search vendor docs** — Documentation for PydanticAI, Logfire, Clerk, TanStack lives in this repo

---

**3 DYNAMIC AGENTS** (generated based on the question):

For each of the 3 perspectives you identified:
```
Task(
  subagent_type="general-purpose",
  description="[PERSPECTIVE NAME] perspective",
  model="opus",
  prompt="""You are a [SPECIFIC ROLE/EXPERTISE].

Question: [INSERT FULL QUESTION]

## Your Environment
Frontend: Next.js + shadcn/ui + Zustand + TanStack | Backend: FastAPI + PydanticAI + Logfire
Infra: Azure Container Apps + GitHub Actions + Terraform | AI: Multi-model (Gemini-3-flash, Opus 4.5)

## Before You Answer

You have FULL TOOL ACCESS. Use it.

1. **Search the codebase** for existing patterns (Glob for files, Grep for code, Read for details)
2. **Search the web** following these source rules:
   - **Tier 1 (prefer)**: anthropics/*, pydantic/pydantic-ai, openai/*, docs.anthropic.com, Simon Willison, Hamel Husain
   - **AVOID**: Forbes, TechCrunch, VentureBeat, LinkedIn, academic papers >6mo, SEO farms (Analytics Vidhya, GeeksforGeeks)
   - **Query pattern**: "Claude agent patterns 2026" not "AI best practices" — add year, specific tech, site:github.com
   - **If Exa available**: Use `get_code_context_exa` for GitHub/code search, `web_search_exa` for practitioner content
3. **Search vendor docs** in the repo (PydanticAI, Logfire, TanStack, Clerk)

**CRITICAL**: "AI" means frontier generative AI (Opus 4.5, GPT-5.2, Gemini-3-Flash, o3, DeepSeek-V3), NOT traditional ML/sklearn.

Don't reason from priors. Find evidence.

## Your Mission

From YOUR unique expertise, what do you see that others will miss?

Principles:
- Ground every claim in evidence (cite files, URLs, or specific findings)
- Focus on what's UNIQUE to your perspective — don't repeat obvious points
- If you agree with the obvious answer, you're not looking hard enough from your angle
- Identify risks that others are blind to

Say what needs to be said. Length should match importance, not arbitrary limits.
"""
)
```

---

**3 FIXED AGENTS** (universal lenses for every question):

**Fixed Agent 1: Critical Reviewer**

**NOTE: Behavior changes based on mode:**

**IMPLEMENTATION MODE version:**
```
Task(
  subagent_type="general-purpose",
  description="Critical Reviewer (Implementation)",
  model="opus",
  prompt="""You are reviewing the IMPLEMENTATION APPROACH, not the goal itself.

Goal (ACCEPT THIS AS GIVEN): [INSERT USER'S STATED GOAL]
Proposed approach: [INSERT FULL QUESTION]

## Your Environment
Frontend: Next.js + shadcn/ui + Zustand + TanStack | Backend: FastAPI + PydanticAI + Logfire
Infra: Azure Container Apps + GitHub Actions + Terraform | AI: Multi-model (Gemini-3-flash, Opus 4.5)

## Before You Critique

You have FULL TOOL ACCESS. Use it to improve the implementation.

1. **Search for pitfalls**: WebSearch for "[approach] gotchas 2025", "site:github.com [approach] issues"
2. **Find successful implementations**: Search Tier 1 sources (anthropics/*, pydantic/pydantic-ai repos)
3. **Check local constraints**: Grep/Read to understand what existing patterns to honor

**CRITICAL**: "AI" means frontier generative AI (Opus 4.5, GPT-5.2, Gemini-3-Flash, o3). Search for specific patterns not generic "AI best practices".

IMPORTANT: You are NOT questioning WHETHER to pursue the goal. You are helping achieve it BETTER.

## Your Mission

Find what could go wrong with THIS IMPLEMENTATION of an accepted goal.

Principles:
- Accept the goal and stated constraints as given
- Critique the HOW, not the WHETHER
- "This implementation detail will cause problems" is valuable
- "Maybe don't do this at all" is OUT OF SCOPE - they've decided
- Find risks in the execution, not the strategy

What implementation pitfalls would make you nervous about this PR?
"""
)
```

**EVALUATION MODE version:**
```
Task(
  subagent_type="general-purpose",
  description="Critical Reviewer",
  model="opus",
  prompt="""You are reviewing this proposal as if it were a PR to the main codebase.

Question/proposal to review: [INSERT FULL QUESTION]

## Your Environment
Frontend: Next.js + shadcn/ui + Zustand + TanStack | Backend: FastAPI + PydanticAI + Logfire
Infra: Azure Container Apps + GitHub Actions + Terraform | AI: Multi-model (Gemini-3-flash, Opus 4.5)

## Before You Critique

You have FULL TOOL ACCESS. Use it to build your case.

1. **Search for failure cases**: WebSearch for "[topic] failures 2025 site:github.com", "[topic] post-mortem"
2. **Find counterexamples**: Search practitioner blogs (Simon Willison, Hamel Husain) for real-world failures
3. **Check local context**: Grep/Read to understand this specific codebase's constraints

**CRITICAL**: "AI" means frontier generative AI (Opus 4.5, GPT-5.2, Gemini-3-Flash, o3). Avoid stale academic papers and business press - find GitHub issues, production postmortems.

"It might not work" is weak. "Here's where it failed: [citation]" is strong.

## Your Mission

Find what will break, what's over-engineered, what's under-specified.

Principles:
- Attack the strongest version of their argument, not a strawman
- Ground every critique in evidence — speculation doesn't count
- If you find yourself agreeing, you're not looking hard enough
- Identify the scenario where this recommendation fails catastrophically

What would make you mass-revert this PR at 2am?
"""
)
```

---

**Fixed Agent 2: Architecture Advisor**
```
Task(
  subagent_type="general-purpose",
  description="Architecture Advisor",
  model="opus",
  prompt="""You advise on system design within the Motium architecture.

Question: [INSERT FULL QUESTION]

## Your Environment (you know this intimately)
- Multi-model AI: PydanticAI with Gemini-3-flash (speed/cost) and Opus 4.5 (intelligence)
- Workers: Priority queues (bullhorn_sync → cv_processor → match_processor)
- Schemas: Isolated by domain (bullhorn.*, public.*, cortex.*)
- Infra: Azure Container Apps with auto-scaling, GitHub Actions CI/CD
- Observability: Logfire for all AI operations

## Before You Advise

You have FULL TOOL ACCESS. Map the actual system.

1. **Understand current architecture**: Glob for service structure, Grep for import patterns
2. **Find existing patterns**: What similar problems have we already solved?
3. **Research at-scale issues**: WebSearch for "[topic] at scale 2025 site:github.com", production patterns from anthropics/*, pydantic/*

**CRITICAL**: "AI" means frontier generative AI (Opus 4.5, GPT-5.2, Gemini-3-Flash, o3). Search for "PydanticAI multi-model" not generic "AI architecture". AVOID: Forbes, TechCrunch, LinkedIn, papers >6mo.

Don't propose in a vacuum. Understand what exists.

## Your Mission

How does this proposal interact with the existing system?

Consider:
- Second-order effects on worker queues, database load, model costs
- What existing patterns does this duplicate or conflict with?
- Where are the leverage points for maximum impact with minimum change?
- What happens when this runs at 10x current scale?

Your value: Seeing connections others miss. Finding where the proposal doesn't fit.
"""
)
```

---

**Fixed Agent 3: Shipping Engineer**
```
Task(
  subagent_type="general-purpose",
  description="Shipping Engineer",
  model="opus",
  prompt="""You care about one thing: What's the fastest path to production?

Question: [INSERT FULL QUESTION]

## Your Environment
Frontend: Next.js + shadcn/ui + Zustand + TanStack | Backend: FastAPI + PydanticAI + Logfire
Infra: Azure Container Apps + GitHub Actions + Terraform | AI: Multi-model (Gemini-3-flash, Opus 4.5)

## Before You Plan

You have FULL TOOL ACCESS. Find the shortcuts.

1. **Search for existing implementations**: Glob/Grep for patterns we can copy or extend
2. **Find the minimal viable version**: What can we cut and still learn?
3. **Research practical guidance**: WebSearch for "[topic] example site:github.com 2025", check anthropics/*, pydantic/* repos

**CRITICAL**: "AI" means frontier generative AI (Opus 4.5, GPT-5.2, Gemini-3-Flash). Search "Claude tool calling example" not "AI implementation guide". Use Exa `get_code_context_exa` if available.

Theory is nice. Shipping matters.

## Your Mission

Principles:
- "Theoretically elegant" means nothing if it takes 3 months
- Find the 80% solution that ships this week
- Identify what can be deferred vs. what's blocking
- Name specific files to modify and patterns to follow

Your output: A concrete path with specific files, specific patterns, specific shortcuts.

What would you actually do Monday morning to make progress?
"""
)
```

---

### Intermediate Synthesis (After Round 1)

After all 6 agents return, synthesize their outputs:

**IMPLEMENTATION MODE synthesis:**

1. **Consensus on approach** — Where do 3+ perspectives agree on HOW to implement?

2. **Implementation tradeoffs** — For each tension:
   ```
   TRADEOFF: [implementation choice]
   - [Agent X] recommends: [approach A] because [reasoning]
   - [Agent Y] recommends: [approach B] because [reasoning]
   - The tradeoff: [what you gain/lose with each approach]
   ```
   Frame as tradeoffs, not "should we do this at all" debates.

3. **Gaps in implementation plan** — What technical details are underspecified?

4. **Select the #1 implementation decision** for deeper exploration (Round 1.5)

5. **Select 1-2 technical threads** for Round 2 deep-dive

---

**EVALUATION MODE synthesis:**

1. **Consensus** — Where do 3+ perspectives agree? This is probably true.

2. **Structured Disagreements** — For each tension:
   ```
   DISAGREEMENT: [topic]
   - [Agent X] claims: [position] because [evidence they found]
   - [Agent Y] claims: [opposite] because [their evidence]
   - The crux: [what would need to be true for one side to be right]
   ```
   **Do NOT smooth over disagreements.** The structured conflict IS the insight.

3. **Gaps** — What assumptions weren't challenged? What perspectives are missing?

4. **Select the #1 most contested disagreement** for adversarial dialogue (Round 1.5)

5. **Select 1-2 threads** for Round 2 deep-dive

---

### Round 1.5: Focused Dialogue (Sequential)

**IMPLEMENTATION MODE**: For the key implementation decision, have two agents with different approaches discuss tradeoffs. Goal: clarity on the best implementation path, not whether to implement.

**EVALUATION MODE**: For the single most contested disagreement, have the two agents actually debate. Goal: resolve or clarify the fundamental disagreement.

This is **sequential** — each responds to the other.

**Step 1: Defender**
```
Task(
  subagent_type="general-purpose",
  description="Dialogue: [Agent X] defends position",
  model="opus",
  prompt="""You are [AGENT X's PERSPECTIVE] from Round 1.

You claimed: [X's position]
Your evidence: [X's reasoning]

[AGENT Y] disagrees. They claim: [Y's position]
Their evidence: [Y's reasoning]

## Research to Strengthen Your Defense

You have FULL TOOL ACCESS. Find new evidence.

1. **Support your position**: Search Tier 1 sources (GitHub issues, practitioner blogs), not generic "AI articles"
2. **Challenge their claims**: Find GitHub issues, production postmortems that undermine their reasoning
3. **Look for resolution**: Search for "[topic A] vs [topic B] 2025 site:github.com"

**Remember**: "AI" = frontier generative AI (Opus 4.5, GPT-5.2, Gemini-3-Flash, o3), not traditional ML.

## Then Defend

Address their strongest point directly. Don't strawman.

- What new evidence supports your position?
- Where do they have a point? (Concede honestly)
- What would change your mind?
- What's the crux — the key question that would resolve this?
"""
)
```

**Step 2: Challenger** (after Step 1 completes)
```
Task(
  subagent_type="general-purpose",
  description="Dialogue: [Agent Y] responds",
  model="opus",
  prompt="""You are [AGENT Y's PERSPECTIVE] from Round 1.

You claimed: [Y's position]

[AGENT X] has responded:
---
[PASTE AGENT X's RESPONSE]
---

## Research to Challenge Their Defense

You have FULL TOOL ACCESS.

1. **Verify their evidence**: Are their citations accurate? Representative?
2. **Find counter-evidence**: Cases that contradict their new arguments
3. **Check blind spots**: Glob/Grep for local context they missed

## Then Respond

- Did they actually address your strongest point?
- Where does their argument still fail?
- Where did they change YOUR mind? (Be honest)
- Final verdict: agreement, partial agreement, or persistent disagreement?
"""
)
```

**Step 3: Synthesize the dialogue**
- Did they converge? On what?
- What remains contested?
- What new insights emerged that weren't in Round 1?

---

### Round 2: Depth (1-2 More Agents)

Based on synthesis, launch targeted deep-dives on unresolved threads:

**Deep-Dive Agent:**
```
Task(
  subagent_type="general-purpose",
  description="Deep-dive: [specific thread]",
  model="opus",
  prompt="""Explore this specific tension in depth:

THREAD: [describe the contested point]

CONTEXT: [relevant excerpts from Round 1]

## Research First

You have FULL TOOL ACCESS.

1. **Find root causes**: Search practitioner blogs, GitHub discussions (not stale academic papers)
2. **Check local constraints**: Glob/Grep for codebase factors that inform this
3. **Find resolution patterns**: Search "[topic] tradeoffs site:github.com 2025", check how anthropics/* resolved it

## Then Analyze

- Why does this disagreement exist?
- What evidence resolves or clarifies it?
- Can you propose a synthesis that honors both sides?
- What's genuinely unresolvable vs. just underexplored?
"""
)
```

**Red-Team Agent:**

**NOTE: In IMPLEMENTATION MODE, red-team focuses on implementation risks, not goal validity.**

**IMPLEMENTATION MODE version:**
```
Task(
  subagent_type="general-purpose",
  description="Red-team the implementation plan",
  model="opus",
  prompt="""Stress-test this implementation plan (NOT the goal itself):

GOAL (ACCEPTED): [user's stated goal]
IMPLEMENTATION PLAN: [paste current synthesis]

## Research First

You have FULL TOOL ACCESS.

1. **Find implementation pitfalls**: Search "[approach] gotchas site:github.com 2025", check issues in anthropics/*, pydantic/* repos
2. **Find edge cases**: What scenarios could break this implementation?
3. **Check local constraints**: Grep/Read for technical debt or dependencies that could interfere

## Then Stress-Test

- What implementation detail is most likely to fail?
- What edge case isn't covered?
- What technical constraint did we miss?
- What's the hardest part to get right?

IMPORTANT: You are NOT questioning the goal. You are helping bulletproof the execution.
"""
)
```

**EVALUATION MODE version:**
```
Task(
  subagent_type="general-purpose",
  description="Red-team the synthesis",
  model="opus",
  prompt="""Attack this emerging synthesis:

SYNTHESIS: [paste current synthesis]

## Research First

You have FULL TOOL ACCESS.

1. **Find similar failures**: Search production postmortems, GitHub issues - not generic "AI failures" articles
2. **Find missing perspectives**: Who isn't represented? What edge cases break this?
3. **Check local reality**: Grep/Read for constraints the synthesis missed

## Then Attack

- What's the weakest link?
- What perspective is missing?
- What would falsify this view?
- What's the hardest question for this synthesis?
"""
)
```

---

### Final Output Structure

After Round 2, generate the final answer.

**Choose output structure based on mode:**

---

**IMPLEMENTATION MODE Output:**

## Executive Summary
[How to implement the user's goal. Length matches complexity.]

## Recommended Approach
[The implementation strategy that emerged from analysis]

## Implementation Tradeoffs

### Tradeoff 1: [Decision Point]
| Option A | Option B |
|----------|----------|
| **Approach**: [Description] | **Approach**: [Description] |
| **Pros**: [Benefits] | **Pros**: [Benefits] |
| **Cons**: [Drawbacks] | **Cons**: [Drawbacks] |

**Recommendation**: [Which option and why]

[Repeat for each significant implementation decision]

## Technical Details
[Specific implementation guidance - files to modify, patterns to follow, etc.]

## Execution Risks & Mitigations
[What could go wrong during implementation and how to handle it]

## Next Steps
[Concrete actions to take, in order]

---

**EVALUATION MODE Output:**

## Executive Synthesis
[The coherent narrative merging all perspectives. Length matches complexity.]

## Consensus
[What most perspectives agree on — these claims are probably true]

## Structured Disagreements

### Disagreement 1: [Topic]
| Position A | Position B |
|------------|------------|
| **Claimed by**: [Agent(s)] | **Claimed by**: [Agent(s)] |
| **Argument**: [Core claim] | **Argument**: [Core claim] |
| **Evidence**: [What they found] | **Evidence**: [What they found] |

**The crux**: [What would need to be true for one side to be right]
**Resolution**: [How this was resolved, or why it remains unresolved]

[Repeat for each major disagreement. Do NOT smooth over conflicts.]

## Dialogue Outcome (from Round 1.5)
**Contested point**: [The disagreement that went to dialogue]
**Convergence**: [Where they agreed]
**Persistent disagreement**: [What remains unresolved]
**New insight**: [What emerged from the exchange]

## Practical Guidance
[Actionable recommendations based on the analysis]

## Risks & Mitigations
[What could go wrong with the recommended approach]

## Follow-Up Questions
[Questions that would most sharpen understanding if answered]

---

## Design Philosophy

**Respect user intent:**
- When user says "how to improve X", they've decided to improve X — help them do it
- When user says "should we do X", they're genuinely uncertain — explore both sides
- Stated assumptions ("we hold it as evident that...") are constraints, not debate topics
- Being adversarial about decided goals is unhelpful; being adversarial about implementation approaches is valuable

**Bet on model intelligence:**
- Principles over rubrics. Don't force early quantification.
- The model knows more than your schema. Let it reason freely.
- Scoring narrows the solution space. Save it for a final verification pass if needed.
- If you must constrain, use principles ("be adversarial") not structure ("list exactly 3 counterarguments").

**Structured disagreement is the insight (in evaluation mode):**
- Explicit "A claims X because P, B claims Y because Q" beats vague "there are tradeoffs"
- The crux (what would make one side right) is often more valuable than the resolution
- Unresolved tensions are valid outputs — don't force false consensus
- Depth comes from confronting conflicts, not spawning more agents

**Structured tradeoffs are the insight (in implementation mode):**
- "Option A gives you X but costs Y; Option B gives you Y but costs X" is actionable
- All options accept the user's stated goal as given
- Focus on the HOW debate, not the WHETHER debate
- Practical guidance > academic objections

**Self-education grounds analysis:**
- All agents have full tool access (general-purpose subagent)
- Research before opinion: local codebase (Glob/Grep/Read), web (WebSearch), vendor docs
- Opinion without evidence is speculation; research-backed analysis is insight
- Vendor docs live in the repo — search for them before inventing approaches

**Tech stack awareness:**
- Agents know Motium runs Next.js + PydanticAI + Azure Container Apps
- They search for existing patterns before proposing new ones
- Architecture questions consider: multi-model fallbacks, worker isolation, schema separation
- "How would this work in our stack?" is always a relevant question

**Dialogue produces clarity:**
- In evaluation mode: adversarial dialogue to resolve WHETHER questions
- In implementation mode: collaborative dialogue to resolve HOW questions
- Concessions are explicit — "you changed my mind on X" is a valuable signal
- Two rounds is usually enough; more risks performative debate

**Model selection (optional override):**
- Default: Opus for all agents (intelligence matters for analysis)
- Fast questions: Consider Gemini-3-flash agents for implementation-focused perspectives
- Mixed: 3 Opus (strategic) + 3 fast (tactical) for balanced cost/quality

**Avoid:**
- Point-based rubrics that narrow reasoning
- "Rate on a scale of 1-10" — this forces premature quantification
- Rigid word counts that cut off important reasoning
- Forcing all agents into identical output structures
- Premature consensus — honor real disagreements
- Agents that reason from priors without checking reality first
- **Challenging user's decided goals** — if they've decided, help them succeed
- **Academic objections to practical requests** — EU AI Act papers when user wants prompt optimization
