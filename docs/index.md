# Namshub Reference

## Quick Links

- [README](../README.md) — Overview and quick start
- [Installation](../QUICKSTART.md) — Setup guide
- [Customization](guides/customization.md) — Create your own extensions

---

## The Five Core Skills

### `/go` — Fast Autonomous Execution
**Use when**: Quick task, you know exactly what to do.
```
/go fix the typo in README.md
```
**No planning phase** → ReAct-style direct execution → lints → commits → **8-10x faster than /build**.

### `/build` — Universal Task Execution
**Use when**: Complex task that benefits from multi-agent planning.
```
/build add a logout button to the navbar
```
**Lite Heavy planning** (4 parallel Opus agents: First Principles + AGI-Pilled + 2 dynamic perspectives) → implements → lints → commits → deploys → verifies in browser → **cannot stop until done**.

### `/repair` — Unified Debugging Router
**Use when**: Something is broken (auto-detects web vs mobile).
```
/repair
```
Detects platform → routes to `/appfix` (web) or `/mobileappfix` (mobile) → **loops until healthy**.

### `/burndown` — Tech Debt Elimination
**Use when**: Codebase has accumulated slop or architecture issues.
```
/burndown src/components/
```
Consolidates `/deslop` + `/qa` into autonomous fix loop → 3 detection agents scan for issues → prioritizes by severity → **fixes iteratively** → re-scans to verify → **cannot stop until critical issues fixed**.

### `/heavy` — Multi-Perspective Analysis
**Use when**: Complex question needing broad perspectives.
```
/heavy Should we use microservices or monolith?
```
5 parallel Opus agents (2 required: **First Principles** + **AGI-Pilled**, 1 fixed: **Critical Reviewer**, 2 dynamic) → **self-educate via codebase + web + vendor docs** → tech-stack aware (Next.js, PydanticAI, Azure) → structured disagreements → adversarial dialogue → intelligence-first, never cost-first → bounded extension (max 3 rounds).

---

## All Slash Commands (15 commands + 5 core skills)

| Command | Purpose |
|---------|---------|
| `/go` | Fast autonomous execution (no planning, 8-10x faster) |
| `/build` | Autonomous task execution (with Lite Heavy planning) |
| `/repair` | Unified debugging router (web → appfix, mobile → mobileappfix) |
| `/burndown` | Autonomous tech debt elimination (combines /deslop + /qa) |
| `/heavy` | Multi-agent analysis |
| `/audiobook` | Transform documents into TTS-optimized audiobooks |
| `/harness-test` | Test harness changes (hooks/skills) in sandbox |
| `/appfix` | Web app debugging |
| `/qa` | Architecture audit (detection only - use /burndown to fix) |
| `/deslop` | AI slop detection (detection only - use /burndown to fix) |
| `/docupdate` | Documentation gaps |
| `/config-audit` | Environment variable analysis |
| `/webtest` | Browser testing |
| `/mobiletest` | Maestro E2E tests |
| `/mobileaudit` | Vision-based UI audit |
| `/interview` | Requirements Q&A |
| `/weboptimizer` | Performance benchmarking |
| `/designimprove` | UI improvement |
| `/uximprove` | UX improvement |
| `/compound` | Capture solved problems as memory events for cross-session learning |

## All Skills (25 total)

| Skill | Triggers |
|-------|----------|
| `go` | /go, "just go", "go fast", "quick fix", "quick build" |
| `build` | /build, /godo (legacy), "go do", "just do it", "execute this" |
| `repair` | /repair, /appfix, /mobileappfix, "fix the app", "debug production" |
| `burndown` | /burndown, "burn down debt", "clean up codebase", "fix the slop" |
| `appfix` | (Internal: web debugging - prefer /repair) |
| `heavy` | /heavy, "heavy analysis", "multiple perspectives", "debate this" |
| `compound` | /compound, "document this solution", "capture this learning", "remember this fix" |
| `episode` | /episode, "generate an episode", "create educational video", "produce an episode" |
| `essay` | /essay, "write an essay", "essay about" |
| `audiobook` | /audiobook, "create an audiobook", "turn this into audio", "make TTS-ready" |
| `mobileappfix` | (Internal: mobile debugging - prefer /repair) |
| `skill-sandbox` | /skill-sandbox, "test skill", "sandbox test" |
| `harness-test` | /harness-test, "test harness changes" (auto-triggers in /build for toolkit) |
| `toolkit` | /toolkit, "update toolkit" |
| `deploy-pipeline` | /deploy, deployment questions |
| `webapp-testing` | Browser testing |
| `frontend-design` | Web UI development |
| `async-python-patterns` | asyncio, concurrent |
| `nextjs-tanstack-stack` | Next.js, TanStack |
| `prompt-engineering-patterns` | Context engineering for prompts, skills, and CLAUDE.md |
| `ux-designer` | UX design |
| `design-improver` | UI review |
| `ux-improver` | UX review |
| `docs-navigator` | Documentation |
| `revonc-eas-deploy` | /eas, /revonc-deploy, "deploy to testflight", "build ios/android" |

