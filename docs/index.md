# Melt Reference

## Quick Links

- [README](../README.md) — Overview and quick start
- [Installation](../QUICKSTART.md) — Setup guide
- [Customization](guides/customization.md) — Create your own extensions

---

## The Four Core Skills

### `/melt` — Universal Task Execution
**Use when**: Complex task that benefits from multi-agent planning.
```
/melt add a logout button to the navbar
```
**Optional Agent Teams planning** (First Principles + AGI-Pilled + dynamic experts as needed) → implements → lints → commits → deploys → verifies in browser → **cannot stop until done**.

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
3-5 parallel Opus agents (First Principles + AGI-Pilled always, Critical Reviewer + dynamic agents as needed) → **self-educate via codebase + web + vendor docs** → tech-stack aware (Next.js, PydanticAI, Azure) → structured disagreements → adversarial dialogue → intelligence-first, never cost-first → bounded extension (max 3 rounds).

---

## All Slash Commands (18 commands + 5 core skills)

| Command | Purpose |
|---------|---------|
| `/melt` | Autonomous task execution (with Optional Agent Teams planning) |
| `/repair` | Unified debugging router (web → appfix, mobile → mobileappfix) |
| `/burndown` | Autonomous tech debt elimination (combines /deslop + /qa) |
| `/heavy` | Multi-agent analysis |
| `/improve` | Universal recursive improvement (design, UX, performance, a11y) targeting 9/10 |
| `/audiobook` | Transform documents into TTS-optimized audiobooks |
| `/harness-test` | Test harness changes (hooks/skills) in sandbox |
| `/appfix` | Web app debugging |
| `/qa` | Architecture audit (detection only - use /burndown to fix) |
| `/deslop` | AI slop detection (detection only - use /burndown to fix) |
| `/docupdate` | Documentation gaps |
| `/config-audit` | Environment variable analysis |
| `/cleanup` | Reclaim disk space from session data |
| `/webtest` | Browser testing |
| `/mobiletest` | Maestro E2E tests |
| `/mobileaudit` | Vision-based UI audit |
| `/interview` | Requirements Q&A |
| `/weboptimizer` | Performance benchmarking |
| `/designimprove` | UI improvement (or `/improve design`) |
| `/uximprove` | UX improvement (or `/improve UX`) |
| `/compound` | Capture solved problems as memory events for cross-session learning |
| `/health` | Toolkit health metrics — memory state, injection effectiveness, trends |

## All Skills (26 total)

| Skill | Triggers |
|-------|----------|
| `melt` | /melt, /build (legacy), /forge (legacy), "go do", "just do it", "execute this" |
| `repair` | /repair, /appfix, /mobileappfix, "fix the app", "debug production" |
| `burndown` | /burndown, "burn down debt", "clean up codebase", "fix the slop" |
| `appfix` | (Internal: web debugging - prefer /repair) |
| `heavy` | /heavy, "heavy analysis", "multiple perspectives", "debate this" |
| `improve` | /improve, "improve design", "improve UX" (enhanced 9/10 target + stall detection) |
| `compound` | /compound, "document this solution", "capture this learning", "remember this fix" |
| `episode` | /episode, "generate an episode", "create educational video", "produce an episode" |
| `essay` | /essay, "write an essay", "essay about" |
| `audiobook` | /audiobook, "create an audiobook", "turn this into audio", "make TTS-ready" |
| `mobileappfix` | (Internal: mobile debugging - prefer /repair) |
| `skill-sandbox` | /skill-sandbox, "test skill", "sandbox test" |
| `harness-test` | /harness-test, "test harness changes" (auto-triggers in /melt for toolkit) |
| `toolkit` | /toolkit, "update toolkit" |
| `deploy-pipeline` | /deploy, deployment questions |
| `webapp-testing` | Browser testing |
| `frontend-design` | Web UI development |
| `async-python-patterns` | asyncio, concurrent |
| `nextjs-tanstack-stack` | Next.js, TanStack |
| `prompt-engineering-patterns` | Context engineering for prompts, skills, and CLAUDE.md |
| `ux-designer` | UX design |
| `design-improver` | UI review (or /improve design) |
| `ux-improver` | UX review (or /improve UX) |
| `docs-navigator` | Documentation |
| `revonc-eas-deploy` | /eas, /revonc-deploy, "deploy to testflight", "build ios/android" |
| `health` | /health, "system health", "how is memory doing", "check health" |

