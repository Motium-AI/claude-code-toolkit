# Maestro MCP Contract

Defines the requirements for using Maestro MCP in the `/mobileappfix` workflow.

## Purpose

The Maestro MCP provides programmatic control over Maestro for mobile E2E testing. It enables:
- Full user journey orchestration
- Screenshot capture and analysis
- Element inspection and interaction
- Automated test execution with structured results

**Using Maestro MCP is MANDATORY for `/mobileappfix`.** Do not use bash `maestro` commands.

## Required MCP Tools

The following MCP tools must be available (pattern: `mcp__maestro__*`):

| Tool | Purpose | Required |
|------|---------|----------|
| `mcp__maestro__run_flow` | Execute a Maestro flow file | Yes |
| `mcp__maestro__hierarchy` | Get element accessibility tree | Yes |
| `mcp__maestro__screenshot` | Capture current screen | Yes |
| `mcp__maestro__tap` | Tap an element by testID or coordinates | Yes |
| `mcp__maestro__input` | Enter text into focused element | Yes |
| `mcp__maestro__wait` | Wait for element or condition | Yes |
| `mcp__maestro__swipe` | Swipe gesture | Recommended |
| `mcp__maestro__scroll` | Scroll in direction | Recommended |
| `mcp__maestro__back` | Press back button | Recommended |

## Pre-Flight Check

Before starting `/mobileappfix`, verify MCP availability:

```
1. Check for mcp__maestro__run_flow tool
2. If not found: STOP and request user configure Maestro MCP
3. If found: Proceed with workflow
```

### Error Message (MCP Not Found)

```
Maestro MCP server is required for /mobileappfix but not detected.

To configure Maestro MCP:
1. Install the Maestro MCP server (npm install -g @anthropic/maestro-mcp)
2. Add to your MCP settings (~/.claude/mcp.json):
   {
     "mcpServers": {
       "maestro": {
         "command": "maestro-mcp",
         "args": ["--app-id", "your.app.id"]
       }
     }
   }
3. Restart Claude Code

For more information: https://docs.maestro.mobile.dev/mcp
```

## Tool Usage Examples

### Running a Flow

```
mcp__maestro__run_flow(
  flow: ".maestro/journeys/J2-returning-user-login.yaml",
  output_dir: ".claude/maestro-smoke/",
  env: {
    "TEST_USER_EMAIL": "test@example.com",
    "TEST_USER_PASSWORD": "${MAESTRO_TEST_PASSWORD}"
  }
)
```

Returns:
```json
{
  "passed": true,
  "duration_ms": 45000,
  "screenshots": [
    ".claude/maestro-smoke/screenshots/j2_01_app_launched.png",
    ".claude/maestro-smoke/screenshots/j2_07_stepping_stones_visible.png"
  ],
  "steps_completed": 12,
  "steps_total": 12
}
```

### Inspecting Hierarchy

```
mcp__maestro__hierarchy()
```

Returns accessibility tree for element identification:
```json
{
  "elements": [
    {
      "id": "login_button",
      "type": "Button",
      "text": "Log In",
      "bounds": {"x": 100, "y": 500, "width": 200, "height": 50}
    }
  ]
}
```

### Capturing Screenshot

```
mcp__maestro__screenshot(
  filename: "current_state.png",
  output_dir: ".claude/maestro-smoke/screenshots/"
)
```

### Tapping Element

```
mcp__maestro__tap(
  element_id: "login_button"
)
// OR by coordinates:
mcp__maestro__tap(
  x: 200,
  y: 525
)
```

### Entering Text

```
mcp__maestro__input(
  text: "test@example.com"
)
```

### Waiting for Element

```
mcp__maestro__wait(
  element_id: "dashboard_screen",
  timeout_ms: 10000
)
```

## Full Journey Requirement

**Single test files are NOT sufficient.** The MCP must execute complete user journeys.

### Minimum Journey Set

| Journey | File | What It Validates |
|---------|------|-------------------|
| J2 | `J2-returning-user-login.yaml` | Login → Main app access |
| J3 | `J3-main-app-navigation.yaml` | All tabs and core screens |

### Running Multiple Journeys

```
// Run J2 first
result_j2 = mcp__maestro__run_flow(
  flow: ".maestro/journeys/J2-returning-user-login.yaml"
)

// Then run J3
result_j3 = mcp__maestro__run_flow(
  flow: ".maestro/journeys/J3-main-app-navigation.yaml"
)

// Both must pass
all_passed = result_j2.passed && result_j3.passed
```

## Artifact Generation

The MCP automatically generates artifacts in `.claude/maestro-smoke/`:

```
.claude/maestro-smoke/
├── summary.json          # Aggregated results from all flows
├── screenshots/          # All captured screenshots
│   ├── j2_01_*.png
│   ├── j2_07_*.png
│   └── ...
└── flows/                # Individual flow results
    ├── J2-returning-user-login.json
    └── J3-main-app-navigation.json
```

## Checkpoint Integration

When creating the completion checkpoint, include MCP evidence:

```json
{
  "self_report": {
    "maestro_mcp_used": true,
    "full_journeys_validated": true,
    "maestro_tests_passed": true,
    "maestro_tests_passed_at_version": "abc1234"
  },
  "evidence": {
    "mcp_tools_used": [
      "mcp__maestro__run_flow",
      "mcp__maestro__hierarchy"
    ],
    "maestro_flows_tested": [
      "J2-returning-user-login.yaml",
      "J3-main-app-navigation.yaml"
    ]
  }
}
```

## Why MCP Over Bash?

| Aspect | Maestro MCP | Bash `maestro test` |
|--------|-------------|---------------------|
| Structured output | JSON results | Text parsing required |
| Screenshot access | Direct in response | File system lookup |
| Element inspection | `hierarchy` tool | Separate command |
| Error details | Structured errors | Exit codes only |
| Integration | Claude-native | Shell subprocess |
| Interactivity | Real-time control | Batch only |

## Fallback Behavior

If Maestro MCP is unavailable and the user explicitly requests a fallback:

1. Warn: "Maestro MCP not available. Using bash fallback (less reliable)."
2. Use bash commands as documented in mobile-topology.md
3. Manually create artifacts in `.claude/maestro-smoke/`
4. Set `maestro_mcp_used: false` in checkpoint

**This fallback should be rare.** Always prefer MCP.
