---
name: tfappfix
description: Terraform debugging for small teams. Diagnoses plan/apply failures, state issues, and Azure provider errors. Use when asked to "fix terraform", "debug infra", "why did apply fail", or "/tfappfix".
---

# Terraform Debugging (/tfappfix)

Pragmatic terraform debugging for a 2-person team. No enterprise overhead.

## Philosophy: What This Skill Is NOT

**Skip these enterprise patterns - you are 2 people:**
- Complex policy checks (Sentinel/OPA) - just review the plan
- Multi-workspace orchestration - you have dev/prod, that is enough
- Drift detection dashboards - just run `terraform plan`
- Checkpoint files - terraform state IS the checkpoint
- 4-agent planning - talk to each other instead

**Terraform already provides:**
- State management (do not reinvent it)
- Change detection (`plan -detailed-exitcode`)
- Locking (do not build another layer)
- Dependency resolution

**This skill focuses on:**
- Diagnosing why plan/apply failed
- Common Azure provider issues
- Safe state manipulation when needed
- Getting CI green again

## Triggers

- `/tfappfix`, "fix terraform", "debug infra", "why did apply fail"
- "plan is failing", "state is locked", "terraform error"

## The 80/20 of Terraform Debugging

| Frequency | Problem Type | Solution |
|-----------|--------------|----------|
| 80% | Code/config error | Read error, fix code, push, CI applies |
| 15% | State issues | Unlock, rm, import (with user confirmation) |
| 5% | Azure API / provider | Wait, retry, or workaround |

**Most terraform issues are solved by reading the error message carefully.**

## Workflow

```
Phase 0: CONTEXT
  - Identify the failing stack
  - Get the error (from user, CI logs, or local run)

Phase 1: DIAGNOSE
  - Run fmt, validate, plan locally
  - Check state lock status if relevant
  - Check Azure resource status if apply failed

Phase 2: FIX
  - Apply code changes
  - State ops require user confirmation

Phase 3: VERIFY
  - Plan shows expected changes
  - Push to trigger CI
```

### Phase 0: Get Context

**Find out:**
1. Which stack? (Look for directories with `main.tf` or `*.tf` files)
2. What is the error? (CI log, local error, or symptom)
3. Plan or apply failure?

**If user provides a GitHub Actions run URL:**
```bash
gh run view <run-id> --log-failed
```

### Phase 1: Diagnose

**Always start here - run the basics:**

```bash
cd <stack-path>  # directory containing main.tf

# 1. Format check
terraform fmt -check -recursive

# 2. Validate (fast, no backend)
terraform init -backend=false
terraform validate

# 3. Full plan (if validate passes)
terraform init
terraform plan -out=debug.tfplan
```

**Check state lock (if plan hangs):**
For Azure Blob backend, check lease status with `az storage blob show`.

**Check Azure resource status (if apply failed mid-way):**
```bash
az resource list -g <resource-group> --query "[].{name:name, state:properties.provisioningState}" -o table
```

### Phase 2: Fix

#### Error: State Lock

For Azure Blob backend:
```bash
# Check lease status
az storage blob show --container-name <container> --name <state-file> --account-name <storage> --query "properties.lease"

# Break lease (ASK USER FIRST)
az storage blob lease break --container-name <container> --name <state-file> --account-name <storage>
```

**Safety gate:** Always ask user before breaking a lock.

#### Error: Resource Already Exists

Resource exists in Azure but not in state.

**⚠️ CRITICAL: 99% of cases should DELETE, not import.**

**DEFAULT ACTION (do not ask, just do this):**
1. Ask user to DELETE the resource in Azure Portal or CLI
2. Re-run terraform to create it fresh under Terraform management

```bash
# Example: delete a role assignment
az role assignment delete --ids "<resource-id>"

# Example: delete a generic resource
az resource delete --ids "<resource-id>"
```

