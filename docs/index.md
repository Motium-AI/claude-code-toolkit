# Claude Code Toolkit Reference

## Quick Links

- [README](../README.md) — Overview and quick start
- [Installation](../QUICKSTART.md) — Setup guide
- [Customization](guides/customization.md) — Create your own extensions

---

## The Three Core Skills

### `/godo` — Universal Task Execution
**Use when**: You have a task and want autonomous execution.
```
/godo add a logout button to the navbar
```
Explores codebase → implements → lints → commits → deploys → verifies in browser → **cannot stop until done**.

### `/appfix` — Autonomous Debugging
**Use when**: Something is broken.
```
/appfix
```
Health checks → collects logs → diagnoses → fixes → deploys → **loops until healthy**.

### `/heavy` — Multi-Perspective Analysis
**Use when**: Complex question needing broad perspectives.
```
/heavy Should we use microservices or monolith?
```
6 parallel Opus agents (3 dynamic + 3 fixed: Critical Reviewer, Architecture Advisor, Shipping Engineer) → **self-educate via codebase + web + vendor docs** → tech-stack aware (Next.js, PydanticAI, Azure) → structured disagreements → adversarial dialogue → principles over rubrics.

---

## All Commands (14)

| Command | Purpose |
|---------|---------|
| `/godo` | Autonomous task execution |
| `/appfix` | Autonomous debugging |
| `/heavy` | Multi-agent analysis |
| `/qa` | Architecture audit |
| `/deslop` | AI slop detection |
| `/docupdate` | Documentation gaps |
| `/config-audit` | Environment variable analysis |
| `/webtest` | Browser testing |
| `/mobiletest` | Maestro E2E tests |
| `/mobileaudit` | Vision-based UI audit |
| `/interview` | Requirements Q&A |
| `/weboptimizer` | Performance benchmarking |
| `/designimprove` | UI improvement |
| `/uximprove` | UX improvement |

## All Skills (16 active, 2 deprecated)

| Skill | Triggers |
|-------|----------|
| `godo` | /godo, "go do", "just do it" |
| `appfix` | /appfix, "fix the app", "debug production" |
| `heavy` | /heavy, "heavy analysis", "multiple perspectives" |
| `mobileappfix` | Mobile app debugging, Maestro tests |
| `skill-sandbox` | /skill-sandbox, "test skill", "sandbox test" |
| `toolkit` | /toolkit, "update toolkit" |
| `deploy-pipeline` | /deploy, deployment questions |
| `webapp-testing` | Browser testing |
| `frontend-design` | Web UI development |
| `async-python-patterns` | asyncio, concurrent |
| `nextjs-tanstack-stack` | Next.js, TanStack |
| `prompt-engineering-patterns` | Prompt optimization |
| `ux-designer` | UX design |
| `design-improver` | UI review |
| `ux-improver` | UX review |
| `docs-navigator` | Documentation |

### Deprecated Skills

| Skill | Status | Redirect |
|-------|--------|----------|
| `skill-tester` | Deprecated | → skill-sandbox |
| `skilltest` | Deprecated | → skill-sandbox |

## Hook Events (10)

| Event | Scripts | Purpose |
|-------|---------|---------|
| SessionStart | auto-update, session-snapshot, read-docs-reminder | Init and toolkit update |
| UserPromptSubmit | skill-state-initializer, read-docs-trigger | State files and doc suggestions |
| PreToolUse (Edit/Write) | plan-mode-enforcer | Block until plan done |
| PreToolUse (Bash) | deploy-enforcer | Block subagent/production deploys |
| PostToolUse (Edit/Write) | checkpoint-invalidator | Reset stale flags |
| PostToolUse (Write) | checkpoint-write-validator | Warn on claims without evidence |
| PostToolUse (Bash) | bash-version-tracker | Track version changes |
| PostToolUse (ExitPlanMode) | plan-mode-tracker, plan-execution-reminder | Mark plan done, inject context |
| PostToolUse (Skill) | skill-continuation-reminder | Continue loop after skill |
| PermissionRequest | appfix-auto-approve | Auto-approve all tools |
| Stop | stop-validator | Validate checkpoint |

---

## Deep Dives

| Document | Description |
|----------|-------------|
| [Commands](concepts/commands.md) | How slash commands work |
| [Skills](concepts/skills.md) | How skills auto-trigger |
| [Hooks](concepts/hooks.md) | Hook lifecycle |
| [Architecture](architecture.md) | System design |
| [Appfix Guide](skills/appfix-guide.md) | Complete debugging guide |

## Directory Structure

```
prompts/
├── config/
│   ├── settings.json      # Hook definitions
│   ├── commands/          # 11 command files (+ 3 skill-commands)
│   ├── hooks/             # Python hooks (15 registered)
│   └── skills/            # 16 skills (+ 2 deprecated)
├── docs/                  # Documentation
├── scripts/               # install.sh, doctor.sh
└── README.md
```
