---
name: burndown
description: Autonomous tech debt elimination. Combines /deslop + /qa into an iterative fix loop. Scans for code slop and architecture issues, prioritizes by severity, and autonomously fixes until completion. Use when asked to "burn down debt", "clean up codebase", or "/burndown".
---

# Tech Debt Burndown (/burndown)

Autonomous tech debt elimination skill that combines `/deslop` (AI slop detection) and `/qa` (architecture audit) into a fully agentic iterative fix loop. Unlike the detection-only commands, `/burndown` **finds AND fixes** issues until a completion checkpoint passes.

## Architecture: Iterative Fix-Verify Loop

```
┌─────────────────────────────────────────────────────────────────┐
│  COMPLETION CHECKPOINT VALIDATION                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Load .claude/completion-checkpoint.json                         │
│                                                                  │
│  Check booleans deterministically:                               │
│    - scan_complete: false → BLOCKED                              │
│    - critical_fixed: false → BLOCKED                             │
│    - linters_pass: false → BLOCKED                               │
│    - re_scan_verified: false → BLOCKED                           │
│    - is_job_complete: false → BLOCKED                            │
│                                                                  │
│  If blocked → continue fixing                                    │
│  All checks pass → exit(0) → Allow stop                          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## CRITICAL: Autonomous Execution

**THIS WORKFLOW IS 100% AUTONOMOUS. YOU MUST:**

1. **NEVER ask for confirmation** - No "Should I fix this?", "Should I commit?"
2. **Auto-fix all issues** - Apply fixes without asking
3. **Auto-commit** - Commit after each batch of fixes
4. **Run linters after every batch** - Fix ALL linter errors including pre-existing
5. **Re-scan to verify** - Confirm fixes worked, catch regressions
6. **Fill out checkpoint honestly** - The stop hook checks your booleans

**Only stop when the checkpoint passes. If critical issues remain, you're blocked.**

## Triggers

- `/burndown` (primary)
- `/burndown [scope]` (scoped to directory/file/pattern)
- "burn down debt"
- "burn down tech debt"
- "clean up the codebase"
- "fix the code slop"
- "remove ai slop"
- "codebase cleanup"

## Scope Arguments

| Invocation | Scope Type | Behavior |
|------------|------------|----------|
| `/burndown` | codebase | Full codebase scan |
| `/burndown src/auth/` | directory | Scan only that directory |
| `/burndown src/api/users.py` | file | Scan only that file |
| `/burndown *.tsx` | pattern | Scan files matching pattern |

## Completion Checkpoint Schema

Before stopping, you MUST create `.claude/completion-checkpoint.json`:

```json
{
  "self_report": {
    "code_changes_made": true,
    "scan_complete": true,
    "scan_complete_at_version": "abc1234",
    "critical_fixed": true,
    "critical_fixed_at_version": "def5678",
    "high_fixed": true,
    "linters_pass": true,
    "linters_pass_at_version": "def5678",
    "re_scan_verified": true,
    "re_scan_verified_at_version": "def5678",
    "browser_verification_skipped": true,
    "browser_verification_skip_reason": "pure_refactoring",
    "is_job_complete": true
  },
  "reflection": {
    "what_was_done": "Fixed 17 critical/high issues across 8 files. Reduced debt score from 47 to 6.",
    "what_remains": "6 low-priority issues (verbose variables, minor naming inconsistencies)",
    "blockers": null
  },
  "burndown_metrics": {
    "issues_at_start": 47,
    "issues_at_end": 6,
    "debt_reduction_percentage": 87.2,
    "iterations_required": 3,
    "files_modified": 8,
    "by_severity": {
      "critical_fixed": 5,
      "high_fixed": 12,
      "medium_fixed": 20,
      "low_remaining": 6
    }
  },
  "evidence": {
    "scan_artifacts": ".claude/burndown-scan.json",
    "fix_log": ".claude/burndown-fixes.json"
  }
}
```

| Field | Type | Required | When Blocked |
|-------|------|----------|--------------|
| `scan_complete` | bool | yes | Detection scan not finished |
| `critical_fixed` | bool | yes | Critical issues remain unfixed |
| `high_fixed` | bool | no | High issues remain (warning, not blocking) |
| `linters_pass` | bool | yes | Linter errors exist |
| `re_scan_verified` | bool | yes | Haven't verified fixes via re-scan |
| `browser_verification_skipped` | bool | conditional | Must be true with valid reason if skipping |
| `is_job_complete` | bool | yes | Self-reported incomplete |
| `what_remains` | string | yes | Must be "none" OR only low/medium issues |

## Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 0: ACTIVATION                                            │
│     └─► Create .claude/autonomous-state.json (auto-approval)    │
│     └─► Parse scope from arguments or detect from context       │
├─────────────────────────────────────────────────────────────────┤
│  ╔═══════════════════════════════════════════════════════════╗  │
│  ║  PHASE 0.5: LITE HEAVY PLANNING (MANDATORY)               ║  │
│  ║     └─► EnterPlanMode                                     ║  │
│  ║     └─► Launch 2 parallel Opus agents (from /heavy):      ║  │
│  ║         ├─► First Principles: "What debt can be deleted?" ║  │
│  ║         └─► AGI-Pilled: "What would zero-debt look like?" ║  │
│  ║     └─► Synthesize deletion vs improvement tradeoffs      ║  │
│  ║     └─► ExitPlanMode                                      ║  │
│  ╚═══════════════════════════════════════════════════════════╝  │
├─────────────────────────────────────────────────────────────────┤
│  PHASE 1: MULTI-AGENT DETECTION SCAN                            │
│     └─► Launch 3 parallel detection agents:                     │
│         ├─► Code Slop Hunter (deslop patterns 1-25)             │
│         ├─► Architecture Auditor (qa size + coupling)           │
│         └─► Debt Classifier (qa scalability + maintainability)  │
│     └─► Store findings in .claude/burndown-scan.json            │
├─────────────────────────────────────────────────────────────────┤
│  PHASE 2: PRIORITIZATION                                        │
│     └─► Synthesize all agent findings                           │
│     └─► Deduplicate overlapping issues                          │
│     └─► Assign severity: Critical > High > Medium > Low         │
│     └─► Generate prioritized fix queue                          │
├─────────────────────────────────────────────────────────────────┤
│  PHASE 3: ITERATIVE FIX LOOP                                    │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  FOR each batch in fix_queue (by severity, then file):    │  │
│  │     └─► Apply fixes via Edit tool                         │  │
│  │     └─► Run linters, fix ALL errors                       │  │
│  │     └─► Commit: "burndown: [summary]"                     │  │
│  │     └─► Update iteration count in state                   │  │
│  └───────────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│  PHASE 4: RE-SCAN VERIFICATION                                  │
│     └─► Run detection agents again on modified files            │
│     └─► Compare: issues_before vs issues_after                  │
│     └─► Calculate debt_burned_percentage                        │
│     └─► If new issues introduced: add to queue, return to Phase 3
├─────────────────────────────────────────────────────────────────┤
│  PHASE 5: BROWSER VERIFICATION (CONDITIONAL)                    │
│     └─► If frontend files modified: run surf-verify.py          │
│     └─► If pure refactoring: skip with documented reason        │
├─────────────────────────────────────────────────────────────────┤
│  PHASE 6: COMPLETION                                            │
│     └─► Update completion-checkpoint.json with metrics          │
│     └─► Stop hook validates checkpoint                          │
│     └─► If blocked: return to Phase 3                           │
│     └─► If passed: clean up state files, done                   │
└─────────────────────────────────────────────────────────────────┘
```

