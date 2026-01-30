#!/usr/bin/env bash
# =============================================================================
# Detect modified harness files in the current repository
# =============================================================================
#
# Returns list of modified harness files (staged + unstaged)
# Harness files are:
#   - config/hooks/*
#   - config/skills/*
#   - config/settings.json
#   - config/commands/*
#
# Usage:
#   ./detect-harness-changes.sh [directory]
#
# Output:
#   List of modified harness files, one per line
#   Empty output = no harness changes
#
# =============================================================================

set -euo pipefail

TARGET_DIR="${1:-$(pwd)}"
cd "$TARGET_DIR"

# Get modified files (staged + unstaged, relative to HEAD)
MODIFIED_FILES=$(git diff --name-only HEAD 2>/dev/null || true)
STAGED_FILES=$(git diff --cached --name-only 2>/dev/null || true)

# Combine and deduplicate
ALL_FILES=$(echo -e "$MODIFIED_FILES\n$STAGED_FILES" | sort -u | grep -v '^$' || true)

if [[ -z "$ALL_FILES" ]]; then
    exit 0
fi

# Filter to harness files only
HARNESS_PATTERNS=(
    "^config/hooks/"
    "^config/skills/"
    "^config/commands/"
    "^config/settings\.json$"
)

HARNESS_FILES=""
for file in $ALL_FILES; do
    for pattern in "${HARNESS_PATTERNS[@]}"; do
        if echo "$file" | grep -qE "$pattern"; then
            HARNESS_FILES="$HARNESS_FILES$file"$'\n'
            break
        fi
    done
done

# Output harness files (remove trailing newline)
echo -n "$HARNESS_FILES" | grep -v '^$' || true
