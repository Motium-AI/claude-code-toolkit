---
name: improve
description: Universal recursive improvement for any quality dimension. Targets 9/10 with stall detection. Use when asked to "/improve", "improve design", "improve UX", "improve the design of", "grade the UI". Routes to appropriate rubric based on dimension.
---

# Universal Recursive Improvement (/improve)

Self-contained improvement loop that observes, grades, fixes, and repeats until exceptional quality (9.0) or diminishing returns.

```
OBSERVE → GRADE → FIX top 3 → VERIFY → REASSESS → loop until 9.0
```

## Invocation

```
/improve <dimension> [of <scope>] [--target N]

/improve design                     # whole app, target 9.0
/improve design of the matches page # scoped to specific page
/improve UX of the checkout flow    # UX dimension
/improve performance                # performance dimension
/improve                            # show dimension menu
```

**Argument parsing**: Strip filler words ("of", "the", "on"). First word = dimension, rest = scope.

## Dimension Routing

| Keywords | Dimension | Rubric | Observation |
|----------|-----------|--------|-------------|
| design, visual, UI, styling, aesthetics | **Design** | `@~/.claude/skills/design-improver/references/grading-rubric.md` | Screenshot |
| UX, usability, flows, navigation, experience | **UX** | `@~/.claude/skills/ux-improver/references/ux-grading-rubric.md` | Screenshot + `read_page(interactive)` |
| performance, speed, loading, latency | **Performance** | Model-generated | Lighthouse + code analysis |
| accessibility, a11y, wcag, screen reader | **Accessibility** | Model-generated | `read_page(all)` + contrast check |
| code quality, architecture, patterns | **Code Quality** | → Suggest `/burndown` | N/A |
| (no match) | **Unknown** | Show menu | N/A |

### No Dimension Specified → Show Menu

```
═══════════════════════════════════════════════════════════════
 /improve — Choose a dimension
═══════════════════════════════════════════════════════════════

 DIMENSION        WHAT IT IMPROVES
 design           Typography, colors, layout, motion, polish
 UX               Usability, flows, feedback, error handling
 performance      Load time, bundle size, runtime efficiency
 accessibility    WCAG compliance, keyboard nav, screen readers

 USAGE
   /improve design                  # whole app
   /improve design matches page     # specific page
   /improve UX checkout flow        # specific flow
   /improve --target 8              # lower the bar

What would you like to improve?
═══════════════════════════════════════════════════════════════
```

## Prerequisites

- **Chrome integration** (`claude --chrome`) — for visual dimensions
- **Web app running** (default: `localhost:3000`) — for visual dimensions
- **Codebase access** — for all dimensions

## The Loop

### Phase 1: Observe

**Visual dimensions (design, UX)**:
```
1. tabs_context_mcp → get/create tab
2. navigate to target URL (scope or localhost:3000)
3. computer(action: "screenshot") → capture full page
4. read_page(filter: "all") → element tree
5. For UX: read_page(filter: "interactive") → buttons, links, inputs
```

**Non-visual dimensions (performance, a11y)**:
```
1. Run analysis tools (Lighthouse, complexity metrics)
2. Grep for known anti-patterns
3. Read relevant code files
```

### Phase 2: Grade

Load the appropriate rubric (or generate one for non-visual dimensions).

**Grade each of 6 dimensions** on the rubric:
- Score 1-10 with specific evidence
- Note key issue per dimension
- Calculate weighted overall score

### Phase 3: Plan Top 3 Fixes

Rank issues by: `(10 - score) × weight × feasibility`

Feasibility:
- 1.0: CSS/style only
- 0.8: Single component
- 0.6: Multiple files
- 0.4: Architecture change

Select top 3 highest-impact fixes.

### Phase 4: Fix

1. Apply fixes via Edit tool — minimal, targeted
2. One fix at a time — verify compilation
3. Preserve existing functionality

### Phase 5: Verify

1. Wait for HMR (2-3 seconds) — visual dimensions
2. Re-observe using same method as Phase 1
3. Confirm fixes took effect
4. Check for regressions

### Phase 6: Reassess

Score against SAME dimensions as Phase 2.

**Track score history**:
```json
{
  "scores": [
    {"iteration": 1, "overall": 5.4, "delta": null},
    {"iteration": 2, "overall": 7.2, "delta": 1.8},
    {"iteration": 3, "overall": 8.1, "delta": 0.9}
  ]
}
```

## Loop Control

