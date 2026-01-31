---
description: Recursively improve UX via screenshot analysis and targeted fixes
argument-hint: [page-or-flow]
---

# /uximprove

> **Tip**: `/improve UX` provides an enhanced version with higher target (9/10 vs 8/10), stall detection, and score trajectory tracking.

Use ultrathink to thoroughly analyze and iteratively improve user experience.

## Target

$ARGUMENTS

If no target specified, default to `localhost:3000`.

## Instructions

1. **Read the ux-improver skill** to understand the methodology:
   @~/.claude/skills/ux-improver/SKILL.md

2. **Read the UX grading rubric** for detailed scoring criteria:
   @~/.claude/skills/ux-improver/references/ux-grading-rubric.md

3. **Execute the recursive UX improvement workflow**:
   - Take screenshot of the target
   - Get accessibility tree via read_page (CRITICAL for UX evaluation)
   - Grade against 6 UX dimensions (Usability, Info Architecture, User Flows, Affordances, Feedback, Error Handling)
   - Fix top 3 issues
   - Re-screenshot and re-grade
   - Continue until score >= 8.0 or 5 iterations

4. **Use Chrome integration** (preferred) or Playwright fallback

## Target Resolution

- Flow name (e.g., "checkout flow", "onboarding") → Evaluate all screens in that flow
- Page name (e.g., "login page", "dashboard") → Evaluate that specific page
- URL (e.g., "localhost:3000/settings") → Navigate directly
- No target → Use `localhost:3000`

## Focus

This command evaluates **user experience** (usability, flows, feedback), NOT visual aesthetics.

For visual design improvements (typography, colors, polish), use `/designimprove` instead.

## Output

Provide structured reports at each iteration showing:
- Current UX score per dimension
- Top 3 issues being fixed
- User impact of each issue
- Files being modified
- Progress toward passing threshold (8.0)

End with a final summary showing before/after scores and all files changed.
