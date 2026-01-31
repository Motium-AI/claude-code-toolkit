#!/usr/bin/env python3
"""
Stop Validator Templates - Blocking message templates and functions.

This module contains the user-facing messages displayed when the stop hook
blocks execution due to missing or invalid completion checkpoints.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add hooks directory to path for sibling imports
sys.path.insert(0, str(Path(__file__).parent))

from _common import get_code_version, get_worktree_info
from _state import is_go_active


# ============================================================================
# Template Constants
# ============================================================================

GO_CHECKPOINT_SCHEMA_TEMPLATE = """{version_note}
{{
  "self_report": {{
    "is_job_complete": false,                // Is the job ACTUALLY done?
    "code_changes_made": false,              // Did you modify any code files?
    "linters_pass": false,                   // (Only if code_changes_made) Did linters pass?
    "category": ""                           // REQUIRED: bugfix | gotcha | architecture | pattern | config | refactor
  }},
  "reflection": {{
    "what_was_done": "...",                  // >20 chars - what you actually did
    "what_remains": "none",                  // Must be empty to allow stop
    "key_insight": "...",                    // >30 chars: reusable lesson for FUTURE sessions. NOT what you did — what you LEARNED.
    "search_terms": []                       // 2-7 concept keywords for memory retrieval. Tool names, error types, patterns. NOT file paths.
  }}
}}"""

CHECKPOINT_SCHEMA_TEMPLATE = """{version_note}
{{
  "self_report": {{
    "code_changes_made": true,              // Did you modify any code files?
    "web_testing_done": false,              // Did you verify in browser/Surf?
    "web_testing_done_at_version": "",      // Git version when tested
    "deployed": false,                      // Did you deploy the changes?
    "deployed_at_version": "",              // Git version when deployed
    "linters_pass": false,                  // Did all linters pass?
    "linters_pass_at_version": "",          // Git version when linted
    "is_job_complete": false,               // Is the job ACTUALLY done?
    "category": ""                          // REQUIRED: bugfix | gotcha | architecture | pattern | config | refactor
  }},
  "reflection": {{
    "what_was_done": "...",                 // Honest summary of work completed
    "what_remains": "none",                 // Must be empty to allow stop
    "key_insight": "...",                   // REQUIRED >30 chars: reusable lesson for FUTURE sessions. NOT what you did — what you LEARNED.
    "search_terms": []                      // REQUIRED 2-7 concept keywords for memory retrieval. Tool names, error types, patterns. NOT file paths.
  }},
  "evidence": {{
    "urls_tested": [],                      // URLs you actually tested
    "console_clean": false                  // Was browser console clean?
  }}
}}"""

VERSION_TRACKING_GUIDANCE = """
VERSION TRACKING:
- Version-dependent fields (deployed, linters_pass, web_testing_done)
  must include a matching *_at_version field with the git commit hash
- If you make code changes AFTER setting a checkpoint, it becomes STALE
- Get current version: git rev-parse --short HEAD
"""

# Guidance blocks keyed by failure keyword for selective display
GUIDANCE_BLOCKS = {
    "STALE": """
  → The code changed since that checkpoint was set
  → Re-run that step (deploy, test, lint) with the current code
  → {version_info}
  → Update checkpoint: "field": true, "field_at_version": "<version>"
""",
    "web_testing_done": """
  → Run Surf CLI or Chrome MCP to verify in browser
  → Check browser console for errors
  → Update checkpoint with results and version
""",
    "deployed": """
  → Commit and push: git add <files> && git commit -m "fix: ..." && git push
  → Deploy: gh workflow run deploy.yml && gh run watch --exit-status
  → Update checkpoint: deployed: true, deployed_at_version: "<version>"
""",
    "linters_pass": """
  → Auto-detect linters: package.json → npm run lint, pyproject.toml → ruff check --fix
  → Fix ALL errors including pre-existing ones
  → Update checkpoint: linters_pass: true, linters_pass_at_version: "<version>"
""",
    "is_job_complete": """
  → You said the job isn't done. Complete the remaining work, then update checkpoint.
""",
    "what_remains": """
  → You listed remaining work — do it!
