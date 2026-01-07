---
description: Audit environment variables for fallback patterns, missing values, and config-dependent runtime behavior
---

Use ultrathink to thoroughly analyze configuration patterns and potential runtime issues.

## Purpose

Static code analysis (like /QA) cannot catch config-dependent runtime behavior. This command specifically audits environment variable usage to find issues that only manifest with production configuration.

## Execution Strategy

**Use the Task tool with subagent_type=Explore to scan systematically.**

### Phase 1: Discovery

Find all environment variable usages:
```bash
# Frontend env vars
grep -rn "NEXT_PUBLIC_" --include="*.ts" --include="*.tsx" src/ app/ lib/ hooks/ components/

# Backend env vars
grep -rn "process\.env\." --include="*.ts" --include="*.tsx" src/
grep -rn "os\.environ\|os\.getenv\|environ\.get" --include="*.py" .

# .env files
cat .env* 2>/dev/null | grep -v "^#"
```

### Phase 2: Fallback Pattern Detection

**CRITICAL: Find dangerous fallback patterns that activate when vars are empty.**

```bash
# JavaScript/TypeScript fallbacks to localhost
grep -rn "|| ['\"]http://localhost" --include="*.ts" --include="*.tsx" .
grep -rn "|| ['\"]ws://localhost" --include="*.ts" --include="*.tsx" .
grep -rn "?? ['\"]http://localhost" --include="*.ts" --include="*.tsx" .

# Empty string fallbacks
grep -rn "|| ['\"]['\"]" --include="*.ts" --include="*.tsx" .

# Python fallbacks
grep -rn "\.get(.*localhost" --include="*.py" .
grep -rn "or ['\"]http://localhost" --include="*.py" .
```

### Phase 3: Side Effect Tracing

For auth-related env vars, trace what happens on failure:

1. Find token/auth clearing functions:
```bash
grep -rn "clearToken\|logout\|removeToken\|deleteToken" --include="*.ts" --include="*.tsx" .
```

2. Find all callers of those functions:
```bash
# For each function found, trace callers
grep -rn "<function_name>" --include="*.ts" --include="*.tsx" .
```

3. Check if network errors trigger auth clearing:
```bash
grep -rn "401\|403\|unauthorized" --include="*.ts" --include="*.tsx" . | grep -i "clear\|logout\|remove"
```

### Phase 4: Link Validation

Find all static links and verify routes exist:

```bash
# Extract href values
grep -roh 'href="[^"]*"' --include="*.tsx" src/ app/ | sort -u

# Extract Link to values
grep -roh "to=['\"][^'\"]*['\"]" --include="*.tsx" src/ app/ | sort -u

# List all page routes
find app -name "page.tsx" -o -name "page.ts" | sed 's|app||;s|/page.tsx||;s|/page.ts||'
```

Compare extracted links against available routes. Flag any mismatches.

---

## Output Format

### Part A — Environment Variable Census

```
Total env vars found: X
- NEXT_PUBLIC_*: X vars
- Server-side: X vars

Env Vars with Fallbacks:
| Variable | Fallback Value | File:Line | Risk |
|----------|---------------|-----------|------|
| NEXT_PUBLIC_API_BASE | "http://localhost:8000" | lib/api.ts:5 | HIGH |
| ... | ... | ... | ... |
```

### Part B — Dangerous Fallback Patterns

```
Finding #<N>
Variable: <NEXT_PUBLIC_*>
Location: <file:line>
Current Code:
    const apiBase = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000"
Issue: Falls back to localhost when empty - will fail in production
Fix:
    const apiBase = process.env.NEXT_PUBLIC_API_BASE
    if (!apiBase) throw new Error("NEXT_PUBLIC_API_BASE is required")
```

### Part C — Auth Cascade Analysis

```
Token clearing functions found:
1. clearToken() in lib/auth.ts:45
   Called by:
   - onError(401) in lib/api.ts:78
   - logout() in components/Header.tsx:23
   - handleAuthError() in hooks/useAuth.ts:56

⚠️ WARNING: Network failure (401) triggers clearToken()
   Path: fetch fails → 401 response → onError → clearToken → user logged out
   Is this intentional? Verify auth cascade behavior.
```

### Part D — Broken Links

```
Links not matching any route:
| Link | Found In | Suggested Fix |
|------|----------|---------------|
| /activity | components/Nav.tsx:34 | Create app/activity/page.tsx or remove link |
| /settings/advanced | ... | ... |
```

### Part E — Recommendations

```
Before changing env vars:
1. Run: grep -rn "|| ['\"]http://localhost" to find fallbacks
2. Test with: NEXT_PUBLIC_API_BASE="" npm run dev
3. Check Network tab for localhost requests

Immediate fixes needed:
1. <file:line> - Remove localhost fallback
2. <file:line> - Add explicit error for missing config
```

---

## Checklist

Before finalizing:
- [ ] All NEXT_PUBLIC_* vars cataloged
- [ ] All fallback patterns identified
- [ ] Auth cascade paths traced
- [ ] Static links validated against routes
- [ ] Each finding has specific file:line reference
- [ ] Each finding has concrete fix