## Registered Hooks (14 scripts)

| Event | Scripts | Purpose |
|-------|---------|---------|
| SessionStart | auto-update (v2), session-init, compound-context-loader, read-docs-reminder | Init, memory injection, smart toolkit update |
| Stop | stop-validator | Validate checkpoint, auto-capture memory event |
| PreToolUse (*) | auto-approve | Auto-approve during autonomous mode |
| PreToolUse (Bash) | deploy-enforcer, azure-command-guard | Block deploys, guard Azure CLI |
| PreToolUse (WebSearch) | exa-search-enforcer | Block WebSearch, redirect to Exa MCP |
| PostToolUse (*) | tool-usage-logger | Log tool usage for post-session analysis |
| PostToolUse (Read/Grep/Glob) | memory-recall | Mid-session memory recall |
| PostToolUse (Bash) | bash-version-tracker, doc-updater-async | Track versions, suggest doc updates |
| PostToolUse (Skill) | skill-continuation-reminder | Continue loop after skill |
| PreCompact | precompact-capture | Inject session summary before compaction |
| PermissionRequest | auto-approve | Fallback auto-approve during autonomous mode |
| UserPromptSubmit | read-docs-trigger | Doc suggestions |

---

## Auto-Update System (v2)

Smart auto-update with customization preservation. The hook detects local modifications, classifies overlap with upstream changes, and chooses the right update strategy automatically.

### Update Flow

```
Session Start
  ├─ Rate-limited check (5 min)
  ├─ git ls-remote vs local HEAD
  │
  ├─ Up to date → silent exit
  ├─ Behind, clean tree → git pull --ff-only
  ├─ Behind, dirty (no overlap) → stash + pull + pop
  └─ Behind, dirty (overlap) → backup branch + agent instructions
```

### Three Update Paths

| Scenario | Strategy | User Sees |
|----------|----------|-----------|
| Clean working tree | `git pull --ff-only` | Brief update notification |
| Dirty files, no upstream overlap | `stash → pull → pop` | "Local changes preserved (no conflicts)" |
| Dirty files overlap upstream | Backup branch + deferred agent merge | Structured instructions for Claude agent |

### Deferred Agent Pattern

When local modifications overlap with upstream changes, the hook outputs structured YAML instructions that the Claude agent executes as its first action. The hook is the **sensor** (fast, <2s); the agent is the **brain** (semantic understanding).

The agent classifies each user modification:
- **TEMPLATE_FILL**: User replaced `[YOUR_*]` placeholders → preserve values
- **PROJECT_GUARD**: User added project-specific conditionals → re-add to new version
- **FEATURE_ADD**: User added new capability → check if upstream added equivalent
- **BUG_FIX**: User patched a bug → check if upstream fixed it
- **CONFIG_OVERRIDE**: User changed defaults → preserve overrides

### File Classification

The hook categorizes each dirty file:

| Category | Detection | Example |
|----------|-----------|---------|
| `config` | `*.json` with "settings" | `settings.json` |
| `hook_module` | `hooks/_*.py` | `_memory.py`, `_scoring.py` |
| `hook` | `hooks/*.py` | `stop-validator.py` |
| `skill` | `skills/**` | `melt/SKILL.md` |
| `command` | `commands/**` | `commit.md` |
| `instructions` | `*CLAUDE.md` | `config/CLAUDE.md` |
| template | Contains `[YOUR_*]` placeholders | `service-topology.md` |