## Registered Hooks (22 scripts)

| Event | Scripts | Purpose |
|-------|---------|---------|
| SessionStart | auto-update, session-snapshot, compound-context-loader, read-docs-reminder | Init, memory injection, toolkit update |
| UserPromptSubmit | skill-state-initializer, read-docs-trigger | State files and doc suggestions |
| PreToolUse (*) | pretooluse-auto-approve | Auto-approve during autonomous mode |
| PreToolUse (Edit/Write) | plan-mode-enforcer | Block until plan done + /go Read-gate |
| PreToolUse (Bash) | deploy-enforcer, azure-command-guard | Block deploys, guard Azure CLI |
| PreToolUse (WebSearch) | exa-search-enforcer | Remind to use Exa MCP instead |
| PreToolUse (ExitPlanMode) | lite-heavy-enforcer | Block until Lite Heavy done |
| PostToolUse (Edit/Write) | checkpoint-invalidator | Reset stale flags |
| PostToolUse (Read/Grep/Glob) | lite-heavy-tracker, go-context-tracker | Track Lite Heavy + /go Read-gate |
| PostToolUse (Task) | lite-heavy-tracker | Track Lite Heavy progress |
| PostToolUse (Bash) | bash-version-tracker, doc-updater-async | Track versions, suggest doc updates |
| PostToolUse (ExitPlanMode) | plan-mode-tracker, plan-execution-reminder | Mark plan done, inject context |
| PostToolUse (Skill) | skill-continuation-reminder | Continue loop after skill |
| Stop | stop-validator | Validate checkpoint, auto-capture memory event |
| PermissionRequest | permissionrequest-auto-approve | Auto-approve during autonomous mode |

---

## Memory System (v3)

**Append-only event store** for cross-session learning. Events stored in `~/.claude/memory/{project-hash}/events/`.

### How It Works

1. **Auto-capture** (primary path): `stop-validator` hook archives checkpoint as LESSON-first memory event on every successful stop. Checkpoint requires `key_insight` (>30 chars), `search_terms` (2-7 concept keywords), and `category` (enum).
2. **Manual capture** (deep captures): `/compound` skill for detailed LESSON/PROBLEM/CAUSE/FIX documentation
3. **Auto-injection**: `compound-context-loader` hook injects top 10 relevant events as structured XML at SessionStart
4. **Scoring**: 4-signal ranking — entity overlap (35%) + recency (30%) + content quality (20%) + source (15%)
5. **Entity matching**: File-path entities (basename, stem, dir) + concept entities (from `search_terms`) with substring matching
6. **Dedup**: Prefix-hash guard (8-event lookback, 60-min window) prevents duplicates
7. **Bootstrap filter**: Commit-message-level events automatically excluded from injection

### Storage

- **Location**: `~/.claude/memory/{project-hash}/events/evt_{timestamp}.json`
- **Isolation**: Project-scoped via SHA256(git_remote_url | repo_root)
- **Retention**: 90-day TTL, 500 event cap per project
- **Format**: JSON events with atomic writes (F_FULLFSYNC + os.replace for crash safety)
- **Budget**: 10 events, 8000 chars, score-tiered (600/350/200 chars per event)

### Event Schema

