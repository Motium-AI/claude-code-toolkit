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

## Available Commands (11)

| Command | Purpose |
|---------|---------|
| `/QA` | Exhaustive architecture audit |
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

## Available Skills (9)

| Skill | Triggers On |
|-------|-------------|
| `async-python-patterns` | asyncio, concurrent programming |
| `nextjs-tanstack-stack` | Next.js, TanStack, Zustand |
| `prompt-engineering-patterns` | Prompt optimization |
| `frontend-design` | Web UI development |
| `webapp-testing` | Browser testing |
| `ux-designer` | UX design |
| `design-improver` | UI design review |
| `ux-improver` | UX usability review |
| `docs-navigator` | Documentation navigation |

## Active Hooks (3)

| Hook | Event | Purpose |
|------|-------|---------|
| SessionStart | Session begins | Forces reading of project docs |
| Stop | Before stopping | Compliance checklist |
| UserPromptSubmit | Each prompt | Status file updates |

## Directory Structure

```
prompts/
├── README.md              # Overview
├── QUICKSTART.md          # 5-minute setup
├── config/
│   ├── settings.json      # Hook definitions
│   ├── commands/          # 11 command specs
│   ├── hooks/             # Python hook scripts
│   └── skills/            # 9 skill directories
├── docs/
│   ├── index.md           # You are here
│   ├── architecture.md    # System design
│   ├── philosophy.md      # Core principles
│   ├── concepts/          # Deep dives
│   └── guides/            # How-to guides
└── examples/              # Sample configurations
```
