# Claude Code Toolkit

> Production-ready commands, skills, and hooks to supercharge your Claude Code workflow.

Claude Code supports three extension mechanisms that let you customize how Claude works with your codebase:

| Mechanism | Trigger | Purpose |
|-----------|---------|---------|
| **Commands** | `/command-name` | Slash-invoked structured workflows |
| **Skills** | Automatic (keyword match) | Domain expertise Claude draws on |
| **Hooks** | Lifecycle events | Inject context, enforce behavior |

This toolkit provides a battle-tested collection of all three, built around the philosophy of **"boring over clever"** — explicit, maintainable, effective.

## Quick Start

```bash
# Clone
git clone https://github.com/Motium-AI/claude-code-toolkit.git
cd claude-code-toolkit

# Install (backs up existing config, creates symlinks)
./scripts/install.sh

# Verify - start Claude Code
claude
# You should see: "SessionStart:startup hook success: MANDATORY..."

# Try a command
/QA   # Runs exhaustive codebase audit
```

For detailed setup instructions, see [QUICKSTART.md](QUICKSTART.md).

## What's Included

### Commands (11)

Slash commands for structured workflows. Run `/command-name` to invoke.

| Command | Purpose |
|---------|---------|
| `/QA` | Exhaustive architecture, scalability, and maintainability audit |
| `/deslop` | Detect and remove 25 patterns of AI-generated code slop |
| `/docupdate` | Documentation gap analysis and staleness detection |
| `/webtest` | Browser automation testing via Chrome integration |
| `/interview` | Clarify requirements before implementation via Q&A |
| `/weboptimizer` | Performance benchmarking for Next.js + FastAPI apps |
| `/config-audit` | Environment variable analysis and fallback pattern detection |
| `/mobiletest` | Run Maestro E2E tests with failure diagnosis and fix suggestions |
| `/mobileaudit` | Vision-based UI/design audit via Maestro screenshots |
| `/designimprove` | Recursively improve web UI via screenshot grading and targeted fixes |
| `/uximprove` | Recursively improve UX via usability analysis and targeted fixes |

### Skills (9)

Domain expertise Claude automatically applies when relevant keywords appear in your prompts.

| Skill | Triggers On |
|-------|-------------|
| `async-python-patterns` | asyncio, concurrent programming, async/await |
| `nextjs-tanstack-stack` | Next.js App Router, TanStack Table/Query/Form, Zustand |
| `prompt-engineering-patterns` | Prompt optimization, few-shot learning, chain-of-thought |
| `frontend-design` | Web UI development, distinctive design |
| `webapp-testing` | Browser testing, Chrome automation, Playwright |
| `ux-designer` | UX flows, wireframes, WCAG accessibility |
| `design-improver` | UI design review, screenshot grading, design audit |
| `ux-improver` | UX usability review, user flows, affordances, feedback states |
| `docs-navigator` | Read the docs, check documentation, unfamiliar codebase |

### Hooks (3)

Lifecycle handlers that run automatically at key moments.

| Hook | Event | Purpose |
|------|-------|---------|
| SessionStart | Session begins | Forces Claude to read project docs before starting |
| Stop | Before stopping | Compliance checklist: code standards, docs, commit |
| UserPromptSubmit | Each prompt | Updates status file, triggers doc reading |

> **Note:** Additional hooks (`skill-reminder.py`, `finalize-status-v5.py`) exist in `config/hooks/` but are not enabled by default. See [docs/concepts/hooks.md](docs/concepts/hooks.md) for configuration.

## How It Works

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Claude Code Session                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  1. SESSION START                                                        │
│     └─→ SessionStart hook fires                                          │
│         └─→ Forces Claude to read docs/index.md, CLAUDE.md, MEMORIES.md, │
│             TECHNICAL_OVERVIEW.md                                        │
│                                                                          │
│  2. USER SENDS PROMPT                                                    │
│     └─→ UserPromptSubmit hook fires                                      │
│         └─→ status-working.py updates session status file                │
│         └─→ read-docs-trigger.py suggests reading relevant docs          │
│                                                                          │
│  3. USER RUNS /COMMAND                                                   │
│     └─→ Command markdown loaded                                          │
│         └─→ Structured workflow executes (plan mode, parallel agents)    │
│             └─→ Formatted output generated                               │
│                                                                          │
│  4. CLAUDE TRIES TO STOP                                                 │
│     └─→ Stop hook fires                                                  │
│         └─→ stop-validator.py checks git diff for change types           │
│             └─→ Shows: "⚠️ AUTH CHANGES DETECTED: test 401 cascade..."  │
│                 └─→ Blocks until compliance confirmed                    │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Documentation

