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


# ============================================================================
# Template Constants
# ============================================================================

CHECKPOINT_SCHEMA_TEMPLATE = '''{version_note}
{{
  "self_report": {{
    "code_changes_made": true,              // Did you modify any code files?
    "web_testing_done": false,              // Did you verify in browser/Surf?
    "web_testing_done_at_version": "",      // Version when web testing was done
    "api_testing_done": false,              // Did you test API endpoints?
    "api_testing_done_at_version": "",      // Version when API testing was done
    "deployed": false,                      // Did you deploy the changes?
    "deployed_at_version": "",              // Version when deployed
    "console_errors_checked": false,        // Did you check browser console?
    "console_errors_checked_at_version": "",// Version when console was checked
    "linters_pass": false,                  // Did all linters pass with zero errors?
    "linters_pass_at_version": "",          // Version when linters passed
    "docs_updated": false,                  // Did you update relevant docs?
    "docs_read_at_start": false,            // Did you read project docs first? (appfix)
    "preexisting_issues_fixed": true,       // Did you fix ALL issues (no "not my code")?
    "az_cli_changes_made": false,           // Did you run az CLI infrastructure commands?
    "infra_pr_created": false,              // Did you create PR to infra repo? (if az CLI used)
    "validation_tests_defined": false,      // Did you define fix-specific tests? (if code changed)
    "validation_tests_passed": false,       // Did ALL validation tests pass?
    "validation_tests_passed_at_version": "",// Version when validation tests passed
    "is_job_complete": false                // Is the job ACTUALLY done?
  }},
  "validation_tests": {{                    // Fix-specific tests (REQUIRED if code changed)
    "tests": [
      {{
        "id": "example_test",
        "description": "What would PROVE this fix worked?",
        "type": "database_query|api_response|page_content",
        "expected": "NOT NULL|status=200|CONTAINS text",
        "actual": "",                       // Fill after executing
        "passed": false
      }}
    ],
    "summary": {{
      "total": 1,
      "passed": 0,
      "failed": 1,
      "last_run_version": ""
    }}
  }},
  "reflection": {{
    "what_was_done": "...",                 // Honest summary of work completed
    "what_remains": "none",                 // Must be empty to allow stop
    "blockers": null                        // Any genuine blockers
  }},
  "evidence": {{
    "urls_tested": [],                      // URLs you actually tested
    "console_clean": false                  // Was browser console clean?
  }}
}}'''

VERSION_TRACKING_GUIDANCE = """
VERSION TRACKING:
- Version-dependent fields (deployed, linters_pass, web_testing_done, etc.)
  must include a matching *_at_version field with the git commit hash
- If you make code changes AFTER setting a checkpoint, it becomes STALE
- Get current version: git rev-parse --short HEAD
"""

DOCUMENTATION_GUIDANCE = """
DOCUMENTATION REQUIREMENTS (docs_updated):
- docs/TECHNICAL_OVERVIEW.md - Update for architectural changes
- Module docs in docs/ directory - Update for feature changes
- .claude/skills/*/references/ - Update service topology, patterns
- .claude/MEMORIES.md - Significant learnings only (not changelog)
"""

CONTINUATION_STALE_GUIDANCE = """
If a checkpoint is marked "STALE":
  → The code changed since that checkpoint was set
  → Re-run that step (deploy, test, lint, etc.) with the current code
  → {version_info}
  → Update checkpoint: "field": true, "field_at_version": "<version>"
"""

CONTINUATION_WEB_TESTING_GUIDANCE = """
If web_testing_done is false:
  → Run /webtest or use Chrome MCP to verify in browser
  → Check browser console for errors
  → Update checkpoint with results and version
"""

CONTINUATION_DEPLOYED_GUIDANCE = """
If deployed is false (and code was changed):
  → Commit and push: git add <files> && git commit -m "fix: ..." && git push
  → Deploy: gh workflow run deploy.yml && gh run watch --exit-status
  → Update checkpoint: deployed: true, deployed_at_version: "<version>"
"""

