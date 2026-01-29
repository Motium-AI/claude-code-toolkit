---
name: mobileappfix
description: Autonomous mobile app debugging using Maestro MCP for E2E tests. Mobile equivalent of /appfix.
---

# Autonomous Mobile App Debugging (/mobileappfix)

Autonomous debugging for React Native/Expo apps. Iterates until Maestro E2E tests pass.

> **Note**: `/mobileappfix` uses the same `appfix-state.json` as `/appfix`.
> For web applications, use `/appfix` instead.

## Triggers

- `/mobileappfix`
- "fix the mobile app"
- "Maestro tests failing"
- "app crashes on startup"

## CRITICAL: Maestro MCP Required

**YOU MUST USE MAESTRO MCP FOR ALL TESTING AND VALIDATION.**

This skill requires a Maestro MCP server for test execution. The MCP provides:
- Full user journey orchestration
- Screenshot capture and analysis
- Element inspection and interaction
- Test result aggregation

**DO NOT use bash `maestro test` commands.** Always use Maestro MCP tools.

### Pre-Flight: Verify Maestro MCP Available

Before any testing, verify Maestro MCP tools are available:

```
Required MCP tools (pattern: mcp__maestro__*):
- mcp__maestro__run_flow      - Execute Maestro flows
- mcp__maestro__hierarchy     - Inspect element tree
- mcp__maestro__screenshot    - Capture screenshots
- mcp__maestro__tap           - Tap elements
- mcp__maestro__input         - Enter text
- mcp__maestro__wait          - Wait for elements
```

**If Maestro MCP is not available, STOP and inform the user:**
> "Maestro MCP server is required for /mobileappfix. Please configure the Maestro MCP in your MCP settings before proceeding."

## CRITICAL: Autonomous Execution

**THIS WORKFLOW IS 100% AUTONOMOUS. YOU MUST:**

1. **NEVER ask for confirmation** - No "Should I rebuild?", "Should I commit?"
2. **Auto-commit and push** - When fixes are applied, commit immediately
3. **Auto-rebuild** - Trigger builds without asking
4. **Complete verification** - Run Maestro tests via MCP on simulator
5. **Fill out checkpoint honestly** - The stop hook checks your booleans

**Only stop when the checkpoint can pass.**

## Workflow

```
┌─────────────────────────────────────────────────────────────────────┐
│  PHASE 0: PRE-FLIGHT                                                │
│     └─► Verify Maestro MCP available (mcp__maestro__* tools)        │
│     └─► If no MCP: STOP and request user configure Maestro MCP      │
│     └─► Check simulator: xcrun simctl list devices available        │
│     └─► Read mobile-topology.md for project config                  │
├─────────────────────────────────────────────────────────────────────┤
│  PHASE 1: PLAN (First Iteration Only)                               │
│     └─► EnterPlanMode                                               │
│     └─► Explore: app structure, .maestro/ tests, recent commits     │
│     └─► ExitPlanMode                                                │
├─────────────────────────────────────────────────────────────────────┤
│  PHASE 2: FIX-VERIFY LOOP (via Maestro MCP)                         │
│     └─► Run FULL user journeys via MCP (not single tests)           │
│     └─► Minimum: J2 + J3 journeys (login + navigation)              │
│     └─► If pass: Update checkpoint, stop                            │
│     └─► If fail: Diagnose via MCP hierarchy, fix code, re-run       │
├─────────────────────────────────────────────────────────────────────┤
│  PHASE 3: COMPLETE                                                  │
│     └─► Commit: git commit -m "mobileappfix: [description]"         │
│     └─► Create checkpoint with honest booleans                      │
│     └─► Stop (hook validates checkpoint)                            │
└─────────────────────────────────────────────────────────────────────┘
```

## Required: Full User Journey Validation

**Single test files are NOT sufficient.** You MUST validate complete user journeys.

### Minimum Journey Set (MANDATORY)

| Journey | Flow File | Validates |
|---------|-----------|-----------|
| J2 | `J2-returning-user-login.yaml` | Login → Main app access |
| J3 | `J3-main-app-navigation.yaml` | All tabs and core screens |

### Full Journey Set (Recommended)

