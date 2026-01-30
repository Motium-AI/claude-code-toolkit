# CLAUDE.md Optimization Rubric

Actionable rubric for optimizing any project's CLAUDE.md file using best practices extracted from production Claude Code hooks, skills, and agent workflows.

## How to Use This Rubric

1. **Read the project's CLAUDE.md** (or note its absence)
2. **Score each section** against the checklist below
3. **Apply fixes** in priority order (P0 first)
4. **Validate** that the result is concise and token-efficient

**Principle**: CLAUDE.md is consumed by Claude on every session start. Every line costs tokens. Only include information that changes Claude's behavior. If removing a line wouldn't change how Claude works, delete it.

---

## Section Checklist

### 1. Repository Purpose (P1)

**What it does**: Orients Claude to the project's domain in 1-3 sentences.

**Required**:
- [ ] Single paragraph explaining what the repo is for
- [ ] Primary language/framework mentioned
- [ ] If monorepo, list the 2-3 main areas

**Anti-patterns**:
- Mission statements or marketing language ("We believe in...")
- Company history or team structure
- Duplicating what's already in README.md

**Good example**:
```markdown
## Repository Purpose
FastAPI backend for Pauwels ATS. Indexes Bullhorn entities into Elasticsearch,
runs PydanticAI matching agents, serves REST API consumed by Next.js frontend.
```

---

### 2. Autonomous Execution Policy (P0)

**What it does**: Prevents Claude from stopping early to ask permission for trivial decisions. This is the single highest-impact section for productivity.

**Why P0**: Without this, Claude asks "Would you like me to..." after every discovery, which:
- Breaks flow during autonomous workflows (/appfix, /godo)
- Can cause session timeouts while waiting for response
- Bypasses stop-hook compliance checks (stop hook fires on explicit stop, not on "waiting for input")

**Required**:
- [ ] Explicit "Do NOT ask" instructions with examples of bad phrases
- [ ] "DO continue" instructions for autonomous behavior
- [ ] Clear exceptions list (when to actually ask)
- [ ] Explanation of WHY this matters (stop hook bypass risk)

**Template**:
```markdown
## Autonomous Execution Policy

**CRITICAL: When working on tasks, especially during plan execution:**

- **Do NOT ask** "Would you like me to investigate..." or "Should I continue with..."
- **Do NOT wait** for user permission for related problems discovered during work
- **DO continue** working and investigate immediately when you find issues
- **ONLY stop** when the user's original goal is FULLY met or you hit a true blocker
- **If you find** a blocking issue, FIX IT -- don't ask permission first

**Exceptions (when to ask):**
- Ambiguous user intent that could lead to destructive actions
- Need for credentials, API keys, or sensitive information
- Actions that would cost money or have irreversible external effects
- Genuinely unclear requirements where multiple valid interpretations exist
```

**Source**: Derived from stop-validator.py behavior -- the stop hook validates completion checkpoints but only fires on explicit stop events, not when Claude is "waiting for input."

---

### 3. Validation Commands (P1)

**What it does**: Gives Claude exact commands to verify its work. Without this, Claude guesses at validation or skips it.

**Required**:
- [ ] Commands are copy-pasteable (not pseudocode)
- [ ] Cover: lint, type-check, test, build
- [ ] Include project-specific validation (e.g., `jq . *.json` for JSON templates)
- [ ] Note any required tools or setup

**Anti-patterns**:
- "Run the tests" without specifying which test command
- Commands that require interactive input
- Commands that only work in CI (not locally)

**Template**:
```markdown
## Validation Commands

\```bash
# Type checking
npx tsc --noEmit

# Lint
npx eslint src/ --max-warnings=0

# Unit tests
npx vitest run

# E2E tests (requires running server)
npx playwright test

# Build verification
npm run build
\```
```

---

### 4. Architecture Overview (P1)

**What it does**: Prevents Claude from proposing changes that conflict with existing patterns.

**Required**:
- [ ] Directory structure (abbreviated, not exhaustive)
- [ ] Key architectural decisions (monorepo structure, service boundaries, data flow)
- [ ] Entity/domain relationships if applicable
- [ ] Tech stack with specific versions where it matters

