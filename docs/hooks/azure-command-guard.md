# Azure Command Guard Hook

A PreToolUse hook that protects Azure infrastructure by blocking dangerous Azure CLI commands while allowing safe read operations and explicitly permitted writes.

## Features

✅ **Blocks dangerous operations**
- Resource creation/deletion/updates
- Infrastructure deployments
- Role assignments
- Authentication changes
- Network modifications

✅ **Allows safe read operations**
- `az ... show`
- `az ... list`
- `az ... get`
- Log queries
- Resource information

✅ **Allows specific write operations**
- KeyVault secret operations (`az keyvault secret set/delete`)
- Storage blob uploads (`az storage blob upload/copy`)
- Storage file uploads

✅ **Fail-safe by default**
- Unrecognized Azure CLI commands are blocked
- Better to ask than to accidentally modify infrastructure

✅ **Multi-command detection**
- Checks ALL az commands in chained operations
- Example: `az account show && az group delete --yes` → BLOCKED

## Installation

### Repository-Level (Recommended)

Add to your repository's `.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "command": "~/.claude/hooks/azure-command-guard.sh"
      }
    ]
  }
}
```

Then commit the settings file:

```bash
git add .claude/settings.json
git commit -m "feat: add Azure command guard hook"
```

This protects everyone working on the repository.

### Testing

Run the test suite to verify the hook works:

```bash
~/.claude/hooks/test-azure-guard.sh
```

Should output:
```
✓ All tests passed!
Passed: 31
Failed: 0
```

## What's Blocked

### Infrastructure Mutations
```bash
❌ az resource create
❌ az resource delete
❌ az resource update
❌ az group delete
❌ az deployment create
```

### Database Changes
```bash
❌ az postgres flexible-server create
❌ az postgres flexible-server update
❌ az postgres flexible-server restart
❌ az sql server update
```

### Network Changes
```bash
❌ az network vnet create
❌ az network vnet delete
❌ az network subnet update
```

### Auth & Identity
```bash
❌ az account set
❌ az role assignment create
❌ az ad ...
```

### Monitoring Changes
```bash
❌ az monitor diagnostic-settings create
❌ az monitor diagnostic-settings update
```

### KeyVault Management (but NOT secrets)
```bash
❌ az keyvault create
❌ az keyvault delete
❌ az keyvault key create
```

### Storage Account Management (but NOT uploads)
```bash
❌ az storage account delete
❌ az storage blob delete
```

## What's Allowed

### Authentication
```bash
✅ az login
```

### Read Operations
```bash
✅ az account show
✅ az resource list
✅ az postgres flexible-server show
✅ az monitor log-analytics query
✅ az keyvault secret show
✅ az storage blob list
```

### KeyVault Secret Operations
```bash
✅ az keyvault secret set --vault-name ... --name ... --value ...
✅ az keyvault secret delete --vault-name ... --name ...
✅ az keyvault secret backup
✅ az keyvault secret restore
```

### Storage Uploads
```bash
✅ az storage blob upload --account-name ... --file ...
✅ az storage blob copy start --source-uri ...
✅ az storage file upload --share-name ... --source ...
```

## Customization

### Adding Safe Patterns

If you have legitimate read commands being blocked, add them to `SAFE_PATTERNS` in the hook script:

```bash
SAFE_PATTERNS=(
    # ... existing patterns ...
    '^az your-service your-safe-command'
)
```

### Adding Allowed Writes

If you need to allow specific write operations, add them to `ALLOWED_WRITES`:

```bash
ALLOWED_WRITES=(
    # ... existing patterns ...
    '^az your-service your-allowed-write'
)
```

### Per-Repository Customization

Copy the hook to your repository and customize it:

```bash
mkdir -p .claude/hooks
cp ~/.claude/hooks/azure-command-guard.sh .claude/hooks/
chmod +x .claude/hooks/azure-command-guard.sh
```

Update `.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "command": ".claude/hooks/azure-command-guard.sh"
      }
    ]
  }
}
```

Now you can customize the patterns for your specific needs.

## How It Works

1. **Hook Trigger**: Runs before every Bash command
2. **Azure Detection**: Checks if command contains `az ` commands
3. **Pattern Matching**: Checks each az command against:
   - Safe patterns (allow)
   - Allowed writes (allow)
   - Dangerous patterns (block)
   - Unknown patterns (block - fail-safe)
4. **Result**: Returns exit code 0 (allow) or 1 (block)

## Example Output

When a dangerous command is blocked:

```
╔════════════════════════════════════════════════════════════════╗
║  ⛔ BLOCKED: Azure Resource Modification Detected             ║
╚════════════════════════════════════════════════════════════════╝

Command: az group delete --name rg-test --yes

Pattern matched: ^az group delete

This command modifies Azure resources and requires explicit approval.

Allowed operations:
  ✓ Read operations (show, list, get, query)
  ✓ KeyVault secret operations (set, delete, backup)
  ✓ Storage blob uploads/copies

To execute this command:
  1. Review the command carefully
  2. Run it manually in your terminal
  3. Or use Claude Code's approval flow if available
```

## Limitations

1. **Not foolproof**: Claude could potentially use `curl` to call Azure REST API directly, or use Python SDKs
2. **Maintenance**: New Azure CLI commands may not be covered until patterns are updated
3. **False positives possible**: Some safe commands might match dangerous patterns (update the hook if this happens)
4. **Guardrail, not security boundary**: A determined agent could find workarounds

## Best Practices

1. **Use repository-level configuration**: Protects the entire team
2. **Test after customization**: Run `test-azure-guard.sh` after modifying patterns
3. **Review blocked commands**: Don't blindly override - understand why it was blocked
4. **Keep patterns updated**: Add new Azure services as they're introduced
5. **Combine with other safeguards**: Use alongside Azure RBAC, resource locks, and policy

## Extending to Other Cloud Providers

The same pattern works for AWS and GCP:

### AWS

```bash
# In the hook script, add AWS checks:
if [[ "$COMMAND" =~ [[:space:]]aws[[:space:]] ]] || [[ "$COMMAND" =~ ^aws[[:space:]] ]]; then
    # Similar pattern matching for aws commands
fi
```

### GCP

```bash
# In the hook script, add GCP checks:
if [[ "$COMMAND" =~ [[:space:]]gcloud[[:space:]] ]] || [[ "$COMMAND" =~ ^gcloud[[:space:]] ]]; then
    # Similar pattern matching for gcloud commands
fi
```

## Troubleshooting

### Hook not running

1. Check `.claude/settings.json` is configured
2. Restart Claude Code (hooks load at session start)
3. Verify hook is executable: `ls -la ~/.claude/hooks/azure-command-guard.sh`

### Legitimate command blocked

1. Identify the command pattern
2. Add to `SAFE_PATTERNS` or `ALLOWED_WRITES` in the hook
3. Test with `test-azure-guard.sh`
4. Commit the updated hook

### Hook not blocking dangerous command

1. Check the command pattern
2. Add to `DANGEROUS_PATTERNS` if missing
3. Test with `test-azure-guard.sh`
4. Report the issue if it's a common pattern that should be included

## Support

- Report issues: https://github.com/Motium-AI/claude-code-toolkit/issues
- Test suite: `~/.claude/hooks/test-azure-guard.sh`
- Hook source: `~/.claude/hooks/azure-command-guard.sh`
