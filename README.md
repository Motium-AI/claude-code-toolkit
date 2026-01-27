# Claude Code Toolkit

> Autonomous execution that actually completes. Use `/godo` for any task, `/appfix` for debugging.

## The Problem

When you need something done, you don't want an AI that asks "Should I continue?" You want one that:

1. Understands the codebase first (mandatory plan mode)
2. Makes the changes
3. Runs linters and fixes ALL errors
4. Deploys the fix
5. Verifies it works in the browser
6. **Doesn't stop until it's actually done**

That's what `/godo` and `/appfix` do.

## Quick Start

```bash
# Install (with automatic verification)
git clone https://github.com/Motium-AI/claude-code-toolkit.git
cd claude-code-toolkit && ./scripts/install.sh

# IMPORTANT: Restart Claude Code after install!
claude

# Execute any task autonomously
> /godo add a logout button to the navbar

# Or debug a broken app
> /appfix
```

Claude will autonomously plan, execute, deploy, and verify your changes.

### Installation Options

```bash
./scripts/install.sh              # Interactive install + verification
./scripts/install.sh --force      # Skip confirmations
./scripts/install.sh --verify     # Only verify (no install)
./scripts/install.sh --remote     # Install on remote devbox

# Troubleshooting
./scripts/doctor.sh               # Comprehensive diagnostics
```

### Installing via Claude Code

Already using Claude Code? Paste this prompt to have Claude install the toolkit:

> Clone https://github.com/Motium-AI/claude-code-toolkit to ~/claude-code-toolkit and run ./scripts/install.sh to install the Claude Code Toolkit. After installation completes, restart Claude Code.

### Auto-Update

The toolkit automatically updates on session start. Use `/toolkit` to check status or manage updates.

---

## How /appfix Works

### The Fix-Verify Loop

```
┌─────────────────────────────────────────────────────────────────────────┐
│  /appfix                                                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  1. HEALTH CHECK                                                         │
│     └─► Check all services (frontend, backend, workers)                 │
│     └─► Run browser tests via Surf CLI (Chrome MCP as fallback)         │
│                                                                          │
│  2. IF FAILURES DETECTED:                                                │
│     a. COLLECT LOGS                                                      │
│        └─► Browser console, Azure Container logs, LogFire               │
│                                                                          │
│     b. DIAGNOSE                                                          │
│        └─► Root cause analysis, create fix plan                         │
│                                                                          │
│     c. FIX                                                               │
│        └─► Apply code changes                                           │
│        └─► git commit && git push                                       │
│        └─► gh workflow run && gh run watch --exit-status                │
│                                                                          │
│     d. VERIFY                                                            │
│        └─► Test in browser (Surf CLI first, Chrome MCP fallback)        │
│        └─► Check console is clean                                       │
│                                                                          │
│  3. LOOP until all services healthy + verified in browser               │
│                                                                          │
│  4. TRY TO STOP → Stop hook validates completion checkpoint             │
│     └─► is_job_complete: false? → BLOCKED, continue working            │
│     └─► web_testing_done: false? → BLOCKED, continue working           │
│     └─► All checks pass? → Done                                         │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Truly Autonomous Execution

The key innovation: **Claude cannot stop until the job is actually done.**

The stop hook checks a completion checkpoint with boolean self-reports:

```json
{
  "self_report": {
    "is_job_complete": true,
    "web_testing_done": true,
    "deployed": true,
    "console_errors_checked": true
  },
  "reflection": {
    "what_was_done": "Fixed CORS config, deployed, verified login works",
    "what_remains": "none"
  }
}
```

If `is_job_complete: false`, Claude is blocked and must continue working. No escape hatch. No rationalization. Just honest boolean answers.

### The Hook System

Four hooks work together to enable autonomous execution:

| Hook | Purpose |
|------|---------|
| `appfix-auto-approve.py` | Auto-approves ALL tools during godo/appfix mode |
| `plan-execution-reminder.py` | Injects autonomous execution context |
| `stop-validator.py` | Validates completion checkpoint before stopping |
| `checkpoint-invalidator.py` | Resets stale checkpoint flags when code changes |

**Security model**: Auto-approval only activates when `.claude/godo-state.json` or `.claude/appfix-state.json` exists. Normal sessions require user approval.

---

## Setup

### 1. Install the Toolkit

```bash
git clone https://github.com/Motium-AI/claude-code-toolkit.git
cd claude-code-toolkit
./scripts/install.sh
```

### 2. Configure Your Project

Create a service topology file so Claude knows what to check:

```bash
mkdir -p .claude/skills/appfix/references
cat > .claude/skills/appfix/references/service-topology.md << 'EOF'
# Service Topology

| Service | URL | Health Endpoint |
|---------|-----|-----------------|
| Frontend | https://staging.example.com | /api/health |
| Backend | https://api-staging.example.com | /health |

## Deployment Commands

```bash
# Frontend
gh workflow run frontend-ci.yml -f environment=staging

# Backend
gh workflow run backend-ci.yml -f environment=staging
```
EOF
```

### 3. Run It

```bash
claude
> /appfix
```

Or trigger with natural language:
- "fix the app"
- "debug production"
- "why is it broken"

---

## Example Session

```
User: /appfix

[PHASE 0] Pre-Flight
  ✓ service-topology.md exists
  ✓ Created appfix-state.json (enables auto-approval)

[PHASE 0.5] Codebase Context
  → EnterPlanMode (auto-approved)
  → Explored: Next.js + FastAPI, recent auth changes
  → ExitPlanMode

[PHASE 1] Health Check
  ✗ Frontend: 500 on /api/health
  ✓ Backend: healthy
  ✗ Browser: login form fails

