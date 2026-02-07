# Search Tool Preference

Use Exa MCP tools for all web search:
- `web_search_exa` — general web search
- `get_code_context_exa` — code, GitHub, docs, Stack Overflow
- `company_research_exa` — company/vendor info

Do not use the built-in WebSearch tool. If Exa tools are not visible, discover them with `ToolSearch(query: 'exa')`.

# Documentation Search (QMD)

When QMD MCP is available, prefer semantic search over manual doc reading:

```bash
# Search for relevant docs
qmd_search "authentication flow"

# Get specific document
qmd_get "qmd://collection/path/to/doc.md"

# Check what's indexed
qmd_status
```

QMD is preferred because:
- Semantic matching finds conceptually related docs
- No need to read index.md first
- Token-efficient (returns excerpts, not full files)
- Works across any project with indexed docs

If QMD tools are not visible, fall back to reading `docs/index.md` manually.

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
