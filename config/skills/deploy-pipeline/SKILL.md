---
name: deploy-pipeline
description: Motium deployment pipeline guide (local → dev → test → prod). Use when asked about deployments, environments, promoting code, or "/deploy".
---

# Motium Deployment Pipeline

Complete guide for deploying through the Motium environment pipeline: **Local → Dev → Test → Prod**.

## Environment Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DEPLOYMENT PIPELINE                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  LOCAL                DEV                 TEST                PROD           │
│  ┌──────────┐        ┌──────────┐        ┌──────────┐        ┌──────────┐   │
│  │ Docker   │  push  │ Azure    │ manual │ Azure    │ manual │ Azure    │   │
│  │ Postgres │───────►│ Container│───────►│ Container│───────►│ Container│   │
│  │ + local  │  to    │ Apps     │ deploy │ Apps     │ deploy │ Apps     │   │
│  │ servers  │  main  │ (dev)    │        │ (test)   │        │ (prod)   │   │
│  └──────────┘        └──────────┘        └──────────┘        └──────────┘   │
│                                                                              │
│  Purpose:            Purpose:            Purpose:            Purpose:        │
│  - Development       - Auto-deploy       - Pre-prod          - Production   │
│  - Testing locally   - CI verification   - Prod clone        - Live users   │
│  - Offline work      - Feature testing   - Final QA          - Data source  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Environment Details

| Environment | Database | Subscription | Purpose |
|-------------|----------|--------------|---------|
| **Local** | `localhost:5432/motium` (Docker) | N/A | Offline development |
| **Dev** | `pg-motium-dev.postgres.database.azure.com` | `sub-motium-applications-dev` | Auto-deploy, CI verification |
| **Test** | `pg-motium-test.postgres.database.azure.com` | `sub-motium-applications-dev` | Pre-prod validation (prod clone) |
| **Prod** | `pg-motium-prod.postgres.database.azure.com` | `sub-motium-applications-prod` | Production, live users |

### Container Apps per Environment

| Service | Dev | Test | Prod |
|---------|-----|------|------|
| Cortex API | `aca-motium-cortex-api-dev` | `aca-motium-cortex-api-test` | `aca-motium-cortex-api-prod` |
| Cortex Web | `aca-motium-cortex-web-dev` | `aca-motium-cortex-web-test` | `aca-motium-cortex-web-prod` |
| Backend | `aca-motium-backend-dev` | `aca-motium-backend-test` | `aca-motium-backend-prod` |

### URLs

| Service | Dev | Prod |
|---------|-----|------|
| Cortex Web | `https://dev.cortex.motium.ai` | `https://cortex.motium.ai` |
| Cortex API | `https://api.dev.cortex.motium.ai` | `https://api.cortex.motium.ai` |

---

## Stage 1: Local Development

### Purpose
- Develop and test features without network dependency
- Fast iteration with hot-reload
- Isolated from cloud resources

### Setup

```bash
# 1. Start local PostgreSQL
docker start motium-postgres
# Or: docker run --name motium-postgres -e POSTGRES_PASSWORD=postgres -p 5432:5432 -d postgres:16

# 2. Start backend services
cd motium-backend
uv sync
uv run python -m app.main  # All workers + API

# 3. Start Cortex
cd cortex/backend
uv sync
uv run uvicorn app.main:app --reload --port 8001

cd cortex/frontend
pnpm install
pnpm dev  # Port 3001
```

### Database Access
```bash
# MCP tool
query_local("SELECT COUNT(*) FROM cv")

# Or psql
psql postgresql://postgres:postgres@localhost:5432/motium
```

### Verify Local Health
```bash
curl http://localhost:8000/health          # motium-backend
curl http://localhost:8001/health          # cortex-api
curl http://localhost:3001                 # cortex-web
```

### Exit Criteria (Ready for Dev)
- [ ] Feature works end-to-end locally
- [ ] Linters pass: `uv run ruff check .`
- [ ] Tests pass: `uv run pytest`
- [ ] No console errors in browser

---

## Stage 2: Dev Environment

### Purpose
- Automated deployment on push to main
- CI/CD verification
- First cloud environment
- Integration testing with Azure services

### Deployment Trigger

**Automatic:** Push to `main` branch triggers CI/CD:

```bash
git add -A
git commit -m "feat: description"
git push origin main
# CI/CD automatically deploys to dev
```

