#!/usr/bin/env python3
"""
Checkpoint Write Validator - Warn on claims without evidence

This PostToolUse hook fires when writing to completion-checkpoint.json.
It warns (not blocks) when claims don't match available evidence at write time.

This provides early feedback to Claude before the stop hook catches issues,
helping prevent wasted effort from setting invalid checkpoint values.

Exit codes:
  0 - Always (warnings only, never blocks)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def get_code_version(cwd: str = "") -> str:
    """
    Get current code version (git HEAD + dirty indicator).

    Returns format:
    - "abc1234" - clean commit
    - "abc1234-dirty" - commit with uncommitted changes (no hash suffix)
    - "unknown" - not a git repo

    NOTE: The dirty indicator is boolean, NOT a hash. This ensures version
    stability during development - version only changes at commit boundaries.
    """
    import subprocess

    try:
        head = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
            cwd=cwd or None,
        )
        head_hash = head.stdout.strip()
        if not head_hash:
            return "unknown"

        diff = subprocess.run(
            ["git", "diff", "HEAD"],
            capture_output=True, text=True, timeout=5,
            cwd=cwd or None,
        )
        # Return stable version - no hash suffix for dirty state
        if diff.stdout.strip():
            return f"{head_hash}-dirty"

        return head_hash
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return "unknown"


def is_autonomous_mode(cwd: str = "") -> bool:
    """Check if any autonomous execution mode is active (godo or appfix)."""
    # User-level state takes precedence (cross-repo compatible)
    user_godo = Path.home() / ".claude" / "godo-state.json"
    user_appfix = Path.home() / ".claude" / "appfix-state.json"
    if user_godo.exists() or user_appfix.exists():
        return True

    # Fall back to project-level state
    if cwd:
        project_godo = Path(cwd) / ".claude" / "godo-state.json"
        project_appfix = Path(cwd) / ".claude" / "appfix-state.json"
        if project_godo.exists() or project_appfix.exists():
            return True

    return False


# Health endpoint patterns that don't count as real app pages
HEALTH_URL_PATTERNS = [
    '/health', '/healthz', '/api/health', '/ping', '/ready', '/live',
    '/readiness', '/liveness', '/_health', '/status', '/api/status'
]


def has_real_app_urls(urls: list[str]) -> bool:
    """Check if any URLs are actual app pages (not just health endpoints)."""
    if not urls:
        return False
    for url in urls:
        url_lower = url.lower()
        is_health = any(pattern in url_lower for pattern in HEALTH_URL_PATTERNS)
        if not is_health:
            return True
    return False


def main():
    raw_input = sys.stdin.read()
    try:
        input_data = json.loads(raw_input) if raw_input else {}
    except json.JSONDecodeError:
        sys.exit(0)

    # Only process Write tool completions
    tool_name = input_data.get("tool_name", "")
    if tool_name != "Write":
        sys.exit(0)

    # Get the file path from tool input
    tool_input = input_data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    # Only process writes to completion-checkpoint.json
    if not file_path.endswith("completion-checkpoint.json"):
        sys.exit(0)

    cwd = input_data.get("cwd", "")

    # Only apply strict validation in autonomous mode
    if not is_autonomous_mode(cwd):
        sys.exit(0)

    # Parse the checkpoint content being written
    content = tool_input.get("content", "")
    try:
        checkpoint = json.loads(content)
    except json.JSONDecodeError:
        print("WARNING: completion-checkpoint.json content is not valid JSON", file=sys.stderr)
        sys.exit(0)

    report = checkpoint.get("self_report", {})
    evidence = checkpoint.get("evidence", {})
    warnings = []

    # Check 1: web_testing_done=true without Surf artifacts
    if report.get("web_testing_done", False):
        artifact_dir = Path(cwd) / ".claude" / "web-smoke" if cwd else Path(".claude/web-smoke")
        summary_path = artifact_dir / "summary.json"

        if not summary_path.exists():
            warnings.append(
                "web_testing_done: true but .claude/web-smoke/summary.json does not exist!\n"
                "The stop hook will BLOCK this. Run Surf CLI first:\n"
                "  python3 ~/.claude/hooks/surf-verify.py --urls 'https://your-app.com'"
            )
        else:
            # Check if artifacts are stale
            try:
                summary = json.loads(summary_path.read_text())
                tested_version = summary.get("tested_at_version", "")
                current_version = get_code_version(cwd)
                if tested_version and current_version != "unknown" and tested_version != current_version:
                    warnings.append(
                        f"web_testing_done: true but Surf artifacts are STALE!\n"
                        f"Artifacts from version '{tested_version}', current is '{current_version}'.\n"
                        "Re-run Surf CLI to update artifacts."
                    )
                # Check if artifacts show pass
                if not summary.get("passed", False):
                    warnings.append(
                        "web_testing_done: true but .claude/web-smoke/summary.json shows passed: false!\n"
                        "Fix the issues identified in the summary, then re-run Surf CLI."
                    )
            except (json.JSONDecodeError, IOError):
                warnings.append("Cannot parse .claude/web-smoke/summary.json - verify it's valid JSON")

    # Check 2: console_errors_checked=true without artifacts
    if report.get("console_errors_checked", False):
        artifact_dir = Path(cwd) / ".claude" / "web-smoke" if cwd else Path(".claude/web-smoke")
        summary_path = artifact_dir / "summary.json"

        if not summary_path.exists():
            warnings.append(
                "console_errors_checked: true but no Surf artifacts exist!\n"
                "The stop hook will BLOCK this. Run Surf CLI for deterministic proof."
            )

    # Check 3: urls_tested contains only health endpoints
    urls_tested = evidence.get("urls_tested", [])
    if report.get("web_testing_done", False) and urls_tested:
        if not has_real_app_urls(urls_tested):
            warnings.append(
                f"urls_tested contains ONLY health endpoints: {urls_tested}\n"
                "Health endpoints don't prove the app works!\n"
                "Add real user-facing URLs like /dashboard, /login, /profile, etc."
            )

    # Check 4: urls_tested is empty when web_testing_done=true
    if report.get("web_testing_done", False) and not urls_tested:
        warnings.append(
            "web_testing_done: true but evidence.urls_tested is empty!\n"
            "The stop hook will BLOCK this. Add the URLs you actually tested."
        )

    # Output warnings
    if warnings:
        print("\n" + "=" * 70, file=sys.stderr)
        print("CHECKPOINT WRITE WARNINGS (stop hook will likely BLOCK):", file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        for i, warning in enumerate(warnings, 1):
            print(f"\n{i}. {warning}", file=sys.stderr)
        print("\n" + "=" * 70, file=sys.stderr)
        print("Fix these issues NOW rather than waiting for the stop hook to block you.", file=sys.stderr)
        print("=" * 70 + "\n", file=sys.stderr)

    # Always exit 0 - this is a warning hook, not a blocker
    sys.exit(0)


if __name__ == "__main__":
    main()
