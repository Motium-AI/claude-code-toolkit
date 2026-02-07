---
name: ux-improver
description: Recursively improve web application UX via vision-based screenshot analysis. Use when asked to "improve UX", "fix usability", "audit user experience", or "/uximprove". Triggers on UX review, usability improvement, user flow analysis, interaction audit.
---

# UX Improver

Recursive workflow that transforms frustrating user experiences into intuitive, efficient interactions through iterative screenshot analysis and targeted fixes.

```
Screenshot → Grade (6 UX dimensions) → Fix Top 3 → Repeat until score >= 8.0
```

## Focus: Usability, Not Aesthetics

This skill evaluates **user experience** (can users accomplish tasks efficiently?) rather than **visual design** (does it look pretty?).

| This Skill Evaluates | NOT This (use /designimprove) |
|---------------------|-------------------------------|
| Clear CTAs and labels | Font choices |
| Navigation efficiency | Color harmony |
| Loading/feedback states | Visual polish |
| Error prevention/recovery | Shadows and depth |
| Affordances (looks clickable) | Typography hierarchy |

## Prerequisites

- **Chrome integration** (`claude --chrome`) - PREFERRED
- **Playwright** - Fallback for CI/headless scenarios
- Web application running (default: `localhost:3000`)

## Browser Decision Tree

```
Is Chrome MCP available? (claude --chrome)
├── Yes → Use Chrome tools
│   ├── tabs_context_mcp → get tab IDs
│   ├── tabs_create_mcp → new tab
│   ├── navigate → go to URL
│   ├── computer action:"screenshot" → capture
│   └── read_page → get accessibility tree (CRITICAL for UX)
│
└── No → Fall back to Playwright
    ├── Use sync_playwright API
    ├── page.screenshot(full_page=True)
    └── Save to /tmp/ for analysis
```

## Workflow

### Phase 1: Screenshot & Analyze

1. **Setup browser context**
   ```
   Chrome: tabs_context_mcp → tabs_create_mcp → navigate
   Playwright: browser.new_page() → page.goto()
   ```

2. **Capture full-page screenshot**
   ```
   Chrome: computer(action: "screenshot", tabId: X)
   Playwright: page.screenshot(path="/tmp/ux_audit.png", full_page=True)
   ```

3. **Get accessibility tree** (essential for UX evaluation)
   ```
   read_page(tabId, filter: "all") → element roles, labels, states
   read_page(tabId, filter: "interactive") → buttons, links, inputs
   ```

4. **Analyze against 6 UX dimensions** using vision + accessibility data

5. **Output structured UX report**

### Phase 2: Fix Top 3 Issues

1. **Rank issues** by: `severity × user_impact × fix_complexity`
   - Prioritize: Blocking issues > Friction issues > Polish issues

2. **For each issue (top 3 only):**
   ```
   a. Use read_page to identify element refs and roles
   b. Grep codebase for component files
   c. Apply UX fix:
      - Add missing labels/aria-labels
      - Add loading/disabled states
      - Improve button text
      - Add error messages
      - Add progress indicators
   d. Preserve existing functionality
   ```

3. **Wait for hot reload** (2-3 seconds for HMR)

### Phase 3: Re-evaluate

1. Take new screenshot
2. Re-check accessibility tree
3. Re-grade against same 6 dimensions
4. Decision:
   - `score < 8.0 AND iteration < 5` → goto Phase 2
   - `score >= 8.0` → auto-stop, generate final report
   - `iteration >= 5` → stop, generate final report with recommendations

## UX Grading Dimensions

| Dimension | Weight | What Makes It Pass |
|-----------|--------|-------------------|
| **Usability** | 20% | Users can accomplish tasks with minimal effort. Clear CTAs, obvious actions. |
| **Information Architecture** | 15% | Content organized logically. Navigation intuitive. Labels clear. |
| **User Flows** | 20% | Paths to goals are efficient. Progress visible. Next steps obvious. |
| **Affordances & Signifiers** | 15% | Interactive elements look interactive. Buttons look clickable. |
| **Feedback & Status** | 15% | System responds to actions. Loading states. Confirmations. |
| **Error Handling** | 15% | Errors prevented. Messages helpful. Recovery paths clear. |

## Scoring Scale

| Score | Status | Action |
|-------|--------|--------|
| 9-10 | Exceptional | Auto-stop - UX is excellent |
| 7-8 | Good | Auto-stop - meets quality bar |
| 5-6 | Needs Work | Auto-continue fixing |
| 1-4 | Significant Issues | Auto-continue fixing |

