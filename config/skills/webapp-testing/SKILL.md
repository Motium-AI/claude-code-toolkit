---
name: webapp-testing
description: Toolkit for testing and automating web applications. Prioritizes Claude Code Chrome integration for real browser testing. Falls back to Playwright scripts for CI/CD or headless scenarios.
license: Complete terms in LICENSE.txt
---

# Web Application Testing

Three approaches for testing web applications:

| Approach | When to Use | Capabilities |
|----------|-------------|--------------|
| **Surf CLI** | Autonomous mode (repair/melt), artifact generation | Deterministic, produces stop-hook-compatible artifacts |
| **Chrome Integration** | Interactive testing, debugging, authenticated apps | Real browser, login state, console/network access, GIF recording |
| **Playwright Scripts** | CI/CD, headless, programmatic automation | Scripted, reproducible, no GUI required |

## Decision Tree

```
User task → Is Autonomous Mode active?
    │       (check: ls .claude/autonomous-state.json 2>/dev/null)
    │
    ├─ Yes (Autonomous Mode) → Is Surf CLI installed?
    │       │                  (check: which surf)
    │       │
    │       ├─ Yes (Surf available) → Use Surf CLI
    │       │       │
    │       │       ├─ Run: python3 ~/.claude/hooks/surf-verify.py --urls ...
    │       │       ├─ Artifacts created in .claude/web-smoke/
    │       │       └─ Stop hook validates summary.json
    │       │
    │       └─ No (Surf not installed) → Fall back to Chrome MCP
    │               │
    │               └─ Note: web_testing_done requires manual proof without Surf
    │
    └─ No (Interactive Mode) → Is Claude Code running with --chrome flag?
            │
            ├─ Yes (Chrome available) → Use Chrome integration tools
            │       │
            │       ├─ Get tab context: tabs_context_mcp
            │       ├─ Create new tab: tabs_create_mcp
            │       ├─ Navigate: navigate tool
            │       ├─ Read page: read_page or find tools
            │       ├─ Interact: computer tool (click/type/screenshot)
            │       └─ Debug: read_console_messages, read_network_requests
            │
            └─ No (Chrome not available) → Fall back to Playwright
                    │
                    ├─ Static HTML? → Read file directly, write Playwright script
                    └─ Dynamic app? → Use with_server.py + Playwright script
```

## Autonomous Mode (repair/melt)

When autonomous mode is active, the stop hook requires proof of web testing via `.claude/web-smoke/summary.json`.

### Detection

```bash
# Check for autonomous mode state file
ls .claude/autonomous-state.json 2>/dev/null && echo "AUTONOMOUS MODE"
```

### Surf CLI Workflow (Preferred)

```bash
# 1. Verify Surf is installed
which surf && surf --version

# 2. Run verification (choose one)
python3 ~/.claude/hooks/surf-verify.py --urls "https://app.example.com" "https://app.example.com/dashboard"
# OR
python3 ~/.claude/hooks/surf-verify.py --from-topology

# 3. Check results
cat .claude/web-smoke/summary.json | jq '.passed'
```

**Artifacts produced** (in `.claude/web-smoke/`):
- `summary.json` - Pass/fail with metadata (stop hook validates this)
- `screenshots/` - Page screenshots
- `console.txt` - Browser console output
- `failing-requests.sh` - Curl commands to reproduce failures

### Chrome MCP Fallback

If Surf CLI is not available but Chrome MCP is:
1. Use Chrome MCP for interactive testing
2. The stop hook will require `web_testing_done: true` in completion checkpoint
3. Proof must include specific observation details (not just "tested and works")

---

## Chrome Integration (Preferred)

### Prerequisites

- Google Chrome browser
- Claude in Chrome extension (v1.0.36+)
- Claude Code CLI (v2.0.73+)
- Start Claude Code with: `claude --chrome`

### Core Pattern: Tab → Navigate → Read → Act

```
1. Get tab context (required first step)
   → tabs_context_mcp

2. Create or select tab
   → tabs_create_mcp (for new tab)

3. Navigate to target
   → navigate tool with URL

4. Read page state
   → read_page (accessibility tree)
   → find (natural language element search)
   → get_page_text (raw text extraction)

5. Interact
   → computer tool: click, type, screenshot, scroll
   → form_input: fill form fields

6. Debug (if needed)
   → read_console_messages (filter with pattern)
   → read_network_requests (filter by URL pattern)
```

### Example Workflows

**Test Local Web App:**
```
Navigate to localhost:3000, try submitting the login form with
invalid data, check if error messages appear correctly.
```

**Debug Console Errors:**
```
Open the dashboard page and check the console for any errors
when the page loads. Filter for "Error" or "Warning".
```

**Test Authenticated App:**
```
Open my Google Sheet at docs.google.com/spreadsheets/d/abc123,
add a new row with today's date and "Test entry".
```

