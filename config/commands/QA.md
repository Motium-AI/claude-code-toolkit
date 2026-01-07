---
description: Exhaustive codebase audit for architectural health, maintainability, and scalability
---

## Execution Strategy

**CRITICAL: Use plan mode and parallel agents for this audit.**

### Phase 1: Strategic Exploration (Plan Mode)
Use `EnterPlanMode` to research before generating findings. Launch up to 3 parallel `Task` agents with `subagent_type=Explore`:

**Agent 1 - Size & Complexity Census:**
- Find all files > 300 lines
- Find all functions > 50 lines
- Map high-complexity areas and nesting depth

**Agent 2 - Architecture & Coupling:**
- Map import graph across modules
- Find circular dependencies
- Identify cross-domain imports and layer violations

**Agent 3 - Patterns & Consistency:**
- Catalog error handling patterns across codebase
- Find naming convention inconsistencies
- Identify dead code and unused exports

**Agent 4 - Configuration Resilience:**
- Find all `NEXT_PUBLIC_*` and `process.env.*` usages
- Detect fallback patterns: `|| 'http://localhost'`, `?? ''`
- Trace auth cascade paths (what triggers `clearToken`/`logout`)
- Validate static links against actual routes

### Phase 2: Synthesis
After agents return, synthesize findings in the plan file:
- Cross-reference findings to identify systemic issues
- Group related violations for batch refactoring
- Prioritize by risk (scalability, maintainability, security)

### Phase 3: Report Generation
Exit plan mode and generate the final report using the synthesized findings.

---

Conduct an exhaustive audit of the ENTIRE codebase for architectural health, maintainability, and scalability. Use ultrathink extended thinking to thoroughly analyze every finding.

**Scope: Leave No Stone Unturned.**
- Scan EVERY source file in the repository — do not sample or spot-check.
- Trace import graphs and data flows completely, not just surface-level inspection.
- Examine every module boundary, every public interface, every integration point.
- Check both the "happy path" code AND error handling, edge cases, and fallback logic.

**Your Priorities (in order):**

**1. File Size & Complexity Violations (Complete Census):**
Analyze EVERY file in the codebase:
- Catalog ALL files exceeding 500 lines of code (list every one, no exceptions).
- Catalog ALL files exceeding 300 lines (as early warning candidates).
- For each oversized file, assess: is the length justified (auto-generated, lookup tables, single cohesive domain) or does it indicate a need to decompose?
- Flag ALL functions/methods exceeding 50 lines.
- Flag ALL functions with cyclomatic complexity > 10 or deep nesting (> 4 levels).
- Flag ALL React components exceeding 200 lines or rendering logic exceeding 100 lines.
- Identify files with too many exports (> 10 public exports suggests unfocused module).

**2. Separation of Concerns Violations (Layer by Layer):**
Systematically check each architectural layer for responsibility bleeding:

*Frontend (React/TS):*
- Components containing business logic, data fetching, AND presentation — all three should be separated.
- Components directly calling APIs instead of going through a data layer.
- Business logic living in components instead of hooks/services.
- UI state mixed with server state.
- Styling logic mixed with behavioral logic.

*Backend (Python):*
- Route handlers containing business logic instead of delegating to services.
- Services directly accessing database/ORM instead of going through repositories.
- Validation logic scattered across layers instead of centralized.
- Domain objects knowing about HTTP, serialization, or infrastructure.

*Cross-cutting:*
- Files that import from unrelated domains (map out every cross-domain import).
- "God objects" or "god files" that have become dumping grounds (> 5 unrelated responsibilities).
- Utility files that have grown into catch-all junk drawers.
- Shared folders that contain domain-specific code that shouldn't be shared.

**3. Abstraction & Coupling Issues (Full Dependency Analysis):**
Map the complete dependency graph and flag:

*Coupling Violations:*
- Modules reaching deep into other modules' internals (accessing non-public members, importing from nested paths like `../../../other-module/internals/private`).
- Feature modules importing from other feature modules instead of shared abstractions.
- Circular dependencies or import cycles (list every cycle found).
- Implicit coupling through shared mutable state.
- Temporal coupling (code that only works if called in a specific order).

