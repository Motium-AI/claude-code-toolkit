# Melt

**Claude cannot stop until the job is done. You get verified code.**

Natural language in, verified deployed code out. The stop hook blocks completion until every checkpoint boolean passes — Claude cannot stop until the job is actually done.

Built for **Opus 4.6** and **Claude Code v2.1+** with native Agent Teams support.

## Invoke It (60 seconds)

```bash
git clone https://github.com/Motium-AI/claude-code-toolkit.git
cd claude-code-toolkit && ./scripts/install.sh
# Restart Claude Code, then:
```

```
> /melt add a logout button to the navbar
```

Watch what happens:
1. Plans the approach (Agent Teams for complex tasks — First Principles + AGI-Pilled + dynamic experts)
2. Implements the plan with parallel agent swarms
3. Runs linters, fixes all errors
4. Commits and pushes
5. Opens browser, verifies the button works
6. **Only then can it stop**

If step 5 fails, it loops back. You get working code, not promises.

## Four Core Skills

**`/melt`** — Autonomous execution with Agent Teams planning. Give it a task, get verified deployed code. Spawns parallel agents for complex work. (Aliases: `/build`, `/forge`)

**`/repair`** — Debugging loop. Auto-detects web vs mobile, collects logs, fixes, deploys, verifies. Loops until healthy.

**`/heavy`** — Multi-perspective analysis. 3-5 parallel Opus agents (First Principles + AGI-Pilled always, Critical Reviewer + dynamic agents as needed), structured disagreements, adversarial dialogue.

**`/burndown`** — Tech debt elimination. Detection agents scan for slop and architecture issues, prioritize by severity, fix iteratively until clean.

## Agent Teams (Swarm Mode)

Complex tasks benefit from **parallel agent swarms**. The toolkit uses Claude Code's experimental Agent Teams feature to spawn specialized agents that work simultaneously:

- **`/melt`** spawns planning agents (First Principles + AGI-Pilled + domain experts) then implementation agents for parallel work items
- **`/heavy`** spawns 3-5 analysis agents for multi-perspective debate
- **`/burndown`** spawns detection agents to scan different aspects of the codebase concurrently

### Enabling Agent Teams

Add this to your **global** `~/.claude/settings.json` (or the toolkit's `config/settings.json`):

```json
{
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  }
}
```

The install script sets this automatically. Without it, skills fall back to sequential `Task()` calls — still functional, but without the shared task list and team coordination that Agent Teams provides.

**Requirements**: Claude Code v2.1.32+ with Opus 4.6. Agent Teams is an experimental feature enabled via environment variable, not a CLI flag.

## Complementary Memory System

The toolkit runs two memory systems in parallel — Claude Code's native MEMORY.md for always-relevant project orientation, and a custom compound memory system for task-specific retrieval:

| Layer | What it does | When it loads |
|-------|-------------|---------------|
| **Native MEMORY.md** | Project structure, conventions, build commands | Every session (Claude Code built-in) |
| **Compound Memory** | Solved problems, key insights, entity-gated retrieval | Every session (SessionStart hook) |
| **Core Assertions** | Hard-won invariants (e.g., "use git rm, not rm") | Every session (before memories) |

The context loader automatically detects native MEMORY.md and reduces compound memory's budget from 8K to 4.5K chars to avoid context bloat. A dedup guard prevents injecting events already documented in MEMORY.md.

High-utility compound memories (frequently cited) can be promoted to MEMORY.md:

```bash
python3 config/scripts/promote-to-memory-md.py --dry-run  # Preview candidates
python3 config/scripts/promote-to-memory-md.py             # Promote top 3
```

## The Stop Hook

When Claude tries to stop, the hook checks a deterministic boolean checkpoint:

```
is_job_complete: true?
linters_pass: true?
what_remains: "none"?
key_insight: >50 chars?
```

All must pass. If not, Claude is blocked and must continue working. On success, the key insight is auto-captured as a compound memory event for future sessions.

## Skill Fluidity

Skills are capabilities, not cages. If the task evolves, adapt inline — use /repair techniques while in /melt, apply /burndown patterns mid-debug. No formal mode switch needed. Opus 4.6 is capable enough that skills work as natural encouragement rather than rigid guardrails.

## What This Is Not

- A replacement for your architectural judgment
- A guarantee of zero bugs (it verifies, but edge cases exist)
- Magic — it reads your files, runs your linters, and tests in your browser

## The Name

The toolkit is built on the Namshub philosophy: In Neal Stephenson's *Snow Crash*, a nam-shub is code that, once invoked, must execute to completion.

"Melt" is what happens to resistance. Give it a task, and parallel Opus agents attack it from every angle until it's solved — linting, deploying, verifying in real browsers. The stop hook blocks completion until every boolean checkpoint passes. The task melts away. You get verified code.

## Documentation

Full reference, hook system, and skill guides: [docs/index.md](docs/index.md)

## License

MIT — see [LICENSE](LICENSE)