**Anti-patterns**:
- Full `tree` output (wastes tokens, gets stale)
- Documenting every file (that's what Glob is for)
- Architecture aspirations vs. current reality

**Optimization**: Only document structure that Claude can't discover via Glob/Grep. Focus on non-obvious relationships and decisions.

---

### 5. Style Conventions (P2)

**What it does**: Prevents Claude from introducing inconsistent formatting or naming.

**Required**:
- [ ] Indentation (tabs vs. spaces, width)
- [ ] Naming conventions (snake_case, camelCase, PascalCase) per context
- [ ] File naming patterns
- [ ] Import ordering if relevant

**Anti-patterns**:
- Duplicating what's in .editorconfig, .prettierrc, or eslint config
- Obvious conventions ("use semicolons in JavaScript" -- eslint handles this)

**Rule**: Only document conventions that automated tools DON'T enforce. If prettier/eslint/ruff handles it, don't mention it.

---

### 6. Scripts & Commands Reference (P2)

**What it does**: Tells Claude what utility scripts exist so it uses them instead of reinventing.

**Required**:
- [ ] Table format: Script | Purpose
- [ ] Only scripts Claude would actually use (not internal CI scripts)
- [ ] Note any required arguments or environment

---

### 7. Hook & Skill Documentation (P1 if using toolkit)

**What it does**: Documents the lifecycle hooks and skills so Claude understands what automated behavior exists around it.

**Required (if using Namshub)**:
- [ ] Extension types table: Type | Location | Trigger
- [ ] Available commands with categories
- [ ] Available skills with triggers and purpose
- [ ] Hook behavior table: Event | Script | Purpose
- [ ] Security model explanation (auto-approval conditions)
- [ ] Key behavioral notes (plan mode enforcement, deployment enforcement, hook reload)

**Why this matters**: Without hook documentation, Claude doesn't know:
- That it will be blocked from editing until plan mode completes
- That stop-validator will prevent stopping if checkpoint is incomplete
- That auto-approval only works during /appfix or /build sessions
- That hooks are captured at startup and won't reflect mid-session changes

**Source**: Extracted from settings.json hook definitions and individual hook docstrings.

---

### 8. Completion Checkpoint Documentation (P1 if using toolkit)

**What it does**: Documents the checkpoint system that enforces task completion.

**Required (if using /appfix or /build)**:
- [ ] Checkpoint JSON structure with field explanations
- [ ] What the stop hook validates
- [ ] Key state files and their purpose
- [ ] How checkpoint invalidation works (edit → reset → re-validate)

---

## Token Optimization Rules

CLAUDE.md is loaded on EVERY session. Token waste here is multiplied by every conversation.

### Do Include
- Information that changes Claude's behavior
- Commands Claude needs to run
- Architecture Claude can't discover via tools
- Policies that override Claude's defaults (e.g., autonomous execution)
- Non-obvious relationships between components

### Do NOT Include
- Information Claude can discover via Glob/Grep/Read
- README content (Claude can read README.md separately)
- Marketing or mission statements
- Detailed API documentation (put in docs/, reference from CLAUDE.md)
- Full directory tree listings (use abbreviated structure)
- Changelog or version history
- Contributor guidelines (not relevant to Claude)
- License information

### Size Guidelines

| Project Size | Target CLAUDE.md Size | Sections |
|-------------|----------------------|----------|
| Small (< 10 files) | 50-100 lines | Purpose, Validation, Style |
| Medium (10-100 files) | 100-200 lines | + Architecture, Scripts |
| Large (100+ files) | 200-400 lines | + Hooks, Skills, Checkpoint |
| Monorepo | 300-500 lines | All sections, abbreviated per area |

**Hard ceiling**: If CLAUDE.md exceeds 500 lines, split into CLAUDE.md (core) + docs/ references.

---

## Optimization Workflow

### Phase 1: Audit
```
1. Read current CLAUDE.md (or confirm it doesn't exist)
2. Score each section against checklist above
3. Identify: missing sections, bloated sections, stale content
4. Check for anti-patterns (marketing language, exhaustive trees, obvious conventions)
```

### Phase 2: Scan Project for Context
```
1. Glob for config files: .eslintrc*, .prettierrc*, tsconfig.json, pyproject.toml
   → Remove style conventions already enforced by tooling
2. Grep for existing patterns: import conventions, error handling, logging
   → Only document non-obvious patterns
3. Check for hooks/skills: ~/.claude/hooks/, ~/.claude/skills/
   → If toolkit installed, add hook/skill documentation
4. Read package.json / pyproject.toml for available scripts
   → Add to validation commands
```

### Phase 3: Write/Rewrite
```
1. Start with P0 sections (Autonomous Execution Policy)
2. Add P1 sections (Purpose, Validation, Architecture, Hooks)
3. Add P2 sections only if they add behavioral value
4. Apply token optimization rules
5. Verify no section duplicates information from config files
```

### Phase 4: Validate
```
1. Token count: wc -w CLAUDE.md (target: < 2000 words for medium projects)
2. Behavioral test: "If I remove this line, would Claude behave differently?"
3. Staleness test: "Will this information be true in 3 months?"
4. Discovery test: "Could Claude find this via Glob/Grep in 2 seconds?"
   → If yes to discovery test, remove it
```

---

## Common Optimization Patterns

### Pattern: Bloated Directory Tree
**Before** (wastes ~200 tokens):
```
src/
  components/
    Button.tsx
    Card.tsx
    Modal.tsx
    ... (50 more files)
```

**After** (saves tokens, still useful):
```
src/components/    # Reusable UI (shadcn/ui based)
src/app/           # Next.js App Router pages
src/lib/           # Shared utilities and API clients
```

### Pattern: Redundant Style Rules
**Before**:
```
- Use 2-space indentation
- Use single quotes for strings
- Add trailing commas
- Use semicolons
```

**After**:
```
Style is enforced by prettier and eslint. See .prettierrc for configuration.
Only non-tooled convention: file names use kebab-case.
```

### Pattern: Missing Autonomous Policy
**Symptom**: Claude constantly asks "Should I continue?" during complex tasks.
**Fix**: Add the Autonomous Execution Policy section (see template above).

### Pattern: No Validation Commands
**Symptom**: Claude makes changes but never verifies them, or guesses wrong test commands.
**Fix**: Add explicit, copy-pasteable validation commands.

### Pattern: Stale Architecture
**Symptom**: CLAUDE.md describes planned architecture, not current. Claude creates files in directories that don't exist.
**Fix**: Run `ls` on key directories and update to match reality. Only document what EXISTS.