## Phase 0: Activation

### State File (Automatic)

Create the state file at activation to enable auto-approval:

**File**: `.claude/autonomous-state.json` (with `"mode": "burndown"`)

```json
{
  "started_at": "2026-01-30T10:00:00Z",
  "last_activity_at": "2026-01-30T10:30:00Z",
  "session_id": "abc123",
  "iteration": 1,
  "plan_mode_completed": false,
  "coordinator": true,

  "scope": {
    "type": "directory",
    "value": "src/components/",
    "detected_from": "argument"
  },

  "scan_results": {
    "total_issues": 47,
    "by_severity": {
      "critical": 5,
      "high": 12,
      "medium": 20,
      "low": 10
    },
    "by_category": {
      "slop": 18,
      "architecture": 15,
      "scalability": 8,
      "dead_code": 6
    }
  },

  "fix_progress": {
    "batches_total": 5,
    "batches_completed": 2,
    "issues_fixed": 17,
    "issues_remaining": 30
  },

  "metrics": {
    "initial_debt_score": 47,
    "current_debt_score": 30,
    "debt_burned_percentage": 36.2
  }
}
```

## Phase 0.5: Lite Heavy Planning (MANDATORY)

Uses `/heavy`'s required agents to determine what should be deleted vs improved.

### Workflow

