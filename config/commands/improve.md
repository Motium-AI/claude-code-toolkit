---
description: Recursively improve any aspect (design, UX, performance, accessibility) until 9/10
argument-hint: <dimension> [of <scope>] [--target N]
---

# /improve

Universal recursive improvement with enhanced loop targeting 9/10.

## Target

$ARGUMENTS

If no dimension specified, show available dimensions: design, UX, performance, accessibility, code quality.

## Instructions

1. **Read the improve skill** to understand the enhanced loop:
   @~/.claude/skills/improve/SKILL.md

2. **Parse the request**:
   - Dimension: design, UX, performance, accessibility
   - Scope: page name, URL, flow, or whole app
   - Target: default 9.0 (overridable via `--target`)

3. **Load dimension-specific rubric** (if available):
   - design → `@~/.claude/skills/design-improver/references/grading-rubric.md`
   - UX → `@~/.claude/skills/ux-improver/references/ux-grading-rubric.md`
   - performance/accessibility → generate dimensions from first principles

4. **Execute the recursive improvement loop**:
   - Observe using appropriate method (screenshot for visual, code analysis for non-visual)
   - Grade against 6 dimensions
   - Fix top 3 issues
   - Verify and reassess
   - Loop until 9/10 or stalled above 8/10 or max 7 iterations

5. **Use Chrome integration** for visual dimensions

## Dimension Routing

| Dimension | Observation | Rubric |
|-----------|-------------|--------|
| design | Screenshot | grading-rubric.md |
| UX | Screenshot + accessibility tree | ux-grading-rubric.md |
| performance | Code + Lighthouse patterns | Model-generated |
| accessibility | Accessibility tree + code | Model-generated |
| code quality | Redirects to /burndown | — |

## Output

At each iteration: current scores, delta from start, top 3 fixes.
Final report: before/after scores, trajectory, files changed, remaining opportunities.
