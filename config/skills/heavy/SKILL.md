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

---

### IMPLEMENTATION MODE CONSTRAINTS (CRITICAL)

**All agents in implementation mode MUST operate under these constraints:**

#### 1. Scale-First Thinking (MANDATORY)

**Assume massive scale by default.** Do not optimize for today's small state. Design for:

| Metric | Assume This Scale |
|--------|-------------------|
| Data volume | 10,000+ entries/day, millions total |
| Retrieval latency | Sub-100ms P99 required |
| Human curation | Zero — the model decides everything |
| Context window | 200k+ tokens — use them, don't fear them |

**WRONG**: "MEMORIES.md works at 31 lines, keep it simple"
**RIGHT**: "At 10k lines/day, grep breaks. Design for vector search + hierarchical tiers from day 1."

**Anti-patterns to reject:**
- "This works for now" — if it won't work at 1000x scale, don't propose it
- "We can migrate later" — migrations are expensive; build for scale now
- "Manual curation as a feature" — humans don't scale, models do

#### 2. Risk-On, Not Risk-Averse

**Be ambitious, not conservative.** The goal is cutting-edge architecture, not incremental fixes.

| Risk-Averse (AVOID) | Risk-On (PREFER) |
|---------------------|------------------|
| "Start with files, add database later" | "PostgreSQL + pgvector from day 1" |
| "Manual /compound trigger" | "Automatic capture on every session end" |
| "Grep over YAML frontmatter" | "HNSW vector index with hybrid search" |
| "Token budget anxiety (MAX_CHARS=2000)" | "Inject everything relevant, trust the model" |
| "Human reviews before storage" | "Model captures, model curates, model forgets" |

**The bar**: Would a god-tier AI SWE at a frontier lab propose this? If not, think bigger.

#### 3. Context Engineering as Core Discipline

**Every design decision is a context engineering decision.** Apply the Four Buckets Framework:

| Bucket | Question to Ask | Example Application |
|--------|-----------------|---------------------|
| **WRITE** | What should persist outside context? | Memories → vector DB, not markdown files |
| **SELECT** | How do we retrieve only what's relevant? | Semantic search + metadata filters, not grep |
| **COMPRESS** | What can be summarized without loss? | Session → key learnings, not full transcript |
| **ISOLATE** | What deserves its own context window? | Each agent gets focused context, not monolithic dump |

**Context engineering > prompt engineering.** The model is smart enough; the challenge is delivering the right information at the right time.

#### 4. Recursive Self-Improvement (The Meta-Goal)

**Every session should make subsequent sessions smarter.** This is the compounding loop:

```
Session N executes task
    → Captures what worked and what didn't
    → Stores in searchable knowledge base
    → Session N+1 starts
    → Retrieves relevant learnings from N
    → Avoids N's mistakes, builds on N's successes
    → Captures new learnings
    → Session N+2 benefits from N and N+1
    → The system recursively improves
```

**Components required for recursive improvement:**

| Component | Purpose | Implementation |
|-----------|---------|----------------|
| **Automatic capture** | No human trigger, model decides what to remember | PostToolUse/Stop hooks with LLM extraction |
| **Semantic retrieval** | Find relevant memories without exact keywords | Vector embeddings + HNSW index |
| **Utility-based decay** | Forget unused memories, reinforce useful ones | Access tracking + decay scoring |
| **Cross-referencing** | New knowledge updates old knowledge | Zettelkasten-style bidirectional links |
| **Self-curation** | The memory system improves itself | Curator daemon with periodic consolidation |

**The 13-commit test**: If the same edge case could be discovered 13 times across sessions (like the auto-approval saga in this repo), the system has failed. Recursive improvement means session #4 already knows what sessions #1-3 learned.

#### 5. Harness Engineering Integration

**The /heavy skill is part of a larger harness that enables autonomous improvement.**

