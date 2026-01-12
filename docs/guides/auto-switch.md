# Auto-Switch: Multiple Claude Max Accounts

Automatically switch between Claude Max accounts when one hits rate limits, preserving conversation context.

## Prerequisites

- Two separate Anthropic accounts (different email addresses)
- Both accounts with active Claude Max subscriptions
- Python 3.10+

## Quick Start

### 1. Install

```bash
cd prompts/config/scripts/claude-auto-switch
./install.sh
```

### 2. Setup Accounts

Create separate config directories:

```bash
mkdir -p ~/.claude-max-1 ~/.claude-max-2
```

Authenticate each account (requires logging in with different Anthropic accounts):

```bash
# Account 1
CLAUDE_CONFIG_DIR=~/.claude-max-1 claude
# Complete login, then exit with Ctrl+C

# Account 2
CLAUDE_CONFIG_DIR=~/.claude-max-2 claude
# Complete login, then exit with Ctrl+C
```

### 3. Symlink Settings and Sessions

Share your MCP servers, hooks, env vars, and sessions across accounts:

```bash
# Share settings (MCP servers, hooks, env vars)
ln -sf ~/.claude/settings.json ~/.claude-max-1/settings.json
ln -sf ~/.claude/settings.json ~/.claude-max-2/settings.json

# Share sessions (enables --resume across accounts)
rm -rf ~/.claude-max-1/projects ~/.claude-max-2/projects
ln -sf ~/.claude/projects ~/.claude-max-1/projects
ln -sf ~/.claude/projects ~/.claude-max-2/projects
```

This ensures all accounts share:
- MCP servers and settings
- Session storage (allows resuming sessions on any account)

### 4. Add Shell Alias

Add to `~/.zshrc` or `~/.bashrc`:

```bash
alias claude='python3 ~/.claude/scripts/claude-auto-switch/switch.py'
```

Reload:

```bash
source ~/.zshrc
```

### 4. Use Normally

```bash
claude  # Auto-switches when rate limited
```

## How It Works

```
┌─────────────────────────────────────────────────────────────────┐
│                     Auto-Switch Flow                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. Start claude with Account 1                                  │
│     └─→ CLAUDE_CONFIG_DIR=~/.claude-max-1                       │
│                                                                  │
│  2. Capture session ID from startup output                       │
│     └─→ UUID pattern: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx      │
│                                                                  │
│  3. Monitor stdout for rate limit patterns                       │
│     └─→ "usage limit", "rate limit", "capacity exceeded"        │
│                                                                  │
│  4. On detection:                                                │
│     ├─→ Save session ID to ~/.claude/.auto-switch-session       │
│     ├─→ Terminate current session                               │
│     └─→ Launch Account 2 with --resume <session-id>             │
│                                                                  │
│  5. Continue conversation on Account 2                           │
│     └─→ Same session, full context preserved                    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Key**: Because accounts share the projects directory via symlink, `--resume` works across accounts with full session continuity.

## Configuration

Edit `~/.claude/scripts/claude-auto-switch/config.json`:

```json
{
  "accounts": [
    {
      "name": "primary",
      "config_dir": "~/.claude-max-1",
      "description": "Primary Claude Max account"
    },
    {
      "name": "secondary",
      "config_dir": "~/.claude-max-2",
      "description": "Backup Claude Max account"
    }
  ],
  "detection_patterns": [
    "usage limit",
    "rate limit",
    "capacity.*exceeded",
    "limit.*reached",
    "please wait.*reset",
    "you've reached",
    "quota.*exceeded"
  ],
  "context_preservation": {
    "enabled": true,
    "method": "summary_injection",
    "max_lines": 50
  }
}
```

### Configuration Options

| Field | Description |
|-------|-------------|
| `accounts` | Array of account configurations |
| `accounts[].name` | Display name for the account |
| `accounts[].config_dir` | Path to Claude config directory |
| `detection_patterns` | Regex patterns to detect rate limits |
| `context_preservation.enabled` | Whether to save/inject context on switch |
| `context_preservation.max_lines` | Lines of context to preserve |

### Adding More Accounts

You can add additional backup accounts:

```json
{
  "accounts": [
    {"name": "primary", "config_dir": "~/.claude-max-1"},
    {"name": "secondary", "config_dir": "~/.claude-max-2"},
    {"name": "tertiary", "config_dir": "~/.claude-max-3"}
  ]
}
```

## Session Resume

When switching accounts, the script uses Claude's native `--resume` flag:

1. Captures session ID from startup output (UUID in first 50 lines)
2. Saves to `~/.claude/.auto-switch-session` on rate limit
3. Launches next account with `--resume <session-id>`

### Requirements

- **Projects symlink**: All accounts must share `~/.claude/projects`
- **Session ID capture**: Script must detect UUID in Claude's output

### Benefits

- **Full context preserved** - Entire conversation history maintained
- **Same session ID** - Continues the exact same session
- **Tool state preserved** - All context from previous account carries over

## Troubleshooting

### Account Not Found

```
⚠️  Config directory not found: ~/.claude-max-2
```

**Solution**: Authenticate the account first:

```bash
CLAUDE_CONFIG_DIR=~/.claude-max-2 claude
```

### First-Run Login Prompt

When running via the wrapper for the first time, you may be prompted to log in even if you've previously authenticated.

**Why**: Setting `CLAUDE_CONFIG_DIR` explicitly (even to the same directory) may trigger Claude to treat it as a new configuration.

**Solution**: This only happens once. Complete the login and subsequent runs will work normally.

### Rate Limit Not Detected

If switches aren't happening when expected, Anthropic may have changed their message format.

**Solution**: Check Claude's output for the exact rate limit message and add it to `detection_patterns` in config.json.

### All Accounts Rate Limited

```
❌ All accounts have hit rate limits!
```

**Solution**: Wait for the 5-hour reset window, or add more accounts.

## Technical Details

### Environment Variable

The script uses `CLAUDE_CONFIG_DIR` - an undocumented but official environment variable that tells Claude Code where to store its configuration, credentials, and session data.

**Important:** The wrapper only sets `CLAUDE_CONFIG_DIR` for non-default directories. Setting it explicitly to `~/.claude` (even though that's the default) can cause issues like MCP servers not being detected. The wrapper handles this automatically.

### PTY Handling

The script uses Python's `pty` module to spawn Claude in a pseudo-terminal, which:
- Preserves interactive features (colors, cursor movement, real-time output)
- Monitors stdout for rate limit patterns
- Forwards stdin to the child process for full interactivity
- Sets terminal to raw mode with `tty.setraw()` for proper keystroke handling
- Restores terminal settings on exit via `termios.tcsetattr()`

This bidirectional PTY handling is essential - without forwarding stdin to the child process, the terminal would appear frozen.

### Rate Limit Detection

Detection is based on pattern matching Claude's terminal output. Patterns are case-insensitive regexes.

## Considerations

### Terms of Service

Review Anthropic's Terms of Service regarding multiple accounts. This tool is provided for convenience; compliance with ToS is your responsibility.

### IP Address

Both accounts will appear to come from the same IP address. Anthropic may use this for abuse detection.

### Cost

Each Claude Max subscription is billed separately. Two Max accounts = 2x the monthly cost.

## Related

- [CLAUDE_CONFIG_DIR discussion](https://github.com/anthropics/claude-code/issues/261)
- [CCS - Claude Code Switch](https://ccs.kaitran.ca) - Alternative multi-account tool
- [Rate Limits Documentation](https://platform.claude.com/docs/en/api/rate-limits)
