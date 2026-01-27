# Claude Code Toolkit Documentation

Central navigation hub for the Claude Code Toolkit documentation.

## Quick Start

- **New to the toolkit?** Start with [QUICKSTART.md](../QUICKSTART.md)
- **Just want to use it?** See [README.md](../README.md)
- **Building custom extensions?** See [Customization Guide](guides/customization.md)

## Core Concepts

| Document | Description |
|----------|-------------|
| [Commands](concepts/commands.md) | How slash commands work |
| [Skills](concepts/skills.md) | How automatic skills work |
| [Hooks](concepts/hooks.md) | How lifecycle hooks work |

## Architecture

| Document | Description |
|----------|-------------|
| [Architecture Overview](architecture.md) | How everything fits together |
| [Philosophy](philosophy.md) | Core design principles |

## Guides

| Document | Description |
|----------|-------------|
| [Customization](guides/customization.md) | Create your own commands, skills, hooks |
| [Appfix Deep Dive](skills/appfix-guide.md) | Comprehensive autonomous debugging guide |
| [Examples](../examples/README.md) | Standalone prompts and templates |

## Reference

| Document | Description |
|----------|-------------|
| [Settings Reference](reference/settings.md) | settings.json configuration options |

## Available Commands (11)

| Command | Purpose |
|---------|---------|
| `/qa` | Exhaustive architecture audit |
| `/deslop` | AI slop detection and removal |
| `/docupdate` | Documentation gap analysis |
| `/webtest` | Browser automation testing |
| `/interview` | Requirements clarification |
| `/weboptimizer` | Performance benchmarking |
| `/config-audit` | Environment variable analysis |
| `/mobiletest` | Maestro E2E test runner |
| `/mobileaudit` | Mobile UI/design audit |
| `/designimprove` | Recursive UI design improvement |
| `/uximprove` | Recursive UX improvement |

## Available Skills (12)

| Skill | Triggers On |
|-------|-------------|
| `godo` | /godo, "go do", "just do it" - task-agnostic autonomous execution |
| `appfix` | "fix the app", autonomous debugging (extends godo) |
| `deploy-pipeline` | /deploy, deployment environments - Motium deployment guide |
| `async-python-patterns` | asyncio, concurrent programming |
| `nextjs-tanstack-stack` | Next.js, TanStack, Zustand |
| `prompt-engineering-patterns` | Prompt optimization |
| `frontend-design` | Web UI development |
| `webapp-testing` | Browser testing |
| `ux-designer` | UX design |
| `design-improver` | UI design review |
| `ux-improver` | UX usability review |
| `docs-navigator` | Documentation navigation |

## Active Hooks (7 Event Types)

| Event | Scripts | Purpose |
|-------|---------|---------|
| SessionStart | auto-update.py, session-snapshot.py, read-docs-reminder.py | Auto-update, git diff snapshot, doc reading |
| UserPromptSubmit | read-docs-trigger.py, skill-state-initializer.py | Doc triggers, state file creation |
| PreToolUse (Edit/Write) | plan-mode-enforcer.py | Blocks edits until plan mode done |
| PostToolUse (Edit/Write) | checkpoint-invalidator.py | Resets stale checkpoint flags |
| PostToolUse (Bash) | bash-version-tracker.py | Tracks version after commits |
| PostToolUse (ExitPlanMode) | plan-execution-reminder.py, plan-mode-tracker.py | Execution context, state update |
| PermissionRequest | appfix-auto-approve.py | Auto-approve all tools during godo/appfix |
| Stop | stop-validator.py | Validates completion checkpoint |

## Testing

```bash
# Hook subprocess tests (fast, no API cost)
cd prompts && python3 -m pytest config/hooks/tests/ -v

# Claude headless E2E tests (real sessions)
cd prompts && bash scripts/test-e2e-headless.sh

# tmux interactive E2E tests
cd prompts && bash scripts/test-e2e-tmux.sh --observe
```

## Directory Structure

```
prompts/
├── README.md              # Overview
├── QUICKSTART.md          # 5-minute setup
├── config/
│   ├── settings.json      # Hook definitions
│   ├── commands/          # 11 command specs
│   ├── hooks/             # 7 active hooks + 5 utilities
│   │   └── tests/         # Pytest hook integration tests
│   └── skills/            # 11 skill directories
├── scripts/
│   ├── install.sh         # Toolkit installer
│   ├── doctor.sh          # Health check
│   ├── test-e2e-headless.sh  # Headless E2E tests
│   └── test-e2e-tmux.sh     # Interactive E2E tests
├── docs/
│   ├── index.md           # You are here
│   ├── architecture.md    # System design
│   ├── philosophy.md      # Core principles
│   ├── concepts/          # Deep dives
│   ├── skills/            # Skill deep-dive guides
│   └── guides/            # How-to guides
└── examples/              # Sample configurations
```
