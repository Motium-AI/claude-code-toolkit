#!/usr/bin/env python3
"""
PostToolUse Hook - Bash Error Advisory (Mid-Execution Enforcement)

Monitors Bash tool output for error patterns and injects advisory warnings.
ADVISORY ONLY — never blocks, just surfaces context to help the agent.

Fires after every Bash tool use. Checks:
1. Non-zero exit codes → warns about failure patterns
2. Common error signatures → suggests fix strategies
3. Repeated failures → escalates advisory urgency

Part of Tier 3 debugging infrastructure. Advisory mode per user preference.

Hook event: PostToolUse (matcher: Bash)
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import log_debug, timed_hook
from _session import is_autonomous_mode_active

# Error pattern → advisory message mapping
ERROR_PATTERNS = [
    # Python errors
    (r"ModuleNotFoundError: No module named '([^']+)'",
     "Missing Python module '{0}'. Check: virtual env active? Package installed? Correct import path?"),
    (r"ImportError: cannot import name '([^']+)'",
     "Import failed for '{0}'. The symbol may have been renamed, moved, or removed."),
    (r"SyntaxError: (.+)",
     "Python syntax error: {0}. Check for unclosed brackets, missing colons, or indentation."),

    # Node/TypeScript errors
    (r"Cannot find module '([^']+)'",
     "Missing Node module '{0}'. Run: npm install or check package.json."),
    (r"error TS\d+: (.+)",
     "TypeScript error: {0}. Run tsc --noEmit for full diagnostics."),
    (r"ERR_MODULE_NOT_FOUND",
     "ESM module not found. Check file extensions (.js/.mjs) and package.json type field."),

    # Git errors
    (r"error: failed to push some refs",
     "Push rejected. Pull first (git pull --rebase) or check if branch is protected."),
    (r"CONFLICT \(content\): Merge conflict in (.+)",
     "Merge conflict in {0}. Resolve manually before continuing."),

    # Docker/Container errors
    (r"Cannot connect to the Docker daemon",
     "Docker daemon not running. Start Docker Desktop or systemctl start docker."),

    # Permission errors
    (r"Permission denied",
     "Permission denied. Check file ownership, executable bits, or sudo requirements."),
    (r"EACCES",
     "Access denied (EACCES). Check directory permissions or try --user flag."),

    # Database errors
    (r"connection refused.*(?:5432|3306|27017)",
     "Database connection refused. Is the database server running? Check connection string."),
    (r"relation \"([^\"]+)\" does not exist",
     "Table '{0}' not found. Run migrations or check schema."),

    # Build errors
    (r"error: command '([^']+)' failed",
     "Build command '{0}' failed. Check build dependencies and compiler version."),
    (r"FATAL ERROR: .* JavaScript heap out of memory",
     "Node.js out of memory. Try: NODE_OPTIONS='--max-old-space-size=4096'"),

    # Network errors
    (r"\b(?:ETIMEDOUT|ECONNREFUSED|ENOTFOUND)\b",
     "Network error. Check internet connection, DNS, or if the target service is running."),
]

# Deploy failure patterns → rollback advisory
DEPLOY_FAILURE_PATTERNS = [
    (r"exit status (\d+)",
     "Workflow/command failed (exit {0}). Check: gh run view --log-failed. "
     "Rollback: git revert HEAD && git push, or re-trigger with fixes."),
    (r"(?:eas build|Build).*failed|Build failed|build failed",
     "EAS build failed. Check build logs: eas build:list. "
     "Rollback: revert the failing commit and rebuild."),
    (r"(?:deploy|deployment).*(?:error|failed|Error)",
     "Deployment failed. For Azure: az webapp deployment slot swap --slot staging. "
     "For k8s: kubectl rollout undo deployment/<name>."),
    (r"(?:error|failed).*(?:apply|rollout|deploy)",
     "Deployment operation failed. Rollback: kubectl rollout undo, or git revert HEAD && git push."),
    (r"deployment.*(?:unhealthy|crash|CrashLoopBackOff|ImagePullBackOff)",
     "Deployment health check failed. Rollback: kubectl rollout undo, "
     "or revert the commit and redeploy."),
    (r"(?:502 Bad Gateway|503 Service Unavailable).*(?:after|deploy|push)",
     "Service returning errors post-deploy. Check health endpoints and rollback if needed."),
]

# Track recent errors for escalation
ERROR_LOG_PATH_TEMPLATE = ".claude/bash-error-log.json"
MAX_ERROR_LOG_ENTRIES = 20
ESCALATION_THRESHOLD = 3  # Same-pattern errors before escalation


def _match_error_patterns(output: str) -> list[str]:
    """Match output against known error patterns, return advisory messages."""
    advisories = []
    for pattern, message_template in ERROR_PATTERNS:
        match = re.search(pattern, output, re.IGNORECASE)
        if match:
            groups = match.groups()
            try:
                msg = message_template.format(*groups) if groups else message_template
            except (IndexError, KeyError):
                msg = message_template
            advisories.append(msg)
    return advisories[:3]  # Cap at 3 advisories per invocation


def _match_deploy_failures(output: str, command: str) -> list[str]:
    """Check for deploy-specific failures and suggest rollback commands."""
    advisories = []
    # Only check if the command looks deploy-related
    deploy_keywords = ["deploy", "push", "eas", "workflow", "kubectl", "az webapp", "gh run"]
    if not any(kw in command.lower() for kw in deploy_keywords):
        return advisories
    for pattern, message_template in DEPLOY_FAILURE_PATTERNS:
        match = re.search(pattern, output, re.IGNORECASE)
        if match:
            groups = match.groups()
            try:
                msg = message_template.format(*groups) if groups else message_template
            except (IndexError, KeyError):
                msg = message_template
            advisories.append(f"DEPLOY FAILURE: {msg}")
    return advisories[:2]


def _track_error(cwd: str, pattern_key: str) -> int:
    """Track error occurrence, return count of recent same-pattern errors."""
    log_path = Path(cwd) / ERROR_LOG_PATH_TEMPLATE
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        entries = []
        if log_path.exists():
            entries = json.loads(log_path.read_text()).get("errors", [])

        # Add new entry
        entries.append({
            "pattern": pattern_key,
            "ts": time.time(),
        })

        # Keep only recent entries
        entries = entries[-MAX_ERROR_LOG_ENTRIES:]

        log_path.write_text(json.dumps({"errors": entries}, indent=2))

        # Count recent same-pattern errors (last 5 minutes)
        cutoff = time.time() - 300
        recent_same = [
            e for e in entries
            if e.get("pattern") == pattern_key and e.get("ts", 0) > cutoff
        ]
        return len(recent_same)
    except (IOError, json.JSONDecodeError):
        return 1


def main():
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    cwd = input_data.get("cwd", "")
    tool_output = input_data.get("tool_output", "")
    tool_input = input_data.get("tool_input", {})

    if not cwd or not tool_output:
        sys.exit(0)

    # Only advise in autonomous mode (casual sessions have user oversight)
    session_id = input_data.get("session_id", "")
    if not is_autonomous_mode_active(cwd, session_id):
        sys.exit(0)

    # Check for non-zero exit or error patterns in output
    # Claude Code tool_output includes stderr; check for error signatures
    advisories = _match_error_patterns(tool_output)

    # Check for deploy failures (with rollback suggestions)
    command = tool_input.get("command", "")
    deploy_advisories = _match_deploy_failures(tool_output, command)
    advisories.extend(deploy_advisories)

    if not advisories:
        sys.exit(0)

    # Track for escalation
    pattern_key = advisories[0][:40]  # Use first 40 chars as key
    error_count = _track_error(cwd, pattern_key)

    # Build advisory message
    parts = ["ADVISORY: Bash command produced error(s):"]
    for adv in advisories:
        parts.append(f"  - {adv}")

    if error_count >= ESCALATION_THRESHOLD:
        parts.append(
            f"\n  WARNING: This error pattern has occurred {error_count} times in the last 5 minutes. "
            "Consider a different approach rather than retrying the same command."
        )

    context = "\n".join(parts)
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": context,
        }
    }

    log_debug(
        f"Bash error advisory: {len(advisories)} patterns matched, count={error_count}",
        hook_name="bash-error-advisor",
    )

    print(json.dumps(output))
    sys.exit(0)


if __name__ == "__main__":
    with timed_hook("bash-error-advisor"):
        main()