### Bootstrap Safety

Before pulling, the hook verifies the upstream `auto-update.py` compiles (`py_compile`). This prevents a broken upstream hook from bricking the update mechanism.

### Settings Local Override (v2)

`config/settings.local.json` provides user overrides that are deep-merged onto `config/settings.json`:

```json
{
  "env": { "MY_CUSTOM_VAR": "value" },
  "permissions": { "defaultMode": "acceptEdits" },
  "hooks": {
    "PostToolUse": [{ "matcher": "Bash", "hooks": [{"type": "command", "command": "python3 my-hook.py"}] }]
  }
}
```

**Merge rules**: Objects deep-merge (nested keys preserved). Arrays replace entirely. Keys starting with `_` are stripped. The merged result is written as a real file to `~/.claude/settings.json` (replacing the symlink).

Both `install.sh` and the auto-update hook perform this merge automatically.

### User Overlay Directory (v3)

`config/user/` provides a gitignored home for user-created extensions:

```
config/user/           # gitignored from upstream
├── hooks/             # Custom hook scripts
├── skills/            # Custom skill directories
├── commands/          # Custom command files
└── README.md          # Usage guide
```

When user overlay files exist, `install.sh` converts directory symlinks to per-file symlinks, linking both upstream and user content into `~/.claude/`. This means custom hooks/skills appear alongside upstream ones seamlessly.

### Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `CLAUDE_TOOLKIT_AUTO_UPDATE=false` | enabled | Disable auto-update via env var |
| `config/settings.local.json` | absent | User overrides, deep-merged onto base |
| `config/user/` | empty | User-created hooks, skills, commands |

---

## Memory System (v5 + Native Integration)

**Complementary dual-layer memory**: Claude Code's native MEMORY.md for project orientation + custom compound memory for task-specific retrieval. Events stored in `~/.claude/memory/{project-hash}/events/`.

### Native + Custom Integration

The context loader auto-detects native MEMORY.md and adjusts its budget:

| Scenario | Compound Budget | Native Budget | Total |
|----------|----------------|---------------|-------|
| No MEMORY.md | 8000 chars | 0 | ~8K |
| With MEMORY.md | 4500 chars | ~4-6K (Claude built-in) | ~10K |

A **dedup guard** prevents injecting compound events whose content (>60% word overlap) is already documented in MEMORY.md. High-utility events can be **promoted** from compound memory to MEMORY.md via `config/scripts/promote-to-memory-md.py`.

### How It Works

1. **Auto-capture** (primary path): `stop-validator` hook archives checkpoint as LESSON-first memory event on every successful stop. Checkpoint requires `key_insight` (>30 chars), `search_terms` (2-7 concept keywords), `category` (enum), optional `problem_type` (controlled vocabulary), optional `core_assertions` (max 5 topic/assertion pairs), and optional `memory_that_helped` (event IDs from `<m>` tags).
2. **Manual capture** (deep captures): `/compound` skill for detailed LESSON/PROBLEM/CAUSE/FIX documentation
3. **Auto-injection**: `compound-context-loader` hook injects top 5 relevant events as structured XML at SessionStart (budget-aware: 4.5K with native memory, 8K standalone)
4. **Core assertions**: Persistent `<core-assertions>` block injected before `<memories>` — topic-based dedup (last-write-wins), LRU eviction at 20 entries, compaction at SessionStart
5. **2-signal scoring**: Entity overlap (50%) + recency (50%) with entity gate (zero-overlap events rejected outright)
6. **MEMORY.md dedup**: Events with >60% significant-word overlap against native MEMORY.md are skipped
7. **Two-layer crash safety**:
   - `precompact-capture` (PreCompact): injects session summary into post-compaction context
   - `stop-validator` (Stop): structured LESSON + core assertions capture on clean exit