```json
{
  "id": "evt_20260131T143022-12345-a1b2c3",
  "ts": "2026-01-31T14:30:22Z",
  "type": "compound",
  "content": "LESSON: <key insight>\nDONE: <what was done>",
  "entities": ["crash-safety", "atomic-write", "macOS", "_memory.py", "hooks/_memory.py"],
  "source": "compound",
  "category": "gotcha",
  "meta": {"quality": "rich", "files_changed": ["config/hooks/_memory.py"]}
}
```

### Manual Search

```bash
grep -riwl "keyword" ~/.claude/memory/*/events/
```

---

## ToolSearch (MCP Lazy Loading)

ToolSearch (`ENABLE_TOOL_SEARCH=auto` in settings.json) defers MCP tool loading until needed, saving 85-95% of context tokens from tool definitions.

### Key Facts

- **Enabled by default** via `auto` mode — tools are eagerly loaded as fallback if ToolSearch fails
- **Chrome MCP is NOT affected** — `mcp__claude-in-chrome__*` tools are injected by the Chrome extension via system prompt, not through user-configured MCP servers
- **Affected servers**: Maestro MCP and Exa MCP are user-configured and subject to lazy loading
- **Discovery pattern**: Skills use `ToolSearch(query: "server-name")` for pre-flight capability detection

### Pre-Flight Pattern

Skills with hard MCP dependencies use ToolSearch as a fail-fast check:

```
# In skill SKILL.md:
ToolSearch(query: "maestro")   # Discovers + loads Maestro MCP tools
ToolSearch(query: "exa")       # Discovers + loads Exa MCP tools
```

If the MCP server isn't configured, ToolSearch returns no results and the skill can error clearly instead of failing mysteriously mid-execution.

### Which Skills Use ToolSearch

| Skill | ToolSearch Call | Why |
|-------|---------------|-----|
| `/mobileappfix` | `ToolSearch(query: "maestro")` | Hard dependency on Maestro MCP for E2E tests |
| `/build` (mobile path) | `ToolSearch(query: "maestro")` | Mobile verification requires Maestro MCP |
| `/heavy` (search policy) | `ToolSearch(query: "exa")` | Preferred search tool, discovered on demand |

Skills without MCP dependencies (`/go`, `/compound`, `/burndown`, `/qa`, `/deslop`) need no ToolSearch calls.

### Hooks Integration

- **exa-search-enforcer**: Reminds agents to use `ToolSearch(query: "exa")` if Exa tools aren't loaded
- **stop-validator**: Error messages reference ToolSearch discovery for Maestro tools

---

## Deep Dives

| Document | Description |
|----------|-------------|
| [Commands](concepts/commands.md) | How slash commands work |
| [Skills](concepts/skills.md) | How skills auto-trigger |
| [Hooks](concepts/hooks.md) | Hook lifecycle |
| [Architecture](architecture.md) | System design |
| [Appfix Guide](skills/appfix-guide.md) | Complete debugging guide |
| [Build Guide](skills/build-guide.md) | Autonomous task execution guide (with Lite Heavy) |
| [Philosophy](philosophy.md) | Core philosophy and principles |
| [Settings Reference](reference/settings.md) | Configuration options |
| [Azure Command Guard](hooks/azure-command-guard.md) | Azure CLI security hook |
| [Azure Guard Testing](hooks/azure-guard-testing.md) | Testing the Azure guard |

## Directory Structure

```
namshub/        # THIS IS THE SOURCE OF TRUTH
├── config/
│   ├── settings.json          # Hook definitions + ENABLE_TOOL_SEARCH=auto
│   ├── commands/              # 11 skill definition files (+ 3 skill-commands)
│   ├── hooks/                 # Python/bash hooks (21 registered)
│   └── skills/                # 25 skills ← EDIT HERE
├── docs/                      # Documentation
├── scripts/                   # install.sh, doctor.sh
└── README.md

~/.claude/                     # SYMLINKED TO REPO + MEMORY
├── skills → config/skills     # Symlink - edits here go to repo
├── hooks → config/hooks       # Symlink - edits here go to repo
├── settings.json → config/settings.json
└── memory/                    # Event store (NOT in repo)
    └── {project-hash}/
        ├── events/            # Memory events (JSON)
        └── manifest.json      # Fast lookup index
```

**IMPORTANT**: `~/.claude/skills/` is a symlink to `config/skills/` in this repo. When you edit skill files, you're editing the repo. Commit changes to preserve them.