**Pass threshold: 8.0** (configurable)

## UX Anti-Patterns to Detect & Fix

### Usability (Critical)

| Anti-Pattern | Why It's Bad | Fix |
|--------------|--------------|-----|
| Vague CTA text ("Submit", "Click Here") | Users don't know what happens | Use action verbs ("Create Account", "Send Message") |
| Hidden primary actions | Users can't find main function | Make primary action prominent |
| Too many options | Choice paralysis | Reduce options, use progressive disclosure |
| Inconsistent interactions | Confuses users | Standardize patterns across app |
| No clear starting point | Users don't know where to begin | Add clear onboarding/guidance |

### Information Architecture (Major)

| Anti-Pattern | Why It's Bad | Fix |
|--------------|--------------|-----|
| Deep navigation (> 3 clicks) | Users get lost | Flatten hierarchy |
| Unclear labels | Users guess meaning | Use user-centric terminology |
| No visual hierarchy | Can't scan page | Size/weight for importance |
| Important info below fold | Users miss it | Move critical content up |
| Inconsistent categorization | Items hard to find | Logical grouping |

### User Flows (Critical)

| Anti-Pattern | Why It's Bad | Fix |
|--------------|--------------|-----|
| Dead ends (no next step) | Users stuck | Always provide next action |
| Unnecessary steps | Wastes user time | Remove or combine steps |
| No progress indication | Users feel lost | Add stepper/progress bar |
| Can't go back | Users trapped | Clear back/cancel buttons |
| Unclear completion | Users unsure if done | Success confirmation |

### Affordances & Signifiers (Major)

| Anti-Pattern | Why It's Bad | Fix |
|--------------|--------------|-----|
| Flat buttons (no visual cue) | Look like text | Add borders, shadows, background |
| Clickable text without style | Users don't know it's a link | Underline, color, or button style |
| Icons without labels | Meaning unclear | Add text labels |
| No hover/focus states | No feedback on interaction | Add visual state changes |
| Disabled looks same as enabled | Users try clicking disabled | Dim/gray disabled elements |

### Feedback & Status (Major)

| Anti-Pattern | Why It's Bad | Fix |
|--------------|--------------|-----|
| No loading state | Users think app frozen | Add spinner/skeleton |
| No action confirmation | Users unsure if worked | Toast/success message |
| Silent failures | Users don't know error occurred | Error feedback |
| No undo option | Mistakes permanent | Allow reversal |
| Stale data displayed | Users see wrong info | Refresh indicators |

### Error Handling (Critical)

| Anti-Pattern | Why It's Bad | Fix |
|--------------|--------------|-----|
| Generic "An error occurred" | No actionable info | Specific error message |
| No inline validation | Errors found too late | Validate on blur/change |
| Errors clear form input | User loses work | Preserve input |
| No recovery suggestion | User stuck | "Try again" or alternatives |
| Blame the user | Bad experience | Neutral, helpful tone |

## Output Format

### Per-Iteration Report

```markdown
## UX Grade: X.X/10 - [Status]

**Iteration**: N of 5

| Dimension | Score | Status | Key Issue |
|-----------|-------|--------|-----------|
| Usability | X/10 | PASS/FAIL | [specific issue] |
| Info Architecture | X/10 | PASS/FAIL | [specific issue] |
| User Flows | X/10 | PASS/FAIL | [specific issue] |
| Affordances | X/10 | PASS/FAIL | [specific issue] |
| Feedback | X/10 | PASS/FAIL | [specific issue] |
| Error Handling | X/10 | PASS/FAIL | [specific issue] |

## Top 3 UX Issues to Fix

### Issue #1: [Title] (Critical/Major/Minor)
- **Location**: [element/page area]
- **Problem**: [UX issue description]
- **User Impact**: [how this hurts users]
- **Root Cause**: [missing component/prop/state]
- **Files Found**:
  - `src/components/Button.tsx:42`
  - `src/pages/checkout.tsx:15`
- **Fix**:
  ```tsx
  // Change this
  <button>Submit</button>
  // To this
  <button disabled={isLoading}>
    {isLoading ? 'Processing...' : 'Complete Purchase'}
  </button>
  ```

### Issue #2: ...
### Issue #3: ...

---
Applying fixes...
```

### Final Report

