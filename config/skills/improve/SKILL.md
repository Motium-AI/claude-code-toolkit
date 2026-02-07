---
name: improve
description: Universal recursive improvement. Assesses any aspect of the codebase (design, UX, performance, accessibility) using a recursive observe-grade-fix loop until 9/10. Use when asked to "/improve", "improve design", "improve UX", etc.
---

# Universal Recursive Improvement (/improve)

One skill. Any aspect. Enhanced loop with 9/10 target, stall detection, and score trajectory tracking.

```
OBSERVE → GRADE → FIX top 3 → VERIFY → REASSESS → loop until 9/10
```

## Input Parsing

```
/improve <dimension> [of <scope>] [--target N]

Examples:
  /improve design                     → dimension=design, scope=full app
  /improve design of the matches page → dimension=design, scope=matches page
  /improve UX of the checkout flow    → dimension=UX, scope=checkout flow
  /improve performance                → dimension=performance, scope=full app
  /improve accessibility              → dimension=accessibility, scope=full app
  /improve                            → show dimension menu
```

## Dimension Routing

| Input | Rubric | Observation Method |
|-------|--------|-------------------|
| design, visual, styling, UI | `@~/.claude/skills/design-improver/references/grading-rubric.md` | Screenshot via Chrome MCP |
| UX, usability, flows | `@~/.claude/skills/ux-improver/references/ux-grading-rubric.md` | Screenshot + `read_page(filter: "interactive")` |
| performance | Model-generated dimensions | Lighthouse patterns + code analysis |
| accessibility, a11y | Model-generated dimensions | `read_page(filter: "all")` + code analysis |
| code quality | Suggest `/burndown` instead | — |
| (no dimension) | Show menu | — |

## Multi-Scope Parallelization

When improving a multi-page scope (e.g., "improve design" without a specific page), parallelize the initial assessment:

1. **Discover routes**: Identify all relevant pages/routes in the application
2. **Parallel grading**: Launch parallel `Task()` agents, one per page, each running observe + grade
3. **Synthesize**: Collect grades, identify which pages need the most work
4. **Fix sequentially**: Apply fixes page-by-page (fixes may touch shared CSS/components)

```
# Example: 3-page parallel grading
Task(subagent_type="general-purpose", description="Grade design: /dashboard",
  prompt="Navigate to localhost:3000/dashboard, screenshot, grade against design rubric (6 dimensions). Return scores + top 3 issues.")
Task(subagent_type="general-purpose", description="Grade design: /settings",
  prompt="Navigate to localhost:3000/settings, screenshot, grade against design rubric (6 dimensions). Return scores + top 3 issues.")
Task(subagent_type="general-purpose", description="Grade design: /profile",
  prompt="Navigate to localhost:3000/profile, screenshot, grade against design rubric (6 dimensions). Return scores + top 3 issues.")
# Launch in a SINGLE message, then fix the lowest-scoring page first
```

For single-page scope, skip parallelization and go directly to the loop.

## The Loop

### Phase 1: Observe

**For visual dimensions (design, UX):**
1. `tabs_context_mcp` → get/create tab
2. `navigate` to target URL (default: `localhost:3000`)
3. `computer(action: "screenshot")` → capture full page
4. For UX: also `read_page(filter: "interactive")` → buttons, links, inputs with roles/states
5. Grep/Read relevant style and component files

**For non-visual dimensions (performance, accessibility):**
1. Read codebase patterns
2. Run analysis tools (Lighthouse patterns, `read_page(all)`)
3. Identify anti-patterns via grep

### Phase 2: Grade

Load the rubric for the dimension (if available) and grade against 6 dimensions:

**Design dimensions** (from grading-rubric.md):
- Typography (20%), Color & Contrast (15%), Layout & Spacing (20%)
- Motion & Interaction (15%), Visual Polish (15%), Accessibility (15%)