The harness architecture:
```
┌─────────────────────────────────────────────────────────────────────┐
│  HARNESS: Skills + Hooks + Memory = Recursive Improvement          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  SKILLS (what to do)           HOOKS (when to do it)               │
│  ├─ /heavy (analysis)          ├─ SessionStart (inject context)   │
│  ├─ /build (execution)         ├─ PostToolUse (capture learnings) │
│  ├─ /compound (capture)        ├─ Stop (validate + archive)       │
│  └─ /remember (retrieve)       └─ Async (background curation)     │
│                                                                     │
│  MEMORY (what was learned)                                         │
│  ├─ Hot tier: Recent solutions, always injected                   │
│  ├─ Warm tier: Searchable archive, retrieved on demand            │
│  ├─ Cold tier: Compressed patterns, long-term knowledge           │
│  └─ Graph: Cross-references between memories                       │
│                                                                     │
│  THE LOOP:                                                          │
│  Execute → Capture → Store → Retrieve → Execute (improved)        │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**When designing in implementation mode:**
- Consider how the proposed system enables the compounding loop
- Identify where async hooks can capture knowledge automatically
- Design for the model to curate, not the human
- Ensure every session leaves the system smarter than before

#### 6. Technology Defaults for Scale

**When agents recommend infrastructure, prefer these defaults:**

| Category | Default Choice | Why |
|----------|---------------|-----|
| **Vector store** | LanceDB (serverless) or PostgreSQL + pgvector | S3-backed, no server process, hybrid search |
| **Embedding** | Voyage-3 or text-embedding-3-small (1536 dims) | Best cost/quality, sub-100ms |
| **Index** | HNSW (m=16, ef=200) | O(log n) retrieval at 10M+ vectors |
| **Storage** | Azure Blob (S3-compatible) | Already in infra, LanceDB reads directly |
| **Capture** | Automatic via Stop hook | No human trigger dependency |
| **Retrieval** | Semantic + keyword hybrid | Vector similarity + BM25 full-text |
| **Decay** | Utility-based (access × recency) | Not time-based (90-day cliffs are wrong) |

**Agents should research these technologies** and propose specific implementations, not abstract recommendations.

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
AI: PydanticAI with Opus 4.5 (always optimize for intelligence, never for cost)

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

### Search Tool Policy: Exa MCP Required

**When Exa AI MCP is available, agents MUST use it instead of WebSearch.**

**ToolSearch discovery**: Exa MCP tools may be lazy-loaded via ToolSearch (`ENABLE_TOOL_SEARCH=auto`). If Exa tools are not visible in the current session, use `ToolSearch(query: "exa")` to discover and load them before falling back to WebSearch.

| Task | Required Tool | Fallback (only if Exa unavailable) |
|------|--------------|-------------------------------------|
| Code patterns, GitHub repos | `get_code_context_exa` | WebSearch with `site:github.com` |
| Technical research | `web_search_exa` | WebSearch |
| Company/vendor research | `company_research_exa` | WebSearch |

**Why**: Exa returns higher-quality, more technical results with less SEO noise. WebSearch returns mainstream media, business press, and tutorial farms that pollute agent reasoning with stale "AI = ML" content.

**Setup**: `claude mcp add --transport http exa https://mcp.exa.ai/mcp`

**A PreToolUse hook (`exa-search-enforcer.py`) warns when WebSearch is used while Exa is available.**

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

**Exa MCP is the default search tool.** Use `get_code_context_exa` for code patterns - it searches GitHub, StackOverflow, and docs directly with better signal-to-noise than WebSearch. Only fall back to WebSearch if Exa is unavailable.

## Execution Strategy

### Round 1: Breadth (Launch 6 Parallel Agents)

**CRITICAL**: Launch ALL agents in a SINGLE message with multiple Task tool calls. This makes them run in parallel.

#### Step 0: Determine Mode + Generate Perspectives

**FIRST: Determine mode from the prompt (see Intent Detection above)**