| Condition | Action |
|-----------|--------|
| `score >= 9.0` | **EXCEPTIONAL** — stop, celebrate |
| `score >= 8.0 AND last 2 deltas < 0.3` | **PLATEAU** — stop gracefully |
| `score dropped > 0.5` | **REGRESSION** — investigate, consider revert |
| `iteration >= 7` | **MAX REACHED** — stop, report remaining |
| Otherwise | **CONTINUE** — back to Phase 3 |

### Plateau Handling

When stalled above 8.0:

```
═══════════════════════════════════════════════════════════════
 PLATEAU DETECTED — Score stabilized at 8.3
═══════════════════════════════════════════════════════════════

 Remaining improvements require:
 • Motion: Animation library (Framer Motion) not installed
 • Polish: Design system refactor needed

 OPTIONS
 1. Accept 8.3 — exceeds "Good" threshold (8.0)
 2. Lower target — /improve design --target 8
 3. Address blockers — install dependencies, then re-run

 Current score (8.3) is acceptable. Stopping gracefully.
═══════════════════════════════════════════════════════════════
```

## Progress Reporting

### Per-Iteration Report

```
═══════════════════════════════════════════════════════════════
 /improve │ Iteration 3 of 7 │ DESIGN │ Target: 9.0
═══════════════════════════════════════════════════════════════

 CURRENT    DELTA     GAP      MOMENTUM
 7.4        +0.8      1.6      Healthy (+0.9 avg)

 TRAJECTORY
 5.4 ━━━> 6.6 ━━━> 7.4 ━ ━ ┄ 9.0

 DIMENSION SCORES
 │ Typography   [████████░░] 8.5  (+1.5)  ✓
 │ Color        [███████░░░] 7.0  (+0.5)
 │ Layout       [████████░░] 8.0  (+1.0)  ✓
 │ Motion       [██████░░░░] 6.0  ( 0  )  ← PRIORITY
 │ Polish       [███████░░░] 7.0  (+1.0)
 │ Accessibility[████████░░] 8.0  ( 0  )  ✓

 FIXING THIS ITERATION
 1. Motion: Add hover transitions to buttons
 2. Color: Increase CTA contrast ratio
 3. Polish: Add subtle shadows to cards
═══════════════════════════════════════════════════════════════
```

### Final Report

```
═══════════════════════════════════════════════════════════════
 /improve COMPLETE │ DESIGN │ 5.4 → 8.6 (+3.2)
═══════════════════════════════════════════════════════════════

 RESULT: PLATEAU at 8.6 (target was 9.0)
 ITERATIONS: 5 of 7
 EXIT REASON: Diminishing returns (last 2 deltas: +0.2, +0.1)

 BEFORE → AFTER
 │ Typography    5 → 9   (+4)
 │ Color         6 → 8   (+2)
 │ Layout        5 → 9   (+4)
 │ Motion        4 → 7   (+3)
 │ Polish        5 → 8   (+3)
 │ Accessibility 7 → 8   (+1)

 FILES MODIFIED (8)
 • src/styles/globals.css — fonts, shadows, transitions
 • src/components/Button.tsx — hover states
 • src/components/Card.tsx — elevation, borders
 • tailwind.config.js — color tokens

 REMAINING OPPORTUNITIES
 • Motion (7/10): Install animation library for micro-interactions
 • Polish (8/10): Design system would enable consistency
═══════════════════════════════════════════════════════════════
```

## Checkpoint

Write lightweight checkpoint matching `validate_improve_completion()`:

```json
{
  "self_report": {
    "is_job_complete": true,
    "code_changes_made": true,
    "linters_pass": true,
    "category": "refactor"
  },
  "reflection": {
    "what_was_done": "Improved design from 5.4 to 8.6 over 5 iterations. Fixed typography, layout, color contrast, added hover transitions.",
    "what_remains": "none",
    "key_insight": "Motion dimension hit ceiling without animation library. Framer Motion would unlock 9.0+.",
    "search_terms": ["improve", "design", "typography", "motion", "stall-detection"]
  }
}
```

## Chrome Tool Reference

| Tool | Purpose |
|------|---------|
| `tabs_context_mcp` | Get available tabs |
| `tabs_create_mcp` | Create new tab |
| `navigate` | Go to URL |
| `computer(action: "screenshot")` | Capture page |
| `read_page(filter: "all")` | Element tree |
| `read_page(filter: "interactive")` | Buttons, links, inputs |

## Backwards Compatibility

`/designimprove` and `/uximprove` still work via skill-state-initializer triggers.
They create `improve-state.json` and route through this skill.

## Integration

- **Auto-approval**: Via `is_improve_active()` in `_state.py`
- **Checkpoint validation**: Via `validate_improve_completion()` in `_sv_validators.py`
- **State file**: `.claude/improve-state.json` with `plan_mode_completed: true`