**UX dimensions** (from ux-grading-rubric.md):
- Usability (20%), Information Architecture (15%), User Flows (20%)
- Affordances & Signifiers (15%), Feedback & Status (15%), Error Handling (15%)

**Non-visual dimensions**: Generate 4-6 appropriate dimensions from first principles.

### Phase 3: Plan Top 3 Fixes

Select top 3 issues ranked by: `severity × impact × feasibility`

Feasibility scale:
- 1.0: CSS/style change only
- 0.8: Single component change
- 0.6: Multiple file changes
- 0.4: Architecture change

### Phase 4: Fix

Apply fixes via Edit tool. Minimal, targeted changes. Wait 2-3s for HMR (visual).

### Phase 5: Verify

Re-observe using same method. Confirm fixes took effect. Check for regressions.

### Phase 6: Reassess

Score against the SAME dimensions. Track score history.

## Loop Control

```
score >= 9.0                           → EXCEPTIONAL. Stop.
score >= 8.0 AND last 2 deltas < 0.3   → DIMINISHING RETURNS. Stop gracefully.
score dropped from previous            → REGRESSION. Investigate before continuing.
iteration >= 7                         → MAX REACHED. Stop with report.
otherwise                              → MAKING PROGRESS. Continue loop.
```

**Constants:**
- `target_score`: 9.0 (default, overridable via `--target`)
- `acceptable_score`: 8.0 (stop if stalled above this)
- `max_iterations`: 7
- `stall_threshold`: 0.3
- `stall_window`: 2 consecutive iterations

## Score Trajectory Reporting

At each iteration:

```markdown
--- Iteration N of 7 ---
Target: 9.0 | Current: X.X | Delta: +X.X from start

| Dimension | Score | Status |
|-----------|-------|--------|
| [dim 1]   | X/10  | PASS/FAIL |
| ...       | ...   | ... |

Fixing: [issue 1], [issue 2], [issue 3]
```

## Final Report

```markdown
## [Dimension] Improvement Summary

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| **Overall** | X.X | X.X | +X.X |
| [dim 1] | X | X | +X |
| ...     | ... | ... | ... |

## Score Trajectory
[5.4] → [7.2] → [8.1] → [8.6] → [9.1] ✓

## Exit Reason: TARGET_REACHED / DIMINISHING_RETURNS / MAX_ITERATIONS

## Files Modified
- `path/to/file.css` — [changes]
- ...

## Iterations: X

## Remaining Opportunities
[If score < 9.0, what else could be done]
```

## Checkpoint Schema

Write `.claude/completion-checkpoint.json` with lightweight 3+1 schema:

```json
{
  "self_report": {
    "is_job_complete": true,
    "code_changes_made": true,
    "linters_pass": true,
    "category": "refactor"
  },
  "reflection": {
    "what_was_done": "Improved design of matches page from 5.4 to 9.1 over 4 iterations",
    "what_remains": "none",
    "key_insight": "[reusable lesson from this session]",
    "search_terms": ["improve", "design", "typography", "shadows"]
  }
}
```

## Prerequisites

- **Chrome integration** (`claude --chrome`) — required for visual dimensions
- **Web application running** (default: `localhost:3000`) — required for visual dimensions
- **Codebase access** — required for all dimensions

## Git Operations

After each iteration that makes code changes:
1. **Commit** with iteration context:
   ```bash
   git add <files> && git commit -m "improve(<dimension>): [changes] (iteration N, score X.X)"
   ```

After the final iteration:
2. **Push** to trigger CI:
   ```bash
   git push
   ```

## Skill Fluidity

You may use techniques from any skill for sub-problems without switching modes. Your autonomous state and checkpoint remain governed by /improve.

## Integration

- State file: `.claude/autonomous-state.json` with `"mode": "improve"`
- Auto-approval: Yes (via `is_autonomous_mode_active()`)
- Plan mode: `plan_mode_completed: true` from start (observe-grade IS the planning)
- Checkpoint: Universal validation via stop-validator