*Abstraction Violations:*
- Leaky abstractions: implementation details (DB schemas, API response shapes, third-party library types) exposed across boundaries.
- Wrong abstraction level: high-level modules depending on low-level details.
- Missing abstractions: raw primitives passed around where domain types should exist.
- Over-abstraction: unnecessary interfaces, abstract classes, or indirection with only one implementation and no foreseeable variants.

*Configuration & Hardcoding:*
- Hardcoded values that should be environment configuration (URLs, credentials, feature flags, limits).
- Magic numbers/strings without named constants (catalog every instance).
- Environment-specific logic embedded in code instead of configuration.

*Duplication:*
- Copy-pasted logic (flag 2+ instances, not just 3+) — include line counts and locations.
- Near-duplicate functions that vary by only 1-2 lines.
- Repeated structural patterns that should be abstracted (e.g., same try/catch/log pattern everywhere).

**4. Scalability Red Flags (Systematic Review):**
Examine every data flow path for scalability issues:

*Data Fetching & Queries:*
- N+1 patterns: loops containing queries, awaits, or API calls.
- Missing pagination on ALL queries and API responses that return lists.
- Queries without limits that could return unbounded results.
- Missing database indexes for common query patterns (infer from query shapes).
- Full table scans or SELECT * patterns.

*Async & Concurrency:*
- Synchronous blocking operations that should be async (file I/O, network calls, heavy computation on main thread).
- Sequential awaits that could be parallelized (Promise.all / asyncio.gather).
- Missing concurrency limits on parallel operations (could spawn thousands of requests).
- Race conditions in shared state access.
- Missing timeouts on external calls.

*Memory & Resources:*
- Unbounded data structures: lists, maps, caches that grow without limits.
- Missing cleanup: event listeners not removed, subscriptions not unsubscribed, connections not closed.
- Large objects held in memory longer than necessary.
- Accumulating state in long-lived processes.

*State & Caching:*
- In-memory caches without TTL or invalidation strategy.
- State that won't survive multiple instances (sticky sessions required but not documented).
- Missing cache layers where repeated expensive operations occur.
- Stale reads from caches without invalidation on writes.

*Frontend-Specific:*
- Unbounded lists rendering without virtualization.
- Missing memoization on expensive derived computations (legitimate cases, not over-memoization).
- Re-renders cascading due to unstable references in context or props.
- Large bundle sizes from uncode-split imports.

**5. Maintainability Debt (Complete Inventory):**
Flag ALL code that will slow down future development:

*Consistency Violations:*
- Inconsistent patterns for the same problem across the codebase (list each pattern and where each variant appears).
- Inconsistent naming conventions (camelCase vs snake_case mixing, inconsistent prefixes/suffixes).
- Inconsistent error handling approaches.
- Inconsistent file/folder organization across similar modules.

*Dead Code (Exhaustive):*
- Unused exports (not imported anywhere).
- Unused functions, classes, components (not called anywhere).
- Unreachable branches (conditions that can never be true).
- Commented-out code blocks (every instance).
- Unused dependencies in package.json / requirements.txt.
- Feature flags that are permanently on/off.
- Dead feature folders (code for removed features still present).

*Type Safety Gaps:*
- Python: untyped public APIs, missing return types, `Any` usage, `# type: ignore` comments.
- TypeScript: `any` usage (every instance), type assertions (`as`), non-null assertions, `@ts-ignore` / `@ts-expect-error` comments.
- Stringly-typed logic that should use enums/unions.
- Runtime type checks that indicate missing compile-time types.

*Error Handling Gaps:*
- Empty catch blocks that swallow errors silently.
- Generic exception catching without specific handling.
- Missing error boundaries in React component trees.
- Errors logged but not propagated or handled.
- User-facing errors exposing internal details.

*Testability Blockers:*
- Hard dependencies that can't be mocked (direct imports of singletons, static methods).
- Side effects in constructors or module initialization.
- Global mutable state.
- Tight coupling to external services without abstraction.

