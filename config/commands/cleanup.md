# /cleanup

Clean up Claude Code session data to reclaim disk space and improve performance.

## What It Cleans

| Category | Default | Location |
|----------|---------|----------|
| **Session transcripts** | Keep 20 most recent per project, delete >30 days | `~/.claude/projects/*/` |
| **Debug logs** | Delete >7 days | `~/.claude/debug/` |
| **Empty session-env dirs** | Delete all empty | `~/.claude/session-env/` |
| **Stale todos** | Delete >30 days | `~/.claude/todos/` |
| **History entries** | Truncate to 1000 entries | `~/.claude/history.jsonl` |

## Usage

```bash
# Show what would be cleaned (dry run)
/cleanup --dry-run

# Run cleanup with defaults
/cleanup

# Aggressive cleanup (keep only 10 sessions, 14 days)
/cleanup --aggressive

# Custom retention
/cleanup --sessions 30 --days 60
```

## Arguments

- `--dry-run`: Show what would be deleted without actually deleting
- `--aggressive`: Use aggressive settings (10 sessions, 14 days retention)
- `--sessions N`: Keep N most recent sessions per project (default: 20)
- `--days N`: Delete sessions older than N days (default: 30)

## Execution

Run the cleanup script:

```bash
python3 ~/.claude/hooks/cleanup.py $ARGUMENTS
```

The script will output:
- Number of files/directories deleted
- Total disk space freed
- Any errors encountered

## When to Use

- When `/resume` or `/mcp` commands become slow
- When disk space is running low
- Periodically (e.g., monthly) for maintenance
- After extended usage periods

## Automatic Cleanup

Session cleanup also runs automatically on every session start via the `session-snapshot.py` hook, but with conservative settings. Use `/cleanup` for more aggressive or customized cleanup.
