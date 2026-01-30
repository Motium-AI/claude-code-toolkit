#!/usr/bin/env bash
# =============================================================================
# Propagate uncommitted changes to sandbox project
# =============================================================================
#
# Copies all modified files (staged + unstaged) from source to sandbox.
# Used to apply work-in-progress changes to an isolated test environment.
#
# Usage:
#   ./propagate-changes.sh <source-dir> <sandbox-project-dir>
#
# Example:
#   ./propagate-changes.sh /path/to/claude-code-toolkit /tmp/claude-sandboxes/sandbox-xxx/project
#
# =============================================================================

set -euo pipefail

SOURCE_DIR="${1:?Usage: $0 <source-dir> <sandbox-project-dir>}"
SANDBOX_PROJECT="${2:?Usage: $0 <source-dir> <sandbox-project-dir>}"

cd "$SOURCE_DIR"

# Get list of modified files (staged + unstaged)
MODIFIED_FILES=$(git diff --name-only HEAD 2>/dev/null || true)
STAGED_FILES=$(git diff --cached --name-only 2>/dev/null || true)

# Combine and deduplicate
ALL_FILES=$(echo -e "$MODIFIED_FILES\n$STAGED_FILES" | sort -u | grep -v '^$' || true)

if [[ -z "$ALL_FILES" ]]; then
    echo "No modified files to propagate"
    exit 0
fi

COUNT=0
echo "$ALL_FILES" | while read -r file; do
    if [[ -n "$file" ]] && [[ -f "$SOURCE_DIR/$file" ]]; then
        # Create parent directory in sandbox
        mkdir -p "$(dirname "$SANDBOX_PROJECT/$file")"
        # Copy the file
        cp "$SOURCE_DIR/$file" "$SANDBOX_PROJECT/$file"
        echo "Propagated: $file"
        COUNT=$((COUNT + 1))
    elif [[ -n "$file" ]] && [[ ! -f "$SOURCE_DIR/$file" ]]; then
        # File was deleted - remove from sandbox if exists
        if [[ -f "$SANDBOX_PROJECT/$file" ]]; then
            rm "$SANDBOX_PROJECT/$file"
            echo "Removed (deleted): $file"
        fi
    fi
done

echo "Done propagating changes"