CONTINUATION_LINTERS_GUIDANCE = """
If linters_pass is false:
  → Auto-detect linters: package.json → npm run lint / eslint
                         pyproject.toml → ruff check --fix
                         tsconfig.json → tsc --noEmit
  → Fix ALL errors - including pre-existing ones
  → "These errors aren't related to our code" is NOT acceptable
  → Update checkpoint: linters_pass: true, linters_pass_at_version: "<version>"
"""

CONTINUATION_DOCS_GUIDANCE = """
If docs_read_at_start is false (appfix mode):
  → Read docs/index.md and docs/TECHNICAL_OVERVIEW.md
  → Update checkpoint: docs_read_at_start: true
"""

CONTINUATION_INFRA_GUIDANCE = """
If infra_pr_created is false (but az_cli_changes_made is true):
  → Document az CLI changes in .claude/infra-changes.md
  → Clone infra repo (see service-topology.md for location)
  → Update Terraform/Bicep/ARM templates to match
  → Create PR: gh pr create --title "Sync infra changes from appfix"
  → Update checkpoint: infra_pr_created: true
"""

CONTINUATION_VALIDATION_TESTS_GUIDANCE = """
If validation_tests_defined is false (and you made code changes):
  → Ask: "What would PROVE this specific fix worked?"
  → Define tests in checkpoint → validation_tests.tests array
  → Test types: database_query, api_response, page_content
  → Each test needs: id, description, type, expected

If validation_tests_passed is false:
  → Execute each test and record actual results
  → If tests FAIL → The fix didn't work! Fix the root cause.
  → Re-run tests until ALL pass
  → Save artifacts to .claude/validation-tests/summary.json
  → Update checkpoint: validation_tests_passed: true, version
"""

CONTINUATION_COMPLETION_GUIDANCE = """
If is_job_complete is false:
  → You honestly answered that the job isn't done
  → Complete the remaining work, then update checkpoint

If what_remains is not empty:
  → You listed remaining work: do it!
"""


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
        if cwd else ".claude/completion-checkpoint.json"
    )

    current_version = get_code_version(cwd)
    version_note = (
        f"// Current version: {current_version}"
        if current_version != "unknown" else ""
    )

    schema = CHECKPOINT_SCHEMA_TEMPLATE.format(version_note=version_note)

    print(f"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║  ❌ COMPLETION CHECKPOINT REQUIRED                                            ║
╚═══════════════════════════════════════════════════════════════════════════════╝

You must create {checkpoint_path} before stopping.

This file requires HONEST self-reporting of what you've done:

{schema}
{VERSION_TRACKING_GUIDANCE}
{DOCUMENTATION_GUIDANCE}
If you answer "false" to required fields and try to stop, you'll be blocked.
The only way to stop is to actually do the work OR have a genuine blocker.

Create this file, answer honestly, then stop again.
""", file=sys.stderr)
    sys.exit(2)


def block_with_continuation(failures: list[str], cwd: str = "") -> None:
    """Block stop with specific continuation instructions.

    Displays failure list and guidance for resolving each issue type.

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
        agent_id = worktree_info.get('agent_id', 'unknown')
        branch = worktree_info.get('branch', 'unknown')
        worktree_banner = f"""
┌─────────────────────────────────────────────────────────────────────────────┐
│  WORKTREE: {agent_id:<20} BRANCH: {branch:<30}│
└─────────────────────────────────────────────────────────────────────────────┘
"""

    stale_guidance = CONTINUATION_STALE_GUIDANCE.format(version_info=version_info)

    print(f"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║  ❌ COMPLETION CHECKPOINT FAILED - CONTINUE WORKING                           ║
╚═══════════════════════════════════════════════════════════════════════════════╝
{worktree_banner}
Your self-report indicates incomplete work:

{failure_list}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
REQUIRED ACTION: Complete the remaining work.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{stale_guidance}{CONTINUATION_WEB_TESTING_GUIDANCE}{CONTINUATION_DEPLOYED_GUIDANCE}{CONTINUATION_LINTERS_GUIDANCE}{CONTINUATION_DOCS_GUIDANCE}{CONTINUATION_INFRA_GUIDANCE}{CONTINUATION_VALIDATION_TESTS_GUIDANCE}{CONTINUATION_COMPLETION_GUIDANCE}
Update .claude/completion-checkpoint.json, then stop again.
""", file=sys.stderr)
    sys.exit(2)