**Manual:** Use workflow dispatch:

```bash
# Trigger specific workflow
gh workflow run cortex-backend-ci.yml

# Watch deployment progress
gh run watch --exit-status
```

### CI/CD Workflows

| Workflow | Trigger | Deploys To |
|----------|---------|------------|
| `cortex-backend-ci.yml` | Push to `cortex/backend/**` | `aca-motium-cortex-api-dev` |
| `cortex-frontend-ci.yml` | Push to `cortex/frontend/**` | `aca-motium-cortex-web-dev` |
| `motium-backend-ci.yml` | Push to `motium-backend/**` | `aca-motium-backend-dev` |

### Database Access

```bash
# Authenticate first
az login

# MCP tool
query_dev("SELECT COUNT(*) FROM cv")

# Connection string for tools
postgresql://user@pg-motium-dev.postgres.database.azure.com:5432/motium
```

### Verify Dev Health

```bash
# Health checks
curl https://aca-motium-cortex-api-dev.lemonbay-8d9b5898.westeurope.azurecontainerapps.io/health
curl https://aca-motium-backend-dev.lemonbay-8d9b5898.westeurope.azurecontainerapps.io/health

# Container logs
az containerapp logs show --name aca-motium-cortex-api-dev --resource-group rg-motium-dev --tail 50
```

### Exit Criteria (Ready for Test)
- [ ] CI/CD pipeline passes (green build)
- [ ] Health endpoints return 200
- [ ] Feature works in dev.cortex.motium.ai
- [ ] No errors in Azure logs
- [ ] No console errors in browser

---

## Stage 3: Test Environment

### Purpose
- **Production clone** for final validation
- Same data structure as prod
- Pre-deployment verification gate
- Validate deployment process itself

### When to Use Test
- Before major releases
- Database migrations
- Infrastructure changes
- Breaking changes
- When dev data isn't representative

### Data Sync (Prod → Test)

Test environment should mirror production data:

```bash
cd motium-backend

# 1. Check current state
uv run python -m app.cli.main status

# 2. Sync CVs and jobs from prod
uv run python -m app.cli.main pull-data --from prod --to test

# 3. Sync matches
uv run python -m app.cli.main sync-matches --from prod --to test
```

### Deploy to Test

Test deployment is **manual** (not auto-triggered):

```bash
# Option 1: Deploy specific image from dev
az containerapp update \
  --name aca-motium-cortex-api-test \
  --resource-group rg-motium-test \
  --image acrmotiumprod.azurecr.io/cortex-api:$GIT_SHA

# Option 2: Build and deploy fresh
# (Create workflow with test environment if needed)
gh workflow run cortex-backend-ci.yml -f environment=test
```

### Database Access

```bash
# MCP tool
query_test("SELECT COUNT(*) FROM cv")

# Verify data parity with prod
query_test("SELECT status, COUNT(*) FROM cv GROUP BY status")
query_prod("SELECT status, COUNT(*) FROM cv GROUP BY status")
```

### Exit Criteria (Ready for Prod)
- [ ] Deployment to test succeeds
- [ ] All health checks pass
- [ ] Feature works with prod-like data
- [ ] Performance acceptable
- [ ] No regressions detected
- [ ] Smoke tests pass

---

## Stage 4: Prod Environment

### Purpose
- Production environment serving real users
- Live Bullhorn data
- Mission critical stability

### ⚠️ CRITICAL: Build-Time Secrets in Frontend

**NEVER deploy dev-built frontend images to production!**

Next.js `NEXT_PUBLIC_*` environment variables are **embedded at build time**, not read at runtime.
This means:
- A frontend image built with dev secrets will **always** use dev Clerk, dev API URLs, etc.
- Even if you set the correct secrets on the prod container app, the baked-in values are used
- The only way to get prod secrets is to **build a new image** with the production workflow

**Signs you deployed a dev-built image to prod:**
- Clerk redirects to `*.accounts.dev` instead of production domain
- API calls go to dev endpoints
- Auth tokens don't work

**The fix:** Always use the workflow with `environment=production`:
```bash
gh workflow run cortex-frontend-ci.yml -f environment=production
```

### Deployment (Manual with Approval)

**CRITICAL:** Production deployment requires explicit action AND correct build.

