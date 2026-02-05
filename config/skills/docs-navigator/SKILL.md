---
name: docs-navigator
description: Navigate project documentation efficiently. Use when asked to "read the docs", "check documentation", or before starting unfamiliar tasks. Triggers on read docs, check docs, documentation, unfamiliar codebase.
---

# Documentation Navigator

Efficiently read project documentation without bloating context.

## When to Use

- User explicitly says "read the docs"
- Starting work in unfamiliar area of codebase
- Need to understand patterns/conventions before implementing

## Workflow

### Step 1: Search for Relevant Docs

**If QMD MCP is available** (check with `qmd_status`):
```
qmd_search "your task description here"
```
QMD returns ranked results with excerpts - read the top 1-3 matches.

**If QMD unavailable**, fall back to manual index:
- Read `docs/index.md`
- Match task keywords to doc keywords in the table
- Identify 1-3 relevant docs

### Step 2: Read Matched Docs

- Use `qmd_get "qmd://collection/path/to/doc.md"` for QMD results
- Or use `Read` tool for manual matches
- Read the 1-3 most relevant docs fully

### Step 3: Apply What You Learned

- Follow documented patterns exactly
- Don't deviate from established conventions
- Reference specific docs in your reasoning

## Anti-Patterns

| Don't Do This | Do This Instead |
|---------------|-----------------|
| Read all docs in index | Use QMD search or read only task-relevant docs |
| Skim docs superficially | Read relevant docs thoroughly |
| Ignore index, guess from memory | Always search first (QMD or index) |
| Read docs once and forget | Re-read when switching tasks |

## Expected docs/index.md Format

Projects without QMD should have a `docs/index.md` with this structure:

```markdown
# Documentation Index

## How to Use This Index

1. Scan the **Keywords** column for terms matching your task
2. Read the **Summary** to confirm relevance
3. Read ONLY the docs that match - don't read everything

## Documentation Map

| Doc | Keywords | Summary |
|-----|----------|---------|
| [architecture.md](architecture.md) | system design, components, data flow | High-level system architecture |
| [api/endpoints.md](api/endpoints.md) | REST, routes, handlers, requests | API endpoint specifications |
| [guides/testing.md](guides/testing.md) | tests, pytest, mocking, fixtures | Testing patterns |

## Quick Reference

- **Adding a feature?** → Read architecture.md first
- **Fixing a bug?** → Check api/errors.md and operations/monitoring.md
```

## Integration with Hooks

This skill complements the hooks:
- **SessionStart**: Reminds to read docs/index.md
- **read-docs-trigger**: When user says "read the docs", suggests QMD search or relevant docs
- **Stop**: Validates work against documented standards

## Example Session

```
User: Read the docs before we add a new payment endpoint

Claude: [Checks qmd_status - QMD available]

qmd_search "payment endpoint API routes authentication"

Results:
1. api/endpoints.md (score: 0.85) - REST API patterns
2. guides/authentication.md (score: 0.72) - Auth middleware
3. architecture.md (score: 0.68) - System overview

[Reads those 3 docs via qmd_get]

Based on the documentation:
- New endpoints go in src/api/routes/
- Must follow RESTful conventions from api/endpoints.md
- Payment endpoints require auth middleware per guides/authentication.md
- Error responses must match format in api/errors.md

Ready to implement the payment endpoint following these patterns.
```

## Context Efficiency

| Approach | Context Cost | Effectiveness |
|----------|--------------|---------------|
| Read all docs | High (10k+ tokens) | Unfocused |
| Read index only | Low (500 tokens) | Incomplete |
| **QMD search + matched docs** | Medium (2-4k tokens) | **Targeted** |

QMD search is preferred because:
- Semantic matching finds conceptually related docs
- No need to read index.md first
- Returns excerpts, reducing token cost
- Works across any project with indexed docs