**Record Demo GIF:**
```
Record a GIF showing the checkout flow from cart to confirmation.
```

### Chrome Tool Reference

| Tool | Purpose | Key Parameters |
|------|---------|----------------|
| `tabs_context_mcp` | Get available tabs | `createIfEmpty: true` |
| `tabs_create_mcp` | Create new tab | (none) |
| `navigate` | Go to URL | `url`, `tabId` |
| `read_page` | Get accessibility tree | `tabId`, `filter`, `depth` |
| `find` | Natural language element search | `query`, `tabId` |
| `computer` | Click/type/screenshot/scroll | `action`, `tabId`, `coordinate`/`ref` |
| `form_input` | Fill form fields | `ref`, `value`, `tabId` |
| `read_console_messages` | Read console logs | `tabId`, `pattern`, `onlyErrors` |
| `read_network_requests` | Read network activity | `tabId`, `urlPattern` |
| `gif_creator` | Record interactions | `action`, `tabId` |
| `javascript_tool` | Execute JS | `text`, `tabId` |

### Chrome Best Practices

1. **Always get tab context first** - Call `tabs_context_mcp` before other operations
2. **Use fresh tabs** - Create new tabs rather than reusing existing ones
3. **Filter console output** - Use `pattern` parameter to avoid verbose output
4. **Handle blockers** - Login pages, CAPTCHAs require manual intervention
5. **Avoid modal dialogs** - JavaScript alerts block browser events

### Production Config Testing (CRITICAL)

**Always test with production-like configuration, not local defaults.**

Before testing, verify environment:
```bash
# Check what config the app is using
grep -r "NEXT_PUBLIC_" .env*

# Start with production-like config
NEXT_PUBLIC_API_BASE="" NEXT_PUBLIC_WS_URL="wss://prod.example.com" npm run dev
```

**During browser testing, verify in Network tab:**
- ❌ No requests to `localhost:8000` or `localhost:3000` (indicates fallback)
- ❌ No unexpected 307 redirects (indicates trailing slash issues)
- ❌ No 401s on page load (indicates auth cascade)

**Console checks:**
```
# Filter for fallback indicators
read_console_messages with pattern: "localhost|fallback|undefined"
```

**Common failure patterns:**
| Symptom | Likely Cause |
|---------|--------------|
| WebSocket to localhost | Empty `NEXT_PUBLIC_WS_URL` triggering fallback |
| Immediate logout | 401 from proxy → `clearToken()` cascade |
| 307 redirects | FastAPI trailing slash redirect losing auth headers |

### Chrome Limitations

- Requires visible browser window (no headless mode)
- Modal dialogs (alert/confirm/prompt) block further actions
- Not supported on Brave, Arc, or WSL

---

## Playwright Fallback

Use when Chrome integration isn't available or for CI/CD pipelines.

### Helper Scripts

- `scripts/with_server.py` - Manages server lifecycle

**Always run with `--help` first** to see usage. Treat as black-box scripts.

### Server Lifecycle Pattern

**Single server:**
```bash
python scripts/with_server.py --server "npm run dev" --port 5173 -- python test.py
```

**Multiple servers:**
```bash
python scripts/with_server.py \
  --server "cd backend && python server.py" --port 3000 \
  --server "cd frontend && npm run dev" --port 5173 \
  -- python test.py
```

### Playwright Script Template

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    page.goto('http://localhost:5173')
    page.wait_for_load_state('networkidle')  # CRITICAL for JS apps

    # Reconnaissance
    page.screenshot(path='/tmp/inspect.png', full_page=True)
    buttons = page.locator('button').all()

    # Action
    page.click('text=Submit')

    browser.close()
```

### Playwright Best Practices

- Always `wait_for_load_state('networkidle')` before inspecting dynamic apps
- Use `sync_playwright()` for synchronous scripts
- Always close browser when done
- Use descriptive selectors: `text=`, `role=`, CSS, or IDs

---

## Comparison

| Capability | Chrome Integration | Playwright |
|------------|-------------------|------------|
| Authenticated apps | ✅ Uses browser login state | ❌ Requires credential handling |
| Console debugging | ✅ `read_console_messages` | ⚠️ Requires explicit capture |
| Network inspection | ✅ `read_network_requests` | ⚠️ Requires explicit capture |
| GIF recording | ✅ `gif_creator` | ❌ Not built-in |
| Headless mode | ❌ Not supported | ✅ Default |
| CI/CD pipelines | ❌ Requires GUI | ✅ Designed for it |
| Script portability | ❌ Claude-specific | ✅ Standard Python |

## Reference Files

- **examples/chrome/** - Chrome integration patterns
- **examples/playwright/** - Playwright script examples
- **scripts/with_server.py** - Server lifecycle helper
