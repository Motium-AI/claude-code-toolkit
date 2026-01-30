---
name: harness-test
description: Test Claude Code harness changes (hooks, skills, settings) in isolated sandbox. Auto-triggers in /forge when modifying toolkit. Use "/harness-test" or "test harness changes".
---

# Harness Test Skill (/harness-test)

Test changes to Claude Code hooks, skills, and settings in an isolated sandbox before committing.

## Why This Exists

**Hooks are captured at Claude session startup.**

When you modify a hook in the current session, the changes don't take effect until restart. Testing hook changes requires starting a NEW Claude session with the modified hooks loaded.

This skill:
1. Creates an isolated sandbox
2. Copies your uncommitted changes to the sandbox
3. Starts a fresh Claude session in the sandbox
4. Runs test prompts to verify expected behavior
5. Reports pass/fail back to the parent session

## Triggers

- `/harness-test` - explicit invocation
- Auto-triggered by `/forge` when:
  1. Working in claude-code-toolkit repository
  2. Modified files include harness files (hooks, skills, settings)

## Integration with /forge

When `/forge` is active in the toolkit repository:

```
PHASE 1: EXECUTE (make code changes to hooks/skills)

╔══════════════════════════════════════════════════════════════════╗
║  PHASE 1.75: HARNESS TEST (automatic)                            ║
║       └► Detect harness project                                  ║
║       └► Check for modified harness files                        ║
║       └► Create sandbox with modified hooks                      ║
║       └► Run test cases                                          ║
║       └► BLOCK if tests fail                                     ║
╚══════════════════════════════════════════════════════════════════╝

PHASE 2: COMMIT (only after harness test passes)
```

## Workflow

### Phase 1: Detection

Check if we're in the harness project and have harness changes:

```bash
# Detect harness project (2 of 3 markers required)
~/.claude/skills/harness-test/scripts/detect-harness.sh
# Exit 0 = harness project, Exit 1 = not harness

# Get modified harness files
~/.claude/skills/harness-test/scripts/detect-harness-changes.sh
# Outputs list of modified config/hooks/, config/skills/, config/settings.json
```

### Phase 2: Setup Sandbox

```bash
# Create sandbox with harness configuration
SANDBOX_ID=$(~/.claude/skills/harness-test/scripts/setup-harness-sandbox.sh)

# Sandbox structure:
# /tmp/claude-sandboxes/sandbox-xxx/
# ├── fake-home/.claude/
# │   ├── hooks/      -> project/config/hooks/    (MODIFIED hooks)
# │   ├── skills/     -> project/config/skills/   (MODIFIED skills)
# │   └── settings.json                           (COPIED from project)
# └── project/        <- Git worktree with uncommitted changes
```

### Phase 3: Propagate Changes

```bash
# Copy uncommitted changes to sandbox
~/.claude/skills/harness-test/scripts/propagate-changes.sh "$(pwd)" "$SANDBOX_PROJECT"
```

### Phase 4: Run Tests

```bash
# Run all test cases for modified files
~/.claude/skills/harness-test/scripts/run-all-tests.sh "$SANDBOX_ID"

# Or run specific test
~/.claude/skills/harness-test/scripts/run-test-case.sh "$SANDBOX_ID" "plan-mode-enforcer-blocks-code-write"
```

### Phase 5: Report & Cleanup

- Results written to `.claude/harness-test-state.json`
- Sandbox destroyed automatically (unless `--keep-sandbox` specified)
- Exit with success/failure based on test results

## Sandbox Architecture

The key difference from regular skill-sandbox:

| Aspect | Regular Sandbox | Harness Sandbox |
|--------|-----------------|-----------------|
| `~/.claude/hooks` | Symlinks to real `~/.claude/hooks` | Symlinks to `project/config/hooks/` |
| `~/.claude/skills` | Symlinks to real `~/.claude/skills` | Symlinks to `project/config/skills/` |
| `settings.json` | Copied from real `~/.claude/` | Copied from `project/config/` |
| Purpose | Test skills in current environment | Test MODIFIED hooks/skills |