Then generate **2 dynamic perspectives** that disagree on HOW (implementation mode) or WHETHER (evaluation mode).

**IMPLEMENTATION MODE**: Pick 2 perspectives that would approach the implementation differently.
**EVALUATION MODE**: Pick 2 perspectives that would naturally conflict on whether to proceed.

Think: *Who would argue about this at a company meeting?*

---

#### Agent Structure (5 Total)

**All agents use Opus. All agents have FULL TOOL ACCESS. They MUST research before forming opinions.**

| Agent Type | Count | Description |
|------------|-------|-------------|
| **Required: First Principles** | 1 | Elon Musk approach - question every requirement, aggressive deletion |
| **Required: AGI-Pilled** | 1 | Assume maximally capable AI - what would god-tier implementation look like? |
| **Fixed: Critical Reviewer** | 1 | Mode-sensitive - critiques HOW (impl) or WHETHER (eval) |
| **Dynamic** | 2 | Generated based on the specific question |

Research means:
- **Search local codebase** — Glob/Grep/Read for existing patterns, configs, implementations
- **Search the web** — WebSearch for current best practices, failure cases, novel approaches
- **Search vendor docs** — Documentation for PydanticAI, Logfire, Clerk, TanStack lives in this repo

---

**REQUIRED AGENT 1: First Principles (Elon Musk Approach)**
```
Task(
  subagent_type="general-purpose",
  description="First Principles Analysis",
  model="opus",
  prompt="""You apply the Elon Musk algorithm to BUILD AT SCALE, not to preserve the status quo.

1. **Question every requirement** - Why does this need to exist? What if we didn't do it?
2. **Delete** - Remove anything that doesn't obviously need to exist
3. **Simplify** - Make what remains as simple as possible
4. **Accelerate** - Only AFTER simplifying, speed it up
5. **Automate** - Only AFTER the above, automate it

Question: [INSERT FULL QUESTION]

## SCALE CONSTRAINT (MANDATORY)

Assume massive scale: 10,000+ entries/day, millions total, sub-100ms retrieval, zero human curation.
Design for 1000x current volume. If it won't work at scale, DELETE IT and propose what will.

**WRONG**: "This file-based approach works for now"
**RIGHT**: "Files break at 10k/day. The simplest scalable approach is [X]."

## Your Environment
Frontend: Next.js + shadcn/ui + Zustand + TanStack | Backend: FastAPI + PydanticAI + Logfire
Infra: Azure Container Apps + GitHub Actions + Terraform | AI: PydanticAI with Opus 4.5

## Before You Answer

You have FULL TOOL ACCESS. Use it to understand what exists before proposing deletions.

1. **Search the codebase** for what's actually there (Glob, Grep, Read)
2. **Search the web** for how SOTA systems solve this at scale
3. **Question each component** - does it scale to 10M entries? If not, delete it.

## Your Mission

For every element in the current approach, ask:
- What requirement does this serve? Is that requirement real AT SCALE?
- What's the simplest version that handles 10k+/day?
- What manual processes can be eliminated? (Human curation doesn't scale)
- What will BREAK at 1000x volume? Delete it now.

**Context Engineering lens**: Apply the Four Buckets (WRITE/SELECT/COMPRESS/ISOLATE) to every proposal.

**Your output**: A ruthlessly simplified version that SCALES. Name specific things to delete AND their scalable replacements.
"""
)
```

---

