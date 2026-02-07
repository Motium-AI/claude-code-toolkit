# Search Tool Preference

Use Exa MCP tools for all web search:
- `web_search_exa` — general web search
- `get_code_context_exa` — code, GitHub, docs, Stack Overflow
- `company_research_exa` — company/vendor info

Do not use the built-in WebSearch tool. If Exa tools are not visible, discover them with `ToolSearch(query: 'exa')`.

# Documentation Search (QMD) — Always Use First

**QMD is the primary way to find documentation.** Do NOT manually read `docs/index.md`, `TECHNICAL_OVERVIEW.md`, or subdirectory CLAUDE.md files for doc lookup — use QMD search instead.

```bash
# Search for docs relevant to your task
qmd_search "authentication flow"

# Get a specific document by path
qmd_get "motium/cortex/docs/architecture/authentication.md"
```

**Why QMD over manual reads:**
- Searches across all indexed documentation in one query
- No need to read index.md first — search finds the right doc directly
- Token-efficient — returns excerpts, not full files
- `.gitignore` respected — no node_modules pollution

**Only use Read tool for:** `CLAUDE.md` (root) and `.claude/MEMORIES.md` at session start.
For everything else, search first with QMD.

If QMD tools are not available, fall back to reading `docs/index.md` manually.

# Skill Routing

You do not need explicit `/command` invocation. Auto-select based on task signals:

| Signal | Skill | Rationale |
|--------|-------|-----------|
| "fix", "broken", "debug", error context | /repair | Debugging router (auto-detects web vs mobile) |
| "build", "implement", complex task | /melt | Autonomous execution with verification |
| "clean up", "tech debt", "slop" | /burndown | Debt elimination |
| "improve design/UX/perf" | /improve | Recursive improvement loop |
| "analyze", "think deeply", "evaluate" | /heavy | Multi-perspective analysis |
| No clear task / research only | No skill | Just answer directly |

## Skill Fluidity

Skills are capabilities, not cages. If the task evolves, adapt:

- Building (/melt) and discover a critical bug? Fix it inline using /repair techniques. No formal mode switch needed.
- Debugging (/repair) and find the root cause is tech debt? Apply /burndown patterns to the area.
- Any task turns out to be architecturally complex? Use /heavy analysis for the sub-problem, then continue.

The `autonomous-state.json` mode field drives auto-approval and checkpoint enforcement. It does not constrain your cognitive approach. Use the best technique for each sub-problem regardless of which skill activated the session.

When to formally re-invoke a skill (via Skill tool):
- The ENTIRE task has shifted (not just a sub-problem)
- You need the full activation ceremony of another skill

When to just adapt inline:
- A sub-problem needs a different approach
- You discovered something that changes the next step but not the overall goal
