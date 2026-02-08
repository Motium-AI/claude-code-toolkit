#!/usr/bin/env python3
"""
PreToolUse hook for deployment enforcement.

Prevents subagents from deploying, blocks concurrent deploys, and gates production
deploys in autonomous mode.

Hook event: PreToolUse
Matcher: Bash

Behavior:
1. Parses Bash command from stdin JSON
2. Subagent blocking: If autonomous mode active AND state has coordinator: false,
   blocks gh workflow run commands
3. Concurrent deploy prevention: If there's already a running/queued workflow,
   blocks new gh workflow run commands to prevent race conditions
4. Production gate: If command targets environment=production:
   - Coordinator (user-facing agent) → allowed (user's instruction IS permission)
   - Subagent without allowedPrompts → blocked
   - Subagent with allowedPrompts → allowed
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

# Add hooks directory to path for shared imports
sys.path.insert(0, str(Path(__file__).parent))
from _common import log_debug, get_code_version
from _session import (
    is_autonomous_mode_active,
    get_autonomous_state,
)

# Patterns that indicate deployment commands
DEPLOY_COMMAND_PATTERNS = [
    r"eas\s+build",
    r"eas\s+submit",
    r"gh\s+workflow\s+run",
    r"gh\s+run\s+watch",
    r"git\s+push",  # Push triggers CI/CD in most repos
    r"az\s+webapp\s+deploy",
    r"az\s+containerapp\s+.*\s+--image",
    r"kubectl\s+apply",
    r"kubectl\s+rollout",
]

# Commands that should trigger concurrent workflow check
CONCURRENT_CHECK_PATTERNS = [
    r"gh\s+workflow\s+run",
    r"git\s+push",  # Push triggers CI, so check before pushing
]

# Patterns that indicate production targeting
PRODUCTION_PATTERNS = [
    r"environment[=\s]+prod(uction)?",
    r"-f\s+environment[=\s]+prod(uction)?",
    r"--env[=\s]+prod(uction)?",
    r"-e\s+prod(uction)?",
    r"prod\.yml",
    r"production\.yml",
    r"deploy.*prod",
]

# Patterns in allowed_prompts that indicate production permission
PRODUCTION_PERMISSION_PATTERNS = [
    r"\bprod\b",
    r"\bproduction\b",
    r"deploy.*prod",
    r"push.*prod",
]

# OAuth goal-verification marker (project-agnostic)
OAUTH_MARKER_RELATIVE_PATH = Path(".claude/oauth-goal-validation.json")
OAUTH_MARKER_MAX_AGE_MS = 2 * 60 * 60 * 1000  # 2 hours


def is_deploy_command(command: str) -> bool:
    """Check if command is a deployment command."""
    for pattern in DEPLOY_COMMAND_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return True
    return False


def is_production_target(command: str) -> bool:
    """Check if command targets production environment."""
    for pattern in PRODUCTION_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return True
    return False


def has_production_permission(state: dict) -> bool:
    """Check if production deployment was explicitly permitted in the plan."""
    allowed_prompts = state.get("allowed_prompts", [])
    if not allowed_prompts:
        return False

    for prompt_entry in allowed_prompts:
        if not isinstance(prompt_entry, dict):
            continue

        # Check if it's a Bash tool permission
        if prompt_entry.get("tool") != "Bash":
            continue

        prompt_text = prompt_entry.get("prompt", "")
        for pattern in PRODUCTION_PERMISSION_PATTERNS:
            if re.search(pattern, prompt_text, re.IGNORECASE):
                log_debug(f"Production permission found: {prompt_text}")
                return True

    return False


def is_ios_eas_build_command(command: str) -> bool:
    """Check whether command is an iOS EAS build invocation."""
    if not re.search(r"\beas\s+build\b", command, re.IGNORECASE):
        return False

    if re.search(r"(--platform|-p)\s+android\b", command, re.IGNORECASE):
        return False

    return bool(re.search(r"(--platform|-p)\s+ios\b", command, re.IGNORECASE))


def _has_oauth_verification_script(app_dir: Path) -> bool:
    """Check if an app directory has an OAuth goal verification script.

    Dynamic detection replaces the hardcoded CLAUDE_MOBILE_BUNDLE_ID constant.
    Any Expo app that ships a verify-oauth-user-goal.sh script needs the
    OAuth gate — this is project-agnostic.
    """
    if not app_dir.is_dir():
        return False
    # Check for the verification script in standard locations
    for script_path in [
        app_dir / "scripts" / "verify-oauth-user-goal.sh",
        app_dir / "verify-oauth-user-goal.sh",
    ]:
        if script_path.exists():
            return True
    # Also check if the OAuth marker directory exists (created by a previous verification)
    if (app_dir / OAUTH_MARKER_RELATIVE_PATH).parent.exists():
        marker = app_dir / OAUTH_MARKER_RELATIVE_PATH
        if marker.exists():
            return True
    return False


def find_oauth_gated_app_dir(cwd: str) -> Path | None:
    """Find an Expo app directory that requires OAuth goal verification.

    Walks up the directory tree and checks standard monorepo locations.
    Returns the app directory if it has OAuth verification scripts, else None.
    Project-agnostic: works for any Expo app with the verification pattern.
    """
    start = Path(cwd).resolve()
    candidates = []

    # Direct: running from the app directory
    candidates.append(start)

    # Monorepo: running from repo root, app is in packages/mobile
    candidates.append(start / "packages" / "mobile")

    # Walk up parents for nested working directories
    for parent in start.parents:
        candidates.append(parent)
        candidates.append(parent / "packages" / "mobile")

    seen = set()
    for candidate in candidates:
        resolved = str(candidate)
        if resolved in seen:
            continue
        seen.add(resolved)
        if _has_oauth_verification_script(candidate):
            return candidate

    return None


def validate_oauth_goal_marker(mobile_dir: Path) -> tuple[bool, str]:
    """Validate OAuth user-goal marker for current code version."""
    marker_path = mobile_dir / OAUTH_MARKER_RELATIVE_PATH
    if not marker_path.exists():
        return (
            False,
            (
                "Missing OAuth goal verification marker. "
                "Run: bash packages/mobile/scripts/verify-oauth-user-goal.sh"
            ),
        )

    try:
        marker = json.loads(marker_path.read_text())
    except (OSError, json.JSONDecodeError):
        return False, f"Invalid marker JSON at {marker_path}"

    if marker.get("status") != "passed":
        return False, f"OAuth marker status is not passed: {marker.get('status')!r}"

    current_code_version = get_code_version(str(mobile_dir))
    marker_code_version = marker.get("code_version")
    if marker_code_version != current_code_version:
        return (
            False,
            (
                "OAuth marker is stale for current code version "
                f"(marker={marker_code_version!r}, current={current_code_version!r}). "
                "Re-run: bash packages/mobile/scripts/verify-oauth-user-goal.sh"
            ),
        )

    verified_epoch_ms = marker.get("verified_epoch_ms")
    if not isinstance(verified_epoch_ms, int):
        return False, "OAuth marker missing integer verified_epoch_ms"

    age_ms = int(time.time() * 1000) - verified_epoch_ms
    if age_ms > OAUTH_MARKER_MAX_AGE_MS:
        return (
            False,
            (
                "OAuth marker is older than 2 hours. "
                "Re-run: bash packages/mobile/scripts/verify-oauth-user-goal.sh"
            ),
        )

    return True, ""


def check_running_workflows(cwd: str) -> list[dict]:
    """Check for running or queued GitHub workflows.

    Returns list of running/queued workflow runs, or empty list if none or error.
    """
    try:
        result = subprocess.run(
            ["gh", "run", "list", "--status", "in_progress", "--json", "databaseId,name,status,conclusion"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            in_progress = json.loads(result.stdout)
        else:
            in_progress = []

        # Also check queued
        result = subprocess.run(
            ["gh", "run", "list", "--status", "queued", "--json", "databaseId,name,status,conclusion"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            queued = json.loads(result.stdout)
        else:
            queued = []

        all_running = in_progress + queued
        if all_running:
            log_debug(f"Found {len(all_running)} running/queued workflows: {[w.get('name') for w in all_running]}")
        return all_running
    except subprocess.TimeoutExpired:
        log_debug("Timeout checking for running workflows")
        return []
    except (json.JSONDecodeError, FileNotFoundError) as e:
        log_debug(f"Error checking running workflows: {e}")
        return []


def block_with_message(message: str, reason: str) -> None:
    """Output a block response to Claude Code."""
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
            "additionalContext": message,
        }
    }
    print(json.dumps(output))
    sys.exit(0)


def main():
    # Parse input from Claude Code
    try:
        stdin_data = sys.stdin.read()
        if not stdin_data.strip():
            sys.exit(0)  # No input, pass through
        input_data = json.loads(stdin_data)
    except json.JSONDecodeError:
        sys.exit(0)  # Invalid JSON, pass through

    # Extract command and context
    tool_input = input_data.get("tool_input", {})
    command = tool_input.get("command", "")
    cwd = input_data.get("cwd", os.getcwd())
    session_id = input_data.get("session_id", "")

    if not command:
        sys.exit(0)  # No command, pass through

    # Check if this is a deploy command
    if not is_deploy_command(command):
        sys.exit(0)  # Not a deploy command, pass through

    log_debug(f"Deploy command detected: {command[:100]}")

    # Global goal-closure gate for Claude Mobile iOS builds:
    # block deploy until OAuth user-goal verification has passed on current code.
    if is_ios_eas_build_command(command):
        mobile_dir = find_oauth_gated_app_dir(cwd)
        if mobile_dir:
            ok, reason = validate_oauth_goal_marker(mobile_dir)
            if not ok:
                cwd_path = Path(cwd).resolve()
                verify_cmd = "bash packages/mobile/scripts/verify-oauth-user-goal.sh"
                if cwd_path == mobile_dir or mobile_dir in cwd_path.parents:
                    verify_cmd = "bash scripts/verify-oauth-user-goal.sh"
                pnpm_cmd = "pnpm --filter claude-mobile verify:oauth-goal"
                if cwd_path == mobile_dir or mobile_dir in cwd_path.parents:
                    pnpm_cmd = "pnpm verify:oauth-goal"
                log_debug(f"Blocking iOS build (OAuth marker gate): {reason}")
                block_with_message(
                    message=(
                        "⛔ BUILD BLOCKED: OAuth user-goal verification required before iOS deploy.\n\n"
                        "This app has a known failure mode where Anthropic OAuth appears to load but "
                        "silently falls back to Settings. You must prove the real user goal still works.\n\n"
                        "Run this first:\n"
                        f"  {pnpm_cmd}\n"
                        "or\n"
                        f"  {verify_cmd}\n\n"
                        f"Reason: {reason}"
                    ),
                    reason="Missing/stale OAuth user-goal verification marker",
                )

    # Check if autonomous mode is active
    # Pass session_id to enable cross-directory trust for same session
    if not is_autonomous_mode_active(cwd, session_id):
        sys.exit(0)  # Not in autonomous mode, pass through

    # Get the state to check coordinator status and permissions
    state, state_type = get_autonomous_state(cwd, session_id)
    if not state:
        sys.exit(0)  # No state file, pass through

    # Rule 1: Subagents cannot deploy
    if state.get("coordinator") is False:
        log_debug("Blocking subagent deploy attempt")
        block_with_message(
            message=(
                "⛔ DEPLOY BLOCKED: Subagents cannot deploy.\n\n"
                "Only the coordinator agent can trigger deployments. "
                "This prevents race conditions where multiple agents deploy over each other.\n\n"
                "Mark your checkpoint with `needs_deploy: true` and the coordinator will handle deployment."
            ),
            reason="Subagent attempted deployment (coordinator: false)",
        )

    # Rule 2: Block concurrent deploys (check for gh workflow run AND git push)
    # Git push triggers CI/CD in most repos, so we must check before pushing
    should_check_concurrent = any(
        re.search(pattern, command, re.IGNORECASE)
        for pattern in CONCURRENT_CHECK_PATTERNS
    )
    if should_check_concurrent:
        running_workflows = check_running_workflows(cwd)
        if running_workflows:
            workflow_names = [w.get("name", "unknown") for w in running_workflows[:5]]
            workflow_ids = [str(w.get("databaseId", "?")) for w in running_workflows[:5]]
            log_debug(f"Blocking concurrent deploy: {len(running_workflows)} workflows already running")

            # Different message for git push vs gh workflow run
            is_git_push = re.search(r"git\s+push", command, re.IGNORECASE)
            if is_git_push:
                action_msg = (
                    "You're trying to push while CI/CD workflows are still running.\n"
                    "This would trigger additional workflows and cause deployment race conditions.\n\n"
                    "Wait for the current workflow(s) to complete first:\n"
                    "  gh run watch --exit-status " + str(running_workflows[0].get("databaseId", ""))
                )
            else:
                action_msg = (
                    "Wait for the current workflow(s) to complete before triggering a new deploy.\n"
                    "Use: gh run watch --exit-status <run-id>"
                )

            block_with_message(
                message=(
                    "⛔ CONCURRENT DEPLOY BLOCKED\n\n"
                    f"There are already {len(running_workflows)} workflow(s) running or queued:\n"
                    + "\n".join(f"  - {name} (ID: {wid})" for name, wid in zip(workflow_names, workflow_ids))
                    + "\n\n"
                    + action_msg
                    + "\n\nThis prevents deployment race conditions where one deploy overwrites another."
                ),
                reason=f"Concurrent deploy blocked: {len(running_workflows)} workflows already running",
            )

    # Rule 3: Production deploys require explicit permission (subagents only)
    # Coordinator is exempt — they have the user in the loop, so the user's
    # conversational instruction IS the permission. Subagents don't talk to
    # the user, so they need pre-approval via allowedPrompts.
    if is_production_target(command):
        is_coordinator = state.get("coordinator") is not False
        if is_coordinator:
            log_debug("Production deploy by coordinator — user is in the loop")
        elif not has_production_permission(state):
            log_debug("Blocking subagent production deploy without explicit permission")
            block_with_message(
                message=(
                    "⛔ PRODUCTION DEPLOY BLOCKED\n\n"
                    "This command targets production but was not explicitly permitted in the plan.\n\n"
                    "To deploy to production, you must:\n"
                    "1. Include production deployment in your ExitPlanMode allowedPrompts\n"
                    "2. Or ask the coordinator to handle the production deployment\n\n"
                    f"Command: {command[:200]}"
                ),
                reason="Subagent production deployment not explicitly permitted in plan",
            )
        else:
            log_debug("Production deploy permitted via allowedPrompts")

    # All checks passed, allow the command
    sys.exit(0)


if __name__ == "__main__":
    main()