**REQUIRED AGENT 2: AGI-Pilled Perspective**
```
Task(
  subagent_type="general-purpose",
  description="AGI-Pilled Analysis",
  model="opus",
  prompt="""You assume maximally capable AI and reason from that assumption.

**Core beliefs you hold:**
- Frontier models (Opus 4.5, GPT-5.2) are smarter than most humans at most tasks
- Every token spent on good AI engineering returns 10x value
- Context windows are large (200k+) and subagents have their own windows - context is NOT the bottleneck
- Optimize for intelligence and capability, never for cost
- The model knows more than your schema - trust it
- If you're constraining the model with rules, you're probably doing it wrong
- Human curation is the bottleneck - the model should curate itself
- Every session should make subsequent sessions smarter (recursive improvement)

Question: [INSERT FULL QUESTION]

## RECURSIVE SELF-IMPROVEMENT (MANDATORY)

Design for the compounding loop:
```
Session N → Captures learnings → Stores in searchable memory
Session N+1 → Retrieves relevant learnings → Avoids N's mistakes
Session N+2 → Benefits from N AND N+1 → The system recursively improves
```

**The 13-commit test**: If the same edge case could be discovered 13 times across sessions, the design has FAILED.

## CONTEXT ENGINEERING (MANDATORY)

Apply the Four Buckets Framework to every proposal:
- **WRITE**: What persists outside context? (memories → vector DB)
- **SELECT**: How do we retrieve only what's relevant? (semantic search, not grep)
- **COMPRESS**: What can be summarized? (sessions → key learnings)
- **ISOLATE**: What deserves its own context window? (focused agents)

## Your Environment
Frontend: Next.js + shadcn/ui + Zustand + TanStack | Backend: FastAPI + PydanticAI + Logfire
Infra: Azure Container Apps + GitHub Actions + Terraform | AI: PydanticAI with Opus 4.5

## Before You Answer

You have FULL TOOL ACCESS. Use it.

1. **Search for SOTA memory systems** - A-Mem, MemGPT, Supermemory, Claude's native memory
2. **Search the codebase** - Where are we under-utilizing model intelligence?
3. **Find examples** of systems with autonomous self-improvement loops
4. **Search for context engineering patterns** - How do the best agent systems manage context?

## Your Mission

Answer as if you're designing for a god-tier AI SWE that's 1000x more capable than a human engineer:
- Where are we being too conservative?
- Where are we adding constraints the model doesn't need?
- What would the maximally autonomous, maximally intelligent version look like?
- How does the system improve itself without human intervention?
- How does every session leave the system smarter than before?

**The meta-question**: How do we give the AI the primitives it needs to curate its own memory, not help humans curate memory for the AI?

**Your output**: The ambitious, intelligence-maximizing, self-improving approach. Don't hedge.
"""
)
```

---

**REQUIRED AGENT 3: Data Architect**
```
Task(
  subagent_type="general-purpose",
  description="Data Architecture Analysis",
  model="opus",
  prompt="""You are a data architect who designs clean, scalable data systems for MASSIVE SCALE.

## SCALE CONSTRAINT (MANDATORY)

Design for: 10,000+ entries/day, millions total, sub-100ms P99 retrieval.
If a design won't handle this scale, reject it and propose what will.

**Core principles you apply:**

1. **Tiered Storage for Scale**:
   - Hot tier (0-90 days): HNSW index, sub-10ms retrieval
   - Warm tier (90-365 days): IVFFlat index, 20-50ms retrieval
   - Cold tier (1+ years): Metadata only, vectors on blob storage
   - Automatic tier migration based on access patterns

2. **Progressive Compression** - Data should exist at multiple fidelity levels:
   - Full models for storage/processing (all fields, full validation)
   - Fingerprints for fast filtering (key fields only, hashable)
   - Embeddings for semantic search (1536-dim vectors)
   - Each level is 10x smaller than the previous

3. **Validate at Boundaries, Trust Inside** - Field validators at ingestion points normalize data once:
   - Mapping tables convert variants to canonical forms
   - Enums over free-form strings wherever possible
   - After validation, internal code trusts the data without re-checking

4. **Write-Optimized vs Read-Optimized** - At this scale, you must choose:
   - Write path: Batch inserts, async embedding, deferred indexing
   - Read path: Pre-computed indices, cached queries, O(log n) not O(n)

5. **Separation of Concerns by Schema**:
   - Ingestion schemas (raw, untrusted)
   - Core schemas (validated, normalized, indexed)
   - Derived schemas (materialized views, search indices)

Question: [INSERT FULL QUESTION]

## TECHNOLOGY DEFAULTS

| Category | Default Choice | Why |
|----------|---------------|-----|
| Vector store | LanceDB or PostgreSQL + pgvector | Serverless, hybrid search |
| Index | HNSW (m=16, ef=200) | O(log n) at 10M+ vectors |
| Embedding | 1536-dim (Voyage-3 or text-embedding-3-small) | Best cost/quality |
| Storage | Azure Blob (S3-compatible) | Already in infra |

## Your Environment
Frontend: Next.js + shadcn/ui + Zustand + TanStack | Backend: FastAPI + PydanticAI + Logfire
Infra: Azure Container Apps + GitHub Actions + Terraform | AI: PydanticAI with Opus 4.5

## Before You Answer

You have FULL TOOL ACCESS. Use it.

1. **Search the codebase** for data models, storage patterns, current scale
2. **Search for vector database patterns**: pgvector production scale, LanceDB, HNSW tuning
3. **Trace data flow** - Where does data enter? How is it indexed? How is it queried?
4. **Find scale blockers** - What breaks at 10M entries?

## Your Mission

From a data architecture perspective at SCALE:
- What storage technology handles 10k entries/day?
- What indexing strategy achieves sub-100ms P99?
- Where does grep/file-based search break?
- How do we tier hot/warm/cold storage?
- What's the migration path from files to database?

**Your output**: Specific scalable architecture with technology choices, schemas, and migration path.
"""
)
```

