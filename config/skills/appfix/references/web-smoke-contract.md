# Web Smoke Contract

Defines the artifact schema for deterministic web verification. The stop hook validates these artifacts exist and pass conditions.

## Required Artifacts

After web verification, the following must exist:

```
.claude/web-smoke/
├── summary.json          # Pass/fail + metadata (REQUIRED)
├── screenshots/          # At least 1 screenshot (REQUIRED)
│   └── *.png
├── console.txt           # Browser console output
├── network.jsonl         # All requests (optional, for debugging)
├── failing-requests.sh   # Curl repros for 4xx/5xx (if any)
└── waivers.json          # Expected errors to ignore (optional)
```

## summary.json Schema

```json
{
  "passed": true,
  "tested_at": "2025-01-25T10:00:00Z",
  "tested_at_version": "abc1234",
  "urls_tested": ["https://staging.example.com/dashboard"],
  "screenshot_count": 3,
  "console_errors": 0,
  "network_errors": 0,
  "content_errors": 0,
  "failing_requests": [],
  "content_errors_found": [],
  "waivers_applied": 0
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `passed` | bool | yes | Overall pass/fail status |
| `tested_at` | string | yes | ISO 8601 timestamp |
| `tested_at_version` | string | yes | Git commit hash when tested |
| `urls_tested` | array | yes | URLs that were verified |
| `screenshot_count` | int | yes | Number of screenshots captured |
| `console_errors` | int | yes | Console errors after waivers |
| `network_errors` | int | yes | Network errors after waivers |
| `content_errors` | int | yes | Page content errors (error text in DOM) |
| `failing_requests` | array | no | List of failed request details |
| `content_errors_found` | array | no | List of error patterns found in page content |
| `waivers_applied` | int | no | Number of errors filtered by waivers |

## Pass Conditions

The stop hook requires ALL of these:

1. `passed: true`
2. `screenshot_count >= 1`
3. `console_errors == 0` (after waivers applied)
4. `network_errors == 0` (after waivers applied)
5. `content_errors == 0` (after waivers applied)
6. `tested_at_version == current_git_version` (not stale)

## Waiver File Schema

For expected errors (third-party, known issues), create `.claude/web-smoke/waivers.json`:

```json
{
  "console_patterns": [
    "Third-party cookie.*deprecated",
    "analytics\\.js.*blocked",
    "\\[React DevTools\\]"
  ],
  "network_patterns": [
    "GET.*googletagmanager\\.com.*4\\d\\d",
    "GET.*facebook\\.com.*blocked"
  ],
  "content_patterns": [
    "maintenance mode",
    "demo error"
  ],
  "reason": "Third-party analytics blocked by browser privacy settings"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `console_patterns` | array | Regex patterns to ignore in console |
| `network_patterns` | array | Regex patterns to ignore in network errors |
| `content_patterns` | array | Regex patterns to ignore in page content (error text) |
| `reason` | string | Why these errors are expected |

Patterns are applied as regex filters. Matching errors are:
- Excluded from `console_errors` / `network_errors` / `content_errors` counts
- Counted in `waivers_applied`
- Still logged in raw artifacts for debugging

## URLs to Test

URLs are defined in `service-topology.md` under the `web_smoke_urls` key:

```yaml
web_smoke_urls:
  - https://staging.example.com/
  - https://staging.example.com/dashboard
  - https://staging.example.com/login
```

If `web_smoke_urls` is not defined, the verification script should fail with a clear error message.

## Verification Methods

### Primary: Surf CLI

```bash
# Install if not present
which surf || npm install -g @nicobailon/surf-cli

# Run verification
python3 ~/.claude/hooks/surf-verify.py --urls "https://staging.example.com/dashboard"
```

### Fallback: Chrome MCP

When Surf CLI is not available or fails:
1. Use `mcp__claude-in-chrome__navigate` to visit each URL
2. Use `mcp__claude-in-chrome__computer action=screenshot` to capture state
3. Use `mcp__claude-in-chrome__read_console_messages` for console output
4. Manually create `summary.json` with results

The stop hook validates artifacts regardless of which method produced them.

## Staleness Detection

Artifacts become stale when code changes after verification:

```
tested_at_version: abc1234
current_version:   def5678  ← Different!
→ STALE: Must re-verify
```

The stop hook automatically rejects stale artifacts and instructs re-verification.