```bash
# Frontend - MUST use workflow (builds with prod secrets)
gh workflow run cortex-frontend-ci.yml -f environment=production
gh run watch --exit-status

# Backend API - can use az CLI (no build-time secrets)
gh workflow run cortex-backend-ci.yml -f environment=production
# OR manually with tested image:
az containerapp update \
  --name aca-motium-cortex-api-prod \
  --resource-group rg-motium-prod \
  --image acrmotiumprod.azurecr.io/cortex-api:$TESTED_SHA
```

### ❌ WRONG: Deploying Dev Image to Prod

```bash
# This will BREAK production - dev secrets baked in!
az containerapp update \
  --name aca-motium-cortex-web-prod \
  --resource-group rg-motium-prod \
  --image acrmotiumprod.azurecr.io/cortex-web:$DEV_SHA  # ← WRONG!
```

### ✅ CORRECT: Use Production Workflow

```bash
# This builds fresh image with production secrets
gh workflow run cortex-frontend-ci.yml -f environment=production
gh run watch --exit-status
```

### Pre-Deployment Checklist

```markdown
## Pre-Prod Deployment Checklist

### Code Readiness
- [ ] All tests pass in CI
- [ ] Code reviewed and approved
- [ ] Linters pass with zero errors

### Verification
- [ ] Feature tested in dev environment
- [ ] Feature tested in test environment
- [ ] Performance acceptable under load
- [ ] No regressions in test

### Database
- [ ] Migrations tested in test environment
- [ ] Rollback plan documented (if migration)
- [ ] No destructive operations without backup

### Monitoring
- [ ] Logfire dashboard accessible
- [ ] Alert thresholds set
- [ ] Rollback procedure documented

### Communication
- [ ] Team notified of deployment
- [ ] Support aware of changes
```

### Post-Deployment Verification

```bash
# 1. Health checks
curl https://cortex.motium.ai/api/health
curl https://api.cortex.motium.ai/health

# 2. Smoke tests (manual)
# - Login works
# - Dashboard loads
# - Data displays correctly

# 3. Monitor Logfire
# https://logfire.pydantic.dev/?project=cortex-prod

# 4. Check container health
az containerapp show --name aca-motium-cortex-api-prod --resource-group rg-motium-prod \
  --query "properties.provisioningState"
```

### Rollback Procedure

```bash
# 1. Get previous revision
az containerapp revision list --name aca-motium-cortex-api-prod \
  --resource-group rg-motium-prod --query "[].name" -o tsv

# 2. Activate previous revision
az containerapp revision activate --name aca-motium-cortex-api-prod \
  --resource-group rg-motium-prod --revision <previous-revision>

# 3. Deactivate broken revision
az containerapp revision deactivate --name aca-motium-cortex-api-prod \
  --resource-group rg-motium-prod --revision <broken-revision>
```

---

## Quick Reference

### Commands by Environment

| Action | Local | Dev | Test | Prod |
|--------|-------|-----|------|------|
| Deploy | `docker start` / `uv run` | `git push main` | Manual `az containerapp` | Manual with approval |
| Health | `curl localhost:*` | CI health step | Manual check | Logfire + manual |
| Logs | Terminal output | `az containerapp logs` | `az containerapp logs` | `az containerapp logs` |
| Database | `query_local()` | `query_dev()` | `query_test()` | `query_prod()` |

### Environment Variables by Stage

| Variable | Local | Dev | Test | Prod |
|----------|-------|-----|------|------|
| `ENVIRONMENT` | `local` | `development` | `test` | `production` |
| Database | Docker localhost | pg-motium-dev | pg-motium-test | pg-motium-prod |
| Auth bypass | `DEV_AUTH_BYPASS=true` | No | No | No |
| CORS | `localhost:3001` | dev.cortex.motium.ai | test.cortex.motium.ai | cortex.motium.ai |

### Pipeline Flow Commands

```bash
# Full deployment pipeline example

# 1. LOCAL: Develop and test
cd motium-backend && uv run pytest
cd cortex/backend && uv run ruff check .

# 2. DEV: Push to deploy
git add -A && git commit -m "feat: new feature" && git push

# 3. Watch CI
gh run watch --exit-status

# 4. TEST: Sync data and deploy
uv run python -m app.cli.main pull-data --from prod --to test
az containerapp update --name aca-motium-cortex-api-test -g rg-motium-test --image acrmotiumprod.azurecr.io/cortex-api:$(git rev-parse --short HEAD)

# 5. PROD: Deploy after test validation
az containerapp update --name aca-motium-cortex-api-prod -g rg-motium-prod --image acrmotiumprod.azurecr.io/cortex-api:$(git rev-parse --short HEAD)
```