**IMPORT IS ALMOST NEVER CORRECT.** Only consider import when ALL of these are true:
1. The resource has existed for a **long time** (months/years, not hours/days)
2. The resource contains **irreplaceable data** or **configuration that cannot be recreated**
3. The resource is managed in a **different terraform repo** OR was created manually before IaC

**If you believe import is appropriate, you MUST:**
1. Stop and ask the user with ALL of these details:
   - Why you believe this qualifies as a rare import case
   - What the resource is and how long it has existed
   - The exact import command you would run
   - The risk: import can cause state corruption if the resource config doesn't match
2. Wait for explicit "yes, import it" confirmation
3. Note: `terraform import` is BLOCKED by the command guard - user must run manually

**DO NOT ask about import** for resources created in the last few days. Just delete and recreate.

#### Error: Resource Not Found (Drift)

Resource in state but deleted from Azure:

```bash
# Remove from state - ASK USER FIRST
terraform state rm <resource.address>
```

#### Error: Provider / API Error

| Error | Cause | Fix |
|-------|-------|-----|
| `StatusCode=409` | Resource busy | Wait 5 min, retry |
| `StatusCode=429` | Rate limited | Retry with `-parallelism=1` |
| `StatusCode=404` on apply | Eventual consistency | Wait 2 min, retry |
| `OperationNotAllowed` | Resource in transitional state | Wait and retry |

#### Error: Module/Provider Version

```bash
terraform providers
terraform init -upgrade
```

### Phase 3: Verify

```bash
# Local plan should show expected changes
terraform plan

# Push to trigger CI
git add <files>
git commit -m "fix(terraform): <description>"
git push

# Monitor CI
gh run watch
```

## Finding Stacks

**Discover terraform stacks in your repo:**
```bash
# Find all directories with terraform files
find . -name "*.tf" -type f | xargs dirname | sort -u

# Or look for backend configurations
grep -r "backend" --include="*.tf" -l
```

**Understand dependencies:**
- Check `terraform_remote_state` data sources for cross-stack references
- Check module sources for shared modules
- Apply order: shared/platform stacks first, then application stacks

## Safety Rules

**BLOCKED (cannot run via Claude - user must run manually):**
- `terraform import` — blocked by command guard
- `terraform state rm` — blocked by command guard
- `terraform apply` — blocked by command guard
- `terraform destroy` — blocked by command guard

**Ask user before:**
- Breaking state locks
- Suggesting user run `terraform import` (see "Resource Already Exists" - 99% should DELETE instead)
- Operations on production stacks
- Any `-force` flags

**Proceed without asking:**
- `terraform fmt`
- `terraform validate`
- `terraform plan`
- `terraform init`
- Code changes to .tf files
- Committing and pushing

## Azure Authentication

```bash
# Check auth
az account show

# Login if needed
az login

# Set subscription
az account set -s <subscription-id>
```

For terraform:
```bash
export ARM_SUBSCRIPTION_ID=$(az  account show --query id -o tsv)
export ARM_TENANT_ID=$(az account show --query tenantId -o tsv)
```

## Error Message Decoder

| Error Message | Meaning | Fix |
|---------------|---------|-----|
| "Error acquiring the state lock" | CI crashed or local tf running | Break lease if stale |
| "Resource already exists" | Exists in Azure, not in state | DELETE resource, recreate (import is rare) |
| "Unsupported attribute" | Module output changed | `terraform init -upgrade` |
| "dial tcp: lookup ... no such host" | DNS/network issue | Retry |
| "AuthorizationFailed" | Missing RBAC | Check permissions |
| "QuotaExceeded" | Azure limits | Request increase or change region |

## When to Escalate

**Talk to your teammate (not Claude):**
- Production outage
- Security-related changes
- Billing/cost decisions
- Architectural changes
- Anything you are not sure about

**This skill is for:**
- Getting a failing plan/apply to pass
- Understanding error messages
- Safe state manipulation with confirmation
- Quick fixes, not redesigns
