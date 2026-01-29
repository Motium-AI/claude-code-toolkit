# Infrastructure Sync (Phase 3.6)

Required when `az CLI` commands modify infrastructure.

## When This Applies

After running: `az containerapp`, `az webapp`, `az functionapp`, `az storage`, `az keyvault`, `az network`, `az resource`

## Required Actions

1. **Document changes** in `.claude/infra-changes.md`
2. **Clone infra repo** (location from `service-topology.md`)
3. **Update IaC files** (Terraform `.tf`, Bicep `.bicep`, ARM templates)
4. **Create PR to infra repo**:

```bash
cd /path/to/infra-repo
git checkout -b appfix/sync-$(date +%Y%m%d)
git add . && git commit -m "appfix: Sync infrastructure state"
gh pr create --title "Sync infra changes from appfix"
```

## Why This Matters

Infrastructure drift causes:
- Next deploy overwrites your fix
- IaC state doesn't match reality
- Team confusion about actual configuration