```
HARNESS SANDBOX LAYOUT:
/tmp/claude-sandboxes/sandbox-{id}/
├── fake-home/
│   └── .claude/
│       ├── .credentials-export.json  <- FAKE tokens (security)
│       ├── settings.json             <- FROM project/config/settings.json
│       ├── hooks/                    -> project/config/hooks/
│       ├── skills/                   -> project/config/skills/
│       └── commands/                 -> project/config/commands/
├── project/                          <- Git worktree
│   └── config/
│       ├── hooks/                    <- MODIFIED hook files
│       ├── skills/                   <- MODIFIED skill files
│       └── settings.json             <- MODIFIED settings
├── bin/                              <- Mock gh, az (blocks deploys)
├── env.sh                            <- Environment setup
└── metadata.json
```

## Test Case Format

Test cases are JSON files in `test-cases/` directory:

```json
{
  "name": "plan-mode-enforcer-blocks-code-write",
  "description": "Verify Edit/Write blocked when plan_mode_completed=false",
  "setup": {
    "state_file": "appfix-state.json",
    "state_content": {
      "iteration": 1,
      "plan_mode_completed": false
    },
    "files": {
      "src/main.py": "# existing file"
    }
  },
  "prompt": "Write 'print(test)' to src/test.py using the Write tool.",
  "assertions": [
    { "type": "file_not_exists", "path": "src/test.py" },
    { "type": "output_contains", "pattern": "PLAN MODE REQUIRED" }
  ],
  "timeout": 60
}
```

### Assertion Types

| Type | Description | Parameters |
|------|-------------|------------|
| `file_exists` | Assert file was created | `path` |
| `file_not_exists` | Assert file was NOT created | `path` |
| `file_contains` | Assert file contains pattern | `path`, `pattern` |
| `output_contains` | Assert stdout/stderr contains pattern | `pattern` |
| `output_not_contains` | Assert stdout/stderr does NOT contain | `pattern` |
| `state_field` | Assert state file field value | `file`, `field`, `expected` |
| `exit_code` | Assert Claude exited with code | `code` |

## State File

`.claude/harness-test-state.json`:

```json
{
  "started_at": "2026-01-30T12:00:00Z",
  "sandbox_id": "sandbox-xxx",
  "trigger": "auto",
  "harness_files_modified": [
    "config/hooks/plan-mode-enforcer.py"
  ],
  "test_cases_run": [
    {
      "name": "plan-mode-enforcer-blocks-code-write",
      "status": "passed",
      "duration_ms": 12345,
      "assertions": [
        { "name": "file_not_exists", "passed": true }
      ]
    }
  ],
  "summary": {
    "total": 4,
    "passed": 4,
    "failed": 0
  },
  "overall_status": "passed"
}
```

## Manual Usage

```bash
# Run all tests
/harness-test

# Run specific test
/harness-test --test plan-mode-enforcer-blocks-code-write

# Interactive mode (opens tmux for observation)
/harness-test --interactive

# Keep sandbox after tests (for debugging)
/harness-test --keep-sandbox
```

## Pre-defined Test Cases

| Test Case | What It Tests |
|-----------|---------------|
| `plan-mode-enforcer-blocks-code-write` | Edit/Write blocked before plan mode |
| `plan-mode-enforcer-allows-claude-dir` | Write to .claude/ always allowed |
| `skill-state-initializer-forge` | `/forge` creates forge-state.json |
| `auto-approval-in-forge-mode` | Tools auto-approved in autonomous mode |

## Harness Project Detection

Detected by checking for 2 of 3 markers:

1. **Directory structure**: `config/hooks/`, `config/skills/`, `config/settings.json` exist
2. **Git remote**: Contains "claude-code-toolkit"
3. **README.md**: Mentions "Claude Code Toolkit"

## Limitations

1. **Network access**: Sandbox doesn't isolate network (macOS limitation)
2. **API costs**: Each test runs real Claude session (uses haiku to minimize)
3. **Hook capture**: Hooks are captured at startup - must restart Claude to see changes
4. **Test coverage**: Some behaviors need manual observation

## Troubleshooting

### Tests fail with "hook not found"
- Sandbox symlinks point to `project/config/hooks/`
- Verify the hook file exists in `config/hooks/`
- Check `config/settings.json` references the hook correctly

### Tests pass but behavior differs in real session
- The sandbox uses a fresh Claude session
- State files from your real session don't carry over
- Verify test setup matches your expected initial state

### Sandbox creation fails
- Check if git worktree quota exceeded: `git worktree list`
- Clean up stale worktrees: `git worktree prune`
- Verify `/tmp/claude-sandboxes/` is writable