""",
    "key_insight": """
  → key_insight captures what FUTURE sessions should know — the reusable lesson
  → Must be >30 chars and different from what_was_done (it's what you LEARNED, not what you DID)
  → Example: "macOS fsync() doesn't flush disk write cache; F_FULLFSYNC is required for crash safety"
""",
    "search_terms": """
  → search_terms are 2-7 concept keywords for memory retrieval
  → Include: tool names, error types, technique names, platform quirks
  → Do NOT include file paths (those are extracted automatically)
  → Example: ["macOS", "fsync", "crash-safety", "atomic-write"]
""",
    "category": """
  → category must be one of: bugfix, gotcha, architecture, pattern, config, refactor
  → Pick the one that best describes this session's work
""",
}


# ============================================================================
# Blocking Functions
# ============================================================================


def block_no_checkpoint(cwd: str) -> None:
    """Block stop - no checkpoint file exists.

    Displays the checkpoint schema template and exits with code 2.

    Args:
        cwd: Working directory
    """
    checkpoint_path = (
        Path(cwd) / ".claude" / "completion-checkpoint.json"
        if cwd
        else ".claude/completion-checkpoint.json"
    )

    current_version = get_code_version(cwd)
    version_note = (
        f"// Current version: {current_version}" if current_version != "unknown" else ""
    )

    # Use GO-specific lightweight template when /go is active
    if is_go_active(cwd):
        schema = GO_CHECKPOINT_SCHEMA_TEMPLATE.format(version_note=version_note)
        print(
            f"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║  ❌ COMPLETION CHECKPOINT REQUIRED (/go)                                      ║
╚═══════════════════════════════════════════════════════════════════════════════╝

You must create {checkpoint_path} before stopping.

/go uses a lightweight 3+1 checkpoint:

{schema}

RULES:
- what_was_done must be >20 characters (describe what you did)
- what_remains must be empty ("none") to stop
- linters_pass only required if you changed code files (code_changes_made: true)

Create this file, answer honestly, then stop again.
""",
            file=sys.stderr,
        )
        sys.exit(2)

    schema = CHECKPOINT_SCHEMA_TEMPLATE.format(version_note=version_note)

    print(
        f"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║  ❌ COMPLETION CHECKPOINT REQUIRED                                            ║
╚═══════════════════════════════════════════════════════════════════════════════╝

You must create {checkpoint_path} before stopping.

This file requires HONEST self-reporting of what you've done:

{schema}
{VERSION_TRACKING_GUIDANCE}
If you answer "false" to required fields and try to stop, you'll be blocked.
The only way to stop is to actually do the work OR have a genuine blocker.

Create this file, answer honestly, then stop again.
""",
        file=sys.stderr,
    )
    sys.exit(2)


def block_with_continuation(failures: list[str], cwd: str = "") -> None:
    """Block stop with specific continuation instructions.

    Shows only guidance relevant to the actual failures (not all guidance).

    Args:
        failures: List of validation failure messages
        cwd: Working directory
    """
    failure_list = "\n".join(f"  • {f}" for f in failures)

    current_version = get_code_version(cwd)
    version_info = (
        f"Current version: {current_version}"
        if current_version != "unknown"
        else "Run: git rev-parse --short HEAD"
    )

    # Check for worktree context
    worktree_info = get_worktree_info(cwd)
    worktree_banner = ""
    if worktree_info and worktree_info.get("is_claude_worktree"):
        agent_id = worktree_info.get("agent_id", "unknown")
        branch = worktree_info.get("branch", "unknown")
        worktree_banner = f"""
┌─────────────────────────────────────────────────────────────────────────────┐
│  WORKTREE: {agent_id:<20} BRANCH: {branch:<30}│
└─────────────────────────────────────────────────────────────────────────────┘
"""

    # Build guidance section: only show blocks relevant to actual failures
    failure_text = " ".join(failures).lower()
    guidance_parts = []
    for keyword, block in GUIDANCE_BLOCKS.items():
        if keyword.lower() in failure_text:
            formatted = block.format(version_info=version_info) if "{version_info}" in block else block
            guidance_parts.append(formatted)

    guidance = "\n".join(guidance_parts) if guidance_parts else ""

    print(
        f"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║  ❌ COMPLETION CHECKPOINT FAILED - CONTINUE WORKING                           ║
╚═══════════════════════════════════════════════════════════════════════════════╝
{worktree_banner}
Your self-report indicates incomplete work:

{failure_list}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
REQUIRED ACTION: Complete the remaining work.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{guidance}
Update .claude/completion-checkpoint.json, then stop again.
""",
        file=sys.stderr,
    )
    sys.exit(2)
