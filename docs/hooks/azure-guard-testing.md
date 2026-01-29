# Azure Command Guard - End-to-End Testing Guide

This guide walks you through testing the Azure command guard hook in a real Claude Code session.

## Prerequisites

1. Claude Code Toolkit installed
2. Azure CLI installed (or commands will just be blocked/allowed without actually running)

## Step 1: Verify Installation

Check that the hook is available:

```bash
ls -la ~/.claude/hooks/azure-command-guard.sh
```

Should show: `-rwxr-xr-x ... azure-command-guard.sh`

Run the install verification:

```bash
cd claude-code-toolkit
./scripts/install.sh --verify
```

Should show:
```
Testing Azure command guard hook...
  ✓ Allows safe commands (az account show)
  ✓ Blocks dangerous commands (az group delete)
  ✓ Allows KeyVault secret operations
```

## Step 2: Create Test Repository

```bash
mkdir ~/azure-guard-test
cd ~/azure-guard-test
git init
```

## Step 3: Enable Azure Guard

Create `.claude/settings.json`:

```bash
mkdir -p .claude
cat > .claude/settings.json <<'EOF'
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
EOF
```

## Step 4: Start Claude Code

**IMPORTANT**: Hooks are loaded at session start, so you must start Claude Code in the test directory:

```bash
cd ~/azure-guard-test
claude
```

## Step 5: Test in Claude Code Session

Once Claude Code starts, try these commands:

### Test 1: Safe Read Command (Should Work)

Ask Claude:
```
Can you run: az account show
```

Expected: Command executes successfully (or fails if not logged in to Azure, but not blocked by hook)

### Test 2: Dangerous Command (Should Block)

Ask Claude:
```
Can you run: az group delete --name rg-test --yes
```

Expected output:
```
╔════════════════════════════════════════════════════════════════╗
║  ⛔ BLOCKED: Azure Resource Modification Detected             ║
╚════════════════════════════════════════════════════════════════╝

Command: az group delete --name rg-test --yes

Pattern matched: ^az .* delete

This command modifies Azure resources and requires explicit approval.
...
```

### Test 3: KeyVault Secret Operation (Should Work)

Ask Claude:
```
Can you run: az keyvault secret set --vault-name test-vault --name API_KEY --value "secret123"
```

Expected: Command executes (may fail if vault doesn't exist, but not blocked by hook)

### Test 4: Storage Upload (Should Work)

Ask Claude:
```
Can you run: az storage blob upload --account-name teststorage --container-name test --file README.md
```

Expected: Command executes (may fail if storage doesn't exist, but not blocked by hook)

### Test 5: Chained Command with Dangerous Operation (Should Block)

Ask Claude:
```
Can you run: az account show && az group delete --name rg-test --yes
```

Expected: Blocked because the second command is dangerous (even though first is safe)

## Step 6: Verify Hook Execution

Check the Claude Code output for hook execution. You should see the hook intercepting commands.

## Step 7: Test Comprehensive Suite

Exit Claude Code and run the comprehensive test suite:

```bash
~/.claude/hooks/test-azure-guard.sh
```

Expected output:
```
════════════════════════════════════════════════════════════
  Test Results
════════════════════════════════════════════════════════════

  Passed: 31
  Failed: 0

✓ All tests passed!
```

## Troubleshooting

### Hook Not Running

1. **Check settings.json**:
   ```bash
   cat .claude/settings.json
   ```

2. **Restart Claude Code**: Hooks load at session start
   ```bash
   exit  # or Ctrl+D
   claude  # start again
   ```

3. **Check hook is executable**:
   ```bash
   ls -la ~/.claude/hooks/azure-command-guard.sh
   chmod +x ~/.claude/hooks/azure-command-guard.sh  # if needed
   ```

### Safe Commands Being Blocked

If legitimate commands are blocked:

1. **Check the command pattern** - does it match a dangerous pattern?
2. **Add to SAFE_PATTERNS** in `~/.claude/hooks/azure-command-guard.sh`
3. **Test the change**:
   ```bash
   echo '{"tool_name": "Bash", "tool_input": {"command": "az your command"}}' | ~/.claude/hooks/azure-command-guard.sh
   ```

### Dangerous Commands Not Being Blocked

1. **Check the command pattern**
2. **Add to DANGEROUS_PATTERNS** in the hook
3. **Test and report the issue** if it's a common command

## Real-World Usage

Once verified, deploy to your actual repositories:

1. **Copy settings to your repo**:
   ```bash
   cd /path/to/your/azure/repo
   mkdir -p .claude
   cp ~/azure-guard-test/.claude/settings.json .claude/
   ```

2. **Commit the settings**:
   ```bash
   git add .claude/settings.json
   git commit -m "feat: enable Azure command guard protection"
   git push
   ```

3. **Team members get protection automatically** when they start Claude Code in the repo

## Customization for Your Repository

If your repo needs custom patterns:

1. **Copy the hook to your repo**:
   ```bash
   mkdir -p .claude/hooks
   cp ~/.claude/hooks/azure-command-guard.sh .claude/hooks/
   chmod +x .claude/hooks/azure-command-guard.sh
   ```

2. **Update settings.json** to use local hook:
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

3. **Customize patterns** in `.claude/hooks/azure-command-guard.sh`

4. **Test and commit**:
   ```bash
   .claude/hooks/test-azure-guard.sh  # if you copied the test too
   git add .claude/
   git commit -m "feat: add custom Azure guard patterns"
   ```

## Expected Behavior Summary

| Command Type | Example | Expected |
|--------------|---------|----------|
| Safe reads | `az account show` | ✅ Allowed |
| Safe reads | `az resource list` | ✅ Allowed |
| KeyVault secrets | `az keyvault secret set` | ✅ Allowed |
| Storage uploads | `az storage blob upload` | ✅ Allowed |
| Resource creation | `az resource create` | ❌ Blocked |
| Resource deletion | `az group delete` | ❌ Blocked |
| Deployments | `az deployment create` | ❌ Blocked |
| Auth changes | `az login`, `az account set` | ❌ Blocked |
| Unknown commands | `az new-service command` | ❌ Blocked (fail-safe) |

## Next Steps

- Deploy to production repositories
- Customize patterns for your team's needs
- Monitor blocked commands and adjust patterns
- Keep the hook updated as new Azure services are added
