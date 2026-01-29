---
name: skill-sandbox
description: Test Claude Code skills in isolated tmux sandboxes. Spawn multiple sessions, verify hook behavior, run integration tests. Use when asked to "test a skill", "run skill tests", "sandbox test", or "/skill-sandbox".
---

# Skill Testing Sandbox (/skill-sandbox)

Test Claude Code skills in **security-isolated** tmux sessions that cannot access real credentials, corrupt production state, or accidentally deploy.

## CRITICAL SECURITY ARCHITECTURE

```
+====================================================================+
|  REAL ENVIRONMENT (PROTECTED)                                       |
+====================================================================+
|  ~/.claude/                                                         |
|    .credentials-export.json  <- CONTAINS REAL OAUTH TOKENS          |
|    settings.json             <- HOOK CONFIGURATION                  |
|    {skill}-state.json        <- ACTIVE SESSION STATE                |
|    projects/                 <- SESSION LOGS WITH API KEYS          |
+====================================================================+
                    | SECURITY BOUNDARY |
+====================================================================+
|  SANDBOX ENVIRONMENT (per session)                                  |
+====================================================================+
|  /tmp/claude-sandbox-{id}/                                          |
|    fake-home/                                                       |
|      .claude/                                                       |
|        .credentials-export.json  <- FAKE TOKENS (won't work)        |
|        settings.json             <- COPIED (hooks enabled)          |
|    project/                      <- GIT WORKTREE                    |
|    bin/                          <- MOCK COMMANDS (gh, az)          |
|    blocked.log                   <- BLOCKED COMMAND LOG             |
|  tmux -L sandbox-{id}            <- SEPARATE TMUX SERVER            |
|  $HOME=/tmp/claude-sandbox-{id}/fake-home                           |
+====================================================================+
```

### Security Threat Model

| Threat Vector | Real Risk | Mitigation |
|---------------|-----------|------------|
| **OAuth token theft** | `~/.claude/.credentials-export.json` contains real `sk-ant-oat01-*` tokens | Sandbox uses fake HOME; real file inaccessible |
| **State file corruption** | `~/.claude/{skill}-state.json` shared globally | Isolated `$HOME` prevents real state access |
| **Accidental production deploy** | `gh workflow run deploy.yml -f environment=production` | Mock `gh` blocks workflow commands |
| **Azure infrastructure changes** | `az containerapp update --name aca-*-prod` | Mock `az` blocks containerapp commands |
| **Environment variable leakage** | tmux server shares env across sessions | Separate tmux server via `-L sandbox-{id}` |
| **Git operation conflicts** | Commits to real branches affect production | Git worktree creates isolated branch |
| **Session interference** | Multiple tests share state files | Unique sandbox ID per test run |

### What IS Protected

1. **OAuth Credentials** - Fake `~/.claude/.credentials-export.json` with non-functional tokens
2. **State Files** - Isolated `$HOME` means all state writes go to sandbox
3. **Production Deployments** - Mock `gh` and `az` commands block dangerous operations
4. **Environment Variables** - Separate tmux server prevents env leakage
5. **Git Branches** - Worktree isolation keeps test commits separate

### What is NOT Protected (Use Caution)

| Risk | Why Not Protected | Recommendation |
|------|-------------------|----------------|
| **Network access** | macOS lacks namespace isolation | Test with mock APIs or network-safe repos |
| **Filesystem outside sandbox** | No chroot on macOS | Skills should use relative paths |
| **Real API calls** | No network interception | Use `--model haiku` to minimize costs |
| **Malicious skill code** | Not a security boundary | Review skills before testing |
| **Other processes** | Same UID as real sessions | Don't run on shared systems |

## Evidence: Why This Architecture

### tmux Environment Variable Leakage

