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

## Available Skills (10)

| Skill | Triggers On |
|-------|-------------|
| `appfix` | "fix the app", autonomous debugging |
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
| SessionStart | session-snapshot.py, read-docs-reminder.py | Git diff snapshot, doc reading |
| Stop | stop-validator.py | Validates completion checkpoint |
| PostToolUse (Edit/Write) | checkpoint-invalidator.py | Resets stale checkpoint flags |
| UserPromptSubmit | read-docs-trigger.py, skill-reminder.py | Doc reading triggers, skill suggestions |
| PostToolUse (ExitPlanMode) | plan-execution-reminder.py, appfix-auto-approve.py | Execution context injection |
| PermissionRequest (Bash) | appfix-bash-auto-approve.py | Auto-approve Bash commands (appfix) |
| PermissionRequest (ExitPlanMode) | appfix-exitplan-auto-approve.py | Auto-approve plan transitions (appfix) |

## Directory Structure

```
prompts/
├── README.md              # Overview
├── QUICKSTART.md          # 5-minute setup
├── config/
│   ├── settings.json      # Hook definitions
│   ├── commands/          # 11 command specs
│   ├── hooks/             # 10 Python hook scripts
│   └── skills/            # 10 skill directories
├── docs/
│   ├── index.md           # You are here
│   ├── architecture.md    # System design
│   ├── philosophy.md      # Core principles
│   ├── concepts/          # Deep dives
│   └── guides/            # How-to guides
└── examples/              # Sample configurations
```