8. **Entity matching**: Multi-tier scoring — exact basename (1.0), stem (0.6), concept keyword (0.5), substring (0.35), directory (0.3) — uses max() not average()
9. **Gradual freshness curve**: Linear ramp 1.0→0.5 over 48h, then exponential decay anchored at 0.5 (half-life 7d), continuous at boundary
10. **Problem-type encoding**: Controlled vocabulary (`race-condition`, `config-mismatch`, `api-change`, `import-resolution`, `state-management`, `crash-safety`, `data-integrity`, `performance`, `tooling`, `dependency-management`) — auto-injected as concept entity
11. **Mid-session recall**: `memory-recall` hook on Read/Grep/Glob triggers, 8 recalls/session, 30s cooldown, file-locked injection log
12. **Dedup**: Prefix-hash guard (8-event lookback, 60-min window) prevents duplicates
13. **Bootstrap filter**: Commit-message-level events automatically excluded from injection
14. **Promotion**: `promote-to-memory-md.py` identifies events with citation rate >= 30% and promotes their LESSON content to native MEMORY.md

### Storage

- **Location**: `~/.claude/memory/{project-hash}/events/evt_{timestamp}.json`
- **Isolation**: Project-scoped via SHA256(git_remote_url | repo_root)
- **Retention**: 90-day TTL, 500 event cap per project
- **Format**: JSON events with atomic writes (F_FULLFSYNC + os.replace for crash safety)
- **Budget**: 5 events, 4500-8000 chars (dynamic), score-tiered (600/350/200 chars per event)
- **Promotion sidecar**: `~/.claude/memory/{project-hash}/promoted-events.json` tracks promoted event IDs

### Event Schema

```json
{
  "id": "evt_20260131T143022-12345-a1b2c3",
  "ts": "2026-01-31T14:30:22Z",
  "v": 1,
  "type": "compound",
  "content": "LESSON: <key insight>\nDONE: <what was done>",
  "entities": ["crash-safety", "atomic-write", "macOS", "_memory.py", "hooks/_memory.py"],
  "source": "compound",
  "category": "gotcha",
  "problem_type": "crash-safety",
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
| `/melt` (mobile path) | `ToolSearch(query: "maestro")` | Mobile verification requires Maestro MCP |
| `/heavy` (search policy) | `ToolSearch(query: "exa")` | Preferred search tool, discovered on demand |

Skills without MCP dependencies (`/compound`, `/burndown`, `/qa`, `/deslop`) need no ToolSearch calls.

### Hooks Integration

- **exa-search-enforcer**: Reminds agents to use `ToolSearch(query: "exa")` if Exa tools aren't loaded
- **stop-validator**: Error messages reference ToolSearch discovery for Maestro tools

---

## QMD (Documentation Search)

QMD (`tobi/qmd`) is a local markdown search engine that provides semantic search over project documentation. When configured, it's preferred over manual `docs/index.md` reading.

### Setup

```bash
# Install QMD globally
bun install -g github:tobi/qmd

# Create collection for your project
qmd collection add ~/your-project --name myproject

# Add context descriptions
qmd context add qmd://myproject "Project description for search context"

# Add MCP server to .mcp.json
{
  "mcpServers": {
    "qmd": {
      "command": "/path/to/.bun/bin/qmd",
      "args": ["mcp"]
    }
  }
}
```

### Usage

```bash
# Search for relevant docs (preferred)
qmd_search "authentication flow"

# Get specific document
qmd_get "qmd://collection/path/to/doc.md"

