---
description: Test new features using Chrome browser automation
---

Use ultrathink to thoroughly plan and execute test scenarios.

## Autonomous Mode (repair/melt)

When running in autonomous mode, use Surf CLI for deterministic artifact generation that the stop hook validates.

### Step 1: Check for Autonomous Mode

```bash
# Check if autonomous mode is active
ls .claude/autonomous-state.json 2>/dev/null && echo "AUTONOMOUS MODE ACTIVE"
```

**If autonomous mode is active, follow Steps 2-4. Otherwise, skip to "Overview" section.**

### Step 2: Check for Surf CLI

```bash
which surf && surf --version || echo "FALLBACK: Use Chrome MCP"
```

### Step 3: Run Surf Verification

```bash
# With explicit URLs
python3 ~/.claude/hooks/surf-verify.py --urls "https://your-app.com" "https://your-app.com/dashboard"

# Or read from service-topology.md
python3 ~/.claude/hooks/surf-verify.py --from-topology
```

### Step 4: Verify Artifacts

```bash
cat .claude/web-smoke/summary.json | jq '.passed'
```

**Only fall back to Chrome MCP if:**
- Surf CLI is not installed (`which surf` fails)
- Interactive debugging is needed (console inspection, step-by-step actions)

**Artifacts produced by Surf CLI** (in `.claude/web-smoke/`):
- `summary.json` - Pass/fail status with metadata (stop hook validates this)
- `screenshots/` - Page screenshots
- `console.txt` - Browser console output
- `failing-requests.sh` - Curl commands to reproduce failures

---

## Overview

Test the features you just built using the webapp-testing skill. This command prioritizes Chrome integration for real browser testing with console/network access and debugging capabilities.

## Prerequisites

Before running this command, ensure:
- Claude Code was started with `claude --chrome` flag
- Chrome browser is running with Claude in Chrome extension (v1.0.36+)
- For authenticated testing, credentials should be in the project's `.env` file

## Authentication Handling

If login is required:
1. Read the project's `.env` file to find relevant credentials
2. Look for variables like `TEST_EMAIL`, `TEST_PASSWORD`, `LOGIN_USERNAME`, etc.
3. Navigate to the login page and authenticate before testing protected routes

**Never hardcode credentials in test scripts.** Always read from `.env`.

## Testing Workflow

### 1. Get Browser Context

First, establish connection to Chrome:
```
Call tabs_context_mcp to get available tabs
If no tabs exist, create one with tabs_create_mcp
```

### 2. Navigate to Target

Navigate to the feature being tested:
```
For local dev: http://localhost:3000 (or the app's dev port)
For staging: use the staging URL from .env
```

### 3. Read Page State

Before interacting, understand the page:
- Use `read_page` for accessibility tree (element refs)
- Use `find` for natural language element search ("login button", "email input")
- Use `get_page_text` for raw text content

### 4. Execute Test Actions

Interact with the page:
- Click elements: `computer` tool with `left_click` action
- Type text: `computer` tool with `type` action
- Fill forms: `form_input` tool with element ref
- Take screenshots: `computer` tool with `screenshot` action

### 5. Verify Results

Check that the feature works correctly:
- Take screenshots before/after actions
- Check console for errors: `read_console_messages` with `pattern: "Error|Warning|error"`
- Check network requests: `read_network_requests` for API call validation
- Verify page content changed as expected

## Common Test Scenarios

### Form Submission
1. Navigate to page with form
2. Find form inputs using `read_page` or `find`
3. Fill each field with `form_input`
4. Click submit button
5. Verify success message or redirect

### Error Handling
1. Submit form with invalid data
2. Verify error messages appear
3. Check that form state is preserved
4. Verify error messages clear on valid input

### Navigation Flow
1. Start at page A
2. Click navigation element
3. Verify page B loads correctly
4. Check URL changed appropriately

### API Integration
1. Trigger action that makes API call
2. Use `read_network_requests` to verify request was made
3. Check request URL, method, and payload
4. Verify response handling in UI

## Debugging Tips

### Console Errors
```
Use read_console_messages with:
- pattern: "Error|Warning" for general issues
- pattern: "localhost|fallback" for config issues
- pattern: "[AppName]" for app-specific logs
- onlyErrors: true for just errors/exceptions
```

### Network Issues
```
Use read_network_requests with:
- urlPattern: "/api/" for API calls
- urlPattern: "localhost:8000" to detect accidental local calls
- Look for 401, 403, 500 status codes
```

### Production Config Verification
Before marking tests as passed, verify:
- No requests to `localhost` in production mode
- No 307 redirects (trailing slash issues)
- No unexpected 401s on page load
- WebSocket connections use correct URL

## Common Failure Patterns

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| WebSocket to localhost | Empty WS URL env var | Set `NEXT_PUBLIC_WS_URL` |
| Immediate logout | 401 cascade from proxy | Check proxy config, auth headers |
| 307 redirects | FastAPI trailing slash | Add trailing slashes to routes |
| CORS errors | Missing CORS headers | Configure backend CORS policy |
| Blank page | JS error on load | Check console for errors |

## GIF Recording

For demo or bug report GIFs:
1. Start recording: `gif_creator` with `action: start_recording`
2. Take initial screenshot
3. Perform the actions to record
4. Take final screenshot
5. Stop recording: `gif_creator` with `action: stop_recording`
6. Export: `gif_creator` with `action: export`, `download: true`

## Limitations

- Requires visible Chrome window (no headless)
- Modal dialogs (alert/confirm) block further actions
- CAPTCHAs require manual intervention
- Some sites block automated testing
