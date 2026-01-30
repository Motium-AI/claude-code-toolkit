#!/usr/bin/env bash
# =============================================================================
# Detect if current directory is a Claude Code harness project
# =============================================================================
#
# Returns exit code 0 if this is a harness project (2 of 3 markers found)
# Returns exit code 1 otherwise
#
# Markers:
#   1. Directory structure: config/hooks/, config/skills/, config/settings.json
#   2. Git remote contains "claude-code-toolkit"
#   3. README.md mentions "Claude Code Toolkit"
#
# Usage:
#   ./detect-harness.sh [directory]
#   Exit code 0 = harness project
#   Exit code 1 = not harness project
#
# =============================================================================

set -euo pipefail

TARGET_DIR="${1:-$(pwd)}"
cd "$TARGET_DIR"

MARKERS_FOUND=0

# Marker 1: Directory structure signature
if [[ -f "config/settings.json" ]] && \
   [[ -d "config/hooks" ]] && \
   [[ -d "config/skills" ]]; then
    MARKERS_FOUND=$((MARKERS_FOUND + 1))
    if [[ -n "${HARNESS_DEBUG:-}" ]]; then
        echo "Marker 1 found: Directory structure (config/hooks, config/skills, config/settings.json)" >&2
    fi
fi

# Marker 2: Git remote contains "claude-code-toolkit"
if git remote -v 2>/dev/null | grep -q "claude-code-toolkit"; then
    MARKERS_FOUND=$((MARKERS_FOUND + 1))
    if [[ -n "${HARNESS_DEBUG:-}" ]]; then
        echo "Marker 2 found: Git remote contains 'claude-code-toolkit'" >&2
    fi
fi

# Marker 3: README.md mentions "Claude Code Toolkit"
if grep -qi "Claude Code Toolkit" README.md 2>/dev/null; then
    MARKERS_FOUND=$((MARKERS_FOUND + 1))
    if [[ -n "${HARNESS_DEBUG:-}" ]]; then
        echo "Marker 3 found: README.md mentions 'Claude Code Toolkit'" >&2
    fi
fi

if [[ -n "${HARNESS_DEBUG:-}" ]]; then
    echo "Markers found: $MARKERS_FOUND/3" >&2
fi

# Need at least 2 markers
if [[ $MARKERS_FOUND -ge 2 ]]; then
    echo "true"
    exit 0
else
    echo "false"
    exit 1
fi