# Check index status
qmd_status
```

### Integration with Skills

| Skill | QMD Usage |
|-------|-----------|
| `docs-navigator` | Primary search method (Step 1) |
| `appfix` | Phase 0 context gathering |
| `read-docs-trigger` hook | Suggests QMD when available |

### Fallback Behavior

All QMD integrations include fallback to manual doc reading when QMD is unavailable:
- If `qmd_status` fails → read `docs/index.md` manually
- Skills detect QMD via `.mcp.json` configuration

---

## Deep Dives

| Document | Description |
|----------|-------------|
| [Commands](concepts/commands.md) | How slash commands work |
| [Skills](concepts/skills.md) | How skills auto-trigger |
| [Hooks](concepts/hooks.md) | Hook lifecycle |
| [Architecture](architecture.md) | System design |
| [Appfix Guide](skills/appfix-guide.md) | Complete debugging guide |
| [Melt Guide](skills/melt-guide.md) | Autonomous task execution guide (with Lite Heavy) |
| [Philosophy](philosophy.md) | Core philosophy and principles |
| [Architecture Philosophy](architecture-philosophy.md) | One System, One Loop — the mental model for recursive self-improvement |
| [Settings Reference](reference/settings.md) | Configuration options |
| [Azure Command Guard](hooks/azure-command-guard.md) | Azure CLI security hook |
| [Azure Guard Testing](hooks/azure-guard-testing.md) | Testing the Azure guard |

## Research & Historical

| Document | Description |
|----------|-------------|
| [Agentic AI 2026 Research](research/agentic-ai-2026-research-report.md) | Research report on agentic AI landscape |
| [Compound + Supermemory Integration](research/compound-engineering-supermemory-integration.md) | Research: integrating Compound Engineering with Supermemory |
| [Memory Analysis (historical)](analysis-persistent-memory-for-harnesses.md) | Pre-v5 memory integration analysis |
| [Memory Architecture (historical)](memory-integration-analysis.md) | Hybrid push/pull memory architecture proposal |

## Directory Structure

```
claude-code-toolkit/   # THIS IS THE SOURCE OF TRUTH
├── config/
│   ├── CLAUDE.md              # Global instructions (symlinked to ~/.claude/CLAUDE.md)
│   ├── settings.json          # Hook definitions + Agent Teams + ToolSearch (upstream-owned)
│   ├── settings.local.json    # User overrides, deep-merged onto settings.json (gitignored)
│   ├── settings.local.json.example  # Template for user overrides
│   ├── commands/              # 15 command files
│   ├── hooks/                 # Python/bash hooks (14 registered)
│   ├── scripts/               # Standalone utilities (promote-to-memory-md.py)
│   ├── skills/                # 26 skills ← EDIT HERE
│   └── user/                  # User overlay directory (gitignored)
│       ├── hooks/             # Custom hook scripts
│       ├── skills/            # Custom skill directories
│       └── commands/          # Custom command files
├── docs/                      # Documentation
├── scripts/                   # install.sh, doctor.sh, skill-tester.sh, test-e2e-*.sh
└── README.md

~/.claude/                     # SYMLINKED TO REPO + MEMORY
├── CLAUDE.md → config/CLAUDE.md  # Global instructions (search preferences)
├── skills → config/skills     # Symlink (or per-skill symlinks if user overlay exists)
├── hooks → config/hooks       # Symlink (or per-file symlinks if user overlay exists)
├── settings.json              # Symlink to config/settings.json OR merged real file
├── projects/                  # Native Claude Code project data
│   └── {encoded-path}/
│       └── memory/
│           └── MEMORY.md      # Native project memory (auto-detected by hooks)
└── memory/                    # Compound event store (NOT in repo)
    └── {project-hash}/
        ├── events/            # Memory events (JSON)
        ├── core-assertions.jsonl  # Persistent assertions (JSONL)
        ├── manifest.json      # Fast lookup index + utility tracking
        └── promoted-events.json   # Tracks events promoted to MEMORY.md
```

**IMPORTANT**: `~/.claude/skills/` is a symlink to `config/skills/` in this repo. When you edit skill files, you're editing the repo. Commit changes to preserve them. For user-created extensions, use `config/user/` instead — it's gitignored from upstream.
