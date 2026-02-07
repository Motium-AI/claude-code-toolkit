---
name: design-improver
description: Recursively improve web UI design via vision-based screenshot analysis. Use when asked to "improve design", "audit UI", "fix styling", "grade the interface", or "/designimprove". Triggers on design review, UI improvement, screenshot analysis, design grade.
---

# Design Improver

Recursive workflow that transforms mediocre UI into world-class design through iterative screenshot analysis and targeted fixes.

```
Screenshot → Grade (6 dimensions) → Fix Top 3 → Repeat until score >= 8.0
```

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
│   └── read_page → get element tree
│
└── No → Fall back to Playwright
    ├── Use sync_playwright API
    ├── page.screenshot(full_page=True)
    └── Save to /tmp/ for analysis
```

## Workflow

### Phase 1: Screenshot & Grade

1. **Setup browser context**
   ```
   Chrome: tabs_context_mcp → tabs_create_mcp → navigate
   Playwright: browser.new_page() → page.goto()
   ```

2. **Capture full-page screenshot**
   ```
   Chrome: computer(action: "screenshot", tabId: X)
   Playwright: page.screenshot(path="/tmp/design_audit.png", full_page=True)
   ```

3. **Analyze screenshot** against 6 dimensions using vision capabilities

4. **Output structured grade report**

### Phase 2: Fix Top 3 Issues

1. **Rank issues** by: `severity × visual_impact × fix_complexity`
   - Prioritize: High Impact + Low Effort fixes first

2. **For each issue (top 3 only):**
   ```
   a. Use read_page to get element refs and class names
   b. Grep codebase for matching selectors:
      - grep "\.classname" **/*.css
      - grep "className.*classname" **/*.tsx
   c. Apply MINIMAL targeted fix (single property when possible)
   d. Preserve existing structure
   ```

3. **Wait for hot reload** (2-3 seconds for HMR)

### Phase 3: Re-evaluate

1. Take new screenshot
2. Re-grade against same 6 dimensions
3. Decision:
   - `score < 8.0 AND iteration < 5` → goto Phase 2
   - `score >= 8.0` → auto-stop, generate final report
   - `iteration >= 5` → stop, generate final report with recommendations

## Grading Dimensions

| Dimension | Weight | What Makes It Pass |
|-----------|--------|-------------------|
| **Typography** | 20% | Distinctive fonts (NOT Inter/Roboto/Arial), clear hierarchy, good line-height |
| **Color & Contrast** | 15% | Harmonious palette, WCAG AA contrast (4.5:1), intentional accent colors |
| **Layout & Spacing** | 20% | Visual interest, asymmetry/grid-breaking, intentional whitespace |
| **Motion & Interaction** | 15% | CSS transitions, hover states, meaningful animations |
| **Visual Polish** | 15% | Depth (shadows), texture (gradients/patterns), refined details |
| **Accessibility** | 15% | Focus indicators, keyboard nav, semantic HTML, ARIA labels |

## Scoring Scale

| Score | Status | Action |
|-------|--------|--------|
| 9-10 | Exceptional | Auto-stop - design is world-class |
| 7-8 | Good | Auto-stop - meets quality bar |
| 5-6 | Needs Work | Auto-continue fixing |
| 1-4 | Significant Issues | Auto-continue fixing |

**Pass threshold: 8.0** (configurable via max score parameter)

## Anti-Patterns to Detect & Fix

### Typography (Critical)
| Anti-Pattern | Why It's Bad | Fix |
|--------------|--------------|-----|
| Inter, Roboto, Arial | Generic AI aesthetic | Use distinctive display + body fonts |
| Single font weight | No hierarchy | Add weight variation (400, 500, 700) |
| Tight line-height | Hard to read | Increase to 1.5-1.7 for body text |
| Inconsistent scale | Chaotic | Use type scale (1.25 or 1.333 ratio) |

### Color (Major)
| Anti-Pattern | Why It's Bad | Fix |
|--------------|--------------|-----|
| Purple gradient on white | AI cliche | Choose intentional, unique palette |
| Low contrast text | WCAG failure | Ensure 4.5:1 minimum |
| Too many colors | Visual noise | Limit to 3-4 with clear roles |
| No accent color | Flat, boring | Add single bold accent for CTAs |

### Layout (Major)
| Anti-Pattern | Why It's Bad | Fix |
|--------------|--------------|-----|
| Symmetric grids | Predictable | Break grid intentionally |
| Even spacing everywhere | Monotonous | Vary spacing for rhythm |
| Cookie-cutter cards | Generic | Add unique visual treatment |
| No negative space | Cramped | Increase margins, let content breathe |

### Visual Polish (Minor-Major)
| Anti-Pattern | Why It's Bad | Fix |
|--------------|--------------|-----|
| Flat solid backgrounds | No depth | Add subtle gradient or texture |
| No shadows | 2D feeling | Add layered box-shadows |
| Missing hover states | No feedback | Add transition + color shift |
| Sharp corners everywhere | Harsh | Mix border-radius values |

## Output Format

### Per-Iteration Report

```markdown
## Design Grade: X.X/10 - [Status]