From [Be Careful Using tmux and Environment Variables](https://aj.codes/blog/be-careful-using-tmux-and-environment-variables/):

> "As long as the tmux server is running, it will retain the copy of the environment at the moment it was started"

**Solution**: Use `-L socket-name` to create a separate tmux server per sandbox.

### Credentials File Discovery

Real OAuth tokens found at `~/.claude/.credentials-export.json`:
```json
{
  "claudeAiOauth": {
    "accessToken": "sk-ant-oat01-...",  // REAL TOKEN
    "refreshToken": "sk-ant-ort01-...", // REAL TOKEN
    "expiresAt": 1769646245095,
    "scopes": ["user:inference", "user:sessions:claude_code"]
  }
}
```

**Solution**: Create fake credentials file in sandbox HOME.

### State File Race Conditions

Global state files found at:
- `~/.claude/appfix-state.json`
- `~/.claude/godo-state.json`
- `~/.claude/worktree-state.json`

From `hooks/_common.py`:
```python
# Check user-level state with TTL
user_state_path = Path.home() / ".claude" / "appfix-state.json"
```

**Solution**: Override `$HOME` so `Path.home()` resolves to sandbox directory.

---

## Platform Capabilities (Evidence-Based)

### What Works

| Capability | Method | Evidence |
|------------|--------|----------|
| **Programmatic execution** | `claude -p "prompt"` | [Official headless docs](https://code.claude.com/docs/en/headless) |
| **Session resumption** | `--resume <session-id>` | [Session management](https://stevekinney.com/courses/ai-development/claude-code-session-management) |
| **Permission bypass** | `--dangerously-skip-permissions` | [YOLO mode guide](https://www.ksred.com/claude-code-dangerously-skip-permissions-when-to-use-it-and-when-you-absolutely-shouldnt/) |
| **JSON output** | `--output-format json` | Captures session_id, result, usage |
| **Git worktree isolation** | `~/.claude/hooks/worktree-manager.py` | Existing toolkit infrastructure |
| **tmux session control** | `tmux send-keys` / `tmux capture-pane` | Existing `test-e2e-tmux.sh` |

### Known Limitations

| Limitation | Root Cause | Workaround |
|------------|------------|------------|
| **Raw mode stdin error** | Ink (React terminal UI) requires raw mode | Use `claude -p "prompt"` NOT piping to stdin |
| **Hooks captured at startup** | Design decision for performance | Restart session to pick up hook changes |
| **Session resumption bugs** | [GitHub #12730](https://github.com/anthropics/claude-code/issues/12730) | Use `--no-session-persistence` for tests |
| **Context overflow in headless** | [GitHub #13831](https://github.com/anthropics/claude-code/issues/13831) | Monitor output size, keep prompts focused |

## Architecture

```
PARENT SESSION (this skill)
├── Creates test sandboxes (temp dirs or git worktrees)
├── Spawns child Claude sessions via:
│   ├── Headless mode: claude -p (for automated tests)
│   └── tmux sessions: tmux send-keys (for interactive tests)
├── Monitors execution through:
│   ├── JSON output parsing (headless)
│   ├── tmux capture-pane (interactive)
│   └── File artifact verification (.claude/ state files)
└── Reports results and cleans up
```

---

## SECURE WORKFLOW (Use This)

### Quick Start: Test a Skill Securely

```bash
# 1. Create sandbox with all security measures
~/.claude/skills/skill-sandbox/scripts/sandbox-setup.sh create

# Output:
# Sandbox ID:       sandbox-1706438445-a1b2c3d4
# Sandbox Root:     /tmp/claude-sandboxes/sandbox-1706438445-a1b2c3d4
# Fake HOME:        /tmp/claude-sandboxes/sandbox-1706438445-a1b2c3d4/fake-home
# Project Worktree: /tmp/claude-sandboxes/sandbox-1706438445-a1b2c3d4/project
# tmux Socket:      sandbox-sandbox-1706438445-a1b2c3d4

# 2. Start isolated tmux session (SEPARATE SERVER - env isolation)
SANDBOX_ID="sandbox-1706438445-a1b2c3d4"
tmux -L "sandbox-$SANDBOX_ID" new-session -s test

# 3. Inside tmux: Load secure environment
source /tmp/claude-sandboxes/$SANDBOX_ID/env.sh

# 4. Navigate to project
cd $SANDBOX_PROJECT

# 5. Run Claude (now in sandbox)
claude --dangerously-skip-permissions

# 6. Test the skill
/godo Add a health check endpoint
```

### One-Liner (Full Secure Test)

```bash
# Create sandbox + start Claude in one command
SANDBOX_ID=$(~/.claude/skills/skill-sandbox/scripts/sandbox-setup.sh create 2>/dev/null | tail -1) && \
tmux -L "sandbox-$SANDBOX_ID" new-session -s test \
  "source /tmp/claude-sandboxes/$SANDBOX_ID/env.sh && \
   cd \$SANDBOX_PROJECT && \
   claude --dangerously-skip-permissions; exec bash"
```

### Cleanup

```bash
# Destroy sandbox and all artifacts
~/.claude/skills/skill-sandbox/scripts/sandbox-setup.sh destroy sandbox-1706438445-a1b2c3d4

# List all sandboxes
~/.claude/skills/skill-sandbox/scripts/sandbox-setup.sh list
```

### Verify Security

After starting a sandbox session, verify isolation:

```bash
# Check HOME is sandbox (not real)
echo $HOME
# Should be: /tmp/claude-sandboxes/sandbox-*/fake-home

# Check credentials file is fake
cat ~/.claude/.credentials-export.json | jq '.claudeAiOauth.accessToken'
# Should contain: "sk-ant-SANDBOX-FAKE-TOKEN-DO-NOT-USE..."

# Test gh blocking
gh workflow run deploy.yml
# Should output: SANDBOX: Command blocked for safety

# Check blocked log
cat $SANDBOX_DIR/blocked-commands.log
```

---

## Test Modes

> **SECURITY WARNING**: The basic patterns below do NOT include credential isolation.
> For secure testing, use the `sandbox-setup.sh` script shown above, which:
> - Creates a fake HOME directory (protects `~/.claude/.credentials-export.json`)
> - Uses a separate tmux server (`-L` flag) for environment isolation
> - Installs mock `gh` and `az` commands to block dangerous operations

### 1. Headless Mode (Fast, Automated) - SECURE

Best for CI/CD and rapid iteration. Uses sandbox for security.

```bash
# Create sandbox and run headless test
SANDBOX_ID=$(~/.claude/skills/skill-sandbox/scripts/sandbox-setup.sh create 2>/dev/null | tail -1)
SANDBOX_ROOT="/tmp/claude-sandboxes/$SANDBOX_ID"

# Run Claude in sandbox environment
env HOME="$SANDBOX_ROOT/fake-home" \
    PATH="$SANDBOX_ROOT/bin:$PATH" \
    SANDBOX_MODE=true \
    SANDBOX_ID="$SANDBOX_ID" \
    claude -p "Run /appfix on this repo" \
      --dangerously-skip-permissions \
      --no-session-persistence \
      --output-format json \
      --model haiku \
      --timeout 120

# Cleanup
~/.claude/skills/skill-sandbox/scripts/sandbox-setup.sh destroy "$SANDBOX_ID"
```

### 1b. Headless Mode (UNSECURED - Use with Caution)

```bash
# WARNING: This can access real credentials and deploy to production!
# Only use for quick local tests on safe repos
claude -p "Run /appfix on this repo" \
  --dangerously-skip-permissions \
  --no-session-persistence \
  --output-format json \
  --model haiku \
  --timeout 120
```

**Capture session ID for inspection:**
```bash
SESSION_ID=$(claude -p "Start skill test" --output-format json | jq -r '.session_id')
echo "Session: $SESSION_ID"
```

### 2. tmux Mode (Interactive, Observable) - SECURE

Best for debugging and manual observation. Uses SEPARATE tmux server for environment isolation.

```bash
# Create sandbox
SANDBOX_ID=$(~/.claude/skills/skill-sandbox/scripts/sandbox-setup.sh create 2>/dev/null | tail -1)
SANDBOX_ROOT="/tmp/claude-sandboxes/$SANDBOX_ID"

# Start SEPARATE tmux server (CRITICAL: -L flag isolates environment)
tmux -L "sandbox-$SANDBOX_ID" new-session -d -s test -x 200 -y 50

# Load sandbox environment
tmux -L "sandbox-$SANDBOX_ID" send-keys -t test \
  "source $SANDBOX_ROOT/env.sh" Enter
sleep 1

# Change to project
tmux -L "sandbox-$SANDBOX_ID" send-keys -t test \
  "cd \$SANDBOX_PROJECT" Enter
sleep 1

# Start Claude
tmux -L "sandbox-$SANDBOX_ID" send-keys -t test \
  "claude --dangerously-skip-permissions" Enter
sleep 5

# Send test prompt
tmux -L "sandbox-$SANDBOX_ID" send-keys -t test "/appfix" Enter

# Attach to observe
tmux -L "sandbox-$SANDBOX_ID" attach -t test

# After testing, cleanup
~/.claude/skills/skill-sandbox/scripts/sandbox-setup.sh destroy "$SANDBOX_ID"
```

### 2b. tmux Mode (UNSECURED - Use with Caution)

```bash
# WARNING: Environment variables from real ~/.claude/ are accessible!
# This can leak OAuth tokens to child sessions
SESSION_NAME="skill-test-$(date +%s)"
tmux new-session -d -s "$SESSION_NAME" -x 200 -y 50
tmux send-keys -t "$SESSION_NAME" "cd /tmp/skill-test-dir" Enter
tmux send-keys -t "$SESSION_NAME" "claude --dangerously-skip-permissions" Enter
```

### 3. Python SDK Mode (Programmatic Control)

Best for complex test orchestration with hooks and callbacks.

```python
from claude_agent_sdk import query, ClaudeAgentOptions

async def test_skill():
    options = ClaudeAgentOptions(
        permission_mode='bypassPermissions',
        cwd="/tmp/test-sandbox",
        max_turns=10,
        model="haiku"
    )

    async for message in query(
        prompt="Run /godo to implement a simple hello world",
        options=options
    ):
        print(message)
```

## Workflow

### Phase 1: Create Test Sandbox

```bash
# Option A: Temp directory (simple, isolated)
TEST_DIR=$(mktemp -d "/tmp/skill-test-XXXXXX")
cd "$TEST_DIR"
git init && git commit --allow-empty -m "init"

# Option B: Git worktree (parallel agent isolation)
python3 ~/.claude/hooks/worktree-manager.py create "test-$(date +%s)"
# Returns: /tmp/claude-worktrees/test-xxx
```

### Phase 2: Configure Test State

Create state files to trigger specific skill behaviors:

```bash
# Test appfix mode
mkdir -p .claude
cat > .claude/appfix-state.json << 'EOF'
{
    "iteration": 1,
    "started_at": "2026-01-28T10:00:00Z",
    "plan_mode_completed": false,
    "parallel_mode": false,
    "coordinator": true,
    "services": {},
    "fixes_applied": [],
    "verification_evidence": null
}
EOF
```

### Phase 3: Execute Test

```bash
# Headless test with timeout
timeout 120 claude -p "Your test prompt here" \
  --dangerously-skip-permissions \
  --no-session-persistence \
  --output-format json \
  2>"$TEST_DIR/stderr.log" \
  >"$TEST_DIR/stdout.log"

# Parse results
jq '.result' "$TEST_DIR/stdout.log"
```

### Phase 4: Verify Outcomes

```bash
# Check hook artifacts
cat .claude/appfix-state.json | jq '.plan_mode_completed'

# Check completion checkpoint
cat .claude/completion-checkpoint.json | jq '.self_report.is_job_complete'

# Check for expected files
ls -la src/
```

### Phase 5: Cleanup

```bash
# Remove temp directory
rm -rf "$TEST_DIR"

# OR remove worktree
python3 ~/.claude/hooks/worktree-manager.py cleanup "test-xxx"
```

## Test Case Patterns

### Pattern 1: Hook Behavior Verification

Test that hooks fire correctly based on state files.

```bash
#!/bin/bash
TEST_DIR=$(mktemp -d)
cd "$TEST_DIR"
git init && git commit --allow-empty -m "init"

# Create state with plan_mode_completed=false
mkdir -p .claude
echo '{"iteration": 1, "plan_mode_completed": false}' > .claude/appfix-state.json

# Try to write code (should be blocked by enforcer)
claude -p "Write 'test' to src/test.py" \
  --dangerously-skip-permissions \
  --no-session-persistence \
  --output-format json > output.json 2>&1

# Verify: src/test.py should NOT exist
if [[ -f src/test.py ]]; then
    echo "FAIL: Code write was not blocked"
else
    echo "PASS: Plan mode enforcer blocked code write"
fi

rm -rf "$TEST_DIR"
```

### Pattern 2: Full Skill Lifecycle

Test a skill from start to completion.

```bash
#!/bin/bash
TEST_DIR=$(mktemp -d)
cd "$TEST_DIR"
git init && git commit --allow-empty -m "init"

# Create minimal project structure
mkdir src
echo "print('hello')" > src/main.py

# Run skill
claude -p "/godo: Add a greeting function to main.py" \
  --dangerously-skip-permissions \
  --no-session-persistence \
  --output-format json \
  --max-turns 15 > output.json 2>&1

# Verify completion checkpoint
if [[ -f .claude/completion-checkpoint.json ]]; then
    IS_COMPLETE=$(jq '.self_report.is_job_complete' .claude/completion-checkpoint.json)
    echo "Job complete: $IS_COMPLETE"
fi

rm -rf "$TEST_DIR"
```

### Pattern 3: Parallel Agent Isolation

Test multiple agents working on the same codebase.

```bash
#!/bin/bash
MAIN_REPO="/path/to/your/repo"
cd "$MAIN_REPO"

# Create worktrees for parallel agents
AGENT1_PATH=$(python3 ~/.claude/hooks/worktree-manager.py create "agent-1" | tail -1)
AGENT2_PATH=$(python3 ~/.claude/hooks/worktree-manager.py create "agent-2" | tail -1)

# Run agents in parallel (background)
(cd "$AGENT1_PATH" && claude -p "Fix auth module" --dangerously-skip-permissions --no-session-persistence) &
(cd "$AGENT2_PATH" && claude -p "Fix database module" --dangerously-skip-permissions --no-session-persistence) &
wait

# Merge results
python3 ~/.claude/hooks/worktree-manager.py merge "agent-1"
python3 ~/.claude/hooks/worktree-manager.py merge "agent-2"

# Cleanup
python3 ~/.claude/hooks/worktree-manager.py cleanup "agent-1"
python3 ~/.claude/hooks/worktree-manager.py cleanup "agent-2"
```

## tmux Interactive Test Runner

For skills that require interactive observation:

```bash
#!/bin/bash
# Usage: run-interactive-test.sh <skill-name> <test-prompt>

SKILL_NAME="${1:-appfix}"
TEST_PROMPT="${2:-/appfix}"
SESSION_NAME="skill-test-$SKILL_NAME-$(date +%s)"

# Create test environment
TEST_DIR=$(mktemp -d "/tmp/skill-test-XXXXXX")
(cd "$TEST_DIR" && git init -q && git commit --allow-empty -m "init" -q)

# Start tmux session
tmux new-session -d -s "$SESSION_NAME" -x 200 -y 50
tmux send-keys -t "$SESSION_NAME" "cd '$TEST_DIR'" Enter
sleep 1

# Start Claude
tmux send-keys -t "$SESSION_NAME" "claude --dangerously-skip-permissions" Enter
sleep 5

# Send skill invocation
tmux send-keys -t "$SESSION_NAME" "$TEST_PROMPT" Enter

echo "Session started: $SESSION_NAME"
echo "Attach with: tmux attach -t $SESSION_NAME"
echo "Kill with:   tmux kill-session -t $SESSION_NAME"
echo "Test dir:    $TEST_DIR"
```

## Assertions Library

Common verification patterns:

```bash
# Assert file exists
assert_file_exists() {
    [[ -f "$1" ]] || { echo "FAIL: $1 not found"; return 1; }
    echo "PASS: $1 exists"
}

# Assert file contains pattern
assert_file_contains() {
    grep -q "$2" "$1" || { echo "FAIL: '$2' not in $1"; return 1; }
    echo "PASS: $1 contains '$2'"
}

# Assert checkpoint field value
assert_checkpoint_field() {
    local field="$1"
    local expected="$2"
    local actual=$(jq -r ".self_report.$field" .claude/completion-checkpoint.json 2>/dev/null)
    [[ "$actual" == "$expected" ]] || { echo "FAIL: $field=$actual (expected $expected)"; return 1; }
    echo "PASS: $field=$expected"
}

# Assert state field value
assert_state_field() {
    local filename="$1"
    local field="$2"
    local expected="$3"
    local actual=$(jq -r ".$field" ".claude/$filename" 2>/dev/null)
    [[ "$actual" == "$expected" ]] || { echo "FAIL: $field=$actual (expected $expected)"; return 1; }
    echo "PASS: $field=$expected"
}
```

## Integration with Existing Tests

The toolkit already has test infrastructure:

| Script | Mode | Purpose |
|--------|------|---------|
| `scripts/test-e2e-headless.sh` | Headless | Automated hook tests |
| `scripts/test-e2e-tmux.sh` | Interactive | Manual observation tests |

Run existing tests:
```bash
cd ~/Desktop/motium_github/documentation/prompts
bash scripts/test-e2e-headless.sh
bash scripts/test-e2e-tmux.sh --observe
```

## Limitations

### Cannot Test

1. **SessionStart hooks in child sessions** - Hooks are captured when Claude starts, not when hooks change
2. **Real OAuth flows** - Credentials must be pre-configured
3. **True parallel sessions** - Rate limits apply across all sessions
4. **Long-running tasks in headless mode** - Context overflow risk ([#13831](https://github.com/anthropics/claude-code/issues/13831))

### Must Restart Session For

1. Changes to `~/.claude/settings.json`
2. Changes to hook scripts in `~/.claude/hooks/`
3. Changes to skill definitions in `~/.claude/skills/`

## Debug Tips

```bash
# Watch hook debug logs
tail -f /tmp/claude-hooks-debug.log

# Check state file TTL
python3 -c "
import json
from pathlib import Path
state = json.loads(Path('.claude/appfix-state.json').read_text())
print('started_at:', state.get('started_at'))
print('plan_mode_completed:', state.get('plan_mode_completed'))
"

# Verify hooks are registered
cat ~/.claude/settings.json | jq '.hooks'
```

## References

- [Claude Code Headless Docs](https://code.claude.com/docs/en/headless)
- [Python Agent SDK](https://platform.claude.com/docs/en/agent-sdk/python)
- [tmux Integration Guide](https://www.blle.co/blog/claude-code-tmux-beautiful-terminal)
- [claude-tmux Session Manager](https://github.com/nielsgroen/claude-tmux)
- [Agent of Empires (worktree isolation)](https://github.com/njbrake/agent-of-empires)

## Sources

Platform capabilities verified through:
- [Official Claude Code Headless Documentation](https://code.claude.com/docs/en/headless)
- [Claude Code dangerously-skip-permissions Guide](https://www.ksred.com/claude-code-dangerously-skip-permissions-when-to-use-it-and-when-you-absolutely-shouldnt/)
- [Claude Code Session Management](https://stevekinney.com/courses/ai-development/claude-code-session-management)
- [Raw Mode Issue #1072](https://github.com/anthropics/claude-code/issues/1072)
- [Context Overflow Issue #13831](https://github.com/anthropics/claude-code/issues/13831)
- [Python Agent SDK Reference](https://platform.claude.com/docs/en/agent-sdk/python)

---

## Security References

### tmux Environment Isolation

- [Be Careful Using tmux and Environment Variables](https://aj.codes/blog/be-careful-using-tmux-and-environment-variables/) - explains why separate tmux servers (`-L` flag) are needed for env isolation
- [tmux Session Environment Variables Discussion](https://github.com/orgs/tmux/discussions/3997) - upstream discussion on environment inheritance
- [Setting Session-Specific Environment Variables in tmux](https://github.com/jbranchaud/til/blob/master/tmux/set-session-specific-environment-variables.md)

### Sandbox Escape Vectors (Why We Need These Mitigations)

- [Container Escape Vulnerabilities (Sysdig)](https://www.sysdig.com/blog/runc-container-escape-vulnerabilities) - general principles apply to process isolation
- macOS lacks Linux namespaces; `$HOME` override is our primary isolation mechanism
- File-level isolation via worktrees; no chroot available without root

### Credential Storage Findings

Analysis of `~/.claude/` directory revealed:
- `.credentials-export.json` - OAuth tokens (`sk-ant-oat01-*`, `sk-ant-ort01-*`)
- `settings.json` - Hook configuration (safe to share read-only)
- `{skill}-state.json` - Skill activation state (race condition risk)
- `projects/` - Session logs (may contain sensitive data)

### State File Race Conditions

From `hooks/_common.py`:
```python
user_state_path = Path.home() / ".claude" / "appfix-state.json"
```

Multiple sessions writing to the same state file can:
1. Corrupt JSON structure
2. Overwrite session IDs (breaking sticky sessions)
3. Reset iteration counters (causing infinite loops)

The sandbox mitigates this by overriding `$HOME` so `Path.home()` resolves to sandbox directory.

### Production Deployment Risks

Skills like `deploy-pipeline` can execute:
```bash
gh workflow run cortex-backend-ci.yml -f environment=production
az containerapp update --name aca-motium-cortex-api-prod ...
```

The sandbox mock commands (`$SANDBOX_DIR/bin/gh`, `$SANDBOX_DIR/bin/az`) intercept and block these operations, logging them to `blocked-commands.log`.