[PHASE 2] Log Collection
  - Azure: TypeError in auth middleware
  - Console: "Cannot read property 'user' of undefined"

[PHASE 3] Execute Fix
  - Edit: auth.py - add null check
  - Commit: "appfix: Add null check in auth middleware"
  - Deploy: gh workflow run + gh run watch (auto-approved)

[PHASE 4] Verification
  - Surf CLI: python3 ~/.claude/hooks/surf-verify.py --urls "..."
  - Screenshot: data displays correctly
  - Console: clean (no errors)

[UPDATE CHECKPOINT]
  - is_job_complete: true
  - web_testing_done: true
  - deployed: true
  - what_remains: "none"

[TRY TO STOP]
  → Stop hook validates checkpoint
  → All checks pass

[SUCCESS] APPFIX COMPLETE
```

---

## Other Commands & Skills

While `/appfix` is the flagship, the toolkit includes additional capabilities:

### Commands

| Command | Purpose |
|---------|---------|
| `/qa` | Exhaustive architecture audit |
| `/deslop` | Detect and remove AI-generated code slop |
| `/docupdate` | Documentation gap analysis |
| `/webtest` | Web testing via Surf CLI (autonomous) or Chrome MCP (interactive) |
| `/interview` | Clarify requirements via Q&A |
| `/designimprove` | Recursively improve UI via screenshot grading |
| `/uximprove` | Recursively improve UX via usability analysis |

### Skills

| Skill | Triggers On |
|-------|-------------|
| `webapp-testing` | Browser testing, Chrome automation |
| `frontend-design` | Web UI development |
| `async-python-patterns` | asyncio, concurrent programming |
| `nextjs-tanstack-stack` | Next.js App Router, TanStack |

---

## How It Works Under the Hood

### Extension Mechanisms

Claude Code supports three extension types:

| Type | Trigger | Purpose |
|------|---------|---------|
| **Commands** | `/command-name` | Structured workflows |
| **Skills** | Automatic keyword match | Domain expertise |
| **Hooks** | Lifecycle events | Inject context, enforce behavior |

### Hook Events (12 Active)

| Event | Scripts | Purpose |
|-------|---------|---------|
| SessionStart | session-snapshot.py, read-docs-reminder.py | Git state capture, doc reminders |
| UserPromptSubmit | read-docs-trigger.py, skill-state-initializer.py | Doc triggers, state file creation |
| PreToolUse (Edit/Write) | plan-mode-enforcer.py | Block edits until plan mode done |
| PostToolUse (Edit/Write) | checkpoint-invalidator.py, checkpoint-write-validator.py | Reset stale flags, validate writes |
| PostToolUse (Bash) | bash-version-tracker.py | Track version after commits |
| PostToolUse (ExitPlanMode) | plan-execution-reminder.py, plan-mode-tracker.py | Inject context, update state |
| PermissionRequest | appfix-auto-approve.py | Auto-approve during godo/appfix |
| Stop | stop-validator.py | Validate completion checkpoint |

See [config/hooks/README.md](config/hooks/README.md) for complete hook documentation.

### The Completion Checkpoint Philosophy

Why boolean checkpoints work:

1. **Forces honesty** - You must choose true/false, no hedging
2. **Self-enforcing** - If you say false, you're blocked
3. **Deterministic** - No regex heuristics, just boolean checks
4. **Trusts the model** - Models don't want to lie when asked directly

The stop hook doesn't try to catch lies. It asks direct questions:
- "Did you test this in the browser?" → Answer honestly
- "Is the job actually complete?" → Answer honestly

If you answer `false`, you're blocked. If you answer `true` honestly, you're done.

---

## Directory Structure

```
claude-code-toolkit/
├── config/
│   ├── settings.json              # Hook definitions
│   ├── commands/                  # Slash commands
│   ├── hooks/                     # Python hook scripts
│   │   ├── _common.py                   # Shared utilities (state detection)
│   │   ├── appfix-auto-approve.py       # Auto-approves ALL tools during godo/appfix
│   │   ├── plan-mode-enforcer.py        # Blocks Edit/Write until plan mode done
│   │   ├── checkpoint-invalidator.py    # Resets stale checkpoint flags
│   │   ├── stop-validator.py            # Validates completion checkpoint
│   │   └── ...
│   └── skills/
│       ├── appfix/
│       │   ├── SKILL.md           # Main skill definition
│       │   └── references/        # Service topology, patterns
│       └── godo/
│           └── SKILL.md           # Universal task execution
├── docs/
│   ├── skills/appfix-guide.md     # Complete appfix guide
│   └── concepts/hooks.md          # Hook system deep dive
└── scripts/
    ├── install.sh                 # Installer with verification
    └── doctor.sh                  # Diagnostic tool
```

---

## Documentation

| Document | Description |
|----------|-------------|
| [docs/skills/appfix-guide.md](docs/skills/appfix-guide.md) | Complete /appfix guide |
| [docs/concepts/hooks.md](docs/concepts/hooks.md) | Hook system deep dive |
| [QUICKSTART.md](QUICKSTART.md) | 5-minute setup guide |

---

## Philosophy

Six principles from [CLAUDE_AGENTS](docs/philosophy.md):

1. **Clarity Over Cleverness** — Explicit, obvious code
2. **Locality Over Abstraction** — Self-contained modules
3. **Compose Small Units** — Single-purpose, rewritable pieces
4. **Stateless by Default** — Pure functions, effects at boundaries
5. **Fail Fast & Loud** — Surface errors, no silent catches
6. **Tests as Specification** — Tests define correct behavior

---

## License

MIT License - see [LICENSE](LICENSE) for details.
