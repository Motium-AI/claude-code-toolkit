# Maestro MCP Contract

Defines the requirements for using Maestro MCP in the `/mobileappfix` workflow.

## Purpose

The Maestro MCP provides programmatic control over Maestro for mobile E2E testing. It enables:
- Full user journey orchestration
- Screenshot capture and analysis
- Element inspection and interaction
- Automated test execution with structured results

**Using Maestro MCP is MANDATORY for `/mobileappfix`.** Do not use bash `maestro` commands.

## Important: Tool Naming

The actual MCP tool names include the server suffix. For the forked Maestro:

```
Pattern: mcp__maestro-oli4-mcp__<tool_name>
```

**Examples:**
- `mcp__maestro-oli4-mcp__run_flow`
- `mcp__maestro-oli4-mcp__take_screenshot`
- `mcp__maestro-oli4-mcp__list_devices`

See [maestro-mcp-setup.md](./maestro-mcp-setup.md) for complete setup instructions.

## Required MCP Tools

| Tool | Purpose | Required |
|------|---------|----------|
| `mcp__maestro-oli4-mcp__list_devices` | List available devices | Yes |
| `mcp__maestro-oli4-mcp__run_flow` | Execute inline Maestro commands | Yes |
| `mcp__maestro-oli4-mcp__run_flow_files` | Execute Maestro flow YAML files | Yes |
| `mcp__maestro-oli4-mcp__inspect_view_hierarchy` | Get element accessibility tree | Yes |
| `mcp__maestro-oli4-mcp__take_screenshot` | Capture current screen | Yes |
| `mcp__maestro-oli4-mcp__tap_on` | Tap element by selector | Yes |
| `mcp__maestro-oli4-mcp__input_text` | Enter text into element | Yes |
| `mcp__maestro-oli4-mcp__launch_app` | Launch application | Recommended |
| `mcp__maestro-oli4-mcp__back` | Press back button | Recommended |
| `mcp__maestro-oli4-mcp__start_device` | Start simulator/emulator | Recommended |

## Pre-Flight Check

Before starting `/mobileappfix`, verify MCP availability:

```
1. ToolSearch(query: "maestro")
2. If no mcp__maestro-oli4-mcp__* tools found: STOP
3. Call mcp__maestro-oli4-mcp__list_devices()
4. If no connected devices: Guide user to start one
5. If Android device: Verify Maestro driver is installed (see setup guide)
```

### Error Message (MCP Not Found)

```
Maestro MCP server is required for /mobileappfix but not detected.

To configure Maestro MCP, see:
~/.claude/skills/mobileappfix/references/maestro-mcp-setup.md

Quick summary:
1. Clone forked Maestro: git clone https://github.com/olivier-motium/Maestro.git
2. Checkout fix branch: git checkout oli4-combined-fixes
3. Build: ./gradlew :maestro-cli:installDist
4. Add to .mcp.json with path to built binary
5. Restart Claude Code

For Android, also run the setup script to install driver APKs.
```

### Error Message (Android UNAVAILABLE)

```
Maestro MCP cannot connect to Android emulator.

This usually means the Maestro driver APKs are not installed.

Run these commands:
ADB=$HOME/Library/Android/sdk/platform-tools/adb
MAESTRO_DIR=~/Desktop/motium_github/maestro-oli4

$ADB install -r $MAESTRO_DIR/maestro-client/build/resources/main/maestro-server.apk
$ADB install -r $MAESTRO_DIR/maestro-client/build/resources/main/maestro-app.apk
$ADB forward tcp:7001 tcp:7001
$ADB shell am instrument -w dev.mobile.maestro.test/androidx.test.runner.AndroidJUnitRunner &

Wait 3 seconds, then retry.
```

## Tool Usage Examples

### Listing Devices

```
mcp__maestro-oli4-mcp__list_devices()
```

Returns:
```json
{
  "devices": [
    {
      "device_id": "emulator-5554",
      "name": "emulator-5554",
      "platform": "android",
      "type": "emulator",
      "connected": true
    },
    {
      "device_id": "E720817F-...",
      "name": "iPhone 16 Pro - iOS 18.3",
      "platform": "ios",
      "type": "simulator",
      "connected": true
    }
  ]
}
```