1. **Call `EnterPlanMode`**

2. **Explore the scope**:
   - What files are in scope?
   - What patterns already exist?
   - What recent changes were made?

3. **Launch 2 parallel Opus agents** (from heavy/SKILL.md):

   **First Principles Agent**:
   > "What tech debt can be DELETED entirely? What code is over-engineered?
   > What abstractions exist that shouldn't? Apply the Elon Musk algorithm:
   > Question every requirement, delete aggressively, simplify what remains."

   **AGI-Pilled Agent**:
   > "What would a zero-debt version of this codebase look like?
   > Where are we being too conservative? What patterns would a god-tier
   > engineer use? What constraints are arbitrary?"

4. **Synthesize tradeoffs**:
   ```
   TRADEOFF: [component/pattern]
   - First Principles: Delete entirely because [reason]
   - AGI-Pilled: Improve to [target state] because [capability argument]
   - Resolution: [chosen approach]
   ```

5. **Write plan with scope decisions**:
   - What to delete (First Principles wins)
   - What to improve (AGI-Pilled wins)
   - What to leave alone (not worth the effort)

6. **Call `ExitPlanMode`**

## Phase 1: Multi-Agent Detection Scan

Launch **3 parallel agents** to detect all tech debt issues.

### Agent 1: Code Slop Hunter

**Focus**: deslop patterns 1-25 (AI-generated code slop)

**Detects**:
- Unnecessary defensive checks (redundant null guards, isinstance checks)
- Verbose variable declarations (assign-and-return, one-line intermediates)
- Over-commented code (comments restating obvious operations)
- Unnecessary exception handling (try/except on non-throwing code)
- Verbose truthiness patterns (`len(x) > 0` instead of `if x`)
- Unnecessary memoization (useMemo on string concat, useCallback with [])
- Type assertion abuse (`as any`, `as unknown`, `@ts-ignore`)
- Verbose conditional rendering (`condition ? X : null` instead of `condition && X`)

**Output format**:
```json
{
  "file": "src/components/Button.tsx",
  "line": 42,
  "pattern_id": "unnecessary_memoization",
  "severity": "medium",
  "current_code": "const label = useMemo(() => `${first} ${last}`, [first, last])",
  "fix_suggestion": "const label = `${first} ${last}`"
}
```

### Agent 2: Architecture Auditor

**Focus**: qa size + coupling patterns

**Detects**:
- Files exceeding 500 lines (critical), 300 lines (warning)
- Functions exceeding 50 lines
- Cyclomatic complexity > 10
- React components exceeding 200 lines
- Circular dependencies
- Cross-domain imports (feature importing from unrelated feature)
- Deep imports (`../../../other/internal/private`)
- God objects (5+ unrelated responsibilities)
- Leaky abstractions (DB schemas exposed across boundaries)

**Output format**:
```json
{
  "file": "src/services/userService.ts",
  "line": 1,
  "category": "file_size",
  "severity": "critical",
  "metric": 623,
  "threshold": 500,
  "refactor_approach": "Split into UserAuthService, UserProfileService, UserPreferencesService"
}
```

### Agent 3: Debt Classifier

**Focus**: qa scalability + maintainability patterns

**Detects**:
- N+1 query patterns (loops containing queries/awaits)
- Missing pagination on list endpoints
- Unbounded data structures (growing without limits)
- Sequential awaits that could be parallelized
- Dead code (unused exports, unreachable branches)
- Type safety gaps (`any`, missing return types)
- Consistency violations (mixed naming conventions)
- Error handling gaps (empty catches, swallowed errors)

**Output format**:
```json
{
  "file": "src/api/users.py",
  "line": 87,
  "category": "n_plus_one",
  "severity": "high",
  "description": "Query inside for loop fetches related data one-by-one",
  "fix_suggestion": "Use prefetch_related or eager loading"
}
```

