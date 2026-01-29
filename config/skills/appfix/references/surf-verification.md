# Browser Verification (Surf CLI)

## Order of Operations

1. **Try Surf CLI first** (automatic artifact generation)
2. **ONLY if Surf CLI fails** → Fall back to Chrome MCP

## Surf CLI Verification

```bash
# Check availability
which surf && echo "Available" || echo "FALLBACK needed"

# Run verification
python3 ~/.claude/hooks/surf-verify.py --urls "https://staging.example.com/dashboard"

# Or from topology
python3 ~/.claude/hooks/surf-verify.py --from-topology
```

## Check Artifacts

```bash
ls -la .claude/web-smoke/
# Expected: summary.json, screenshots/, console.txt
cat .claude/web-smoke/summary.json
# Should show: "passed": true
```

## If Verification Fails

1. Check `.claude/web-smoke/summary.json` for errors
2. Check `.claude/web-smoke/console.txt` for console errors
3. **Fix the issues** and re-run Surf
4. Do NOT bypass by using Chrome MCP

## Waiver File (third-party errors)

```json
// .claude/web-smoke/waivers.json
{
  "console_patterns": ["analytics\\.js.*blocked"],
  "network_patterns": ["GET.*googletagmanager\\.com.*4\\d\\d"],
  "reason": "Third-party analytics blocked by privacy settings"
}
```

## Chrome MCP Fallback

Only if Surf CLI is unavailable:
```
mcp__claude-in-chrome__navigate → app URL
mcp__claude-in-chrome__computer action=screenshot → capture state
mcp__claude-in-chrome__read_console_messages → check errors
```

When using Chrome MCP, manually create `.claude/web-smoke/summary.json` and set `web_testing_done: true` with `web_testing_done_at_version`.
