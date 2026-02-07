---
name: prompt-engineering-patterns
description: Design prompts, skills, and CLAUDE.md files as context engineering problems. Use when writing skills, optimizing prompts, designing agent workflows, auditing CLAUDE.md, or reducing prompt bloat. Triggers on "prompt engineering", "optimize prompt", "write a skill", "reduce bloat", "context engineering".
---

# Context Engineering for Prompts

Context engineering > prompt engineering. The model is smart enough. The challenge
is delivering the right information at the right time in the right format.

## Section Map

| If your task is... | Read section... |
|---------------------|----------------|
| Writing a new skill SKILL.md | #writing-skills-and-prompts |
| Optimizing an existing prompt/skill | #the-deletion-test + #compression-patterns |
| Designing subagent prompts | #isolation-for-multi-agent |
| Auditing CLAUDE.md | #the-deletion-test + #compression-patterns |
| Debugging bad outputs | #context-failure-diagnosis |

## The One Rule

**Every token must earn its place.** A skill loads into context on every invocation.
A CLAUDE.md loads on every session. Waste compounds at scale.

### The Deletion Test

For every line in a prompt or skill, ask these four questions:

| # | Question | If YES... |
|---|----------|-----------|
| 1 | Would removing this change the model's behavior? | Keep |
| 2 | Does the model already know this from training? | Delete |
| 3 | Could the model discover this via Glob/Grep in 2 seconds? | Delete |
| 4 | Can this be said in half the words without losing meaning? | Compress |

If a line fails question 1, delete it. Everything else is negotiable.

## Context Engineering Applied

The Four Buckets framework (see /heavy for full treatment) maps directly to
prompt and skill design:

| Bucket | Question for Prompts | Toolkit Primitive |
|--------|---------------------|-------------------|
| **WRITE** | What must persist in the skill file vs. left to the model's training? | Skills, CLAUDE.md, memory events |
| **SELECT** | What information does this specific invocation need? | Section maps, conditional loading |
| **COMPRESS** | Can you say it in fewer tokens without losing behavioral impact? | Tables over prose, constraints over guidance |
| **ISOLATE** | Does this work belong in its own context window? | Subagents via Task(), parallel execution |

**Key insight**: Only WRITE what the model doesn't already know AND is specific
to this toolkit/project. Everything else is wasted tokens.

## Writing Skills and Prompts

### Checklist (follow in order)

1. **State the role in one sentence.** "You are X." Not a paragraph.
2. **List 3-7 behavioral constraints.** What the model MUST and MUST NOT do.
   Constraints change behavior more than guidance.
3. **Provide the workflow.** Numbered steps or ASCII diagram. Not prose.
4. **Add ONE concrete example** if the output format isn't obvious.
   One example provides ~80% of the value of five.
5. **Specify output format explicitly** when it matters (JSON schema, table, etc.)
6. **Run the Deletion Test.** Remove everything that fails question 1.

### Behavioral Anchors (imperatives, not explanations)

- **Start simple, add complexity only when needed.** The first draft should be
  the shortest version that works. Add detail only when testing reveals gaps.
- **Demonstrate, don't explain.** One before/after example teaches more than
  a paragraph of theory. Never explain a technique without showing it.
- **Constraints over guidance.** "Never output more than 3 items" beats
  "Please try to keep your output concise and focused."
- **Imperative voice.** "Extract entities." not "The model should attempt to
  extract entities from the provided text."

## Anti-Patterns

| Anti-Pattern | Wrong | Right |
|-------------|-------|-------|
| **Teaching the model what it knows** | 400 lines explaining chain-of-thought | Don't include it (Claude invented CoT) |
| **Dead code in markdown** | Python classes with imports that never execute | If code must exist, put it in scripts/ where it runs |
| **Generic examples** | Sentiment analysis few-shot examples | Examples from THIS project's actual domain |
| **Padding phrases** | "This technique is highly effective for tasks requiring specific formats" | Delete the sentence |
| **Aspirational infrastructure** | MockLLMClient, PromptVersionControl classes | Reference actual infrastructure (hooks, memory) |
| **Completeness trap** | "Also consider edge cases, error handling, performance, security, accessibility..." | List only what's relevant to THIS task |
| **Politeness tokens** | "Please kindly ensure that you carefully..." | "Do X." (agent-to-agent needs no pleasantries) |
| **The textbook trap** | A skill that explains prompt engineering theory | A skill that changes the model's next output |

