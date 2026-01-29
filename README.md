# Claude Code Toolkit

> Autonomous execution that actually completes. Three skills: `/godo` for tasks, `/appfix` for debugging, `/heavy` for analysis.

## Quick Start

```bash
git clone https://github.com/Motium-AI/claude-code-toolkit.git
cd claude-code-toolkit && ./scripts/install.sh
# IMPORTANT: Restart Claude Code after install
claude
```

---

## The Three Skills

### `/godo` — Universal Task Execution

**When**: You have a task and want it done autonomously.

```
> /godo add a logout button to the navbar
```

**What happens**:
1. Explores codebase first (mandatory plan mode)
2. Implements the change
3. Runs linters, fixes ALL errors (including pre-existing)
4. Commits, pushes, deploys
5. Verifies in browser via Surf CLI
6. **Cannot stop until checkpoint passes**

---

### `/appfix` — Autonomous Debugging

**When**: Something is broken and needs fixing.

```
> /appfix
```

Or natural language: "fix the app", "debug production", "why is it broken"

**What happens**:
1. Health check all services
2. Collect logs (Azure Container Apps, browser console, LogFire)
3. Diagnose root cause
4. Apply fix → commit → push → deploy
5. Verify fix works in browser
6. **Loop until all services healthy**

---

### `/heavy` — Multi-Perspective Analysis

**When**: Complex question needing broad perspectives before deciding.

```
> /heavy Should we use microservices or monolith?
```

**What happens**:
1. Spawns 6 parallel Opus agents (3 dynamic + 3 fixed):
   - **3 Dynamic**: Perspectives that will DISAGREE (e.g., Feature Dev vs Platform Engineer vs Finance)
   - **3 Fixed**: Critical Reviewer | Architecture Advisor | Shipping Engineer
2. **All agents self-educate first**: Search codebase, web, and vendor docs (PydanticAI, Logfire, etc.)
3. **Tech stack aware**: Agents know Motium runs Next.js + PydanticAI + Azure Container Apps
4. Synthesizes to surface **structured disagreements** (not vague "tradeoffs")
5. **Adversarial dialogue**: Top disagreement goes to 2-round debate between agents

**Philosophy**: Principles over rubrics. No rigid word counts or scoring. Let models reason freely.

---

## How It Works

### The Stop Hook Philosophy

Claude cannot stop until the job is actually done. A completion checkpoint enforces this:

```json
{
  "self_report": {
    "is_job_complete": true,
    "web_testing_done": true,
    "deployed": true,
    "linters_pass": true
  },
  "reflection": {
    "what_was_done": "Fixed CORS, deployed, verified login works",
    "what_remains": "none"
  }
}
```

If `is_job_complete: false` → Claude is **blocked** and must continue working.

### Hook System (15 registered)

| Hook | Event | Purpose |
|------|-------|---------|
| `auto-update.py` | SessionStart | Auto-updates toolkit from git |
| `session-snapshot.py` | SessionStart | Captures git diff hash |
| `read-docs-reminder.py` | SessionStart | Forces reading docs on start |
| `skill-state-initializer.py` | UserPromptSubmit | Creates state files on `/godo` or `/appfix` |
| `read-docs-trigger.py` | UserPromptSubmit | Suggests reading relevant docs |
| `plan-mode-enforcer.py` | PreToolUse (Edit/Write) | Blocks Edit/Write until plan mode completes |
| `deploy-enforcer.py` | PreToolUse (Bash) | Blocks subagent/production deploys |
| `checkpoint-invalidator.py` | PostToolUse (Edit/Write) | Resets checkpoint when code changes |
| `checkpoint-write-validator.py` | PostToolUse (Write) | Warns on claims without evidence |
| `bash-version-tracker.py` | PostToolUse (Bash) | Tracks version changes after commits |
| `plan-mode-tracker.py` | PostToolUse (ExitPlanMode) | Marks plan mode completed |
| `plan-execution-reminder.py` | PostToolUse (ExitPlanMode) | Injects autonomous execution context |
| `skill-continuation-reminder.py` | PostToolUse (Skill) | Continues loop after skill delegation |
| `appfix-auto-approve.py` | PermissionRequest | Auto-approves ALL tools during autonomous mode |
| `stop-validator.py` | Stop | Validates checkpoint before allowing stop |

**Security**: Auto-approval only activates when `.claude/godo-state.json` or `.claude/appfix-state.json` exists with a valid TTL.

---

## All Commands

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
| `/designimprove` | UI improvement |
| `/uximprove` | UX improvement |
| `/weboptimizer` | Performance benchmarking |

## All Skills (Auto-Triggered)

| Skill | Triggers On |
|-------|-------------|
| `heavy` | Multi-perspective analysis, "debate this" |
| `skill-sandbox` | Skill testing, sandbox test |
| `toolkit` | Toolkit management, "update toolkit" |
| `deploy-pipeline` | Deployment questions, environment promotion |
| `mobileappfix` | Mobile app debugging, Maestro tests |
| `webapp-testing` | Browser testing, Chrome automation |
| `frontend-design` | Web UI development |
| `async-python-patterns` | asyncio, concurrent programming |
| `nextjs-tanstack-stack` | Next.js, TanStack, Zustand |
| `prompt-engineering-patterns` | Prompt optimization |
| `ux-designer` | UX design, user experience |
| `design-improver` | UI review, design audit |
| `ux-improver` | UX review, usability audit |
| `docs-navigator` | Documentation, "read the docs" |

---

## Directory Structure

```
claude-code-toolkit/
├── config/
│   ├── settings.json        # Hook definitions
│   ├── commands/            # Slash commands
│   ├── hooks/               # Python hook scripts
│   └── skills/              # Skill definitions
├── docs/                    # Documentation
├── scripts/
│   ├── install.sh           # Installer
│   └── doctor.sh            # Diagnostics
└── README.md
```

---

## Documentation

| Document | Purpose |
|----------|---------|
| [QUICKSTART.md](QUICKSTART.md) | Installation guide |
| [docs/index.md](docs/index.md) | Full reference |
| [docs/skills/appfix-guide.md](docs/skills/appfix-guide.md) | Complete appfix guide |
| [docs/concepts/hooks.md](docs/concepts/hooks.md) | Hook system deep dive |

---

## License

MIT License - see [LICENSE](LICENSE)
