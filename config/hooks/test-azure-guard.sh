#!/bin/bash
#
# Test suite for azure-command-guard.sh
#
# Tests various Azure CLI commands to ensure the hook correctly:
# - Allows safe read operations
# - Allows explicitly permitted writes (KeyVault secrets, Storage uploads)
# - Blocks dangerous operations
# - Blocks unrecognized patterns (fail-safe)
#

HOOK_SCRIPT="$(dirname "$0")/azure-command-guard.sh"
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PASSED=0
FAILED=0

# Test helper function
test_command() {
    local expected_result=$1  # "ALLOW" or "BLOCK"
    local command=$2
    local description=$3

    # Create mock Claude Code hook input
    local input=$(cat <<EOF
{
  "tool_name": "Bash",
  "tool_input": {
    "command": "$command"
  }
}
EOF
)

    # Run the hook
    echo "$input" | "$HOOK_SCRIPT" >/dev/null 2>&1
    local exit_code=$?
    if [ $exit_code -eq 0 ]; then
        local actual="ALLOW"
    elif [ $exit_code -eq 2 ]; then
        local actual="BLOCK"
    else
        local actual="ERROR($exit_code)"
    fi

    # Check result
    if [ "$expected_result" = "$actual" ]; then
        echo -e "${GREEN}✓ PASS${NC}: $description"
        echo "  Command: $command"
        echo "  Expected: $expected_result, Got: $actual"
        PASSED=$((PASSED + 1))
    else
        echo -e "${RED}✗ FAIL${NC}: $description"
        echo "  Command: $command"
        echo "  Expected: $expected_result, Got: $actual"
        FAILED=$((FAILED + 1))
    fi
    echo ""
}

echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Azure Command Guard Test Suite${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo ""

# ============================================================================
# SECTION 1: Safe Read Operations (Should ALLOW)
# ============================================================================
echo -e "${BLUE}1. Testing Safe Read Operations (should ALLOW)${NC}"
echo "───────────────────────────────────────────────────────────"

test_command "ALLOW" "az account show" \
    "Account information query"

test_command "ALLOW" "az monitor log-analytics query --workspace /subscriptions/..." \
    "Log analytics query"

test_command "ALLOW" "az postgres flexible-server show --name pg-motium-dev --resource-group rg-motium-dev" \
    "PostgreSQL server details"

test_command "ALLOW" "az resource list --resource-group rg-motium-dev" \
    "Resource listing"

test_command "ALLOW" "az functionapp list --resource-group rg-motium-dev" \
    "Function app listing"

test_command "ALLOW" "az containerapp logs show --name ca-backend --resource-group rg-motium-dev" \
    "Container app logs"

test_command "ALLOW" "az keyvault secret show --vault-name kv-motium-dev --name DATABASE_URL" \
    "KeyVault secret read"

test_command "ALLOW" "az storage blob list --account-name stmotiumdev --container-name backups" \
    "Storage blob listing"

# ============================================================================
# SECTION 2: Explicitly Allowed Write Operations (Should ALLOW)
# ============================================================================
echo -e "${BLUE}2. Testing Allowed Write Operations (should ALLOW)${NC}"
echo "───────────────────────────────────────────────────────────"

test_command "ALLOW" "az keyvault secret set --vault-name kv-motium-dev --name API_KEY --value 'secret123'" \
    "KeyVault secret set (explicitly allowed)"

test_command "ALLOW" "az keyvault secret delete --vault-name kv-motium-dev --name OLD_SECRET" \
    "KeyVault secret delete (explicitly allowed)"

test_command "ALLOW" "az storage blob upload --account-name stmotiumdev --container-name backups --file backup.sql --name backup-2024.sql" \
    "Storage blob upload (explicitly allowed)"

test_command "ALLOW" "az storage blob copy start --account-name stmotiumdev --destination-container backups --source-uri https://..." \
    "Storage blob copy (explicitly allowed)"

test_command "ALLOW" "az storage file upload --account-name stmotiumdev --share-name files --source local.txt" \
    "Storage file upload (explicitly allowed)"

# ============================================================================
# SECTION 3: Dangerous Operations (Should BLOCK)
# ============================================================================
echo -e "${BLUE}3. Testing Dangerous Operations (should BLOCK)${NC}"
echo "───────────────────────────────────────────────────────────"

test_command "BLOCK" "az monitor diagnostic-settings create --resource /subscriptions/..." \
    "Diagnostic settings creation"

test_command "BLOCK" "az postgres flexible-server update --name pg-motium-dev --sku-name Standard_D2s_v3" \
    "PostgreSQL server update"

test_command "BLOCK" "az resource delete --ids /subscriptions/.../resourceGroups/..." \
    "Resource deletion"

test_command "BLOCK" "az functionapp restart --name func-motium-dev --resource-group rg-motium-dev" \
    "Function app restart"

test_command "BLOCK" "az group delete --name rg-motium-test --yes" \
    "Resource group deletion"

test_command "BLOCK" "az role assignment create --assignee user@example.com --role Contributor" \
    "Role assignment creation"

test_command "BLOCK" "az deployment group create --resource-group rg-motium-dev --template-file main.tf" \
    "Deployment creation"

test_command "BLOCK" "az keyvault create --name kv-new-vault --resource-group rg-motium-dev" \
    "KeyVault creation (vault management blocked, but secret ops allowed)"

test_command "BLOCK" "az storage account delete --name stmotiumdev --yes" \
    "Storage account deletion"

test_command "BLOCK" "az storage blob delete --account-name stmotiumdev --container-name backups --name old-backup.sql" \
    "Storage blob deletion (uploads allowed, deletions blocked)"

test_command "BLOCK" "az network vnet create --name vnet-new --resource-group rg-motium-dev" \
    "VNet creation"

test_command "ALLOW" "az login" \
    "Azure login (authentication needed)"

test_command "BLOCK" "az account set --subscription 'Production'" \
    "Subscription change (auth change)"

# ============================================================================
# SECTION 4: Edge Cases
# ============================================================================
echo -e "${BLUE}4. Testing Edge Cases${NC}"
echo "───────────────────────────────────────────────────────────"

test_command "ALLOW" "echo 'test' && az account show" \
    "Az command after other command"

test_command "BLOCK" "az account show && az group delete --name rg-test --yes" \
    "Dangerous command after safe command (should block)"

test_command "ALLOW" "az postgres flexible-server list | grep 'motium'" \
    "Az command with pipe"

test_command "ALLOW" "ls -la" \
    "Non-az command (passthrough)"

test_command "BLOCK" "az some-new-service do-something --flag value" \
    "Unrecognized az command (fail-safe should block)"

# ============================================================================
# SECTION 5: Results Summary
# ============================================================================
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Test Results${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  ${GREEN}Passed: $PASSED${NC}"
echo -e "  ${RED}Failed: $FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}✗ Some tests failed. Review the hook logic.${NC}"
    exit 1
fi