```markdown
## UX Improvement Summary

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| **Overall** | X.X | X.X | +X.X |
| Usability | X | X | +X |
| Info Architecture | X | X | +X |
| User Flows | X | X | +X |
| Affordances | X | X | +X |
| Feedback | X | X | +X |
| Error Handling | X | X | +X |

## Files Modified
- `src/components/Button.tsx` - Added loading state
- `src/components/Form.tsx` - Added inline validation
- `src/pages/checkout.tsx` - Added progress indicator

## Iterations Completed: X

## Final Status: PASSING / NEEDS_MORE_WORK

## Remaining Recommendations
[If score < 8, list remaining UX issues]
```

## File Discovery Patterns

### From Screenshot to Source File

1. **Get accessibility tree**
   ```
   read_page(tabId, filter: "interactive") → buttons, links, inputs with roles
   find(query: "submit button", tabId) → specific element refs
   ```

2. **Extract identifying info**
   - Element text content
   - ARIA labels/roles
   - Class names
   - Test IDs (data-testid)

3. **Search codebase**
   ```bash
   # Find by button text
   grep -r "Submit" --include="*.tsx" --include="*.jsx"

   # Find by component name
   grep -r "CheckoutButton" --include="*.tsx"

   # Find by test ID
   grep -r "data-testid=\"checkout" --include="*.tsx"
   ```

4. **Common UX-related locations**
   ```
   src/components/           # UI components
   src/components/forms/     # Form components
   src/components/feedback/  # Toast, loading, error components
   src/hooks/               # State hooks (useLoading, useError)
   src/pages/               # Page-level UX
   ```

## Chrome Tool Reference

| Tool | Purpose | UX-Specific Usage |
|------|---------|-------------------|
| `tabs_context_mcp` | Get available tabs | Required first |
| `navigate` | Go to URL | Test different pages/flows |
| `computer` | Screenshot/click | Capture state, test interactions |
| `read_page` | Get accessibility tree | **Critical** - reveals labels, roles, states |
| `find` | Natural language search | Find "submit button", "error message" |

## Iteration Control

- **max_iterations**: 5 (prevents infinite loops)
- **pass_threshold**: 8.0 (UX is "good enough")
- **auto_continue**: When score < 8.0
- **auto_stop**: When score >= 8.0 OR iterations >= 5

## Git Operations

After each iteration that makes code changes:
1. **Commit** with iteration context:
   ```bash
   git add <files> && git commit -m "ux: [changes] (iteration N, score X.X)"
   ```

After the final iteration:
2. **Push** to trigger CI:
   ```bash
   git push
   ```

## Integration Notes

This skill integrates with:
- **webapp-testing**: Shares Chrome/Playwright decision patterns
- **ux-designer**: Uses WCAG accessibility principles
- **design-improver**: Complementary (design-improver for aesthetics, this for UX)

## Example Session

```
User: /uximprove the checkout flow

Claude: [Takes screenshot of localhost:3000/checkout]

## UX Grade: 4.8/10 - Significant Issues

| Dimension | Score | Status | Key Issue |
|-----------|-------|--------|-----------|
| Usability | 4/10 | FAIL | Vague "Submit" button |
| Info Architecture | 6/10 | PASS | Sections organized |
| User Flows | 3/10 | FAIL | No progress indicator |
| Affordances | 5/10 | FAIL | Payment fields look disabled |
| Feedback | 4/10 | FAIL | No loading state on submit |
| Error Handling | 5/10 | FAIL | Generic error messages |

## Top 3 UX Issues to Fix

### Issue #1: No Loading State (Critical)
- **Location**: Submit button
- **Problem**: Button doesn't indicate processing
- **User Impact**: Users click multiple times, think app is broken
- **Fix**: Add isLoading state and spinner

### Issue #2: Vague Button Text (Major)
- **Location**: Submit button
- **Problem**: "Submit" doesn't describe action
- **User Impact**: Users unsure what clicking will do
- **Fix**: Change to "Complete Purchase"

### Issue #3: No Progress Indicator (Major)
- **Location**: Checkout flow
- **Problem**: Users don't know how many steps remain
- **User Impact**: Abandonment due to uncertainty
- **Fix**: Add step indicator (Step 2 of 3)

[Applies fixes]
[Takes new screenshot]

## UX Grade: 7.1/10 - Good (+2.3)

[Continues until score >= 8.0]

## Final Report
UX improved from 4.8 to 8.2 in 3 iterations.
```

## Complementary Usage

For complete UI improvement, run both:

```
/designimprove the checkout page  # Fix visual aesthetics
/uximprove the checkout flow      # Fix user experience
```

The skills don't overlap - they address different aspects of quality.
