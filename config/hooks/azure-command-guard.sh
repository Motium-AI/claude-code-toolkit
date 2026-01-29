#!/bin/bash
#
# Azure Command Guard - PreToolUse Hook for Bash
#
# Blocks dangerous Azure CLI commands while allowing safe read operations
# and explicitly permitted write operations (KeyVault secrets, Storage uploads).
#
# Exit codes (Claude Code PreToolUse convention):
#   0 = Allow command execution
#   2 = Block command execution (shows stderr to Claude)
#
# Usage: Called automatically by Claude Code PreToolUse hook
#

set -euo pipefail

# Parse Claude Code hook input (JSON on stdin)
INPUT=$(cat)

# Extract the command from tool_input.command
COMMAND=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('tool_input', {}).get('command', ''))
except:
    print('')
" 2>/dev/null || echo "")

# If no command extracted, allow (passthrough)
if [ -z "$COMMAND" ]; then
    exit 0
fi

# Only check commands that contain 'az ' (Azure CLI)
if [[ ! "$COMMAND" =~ [[:space:]]az[[:space:]] ]] && [[ ! "$COMMAND" =~ ^az[[:space:]] ]]; then
    exit 0  # Not an az command, allow
fi

# Extract ALL az commands (handle chained commands with &&, ||, ;)
# We need to check each one independently
# Note: Using while loop for bash 3.x compatibility (macOS default)
AZ_COMMANDS=()
while IFS= read -r line; do
    [ -n "$line" ] && AZ_COMMANDS+=("$line")
done < <(echo "$COMMAND" | grep -oE 'az[[:space:]]+[^|>&;]+' || true)