---

## Database Sync (Cross-Environment Data Transfer)

The Data Sync CLI allows copying CVs, jobs, and matches between environments. This is essential for:
- Seeding dev/test with production data
- Testing features with real data
- Pre-prod validation with prod-like data

### Prerequisites

```bash
# 1. Azure AD Authentication
az login

# 2. Set your Azure email
export AZURE_USER_EMAIL="your.name@motium.ai"

# 3. Verify database access
cd motium-backend
uv run python -m app.cli.main status
```

### Commands Overview

| Command | Purpose | Common Use Case |
|---------|---------|-----------------|
| `status` | Show data counts per environment | Compare env sizes |
| `pull-data` | Sync CVs and jobs | Seed dev/test from prod |
| `sync-matches` | Sync match results | Copy matches after pull-data |
| `generate-matches` | Trigger new matching | Generate matches for specific CVs |

### status - Check Environment State

```bash
uv run python -m app.cli.main status
```

**Output:**
```
============================================================
  PROD ENVIRONMENT
============================================================
CVs: 15,432
Jobs: 2,891
Matches: 847,293

============================================================
  DEV ENVIRONMENT
============================================================
CVs: 500
Jobs: 100
Matches: 5,000
```

### pull-data - Sync CVs and Jobs

**Syncs `cv_parsed` and `job_parsed` tables between environments.**

```bash
# Full sync from prod to dev
uv run python -m app.cli.main pull-data --from prod --to dev

# Full sync from prod to test
uv run python -m app.cli.main pull-data --from prod --to test

# Incremental sync (only records updated since date)
uv run python -m app.cli.main pull-data --from prod --to dev --since 2025-01-01

# Dry run (preview without changes)
uv run python -m app.cli.main pull-data --from prod --to dev --dry-run

# Limit records per table
uv run python -m app.cli.main pull-data --from prod --to dev --limit 1000
```

**Arguments:**

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--from` | Yes | - | Source environment (prod, dev, test) |
| `--to` | Yes | - | Target environment (prod, dev, test) |
| `--since` | No | - | ISO timestamp for incremental sync |
| `--limit` | No | 10000 | Max records per table |
| `--dry-run` | No | false | Preview without making changes |

**Behavior:**
- Updates existing records only if source is newer (`updated_at`)
- Inserts new records that don't exist in target
- Commits after all records are processed

### sync-matches - Sync Match Results

**Syncs matches with provenance tracking. MUST run after `pull-data`.**

```bash
# Downstream sync (prod to dev) - most common
uv run python -m app.cli.main sync-matches --from prod --to dev

# Downstream sync (prod to test)
uv run python -m app.cli.main sync-matches --from prod --to test

# Upstream sync (dev to prod) - use with caution!
uv run python -m app.cli.main sync-matches --from dev --to prod --target-label "reviewed-dev"

# Incremental sync
uv run python -m app.cli.main sync-matches --from prod --to dev --since 2025-01-15

# Dry run
uv run python -m app.cli.main sync-matches --from prod --to dev --dry-run
```

**Arguments:**

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--from` | Yes | - | Source environment |
| `--to` | Yes | - | Target environment |
| `--target-label` | No | `synced-from-{source}` | Value for `source_environment` column |
| `--since` | No | - | ISO timestamp for incremental sync |
| `--limit` | No | 10000 | Max matches to sync |
| `--dry-run` | No | false | Preview without making changes |

**Behavior:**
- **FK Validation**: Skips matches if CV or Job doesn't exist in target
- **Idempotency**: Uses `source_match_id` to prevent duplicate syncs
- **Provenance**: Sets `source_match_id` and `source_synced_at` for tracking

**Output:**
```
Matches: 150 synced, 20 skipped, 5 missing FK
```
- `skipped`: Already synced (same `source_match_id` exists)
- `missing FK`: CV or Job not in target database

### generate-matches - Trigger New Matching