## Compression Patterns

### Tables Over Prose
Tables compress 3-5x vs prose for the same information. Use tables for:
comparisons, decision matrices, anti-patterns, mappings. Use prose only for
concepts that require narrative flow.

### Constraints Over Guidance
"DO NOT use EnterPlanMode" (from /go) is 6 tokens that change behavior.
"You should generally avoid using planning mode unless necessary" is 11 tokens
that change nothing.

### Imperative Over Descriptive
- Wrong: "The system prompt section is responsible for defining the model's role"
- Right: "Set the role in the system section."

### Negative Space
What you omit teaches as much as what you include. The model fills gaps
intelligently. Sparse instructions + clear constraints > detailed step-by-step
that the model would figure out anyway.

### Reference, Don't Duplicate
If content exists elsewhere in the toolkit, point to it:
"Apply the Four Buckets framework (see /heavy SKILL.md lines 86-96)"
One line replaces duplicating a section.

## Context Failure Diagnosis

When a prompt or skill produces bad output, diagnose which bucket failed:

| Symptom | Likely Bucket Failure | Fix |
|---------|----------------------|-----|
| Output is wrong or hallucinated | **SELECT** — wrong context provided | Check what information reached the model |
| Output is correct but verbose/sloppy | **COMPRESS** — too much low-quality context dilutes signal | Trim the skill/prompt, run Deletion Test |
| Output misses critical info | **WRITE** — knowledge not persisted anywhere | Add to skill, CLAUDE.md, or memory event |
| Agent duplicates another agent's work | **ISOLATE** — context bleeding between agents | Give each agent a focused, non-overlapping mandate |

## Isolation for Multi-Agent

When designing prompts for /heavy or /build subagents:

1. **Each agent gets a focused role.** One sentence. Not the full project context.
2. **Each agent researches independently.** Give them tools, not pre-digested context.
3. **Minimum viable context transfer.** When passing Agent A's output to Agent B,
   pass claims + evidence, not the full analysis.
4. **Diminishing returns.** 2 agents = 1 tension. 5 agents = 10 tensions.
   8+ agents = diminishing returns. Sweet spots: /heavy uses 5, /build uses 4.

## Living References

Don't read explanations. Read exemplary skills:

| Principle | Read This Skill | What to Notice |
|-----------|----------------|----------------|
| Maximum compression | /go (115 lines) | Assumes model competence, no ceremony |
| Context isolation | /heavy (5 parallel agents) | Each agent gets focused prompt |
| Constraint-driven design | /build (checkpoint schema) | Booleans force honest behavior |
| Memory integration | /compound (95 lines) | Captures learnings, system injects them |
| Operational checklist | /compound Step 1-4 | Every line drives action, not theory |

## Integration

| System | How It Connects |
|--------|----------------|
| **Memory** | stop hook auto-captures session outcomes; compound-context-loader injects relevant events at SessionStart |
| **Hooks** | Enforce behavioral contracts (stop-validator checks checkpoint booleans, auto-approve enables autonomous execution) |
| **Subagents** | Task() provides the ISOLATE primitive — each agent gets its own context window |
| **/compound** | When you discover a prompt anti-pattern, capture it. If the same fix applies 3+ times, modify the skill itself |

## The Meta-Test

This skill practices what it preaches. It replaced a 2,680-line / 9-file skill
(Python classes, template libraries, textbook CoT explanations) with ~170 lines.
Every deleted line failed the Deletion Test. If you can delete a line from THIS
skill without changing behavior, open a PR.