**Iteration**: N of 5

| Dimension | Score | Status | Key Issue |
|-----------|-------|--------|-----------|
| Typography | X/10 | PASS/FAIL | [specific issue] |
| Color | X/10 | PASS/FAIL | [specific issue] |
| Layout | X/10 | PASS/FAIL | [specific issue] |
| Motion | X/10 | PASS/FAIL | [specific issue] |
| Polish | X/10 | PASS/FAIL | [specific issue] |
| Accessibility | X/10 | PASS/FAIL | [specific issue] |

## Top 3 Issues to Fix

### Issue #1: [Title] (Critical/Major/Minor)
- **Location**: [element description, area of page]
- **Problem**: [what's wrong]
- **Root Cause**: [CSS property, missing style, etc.]
- **Files Found**:
  - `src/styles/globals.css:42`
  - `src/components/Hero.tsx:15`
- **Fix**:
  ```css
  /* Change this */
  font-family: Inter, sans-serif;
  /* To this */
  font-family: 'Playfair Display', serif;
  ```

### Issue #2: ...
### Issue #3: ...

---
Applying fixes...
```

### Final Report

```markdown
## Design Improvement Summary

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| **Overall** | X.X | X.X | +X.X |
| Typography | X | X | +X |
| Color | X | X | +X |
| Layout | X | X | +X |
| Motion | X | X | +X |
| Polish | X | X | +X |
| Accessibility | X | X | +X |

## Files Modified
- `src/styles/globals.css` - Font family, shadows
- `src/styles/variables.css` - Color tokens
- `src/components/Hero/Hero.tsx` - Layout adjustments

## Iterations Completed: X

## Final Status: PASSING / NEEDS_MORE_WORK

## Remaining Recommendations
[If score < 8, list what else could be improved]
```

## File Discovery Patterns

### From Screenshot to Source File

1. **Extract element info from page**
   ```
   read_page(tabId, filter: "all") → accessibility tree with refs
   find(query: "hero section", tabId) → specific element refs
   ```

2. **Get class names from elements**
   - Look for `className`, `class` attributes in tree
   - Note component names from React DevTools patterns

3. **Search codebase**
   ```bash
   # CSS/SCSS files
   grep -r "\.hero-section" --include="*.css" --include="*.scss"

   # React/Vue components
   grep -r "className.*hero" --include="*.tsx" --include="*.jsx"

   # Tailwind classes
   grep -r "bg-gradient" --include="*.tsx"
   ```

4. **Common locations to check**
   ```
   src/styles/          # Global CSS
   src/app/globals.css  # Next.js global styles
   src/theme/           # Theme tokens
   src/components/      # Component styles
   tailwind.config.js   # Tailwind customization
   ```

## Chrome Tool Reference

| Tool | Purpose | Key Params |
|------|---------|------------|
| `tabs_context_mcp` | Get available tabs | `createIfEmpty: true` |
| `tabs_create_mcp` | Create new tab | - |
| `navigate` | Go to URL | `url`, `tabId` |
| `computer` | Screenshot/click | `action: "screenshot"`, `tabId` |
| `read_page` | Get element tree | `tabId`, `filter`, `depth` |
| `find` | Natural language search | `query`, `tabId` |

## Iteration Control

- **max_iterations**: 5 (prevents infinite loops)
- **pass_threshold**: 8.0 (design is "good enough")
- **auto_continue**: When score < 8.0
- **auto_stop**: When score >= 8.0 OR iterations >= 5

## Git Operations

After each iteration that makes code changes:
1. **Commit** with iteration context:
   ```bash
   git add <files> && git commit -m "design: [changes] (iteration N, score X.X)"
   ```

After the final iteration:
2. **Push** to trigger CI:
   ```bash
   git push
   ```

## Integration Notes

This skill integrates with:
- **webapp-testing**: Shares Chrome/Playwright decision patterns
- **frontend-design**: Uses design anti-pattern definitions
- **ux-designer**: Uses WCAG accessibility checklist

## Example Session

```
User: /designimprove the dashboard

Claude: [Takes screenshot of localhost:3000/dashboard]

## Design Grade: 5.4/10 - Needs Work

| Dimension | Score | Status | Key Issue |
|-----------|-------|--------|-----------|
| Typography | 4/10 | FAIL | Default Inter font |
| Color | 6/10 | PASS | Acceptable palette |
| Layout | 5/10 | FAIL | Standard grid layout |
| Motion | 3/10 | FAIL | No transitions |
| Polish | 5/10 | FAIL | Flat backgrounds |
| Accessibility | 8/10 | PASS | Good contrast |

## Top 3 Issues to Fix

### Issue #1: Generic Typography (Critical)
...

[Applies fixes]
[Takes new screenshot]

## Design Grade: 7.2/10 - Good (+1.8)

[Continues until score >= 8.0]

## Final Report
Overall improved from 5.4 to 8.1 in 3 iterations.
```
