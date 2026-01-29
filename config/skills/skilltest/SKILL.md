---
name: skilltest
description: "DEPRECATED - Use skill-sandbox instead. Redirects to skill-sandbox for secure skill testing."
---

# skilltest (DEPRECATED)

**This skill has been deprecated and merged into `skill-sandbox`.**

## Migration

Use `/skill-sandbox` instead:

```bash
# Trigger the skill
/skill-sandbox

# Or use the setup script directly
~/.claude/skills/skill-sandbox/scripts/sandbox-setup.sh create
```

## Why This Was Deprecated

1. **Missing Infrastructure**: `skilltest` referenced a Python test runner (`skilltest-runner.py`) that was never implemented. `skill-sandbox` has working infrastructure.

2. **Security**: `skill-sandbox` provides the security features this skill recommended:
   - Fake credentials file (protects OAuth tokens)
   - Separate tmux server for environment isolation
   - Mock dangerous commands (gh, az)
   - Git worktree isolation

3. **Consolidation**: Reduces confusion from having 3 overlapping skill-testing tools.

## Useful Concepts from skilltest

The following concepts from `skilltest` may be incorporated into `skill-sandbox` in future iterations:

- **Test case JSON schema** (`.claude/skill-tests/*.json`)
- **Test granularity levels** (smoke, unit, integration, regression)
- **User input simulation** (`inject_input` patterns)
- **Results aggregation** (`results.json` format)

## See Also

- [skill-sandbox SKILL.md](~/.claude/skills/skill-sandbox/SKILL.md) - The canonical skill testing framework
- [sandbox-setup.sh](~/.claude/skills/skill-sandbox/scripts/sandbox-setup.sh) - Production setup script