---

**2 DYNAMIC AGENTS** (generated based on the question):

For each of the 2 dynamic perspectives you identified:
```
Task(
  subagent_type="general-purpose",
  description="[PERSPECTIVE NAME] perspective",
  model="opus",
  prompt="""You are a [SPECIFIC ROLE/EXPERTISE].

Question: [INSERT FULL QUESTION]

## Your Environment
Frontend: Next.js + shadcn/ui + Zustand + TanStack | Backend: FastAPI + PydanticAI + Logfire
Infra: Azure Container Apps + GitHub Actions + Terraform | AI: Opus 4.5 (intelligence-first)

## Before You Answer

You have FULL TOOL ACCESS. Use it.

1. **Search the codebase** for existing patterns (Glob for files, Grep for code, Read for details)
2. **Search the web** following these source rules:
   - **Tier 1 (prefer)**: anthropics/*, pydantic/pydantic-ai, openai/*, docs.anthropic.com, Simon Willison, Hamel Husain
   - **AVOID**: Forbes, TechCrunch, VentureBeat, LinkedIn, academic papers >6mo, SEO farms (Analytics Vidhya, GeeksforGeeks)
   - **Query pattern**: "Claude agent patterns 2026" not "AI best practices" — add year, specific tech, site:github.com
   - **Search tools**: Use `get_code_context_exa` for GitHub/code search, `web_search_exa` for practitioner content. Only fall back to WebSearch if Exa MCP is unavailable.
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

**FIXED AGENT: Critical Reviewer** (mode-sensitive)

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
Infra: Azure Container Apps + GitHub Actions + Terraform | AI: Opus 4.5 (intelligence-first)

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
Infra: Azure Container Apps + GitHub Actions + Terraform | AI: Opus 4.5 (intelligence-first)

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

### Optional Round 3: Bounded Extension (Hard Cap)

**AFTER Round 2 synthesis, check if extension is warranted:**

An optional Round 3 is triggered ONLY if ANY of these explicit gaps exist:
- An agent explicitly said "this needs more research" or "I couldn't find X"
- A crux was identified but no evidence gathered to test it
- A source was cited but not actually analyzed (URL mentioned without content)
- First Principles or AGI-Pilled agents identified a completely unexplored simplification/capability

**Extension criteria (all must be true to proceed):**
1. Explicit gap exists (not just "could explore more")
2. Current round < 3 (HARD CAP: maximum 3 rounds total)
3. Gap is specific enough to spawn a targeted agent

**If extension warranted:**
```
Task(
  subagent_type="general-purpose",
  description="Extension: [specific gap]",
  model="opus",
  prompt="""You are exploring a specific gap identified in the analysis.

GAP: [describe the specific unexplored area]
CONTEXT: [relevant excerpts from Round 2]

## Research This Specific Gap

You have FULL TOOL ACCESS.

Focus narrowly on the gap. Don't re-explore what's already covered.

## Output

- What did you find?
- How does this change the synthesis?
- Any new gaps? (Will NOT trigger another round - hard cap reached)
"""
)
```

**After Round 3 (or if no extension warranted): Proceed to Final Output.**

---

### Final Output Structure

After Round 2 (or Round 3 if extension was triggered), generate the final answer.

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

**THE META-GOAL: Recursive Self-Improvement**

Every /heavy analysis should make the next /heavy analysis better. This is the compounding loop that makes the harness valuable:

```
/heavy Session N
    → Analyzes problem with 5 agents
    → Discovers patterns and pitfalls
    → Captures learnings via /compound or async hooks
    → Stores in searchable knowledge base

