---
description: Recursively improve UI design via screenshot analysis and targeted fixes
argument-hint: [page-name-or-url]
---

# /designimprove

> **Tip**: `/improve design` provides an enhanced version with higher target (9/10 vs 8/10), stall detection, and score trajectory tracking.

Use ultrathink to thoroughly analyze and iteratively improve UI design like a world-class designer.

## Target

$ARGUMENTS

If no target specified, default to `localhost:3000`.

## Instructions

1. **Read the design-improver skill** to understand the methodology:
   @~/.claude/skills/design-improver/SKILL.md

2. **Read the grading rubric** for detailed scoring criteria:
   @~/.claude/skills/design-improver/references/grading-rubric.md

3. **Execute the recursive improvement workflow**:
   - Take screenshot of the target
   - Grade against 6 dimensions (Typography, Color, Layout, Motion, Polish, Accessibility)
   - Fix top 3 issues
   - Re-screenshot and re-grade
   - Continue until score >= 8.0 or 5 iterations

4. **Use Chrome integration** (preferred) or Playwright fallback for browser automation

## Target Resolution

- Page name (e.g., "the home page", "dashboard") → Navigate to that route
- URL (e.g., "localhost:3000/login") → Navigate directly
- No target → Use `localhost:3000`

## Output

Provide structured reports at each iteration showing:
- Current score per dimension
- Top 3 issues being fixed
- Files being modified
- Progress toward passing threshold (8.0)

End with a final summary showing before/after scores and all files changed.