## Phase 2: Prioritization

After agents return, synthesize findings into a prioritized fix queue.

### Severity Classification

| Severity | Criteria | Action |
|----------|----------|--------|
| **Critical** | Breaks at scale, security risk, circular deps | MUST fix to pass checkpoint |
| **High** | Performance impact, coupling issues, 500+ line files | Should fix |
| **Medium** | Code slop, style violations, minor duplication | Nice to fix |
| **Low** | Verbose patterns, naming consistency | Optional |

### Deduplication

Multiple agents may flag the same issue differently:
- Slop Hunter: "unnecessary memoization"
- Architecture Auditor: "component too complex"

Merge overlapping findings, keep highest severity.

### Fix Queue Structure

```json
{
  "queue": [
    {
      "batch": 1,
      "severity": "critical",
      "files": ["src/services/userService.ts"],
      "issues": [
        {"type": "file_size", "fix": "split_service"},
        {"type": "circular_dep", "fix": "extract_interface"}
      ]
    },
    {
      "batch": 2,
      "severity": "high",
      "files": ["src/api/users.py", "src/api/orders.py"],
      "issues": [
        {"type": "n_plus_one", "fix": "prefetch_related"},
        {"type": "sequential_await", "fix": "Promise.all"}
      ]
    }
  ]
}
```

## Phase 3: Iterative Fix Loop

### Fix Each Batch

1. **Apply fixes** via Edit tool
2. **Run linters** after each batch:
   ```bash
   # JavaScript/TypeScript
   [ -f package.json ] && npm run lint 2>/dev/null || npx eslint . --ext .js,.jsx,.ts,.tsx
   [ -f tsconfig.json ] && npx tsc --noEmit

   # Python
   [ -f pyproject.toml ] && ruff check --fix .
   [ -f pyrightconfig.json ] && pyright
   ```
3. **Fix ALL linter errors** including pre-existing ones
4. **Commit** after each batch:
   ```bash
   git add <files> && git commit -m "burndown: fix [severity] issues in [files]"
   ```

### Iteration Tracking

Update `autonomous-state.json` after each batch:
- Increment `iteration`
- Update `batches_completed`
- Update `issues_fixed` / `issues_remaining`
- Recalculate `debt_burned_percentage`

## Phase 4: Re-Scan Verification

After fixing all batches, re-run detection on modified files.

### Verification Checks

1. **Issues reduced**: `issues_after < issues_before`
2. **No regressions**: No new critical/high issues introduced
3. **Fixes worked**: Specific patterns no longer detected

### Regression Handling

If re-scan finds new issues:
1. Add to fix queue
2. Return to Phase 3
3. Repeat until clean

## Phase 5: Browser Verification (Conditional)

### When Required

| Change Type | Browser Verification |
|-------------|---------------------|
| React component refactoring | Required |
| CSS/styling changes | Required |
| API endpoint changes | Required (check UI still works) |
| Pure backend refactoring | Skip |
| Type-only changes | Skip |
| Dead code removal | Skip |
| Import reorganization | Skip |

### Skip Documentation

If skipping browser verification:
```json
{
  "browser_verification_skipped": true,
  "browser_verification_skip_reason": "pure_refactoring|no_frontend_changes|dead_code_only|type_changes_only"
}
```

### When Required

Use Surf CLI first:
```bash
python3 ~/.claude/hooks/surf-verify.py --urls "https://staging.example.com/affected-page"
cat .claude/web-smoke/summary.json
```

## Phase 6: Completion

### Update Checkpoint

```json
{
  "self_report": {
    "scan_complete": true,
    "critical_fixed": true,
    "linters_pass": true,
    "re_scan_verified": true,
    "is_job_complete": true
  },
  "reflection": {
    "what_was_done": "Burned down 41 issues (5 critical, 12 high, 20 medium, 4 low). Split userService.ts, fixed N+1 queries, removed dead code.",
    "what_remains": "6 low-priority issues: verbose variables in utils.ts, naming consistency in tests"
  },
  "burndown_metrics": {
    "issues_at_start": 47,
    "issues_at_end": 6,
    "debt_reduction_percentage": 87.2
  }
}
```

### Exit Conditions