| Journey | Flow File | Validates |
|---------|-----------|-----------|
| J1 | `J1-new-user-onboarding.yaml` | Registration → Onboarding |
| J2 | `J2-returning-user-login.yaml` | Login flow |
| J3 | `J3-main-app-navigation.yaml` | Core navigation |
| J4 | `J4-exercise-completion.yaml` | Primary feature flow |
| J5 | `J5-profile-settings.yaml` | Profile and settings |

### Running Journeys via MCP

```
# Use Maestro MCP tools, NOT bash commands:
mcp__maestro__run_flow(flow: ".maestro/journeys/J2-returning-user-login.yaml")
mcp__maestro__run_flow(flow: ".maestro/journeys/J3-main-app-navigation.yaml")

# DO NOT USE:
# maestro test .maestro/journeys/J2-*.yaml  ❌ (bash command)
```

## MCP vs Bash Commands

**ALWAYS prefer MCP tools over bash commands:**

| Action | Maestro MCP (Required) | Bash (Fallback Only) |
|--------|------------------------|----------------------|
| Run test | `mcp__maestro__run_flow` | `maestro test` ❌ |
| Inspect UI | `mcp__maestro__hierarchy` | `maestro hierarchy` ❌ |
| Take screenshot | `mcp__maestro__screenshot` | N/A |
| Tap element | `mcp__maestro__tap` | N/A |
| Enter text | `mcp__maestro__input` | N/A |

### Simulator Commands (Bash OK)

```bash
# These bash commands are acceptable (not Maestro):
xcrun simctl boot "iPhone 15 Pro"
open -a Simulator
npm start --reset-cache
npm run ios
npm run prebuild:clean && cd ios && pod install && cd ..
```

## Completion Checkpoint

Before stopping, create `.claude/completion-checkpoint.json`:

```json
{
  "self_report": {
    "code_changes_made": true,
    "maestro_mcp_used": true,
    "full_journeys_validated": true,
    "maestro_tests_passed": true,
    "maestro_tests_passed_at_version": "abc1234",
    "linters_pass": true,
    "linters_pass_at_version": "abc1234",
    "is_job_complete": true
  },
  "reflection": {
    "what_was_done": "Fixed auth guard timing, login flow works",
    "what_remains": "none"
  },
  "evidence": {
    "mcp_tools_used": ["mcp__maestro__run_flow", "mcp__maestro__hierarchy"],
    "maestro_flows_tested": [
      "J2-returning-user-login.yaml",
      "J3-main-app-navigation.yaml"
    ],
    "platform": "ios",
    "device": "iPhone 15 Pro Simulator"
  }
}
```

<reference path="references/checkpoint-schema.md" />

## Maestro MCP Artifacts

The Maestro MCP automatically saves test evidence to `.claude/maestro-smoke/`.

**MCP tools handle artifact creation** - no manual bash commands needed:

```
mcp__maestro__run_flow(flow: "...", output_dir: ".claude/maestro-smoke/")
```

<reference path="references/maestro-mcp-contract.md" />
<reference path="references/maestro-smoke-contract.md" />

## Environment Variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `TEST_USER_EMAIL` | Yes | E2E test user |
| `MAESTRO_TEST_PASSWORD` | Yes | E2E test password |
| `ANDROID_HOME` | For Android | SDK path |

## Exit Conditions

| Condition | Result |
|-----------|--------|
| All booleans true, `what_remains: "none"` | SUCCESS - stop allowed |
| Any required boolean false | BLOCKED - continue working |
| Missing credentials | ASK USER (once) |

## Reference Files

| Reference | Purpose |
|-----------|---------|
| [maestro-mcp-contract.md](references/maestro-mcp-contract.md) | **Maestro MCP requirements and tools** |
| [mobile-topology.md](references/mobile-topology.md) | Project config, devices, test commands |
| [checkpoint-schema.md](references/checkpoint-schema.md) | Full checkpoint field reference |
| [maestro-smoke-contract.md](references/maestro-smoke-contract.md) | Artifact schema |
| [debugging-rubric.md](references/debugging-rubric.md) | Mobile-specific troubleshooting |
| [validation-tests-contract.md](references/validation-tests-contract.md) | Fix-specific test requirements |