```bash
# Generate matches for specific CVs
uv run python -m app.cli.main generate-matches \
    --cv-ids "abc123,def456" \
    --target-env cortex-dev

# Use custom model
uv run python -m app.cli.main generate-matches \
    --cv-ids "abc123" \
    --target-env cortex-dev \
    --model grok-4-1
```

### Common Workflows

#### Seed Dev from Production

```bash
cd motium-backend

# 1. Check current state
uv run python -m app.cli.main status

# 2. Preview what would sync
uv run python -m app.cli.main pull-data --from prod --to dev --dry-run

# 3. Sync CVs and jobs
uv run python -m app.cli.main pull-data --from prod --to dev

# 4. Sync matches (requires CVs/jobs to exist first!)
uv run python -m app.cli.main sync-matches --from prod --to dev

# 5. Verify
uv run python -m app.cli.main status
```

#### Seed Test Environment (Pre-Prod Validation)

```bash
cd motium-backend

# 1. Full sync of CVs and jobs
uv run python -m app.cli.main pull-data --from prod --to test

# 2. Full sync of matches
uv run python -m app.cli.main sync-matches --from prod --to test

# 3. Verify data parity
uv run python -m app.cli.main status
```

#### Daily Incremental Sync

```bash
# Sync only records updated in the last 7 days
uv run python -m app.cli.main pull-data --from prod --to dev --since $(date -d '7 days ago' +%Y-%m-%d)
uv run python -m app.cli.main sync-matches --from prod --to dev --since $(date -d '7 days ago' +%Y-%m-%d)
```

#### Promote Dev Matches to Production

Use when matches have been reviewed/curated in dev and should be visible in production.

```bash
# Label these as coming from dev review
uv run python -m app.cli.main sync-matches \
    --from dev --to prod \
    --target-label "reviewed-dev-2025-01"
```

### Tables Synced

| Table | Command | Key Fields |
|-------|---------|------------|
| `motium.cv_parsed` | `pull-data` | `bullhorn_candidate_id`, `parsed_cv_json`, `fingerprint_json` |
| `motium.job_parsed` | `pull-data` | `bullhorn_job_order_id`, `parsed_job_json`, `fingerprint_json` |
| `motium.match` | `sync-matches` | `cv_id`, `job_id`, `overall_score`, `pitch`, `evidence` |

### Troubleshooting Sync Issues

#### "AZURE_USER_EMAIL is required"

```bash
export AZURE_USER_EMAIL="your.name@motium.ai"
```

#### "Failed to connect to {env}"

1. Run `az login` to refresh credentials
2. Verify you have Entra admin access on the target database
3. Check VPN/network connectivity to Azure

#### "Missing CV/Job in target - skipping match"

Sync CVs and jobs before matches:
```bash
uv run python -m app.cli.main pull-data --from prod --to dev
uv run python -m app.cli.main sync-matches --from prod --to dev
```

#### High "skipped" count in sync-matches

Matches already synced (idempotent). Check `source_match_id` in target:
```sql
SELECT source_match_id, source_environment, COUNT(*)
FROM motium.match
WHERE source_match_id IS NOT NULL
GROUP BY source_match_id, source_environment;
```

---

## Troubleshooting

### Deployment Failed

```bash
# Check workflow run
gh run view --log-failed

# Check container status
az containerapp show --name $APP_NAME --resource-group $RG --query "properties.provisioningState"

# Check container logs
az containerapp logs show --name $APP_NAME --resource-group $RG --tail 100
```

### Authentication Issues

```bash
# Refresh Azure credentials
az login

# Check identity permissions
az role assignment list --assignee $(az identity show -n $IDENTITY_NAME -g $RG --query principalId -o tsv)
```

### Database Connection Issues

```bash
# Check database health via MCP
db_health("dev")  # or test, prod

# Verify Azure AD token
az account get-access-token --resource-type oss-rdbms
```

### Environment Drift

```bash
# Compare environments
query_dev("SELECT COUNT(*) FROM cv")
query_test("SELECT COUNT(*) FROM cv")
query_prod("SELECT COUNT(*) FROM cv")

# Sync if needed
uv run python -m app.cli.main pull-data --from prod --to test
```

---

## Triggers

- `/deploy`
- "deploy to prod"
- "promote to test"
- "deployment pipeline"
- "how do I deploy"
- "push to production"
- "sync database"
- "pull data from prod"
- "seed dev environment"
- "copy data to test"