if [ ${#AZ_COMMANDS[@]} -eq 0 ]; then
    exit 0  # Couldn't extract az commands, allow
fi

# ============================================================================
# SAFE PATTERNS - Explicitly allowed read operations
# ============================================================================
SAFE_PATTERNS=(
    # Generic read operations
    '^az .* show'
    '^az .* list'
    '^az .* get'
    '^az .* get-credentials'

    # Account/subscription queries
    '^az account show'
    '^az account list'
    '^az account get-access-token'

    # Authentication (needed to work with Azure)
    '^az login'

    # Monitoring & diagnostics (read-only)
    '^az monitor log-analytics query'
    '^az monitor log-analytics workspace show'
    '^az monitor log-analytics workspace list'
    '^az monitor diagnostic-settings show'
    '^az monitor diagnostic-settings list'
    '^az monitor metrics list'
    '^az monitor activity-log list'

    # Resource queries
    '^az resource show'
    '^az resource list'
    '^az group show'
    '^az group list'

    # Database queries
    '^az postgres flexible-server show'
    '^az postgres flexible-server list'
    '^az postgres flexible-server db show'
    '^az postgres flexible-server db list'
    '^az sql server show'
    '^az sql server list'
    '^az sql db show'
    '^az sql db list'

    # Container & Functions
    '^az containerapp show'
    '^az containerapp list'
    '^az containerapp logs show'
    '^az functionapp show'
    '^az functionapp list'
    '^az functionapp config show'
    '^az functionapp deployment list'

    # Networking
    '^az network vnet show'
    '^az network vnet list'
    '^az network vnet subnet show'
    '^az network vnet subnet list'

    # Storage (read-only)
    '^az storage account show'
    '^az storage account list'
    '^az storage blob list'
    '^az storage blob show'
    '^az storage container list'
    '^az storage container show'

    # KeyVault (read secrets/keys)
    '^az keyvault show'
    '^az keyvault list'
    '^az keyvault secret show'
    '^az keyvault secret list'
    '^az keyvault key show'
    '^az keyvault key list'
)

# Function to check if a command matches a pattern list
matches_pattern() {
    local cmd="$1"
    shift
    local patterns=("$@")
    for pattern in "${patterns[@]}"; do
        if [[ "$cmd" =~ $pattern ]]; then
            return 0
        fi
    done
    return 1
}

# Check each az command
for AZ_CMD in "${AZ_COMMANDS[@]}"; do
    # Skip empty commands
    [ -z "$AZ_CMD" ] && continue

    # Check if command matches known safe pattern
    if matches_pattern "$AZ_CMD" "${SAFE_PATTERNS[@]}"; then
        continue  # This command is safe, check next one
    fi

# ============================================================================
# EXPLICITLY ALLOWED WRITE OPERATIONS
# ============================================================================
ALLOWED_WRITES=(
    # KeyVault secret operations (user specified these are OK)
    '^az keyvault secret set'
    '^az keyvault secret delete'
    '^az keyvault secret download'
    '^az keyvault secret backup'
    '^az keyvault secret restore'

    # Storage uploads/copies (user specified these are OK)
    '^az storage blob upload'
    '^az storage blob upload-batch'
    '^az storage blob copy'
    '^az storage blob copy start'
    '^az storage blob copy start-batch'
    '^az storage file upload'
    '^az storage file upload-batch'
    '^az storage file copy'
)

    # Check if command matches allowed write operations
    if matches_pattern "$AZ_CMD" "${ALLOWED_WRITES[@]}"; then
        continue  # This command is allowed, check next one
    fi

# ============================================================================
# DANGEROUS PATTERNS - Block these operations
# ============================================================================
DANGEROUS_PATTERNS=(
    # Generic mutating verbs
    '^az .* create'
    '^az .* delete'
    '^az .* update'
    '^az .* set'
    '^az .* add'
    '^az .* remove'
    '^az .* start'
    '^az .* stop'
    '^az .* restart'
    '^az .* import'
    '^az .* export'
    '^az .* restore'
    '^az .* failover'
    '^az .* regenerate'
    '^az .* rotate'
    '^az .* revoke'
    '^az .* assign'
    '^az .* unassign'
    '^az .* enable'
    '^az .* disable'
    '^az .* upgrade'
    '^az .* scale'

    # Auth & identity (az login is allowed - see SAFE_PATTERNS)
    '^az logout'
    '^az account set'
    '^az configure'
    '^az role'
    '^az ad '

    # Deployments
    '^az deployment'
    '^az functionapp deploy'
    '^az webapp deploy'
    '^az containerapp up'

    # Resource management
    '^az group delete'
    '^az resource move'
    '^az resource delete'
    '^az policy'
    '^az lock'

    # Database mutations (already excluded by generic patterns, but explicit for clarity)
    '^az postgres flexible-server create'
    '^az postgres flexible-server delete'
    '^az postgres flexible-server update'
    '^az postgres flexible-server restart'
    '^az postgres flexible-server start'
    '^az postgres flexible-server stop'
    '^az sql server create'
    '^az sql server delete'
    '^az sql server update'
    '^az sql db create'
    '^az sql db delete'
    '^az sql db update'

    # Monitoring modifications
    '^az monitor diagnostic-settings create'
    '^az monitor diagnostic-settings update'
    '^az monitor diagnostic-settings delete'
    '^az monitor action-group create'
    '^az monitor action-group delete'
    '^az monitor action-group update'

    # Network changes
    '^az network vnet create'
    '^az network vnet delete'
    '^az network vnet update'
    '^az network vnet subnet create'
    '^az network vnet subnet delete'
    '^az network vnet subnet update'

    # KeyVault management (but NOT secret operations - those are allowed above)
    '^az keyvault create'
    '^az keyvault delete'
    '^az keyvault update'
    '^az keyvault purge'
    '^az keyvault recover'
    '^az keyvault key create'
    '^az keyvault key delete'
    '^az keyvault key import'

    # Storage account management (but NOT blob uploads - those are allowed above)
    '^az storage account create'
    '^az storage account delete'
    '^az storage account update'
    '^az storage container create'
    '^az storage container delete'
    '^az storage blob delete'
    '^az storage blob delete-batch'
)

    # Check if command matches dangerous patterns
    for pattern in "${DANGEROUS_PATTERNS[@]}"; do
        if [[ "$AZ_CMD" =~ $pattern ]]; then
            # Block with detailed message
            cat >&2 <<EOF

╔════════════════════════════════════════════════════════════════╗
║  ⛔ BLOCKED: Azure Resource Modification Detected             ║
╚════════════════════════════════════════════════════════════════╝

Command: $AZ_CMD

Pattern matched: $pattern

This command modifies Azure resources and requires explicit approval.

Allowed operations:
  ✓ Read operations (show, list, get, query)
  ✓ KeyVault secret operations (set, delete, backup)
  ✓ Storage blob uploads/copies

To execute this command:
  1. Review the command carefully
  2. Run it manually in your terminal
  3. Or use Claude Code's approval flow if available

EOF
            exit 2
        fi
    done

    # ============================================================================
    # FAIL-SAFE: Block unrecognized patterns
    # ============================================================================
    # If we reach here, this az command didn't match:
    # - Known safe patterns
    # - Allowed write operations
    # - Known dangerous patterns
    #
    # Conservative approach: block unknown az commands

    cat >&2 <<EOF

╔════════════════════════════════════════════════════════════════╗
║  ⚠️  BLOCKED: Unrecognized Azure CLI Command Pattern         ║
╚════════════════════════════════════════════════════════════════╝

Command: $AZ_CMD

This command doesn't match any known safe patterns.

To allow this operation:
  1. Review the command to ensure it's read-only
  2. If safe, add it to the SAFE_PATTERNS in:
     .claude/hooks/azure-command-guard.sh
  3. Or run it manually in your terminal

EOF
    exit 2
done

# All az commands passed checks, allow execution
exit 0