### Taking Screenshot

```
mcp__maestro-oli4-mcp__take_screenshot(
  device_id: "emulator-5554"
)
```

Returns an image of the current device screen.

### Inspecting View Hierarchy

```
mcp__maestro-oli4-mcp__inspect_view_hierarchy(
  device_id: "emulator-5554"
)
```

Returns CSV-formatted element tree with bounds, text, and IDs.

### Running Inline Commands

```
mcp__maestro-oli4-mcp__run_flow(
  device_id: "emulator-5554",
  flow_yaml: "- tapOn: \"Log In\""
)
```

### Running Flow Files

```
mcp__maestro-oli4-mcp__run_flow_files(
  device_id: "emulator-5554",
  flow_files: "/path/to/project/.maestro/journeys/J2-returning-user-login.yaml"
)
```

**IMPORTANT**: Use absolute paths for flow files. Relative paths may fail.

### Tapping Elements

```
mcp__maestro-oli4-mcp__tap_on(
  device_id: "emulator-5554",
  text: "Log In"
)
```

Or by element ID:
```
mcp__maestro-oli4-mcp__tap_on(
  device_id: "emulator-5554",
  id: "login_button"
)
```

### Entering Text

```
mcp__maestro-oli4-mcp__input_text(
  device_id: "emulator-5554",
  text: "test@example.com"
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
mcp__maestro-oli4-mcp__run_flow_files(
  device_id: "emulator-5554",
  flow_files: "/abs/path/.maestro/journeys/J2-returning-user-login.yaml"
)

// Then run J3
mcp__maestro-oli4-mcp__run_flow_files(
  device_id: "emulator-5554",
  flow_files: "/abs/path/.maestro/journeys/J3-main-app-navigation.yaml"
)
```

## Artifact Generation

Create test artifacts in `.claude/maestro-smoke/`:

```bash
mkdir -p .claude/maestro-smoke/screenshots
```

Screenshots from `take_screenshot` should be saved there with descriptive names.

### summary.json Schema

```json
{
  "passed": true,
  "tested_at": "2026-01-31T10:00:00Z",
  "tested_at_version": "abc1234",
  "platform": "android",
  "device": "emulator-5554",
  "app_id": "be.revonc.mobileapp",
  "maestro_version": "2.1.0",
  "flows_executed": [
    {
      "name": "J2-returning-user-login.yaml",
      "passed": true,
      "screenshots": ["j2_login.png", "j2_main_app.png"]
    }
  ],
  "total_flows": 2,
  "passed_flows": 2,
  "failed_flows": 0
}
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
      "mcp__maestro-oli4-mcp__run_flow_files",
      "mcp__maestro-oli4-mcp__take_screenshot",
      "mcp__maestro-oli4-mcp__inspect_view_hierarchy"
    ],
    "maestro_flows_tested": [
      "J2-returning-user-login.yaml",
      "J3-main-app-navigation.yaml"
    ],
    "platform": "android",
    "device": "emulator-5554"
  }
}
```

## Why MCP Over Bash?

| Aspect | Maestro MCP | Bash `maestro test` |
|--------|-------------|---------------------|
| Structured output | JSON/images | Text parsing required |
| Screenshot access | Direct in response | File system lookup |
| Element inspection | `inspect_view_hierarchy` | Separate command |
| Error details | Structured errors | Exit codes only |
| Integration | Claude-native | Shell subprocess |
| Interactivity | Real-time control | Batch only |

## Fallback Behavior

If Maestro MCP is unavailable after setup attempts:

1. Document the specific error in checkpoint
2. Use bash commands as last resort
3. Set `maestro_mcp_used: false` in checkpoint
4. Note the fallback reason in `reflection.what_was_done`

**This fallback should be rare.** Always prefer MCP.

## Related Documentation

- [maestro-mcp-setup.md](./maestro-mcp-setup.md) - **Complete setup instructions**
- [maestro-smoke-contract.md](./maestro-smoke-contract.md) - Artifact schema
- [mobile-topology.md](./mobile-topology.md) - Project config and devices
