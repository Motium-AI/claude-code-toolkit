---
description: Establish performance benchmarks and optimize Next.js + FastAPI apps
---

Use ultrathink to thoroughly analyze performance bottlenecks and optimization opportunities.

**Context:** Next.js 14 (App Router) frontend + FastAPI backend.
Running locally via `pnpm dev` (port 3000) and `uvicorn` (port 8000).
Auth: Cookie-based session (login as test user before benchmarks).

**Goal:** Establish reproducible performance benchmarks, identify
top 3 optimization opportunities, implement them, and measure impact.

**Success criteria:** Achieve ≥20% improvement in LCP or ≥30%
reduction in JS bundle size, whichever comes first. Stop after
3 optimization rounds regardless.

---

## Phase 1: Setup

1. Install: `playwright`, `lighthouse`, `@next/bundle-analyzer`
2. Create `benchmarks/` with this structure:
   ```
   benchmarks/
     scripts/
       lighthouse.ts    # Core Web Vitals via Lighthouse
       api-timing.ts    # FastAPI endpoint latency
       bundle-size.ts   # Analyze next build output
     results/
       baseline.json
     config.ts          # Routes, endpoints, run count
   ```

3. Define targets in `config.ts`:
   - Routes: `/`, `/dashboard`, `/candidates/[id]`
   - API endpoints: `GET /cvs`, `POST /cvs/{id}/match`, `GET /jobs`
   - Runs per measurement: 5 (discard first as warmup)

## Phase 2: Baseline

Measure and record (use median of 5 runs):

| Metric | Tool | Target |
|--------|------|--------|
| LCP | Lighthouse | <2.5s |
| TTFB | Lighthouse | <600ms |
| JS size (gzip) | bundle-analyzer | Report only |
| API P95 latency | Playwright + timestamps | <200ms |

Output: `baseline.json` with structure:
```json
{
  "timestamp": "ISO8601",
  "routes": { "/dashboard": { "lcp_ms": 1850, "ttfb_ms": 320 } },
  "api": { "GET /cvs": { "p50_ms": 45, "p95_ms": 120 } },
  "bundle": { "total_kb": 412, "largest_chunks": [...] }
}
```

## Phase 3: Analyze

Output `analysis.md` with:
1. Top 3 bottlenecks ranked by impact (quantified)
2. Root cause for each (e.g., "lodash bundled entirely for one function")
3. Proposed fix with estimated effort (S/M/L)

## Phase 4: Optimize Loop

For each fix (max 3 iterations):
1. Create branch: `perf/optimize-{description}`
2. Implement fix
3. Run `pnpm build && pnpm test` — abort if tests fail
4. Re-run benchmark suite
5. Append to `results/optimization-{n}.json`
6. Commit with message: `perf: {description} (LCP -X%, bundle -Y%)`

**Stop when:** target met OR 3 iterations complete OR next-best
opportunity offers <5% projected improvement.