| Condition | Result |
|-----------|--------|
| `critical_fixed: true` AND `linters_pass: true` AND `re_scan_verified: true` | SUCCESS - stop allowed |
| Any required boolean false | BLOCKED - continue fixing |
| `what_remains` lists critical issues | BLOCKED - continue fixing |
| `what_remains` lists only low issues | SUCCESS - acceptable |

### Cleanup

On successful completion:
```bash
rm -f ~/.claude/autonomous-state.json .claude/autonomous-state.json
```

## Comparison with /deslop and /qa

| Aspect | /deslop | /qa | /burndown |
|--------|---------|-----|-----------|
| **Type** | Command (stateless) | Command (stateless) | Skill (stateful) |
| **Output** | Report findings | Report findings | **Fix findings** |
| **Patterns** | 25 slop patterns | 6 arch dimensions | All combined |
| **Iteration** | Single pass | Single pass | Fix-verify loop |
| **Checkpoint** | None | None | Enforced |
| **Auto-approval** | No | No | Yes |
| **Prioritization** | By slop density | By severity | By severity + category |
| **Verification** | None | None | Re-scan + browser |
| **Metrics** | Count | Count | Debt burned % |
| **Exit** | Report complete | Report complete | Zero critical + linters pass |

## Example Session

```
User: /burndown src/components/

[Phase 0: Activation]
→ Created .claude/autonomous-state.json
→ Scope: {type: "directory", value: "src/components/"}

[Phase 0.5: Lite Heavy Planning]
→ EnterPlanMode
→ First Principles: "Delete unused Modal, Tooltip components"
→ AGI-Pilled: "Consolidate 5 button variants into 1 polymorphic Button"
→ Plan: Delete 2 components, consolidate buttons, fix slop in remaining
→ ExitPlanMode

[Phase 1: Detection Scan]
→ Code Slop Hunter: 18 issues (memoization, null guards, verbose patterns)
→ Architecture Auditor: 8 issues (file size, coupling)
→ Debt Classifier: 6 issues (dead code, type safety)
→ Total: 32 issues (4 critical, 8 high, 14 medium, 6 low)

[Phase 2: Prioritization]
→ Batch 1: Critical (circular dep in Modal.tsx, 600-line Table.tsx)
→ Batch 2: High (N+1 in DataGrid, memoization abuse in Form)
→ Batch 3: Medium (verbose patterns, dead imports)

[Phase 3: Fix Loop]
→ Iteration 1: Fix Batch 1 (critical) → lint → commit
→ Iteration 2: Fix Batch 2 (high) → lint → commit
→ Iteration 3: Fix Batch 3 (medium) → lint → commit

[Phase 4: Re-scan]
→ Re-scan modified files
→ Issues now: 6 (0 critical, 0 high, 2 medium, 4 low)
→ No regressions

[Phase 5: Browser Verification]
→ Frontend components modified → run surf-verify.py
→ Screenshot shows components working
→ Console: 0 errors

[Phase 6: Completion]
→ Checkpoint: critical_fixed=true, linters_pass=true, re_scan_verified=true
→ what_remains: "6 low-priority issues in Button.tsx, utils.ts"
→ Stop hook validates → PASS
→ debt_burned_percentage: 81.25%
→ Session complete
```

## Reference Files

| Reference | Path |
|-----------|------|
| Detection patterns | `references/detection-patterns.md` |
| Checkpoint schema | `references/checkpoint-schema.md` |
| Heavy agent prompts | `~/.claude/skills/heavy/SKILL.md` |

## Philosophy

### Why "/burndown" Works

1. **Iterative loop** - Fixes are verified, regressions caught
2. **Priority enforcement** - Critical issues must be fixed
3. **Honest checkpoint** - Can't exit with lies
4. **Combined detection** - Best of deslop + qa
5. **Autonomous execution** - No confirmation fatigue

### Debt Reduction Strategy

1. **Delete first** (First Principles) - Remove what shouldn't exist
2. **Simplify second** - Reduce complexity before optimizing
3. **Fix patterns** - Apply consistent fixes across codebase
4. **Verify everything** - Re-scan confirms fixes worked

### Exit Philosophy

Zero critical issues = exit allowed.
Medium/low issues = documented in `what_remains`.
This prevents perfectionism loops while ensuring critical debt is addressed.