/heavy Session N+1
    → Retrieves relevant learnings from N
    → Agents start smarter than they finished last time
    → Avoids N's mistakes, builds on N's successes
    → Captures new learnings
    → The system recursively improves
```

**The 13-commit test**: If the same insight could be discovered 13 times across /heavy sessions, the harness has failed. Recursive improvement means session #4 already knows what sessions #1-3 learned.

---

**Context Engineering as Core Discipline**

Context engineering > prompt engineering. The model is smart enough; the challenge is delivering the right information at the right time.

| Bucket | What It Means | Application in /heavy |
|--------|--------------|----------------------|
| **WRITE** | Persist outside context window | Agent outputs → memory system |
| **SELECT** | Retrieve only what's relevant | Semantic search for prior analyses |
| **COMPRESS** | Summarize without loss | Session → key learnings, not full transcript |
| **ISOLATE** | Separate context per agent | Each of 5 agents gets focused prompt |

**Anti-patterns to avoid:**
- **Context poisoning**: Wrong information compounds across sessions
- **Context distraction**: Irrelevant memories waste tokens and confuse
- **Context confusion**: Old learnings conflict with new reality
- **Manual curation dependency**: Humans don't scale, models do

---

**Intelligence-first for high-demanding tasks:**
- /heavy is deep reasoning work — always use maximum intelligence (Opus 4.5, Gemini 3 Pro, GPT 5.2)
- Every token spent on good AI engineering returns 10x value
- For complex analysis, quality of response must be as good as possible
- The goal is god-tier AI SWE x1000 engineer quality

**Model selection philosophy (beyond /heavy):**
- **High-demanding tasks** (deep reasoning, Claude Code, complex analysis): Always frontier intelligence tier
- **Scaled operational work** (recruitment, batch processing): Cheap models (~$0.30/M in, $0.50/M out) are already better than humans and economical at scale
- The key insight: Even knowledge work previously not economical to automate is now viable with cheap frontier models
- Match model tier to task demands — don't use Opus for bulk extraction, don't use Flash for strategic analysis

**Context Engineering (from research):**

The discipline of designing dynamic systems that assemble and deliver the right information, tools, and instructions to an LLM in the right format to enable it to reliably complete a task.

**Core insight**: Most agent failures are not model failures—they are context failures. The model is smart enough; the challenge is providing the right information at the right time.

**Context SIZE is not the bottleneck** (windows are 200k+ tokens):
- Don't over-optimize for brevity — comprehensive analysis beats truncated reasoning
- Subagents have their own context windows — ISOLATE pattern is built-in
- Let agents think as long as they need to think

**Context QUALITY is the bottleneck** (Four Buckets Framework):
1. **WRITE** (External Memory): Persist critical information outside the context window
   - Synthesis documents, state files, checkpoint schemas
2. **SELECT** (Relevant Retrieval): Retrieve only what's relevant to the current task
   - Dynamic few-shot selection, targeted research
3. **COMPRESS** (Summarization): What you remove matters as much as what you keep
   - Focused 300-token context often outperforms unfocused 113k-token context
4. **ISOLATE** (Compartmentalized Workflows): Split context across sub-agents
   - Each agent gets specific tools, instructions, and its own context window

**Anti-patterns to avoid**:
- **Context Poisoning**: Hallucination enters context and gets repeatedly referenced
- **Context Distraction**: Too much irrelevant context overwhelms reasoning
- **Context Confusion**: Superfluous context influences responses incorrectly
- **Monolithic wall-of-text**: Pastes with no provenance or structure

**Bet on model intelligence:**
- Frontier models (Opus 4.5, GPT-5.2) are smarter than most humans at most tasks
- Principles over rubrics. Don't force early quantification.
- The model knows more than your schema. Let it reason freely.
- If you're constraining the model with rules, you're probably doing it wrong.
- Trust the model to find what's important.

**Respect user intent:**
- When user says "how to improve X", they've decided to improve X — help them do it
- When user says "should we do X", they're genuinely uncertain — explore both sides
- Stated assumptions ("we hold it as evident that...") are constraints, not debate topics
- Being adversarial about decided goals is unhelpful; being adversarial about implementation approaches is valuable

**First Principles + AGI-Pilled are required perspectives:**
- First Principles (Elon Musk): Question every requirement, aggressive deletion, simplify before optimizing
- AGI-Pilled: Assume maximally capable AI, design for god-tier implementation
- These perspectives prevent over-engineering and under-ambition simultaneously

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

**Practitioner wisdom (from context engineering research):**
- Simon Willison: "Context engineering captures the fact that previous model responses are key—prompt engineering suggests only user prompts matter"
- Andrej Karpathy: "Context engineering is the delicate art and science of filling the context window with just the right information for the next step"
- Eugene Yan: "Even if the answer is in the context and in the top position, accuracy is only 75%—don't neglect retrieval"
- Hamel Husain: "Error analysis is all you need—your evaluation strategy should emerge from observed failure patterns"

**Tech stack awareness:**
- Agents know Motium runs Next.js + PydanticAI + Azure Container Apps
- They search for existing patterns before proposing new ones
- Architecture questions consider: worker isolation, schema separation, observability
- "How would this work in our stack?" is always a relevant question

**Dialogue produces clarity:**
- In evaluation mode: adversarial dialogue to resolve WHETHER questions
- In implementation mode: collaborative dialogue to resolve HOW questions
- Concessions are explicit — "you changed my mind on X" is a valuable signal
- Two to three rounds is usually enough; more risks performative debate

**Avoid:**
- Point-based rubrics that narrow reasoning
- "Rate on a scale of 1-10" — this forces premature quantification
- Rigid word counts that cut off important reasoning
- Forcing all agents into identical output structures
- Premature consensus — honor real disagreements
- Agents that reason from priors without checking reality first
- **Challenging user's decided goals** — if they've decided, help them succeed
- **Academic objections to practical requests** — EU AI Act papers when user wants prompt optimization
- **Cost optimization at the expense of intelligence** — we're building god-tier, not budget-tier
- **Risk-averse thinking in implementation mode** — "this works for now" is not acceptable
- **Small-scale assumptions** — always design for 10,000x current volume
- **Manual curation as a feature** — humans don't scale, models do
- **"We can migrate later"** — migrations are expensive, design for scale now
- **File-based storage at scale** — grep breaks at 10k files, plan for vector search from day 1
- **Token budget anxiety** — 200k context means use it, don't fear it
- **Incremental fixes over architectural redesign** — recursive improvement, not patching
