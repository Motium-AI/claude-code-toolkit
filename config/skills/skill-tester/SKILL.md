---
name: skill-tester
description: "DEPRECATED - Use skill-sandbox instead. Redirects to skill-sandbox for secure skill testing."
---

# skill-tester (DEPRECATED)

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

1. **Security**: `skill-sandbox` provides superior security with 5-layer isolation:
   - Fake credentials file (protects OAuth tokens)
   - Separate tmux server (`-L` flag) for environment isolation
   - Mock `gh` and `az` commands to block production deployments
   - Git worktree isolation
   - Environment variable scrubbing

2. **Infrastructure**: `skill-tester` lacked production-ready scripts. `skill-sandbox` has a complete `sandbox-setup.sh` (15KB+).

3. **Consolidation**: Reduces confusion and maintenance burden from having 3 overlapping skill-testing tools.

## See Also

- [skill-sandbox SKILL.md](~/.claude/skills/skill-sandbox/SKILL.md) - The canonical skill testing framework
- [sandbox-setup.sh](~/.claude/skills/skill-sandbox/scripts/sandbox-setup.sh) - Production setup script

## Historical Reference

The original `skill-tester` patterns (headless testing with `claude -p`) are preserved in:
- `~/.claude/skills/skill-tester/scripts/` - Original test scripts (kept for reference)

These patterns are now incorporated into `skill-sandbox` which supports both headless and interactive testing modes with proper security.