| Document | Description |
|----------|-------------|
| [QUICKSTART.md](QUICKSTART.md) | 5-minute setup guide |
| [docs/concepts/commands.md](docs/concepts/commands.md) | Deep dive into commands |
| [docs/concepts/skills.md](docs/concepts/skills.md) | Deep dive into skills |
| [docs/concepts/hooks.md](docs/concepts/hooks.md) | Deep dive into hooks |
| [docs/architecture.md](docs/architecture.md) | How everything fits together |
| [docs/guides/customization.md](docs/guides/customization.md) | Create your own commands, skills, hooks |

## Directory Structure

```
claude-code-toolkit/
├── config/                     # The actual config files
│   ├── settings.json           # Global settings + hook definitions
│   ├── commands/               # 11 slash commands
│   │   ├── QA.md
│   │   ├── deslop.md
│   │   └── ...
│   ├── hooks/                  # 5 Python hook scripts (3 enabled by default)
│   │   ├── stop-validator.py         # Enabled: Stop compliance checks
│   │   ├── status-working.py         # Enabled: Status file updates
│   │   ├── read-docs-trigger.py      # Enabled: Doc reading suggestions
│   │   ├── skill-reminder.py         # Disabled: Skill keyword matching
│   │   └── finalize-status-v5.py     # Disabled: AI status analysis
│   └── skills/                 # 9 skill directories
│       ├── async-python-patterns/
│       ├── nextjs-tanstack-stack/
│       └── ...
├── docs/                       # Documentation
│   ├── concepts/               # What are commands, skills, hooks
│   ├── guides/                 # How-to guides
│   └── architecture.md         # System overview
├── examples/                   # Example configurations
│   ├── minimal-setup/          # Just the essentials
│   └── standalone-prompts/     # Individual audit prompts
└── scripts/
    └── install.sh              # One-line installer
```

## Philosophy

This toolkit embodies six principles from [CLAUDE_AGENTS](docs/philosophy.md):

1. **Clarity Over Cleverness** — Explicit, obvious code. Optimize for human review.
2. **Locality Over Abstraction** — Self-contained modules. Duplication is acceptable.
3. **Compose Small Units** — Single-purpose, safely rewritable pieces.
4. **Stateless by Default** — Pure functions. Side effects at boundaries.
5. **Fail Fast & Loud** — Surface errors. No silent catches.
6. **Tests as Specification** — Tests define correct behavior. Code is disposable.

## Customization

### Create a Custom Command

```bash
# Create command file
cat > ~/.claude/commands/my-audit.md << 'EOF'
---
description: Run my custom audit
---

Analyze the codebase for [specific concern]. Output findings as:

1. **Critical** - Must fix immediately
2. **Warning** - Should fix soon
3. **Info** - Consider improving
EOF

# Use it
claude
> /my-audit
```

### Create a Custom Skill

```bash
mkdir -p ~/.claude/skills/my-domain
cat > ~/.claude/skills/my-domain/SKILL.md << 'EOF'
---
name: my-domain
description: Expertise in [your domain]. Use when building [trigger keywords].
---

## Core Patterns

[Your domain knowledge here]
EOF
```

See [docs/guides/customization.md](docs/guides/customization.md) for complete guides.

## Contributing

PRs welcome! Please follow existing patterns:

- **Commands**: Markdown with YAML frontmatter, structured output format
- **Skills**: Directory with `SKILL.md` + optional `references/`, `examples/`
- **Hooks**: Python with JSON stdin, exit codes 0 (allow) or 2 (block)

## License

MIT License - see [LICENSE](LICENSE) for details.