**6. Security & Reliability Red Flags (Bonus Pass):**
While auditing, also note:
- SQL/NoSQL injection risks (string concatenation in queries).
- Unsanitized user input rendered in UI (XSS risks).
- Secrets or credentials in code (even if env vars, note any hardcoded fallbacks).
- Missing input validation on API boundaries.
- Missing rate limiting on public endpoints.
- Overly permissive CORS or authentication gaps.

**Output Format:**

**Part A — Codebase Census:**
```
Total Files Scanned: X
Total Lines of Code: X

Files by Size:
- > 1000 lines: X files (list all)
- 500-1000 lines: X files (list all)
- 300-500 lines: X files (list all)

Functions Exceeding 50 Lines: X (list all with line counts)
Functions with Cyclomatic Complexity > 10: X (list all)
Circular Dependencies Found: X (list all cycles)
Cross-Domain Imports: X (list all with source → target)
```

**Part B — Detailed Findings (Every Issue):**
Report EVERY finding, organized by category:

```
Finding #<N>
Category: <Size | Separation | Coupling | Scalability | Maintainability | Security>
Subcategory: <specific issue type>
Target: <file path:line number and function/component name>
Severity: <Critical | High | Medium | Low>
The Issue: <Detailed explanation of the violation — be specific, include evidence>
Impact: <What breaks or degrades if this isn't fixed? Who is affected?>
Current State:
   <Concise description of what the code does now>
   <Include relevant code snippet if helpful, max 10 lines>
Suggested Refactor:
   <Step-by-step approach to fix>
   <Describe the target state architecture, not just "refactor this">
   <Note any dependencies on other refactors>
Related Findings: <List finding #s that should be addressed together>
```

**Part C — Dependency & Coupling Analysis:**
```
Module Dependency Graph:
<ASCII or structured representation of how modules depend on each other>

Most Coupled Modules (by inbound + outbound dependencies):
1. <module> — X inbound, Y outbound, imports from Z different domains
2. ...

Dependency Violations:
- <module A> should not import from <module B> because <reason>
- ...

Suggested Module Boundaries:
<Proposed clean architecture with clear layer responsibilities>
```

**Part D — Pattern Inconsistency Report:**
```
Pattern: <e.g., "API error handling">
Variant A: <description> — used in <list of files>
Variant B: <description> — used in <list of files>
Variant C: <description> — used in <list of files>
Recommended Standard: <which variant, or new approach>

Pattern: <next pattern>
...
```

**Part E — Prioritized Refactoring Roadmap:**
```
Phase 1 — Critical (blocks development or causes incidents):
1. <Finding #X>: <one-line summary> — Effort: <days> — Risk if delayed: <description>
2. ...

Phase 2 — High (significant tech debt with compounding cost):
1. ...

Phase 3 — Medium (improves velocity but not urgent):
1. ...

Phase 4 — Low (cleanup, nice to have):
1. ...

Suggested Sequencing:
<Which refactors should be done together? Which unblock others?>
```

**Part F — Summary Statistics:**
```
Total Findings: X
- Critical: X
- High: X
- Medium: X
- Low: X

By Category:
- Size/Complexity: X findings
- Separation of Concerns: X findings
- Coupling/Abstraction: X findings
- Scalability: X findings
- Maintainability: X findings
- Security: X findings

Technical Debt Score: <qualitative assessment: Healthy | Manageable | Concerning | Critical>

Top 5 Riskiest Files (most findings, highest severity):
1. <file> — X findings (Y critical)
2. ...

Top 5 Highest-Impact Refactors:
1. <description> — unblocks X other improvements, affects Y files
2. ...

Architectural Patterns to Standardize:
1. <pattern> — adopt across X files
2. ...
```

**Completeness Checklist:**
Before finalizing, verify:
- [ ] Every source file was scanned (confirm file count matches repo)
- [ ] Every file over 300 lines is cataloged
- [ ] Every circular dependency is identified
- [ ] Every cross-domain import is mapped
- [ ] Every finding includes specific file:line references
- [ ] Every finding includes a concrete remediation, not just a description
- [ ] Findings are cross-referenced where they relate to each other
- [ ] Prioritization considers both severity and effort
