#!/usr/bin/env python3
"""
Stop Validator - Validation functions for completion checkpoint.

This module contains all validation logic for the stop hook, broken into
composable sub-validators for maintainability.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
import sys

# Add hooks directory to path for sibling imports
sys.path.insert(0, str(Path(__file__).parent))

from _common import (
    get_code_version,
    get_fields_to_invalidate,
    save_checkpoint,
    is_appfix_active,
    is_autonomous_mode_active,
    VERSION_DEPENDENT_FIELDS,
)


# ============================================================================
# Git Utilities
# ============================================================================


def get_git_diff_files() -> list[str]:
    """Get list of modified files (staged + unstaged)."""
    try:
        staged = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        unstaged = subprocess.run(
            ["git", "diff", "--name-only"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        staged_files = [f for f in staged.stdout.strip().split("\n") if f]
        unstaged_files = [f for f in unstaged.stdout.strip().split("\n") if f]
        return list(set(staged_files + unstaged_files))
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def has_code_changes(files: list[str]) -> bool:
    """Check if any application code files were modified (not infrastructure/toolkit).

    Excludes:
    - Claude Code hooks, skills, commands (config/hooks/, config/skills/, config/commands/)
    - .claude/ directory files
    - Documentation and scripts in prompts/ directory
    """
    code_extensions = {
        ".py",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".go",
        ".rs",
        ".java",
        ".rb",
        ".php",
    }
    infrastructure_patterns = [
        "config/hooks/",
        "config/skills/",
        "config/commands/",
        ".claude/",
        "prompts/config/",
        "prompts/scripts/",
        "prompts/docs/",
        "scripts/",
        "docs/",
    ]
    for f in files:
        if any(pattern in f for pattern in infrastructure_patterns):
            continue
        ext = Path(f).suffix.lower()
        if ext in code_extensions:
            return True
    return False


def has_frontend_changes(files: list[str]) -> bool:
    """Check if any frontend files were modified."""
    frontend_patterns = [".tsx", ".jsx", "components/", "app/", "pages/"]
    hooks_pattern = "src/hooks/"

    for f in files:
        for pattern in frontend_patterns:
            if pattern in f or f.endswith(pattern.rstrip("/")):
                return True
        if hooks_pattern in f:
            return True
    return False


# ============================================================================
# Helper Functions
# ============================================================================


def load_web_smoke_waivers(cwd: str) -> dict:
    """Load waiver patterns for expected errors."""
    if not cwd:
        return {"console_patterns": [], "network_patterns": []}
    waivers_path = Path(cwd) / ".claude" / "web-smoke" / "waivers.json"
    if not waivers_path.exists():
        return {"console_patterns": [], "network_patterns": []}
    try:
        return json.loads(waivers_path.read_text())
    except (json.JSONDecodeError, IOError):
        return {"console_patterns": [], "network_patterns": []}


# ============================================================================
# Artifact Validators
# ============================================================================


def validate_web_smoke_artifacts(cwd: str) -> tuple[bool, list[str]]:
    """Check if web smoke artifacts exist and pass conditions.

    Returns (is_valid, list_of_errors)
    """
    errors = []
    artifact_dir = (
        Path(cwd) / ".claude" / "web-smoke" if cwd else Path(".claude/web-smoke")
    )
    summary_path = artifact_dir / "summary.json"
    screenshots_dir = artifact_dir / "screenshots"

    if not summary_path.exists():
        errors.append(
            "web_smoke: No summary.json found. Run Surf verification first:\n"
            "  python3 ~/.claude/hooks/surf-verify.py --urls 'https://your-app.com'\n"
            "Or use Chrome MCP and manually create .claude/web-smoke/summary.json"
        )
        return False, errors

    try:
        summary = json.loads(summary_path.read_text())
    except (json.JSONDecodeError, IOError) as e:
        errors.append(f"web_smoke: Cannot parse summary.json: {e}")
        return False, errors

    # Check version freshness
    current_version = get_code_version(cwd)
    tested_version = summary.get("tested_at_version", "")
    if (
        tested_version
        and current_version != "unknown"
        and tested_version != current_version
    ):
        errors.append(
            f"web_smoke: Artifacts are STALE - tested at version '{tested_version}', "
            f"but code is now at '{current_version}'. Code changed since verification.\n"
            f"Re-run: python3 ~/.claude/hooks/surf-verify.py --urls ..."
        )
        return False, errors

    # Check pass status
    if not summary.get("passed", False):
        console_errors = summary.get("console_errors", 0)
        network_errors = summary.get("network_errors", 0)
        failing_requests = summary.get("failing_requests", [])
        error_msg = f"web_smoke: Verification FAILED - {console_errors} console errors, {network_errors} network errors"
        if failing_requests:
            error_msg += f"\n  Failing requests: {failing_requests[:3]}"
            if len(failing_requests) > 3:
                error_msg += f" ... and {len(failing_requests) - 3} more"
        errors.append(error_msg)
        return False, errors

    # Check screenshots exist
    screenshot_count = summary.get("screenshot_count", 0)
    if screenshot_count < 1:
        actual_screenshots = (
            list(screenshots_dir.glob("*.png")) if screenshots_dir.exists() else []
        )
        if not actual_screenshots:
            errors.append(
                "web_smoke: No screenshots captured. At least 1 screenshot required.\n"
                "Screenshots prove the page actually loaded and rendered."
            )
            return False, errors

    # Check URLs were tested
    urls_tested = summary.get("urls_tested", [])
    if not urls_tested:
        errors.append(
            "web_smoke: urls_tested is empty. You must verify actual URLs.\n"
            "Add URLs to test in service-topology.md under web_smoke_urls"
        )
        return False, errors

    return True, []


def validate_deployment_artifacts(cwd: str) -> tuple[bool, list[str]]:
    """Check if deployment artifacts exist and pass conditions.

    Looks for .claude/deployment/summary.json produced by deploy-verify.py.

    Returns (is_valid, list_of_errors)
    """
    errors = []
    artifact_dir = (
        Path(cwd) / ".claude" / "deployment" if cwd else Path(".claude/deployment")
    )
    summary_path = artifact_dir / "summary.json"

    if not summary_path.exists():
        errors.append(
            "deployment: No summary.json found. Run deploy-verify.py after deployment:\n"
            "  python3 ~/.claude/hooks/deploy-verify.py --run-id <workflow-run-id>\n"
            "Or wait for gh run watch to complete and re-run verification."
        )
        return False, errors

    try:
        summary = json.loads(summary_path.read_text())
    except (json.JSONDecodeError, IOError) as e:
        errors.append(f"deployment: Cannot parse summary.json: {e}")
        return False, errors

    # Check version freshness - deployed version should match current code
    current_version = get_code_version(cwd)
    deployed_version = summary.get("deployed_version", "")
    if (
        deployed_version
        and current_version != "unknown"
        and deployed_version != current_version
    ):
        errors.append(
            f"deployment: Artifacts are STALE - deployed at version '{deployed_version}', "
            f"but code is now at '{current_version}'. Code changed since deployment.\n"
            "Re-deploy and re-verify."
        )
        return False, errors

    # Check pass status
    if not summary.get("passed", False):
        conclusion = summary.get("conclusion", "unknown")
        run_id = summary.get("run_id", "unknown")
        deploy_errors = summary.get("errors", [])
        error_msg = f"deployment: Workflow FAILED (conclusion: {conclusion}, run_id: {run_id})"
        if deploy_errors:
            error_msg += f"\n  Errors: {deploy_errors[:3]}"
            if len(deploy_errors) > 3:
                error_msg += f" ... and {len(deploy_errors) - 3} more"
        errors.append(error_msg)
        return False, errors

    # Check version_match flag if present
    if summary.get("version_match") is False:
        tested_version = summary.get("tested_at_version", "unknown")
        errors.append(
            f"deployment: Version match is false - deployed_version '{deployed_version}' "
            f"!= tested_at_version '{tested_version}'"
        )
        return False, errors

    return True, []


def validate_fix_specific_tests(cwd: str, checkpoint: dict) -> tuple[bool, list[str]]:
    """Validate that fix-specific validation tests were defined and passed.

    Only required for appfix mode with code changes.
    Returns (is_valid, list_of_errors)
    """
    errors = []

    # Only required for appfix mode
    if not is_appfix_active(cwd):
        return True, []

    validation_tests = checkpoint.get("validation_tests", {})
    tests = validation_tests.get("tests", [])

    artifact_dir = (
        Path(cwd) / ".claude" / "validation-tests"
        if cwd
        else Path(".claude/validation-tests")
    )
    summary_path = artifact_dir / "summary.json"

    # Check if code changes were made
    report = checkpoint.get("self_report", {})
    code_changes_made = report.get("code_changes_made", False)

    if not code_changes_made:
        return True, []  # Research/audit, validation tests optional

    # Code changes made - validation tests expected
    if not tests and not summary_path.exists():
        errors.append(
            "VALIDATION TESTS REQUIRED: You made code changes but didn't define fix-specific tests.\n"
            "These tests PROVE the fix worked, not just that the app loads.\n\n"
            "Ask yourself: 'What would PROVE this specific fix worked?'\n\n"
            "Example for 'notes summarization fix':\n"
            '  {"id": "notes_summary_populated", "type": "database_query", "expected": "NOT NULL"}\n\n'
            "Add tests to .claude/completion-checkpoint.json → validation_tests.tests"
        )
        return False, errors

    # Load artifact if exists
    if summary_path.exists():
        try:
            summary = json.loads(summary_path.read_text())
            tests = summary.get("tests", tests)
        except (json.JSONDecodeError, IOError):
            pass

    if not tests:
        errors.append("VALIDATION TESTS EMPTY: Tests array is empty.")
        return False, errors

    # Check for failed tests
    failed_tests = [t for t in tests if not t.get("passed", False)]
    if failed_tests:
        errors.append(
            f"VALIDATION TESTS FAILED: {len(failed_tests)} of {len(tests)} tests failed."
        )
        for test in failed_tests:
            test_desc = test.get("description", test.get("id", "unknown"))
            expected = test.get("expected", "?")
            actual = test.get("actual", "?")
            errors.append(
                f"  FAILED: {test_desc}\n    Expected: {expected}\n    Actual: {actual}"
            )
        return False, errors

    # Check version freshness
    if summary_path.exists():
        try:
            summary = json.loads(summary_path.read_text())
            tested_version = summary.get("tested_at_version", "")
            current_version = get_code_version(cwd)
            if (
                tested_version
                and current_version != "unknown"
                and tested_version != current_version
            ):
                errors.append(
                    f"VALIDATION TESTS STALE: Tested at version '{tested_version}', "
                    f"but code is now at '{current_version}'. Re-run validation tests."
                )
                return False, errors
        except (json.JSONDecodeError, IOError):
            pass

    return True, []


# ============================================================================
# Sub-validators
# ============================================================================


def validate_version_staleness(
    checkpoint: dict, cwd: str
) -> tuple[bool, list[str], set[str]]:
    """Detect stale version-dependent fields and cascade to dependents.

    Returns (checkpoint_modified, failures, fields_reset)
    """
    failures = []
    fields_to_reset = set()
    report = checkpoint.get("self_report", {})
    current_version = get_code_version(cwd)

    # Phase 1: Identify stale fields
    for field in VERSION_DEPENDENT_FIELDS:
        if report.get(field, False):
            field_version = report.get(f"{field}_at_version", "")
            if field_version and field_version != current_version:
                fields_to_reset.add(field)
                failures.append(
                    f"{field} is STALE - set at version '{field_version}', "
                    f"but code is now at '{current_version}'. Re-run and update."
                )
            elif not field_version and current_version != "unknown":
                fields_to_reset.add(field)
                failures.append(f"{field} is true but missing version tracking.")

    # Phase 2: Cascade to dependent fields
    cascade_fields = set()
    for stale_field in fields_to_reset:
        dependents = get_fields_to_invalidate(stale_field) - {stale_field}
        for dep in dependents:
            if report.get(dep, False) and dep not in fields_to_reset:
                cascade_fields.add(dep)
                failures.append(
                    f"{dep} CASCADE INVALIDATED - depends on {stale_field}."
                )

    fields_to_reset.update(cascade_fields)

    # Phase 3: Reset stale fields
    checkpoint_modified = False
    for field in fields_to_reset:
        if report.get(field, False):
            report[field] = False
            report[f"{field}_at_version"] = ""
            checkpoint_modified = True

    return checkpoint_modified, failures, fields_to_reset


def validate_core_completion(report: dict, reflection: dict) -> list[str]:
    """Check is_job_complete and what_remains."""
    failures = []

    if not report.get("is_job_complete", False):
        failures.append("is_job_complete is false - YOU said the job isn't done")

    what_remains = reflection.get("what_remains", "")
    if what_remains and what_remains.lower() not in ["none", "nothing", "n/a", ""]:
        failures.append(f"what_remains is not empty: '{what_remains}'")

    return failures


def validate_code_requirements(
    report: dict, has_app_code: bool, has_frontend: bool
) -> list[str]:
    """Check linters, deployed for app code changes."""
    failures = []

    # Trust session's self-report over git diff for multi-session scenarios.
    # Git diff is repo-global, but code_changes_made is session-specific.
    # Session B shouldn't be blocked by Session A's dirty git state.
    if not report.get("code_changes_made", False):
        return failures

    if not has_app_code:
        return failures

    if has_frontend and not report.get("web_testing_done", False):
        failures.append(
            "web_testing_done is false - frontend changes require browser testing"
        )

    if not report.get("deployed", False):
        failures.append(
            "deployed is false - you made application code changes but didn't deploy"
        )

    if not report.get("linters_pass", False):
        failures.append(
            "linters_pass is false - run linters and fix ALL errors (including pre-existing ones)"
        )

    return failures


def validate_web_testing(
    checkpoint: dict, has_app_code: bool, has_infra_changes: bool, cwd: str
) -> tuple[list[str], bool]:
    """Check web testing requirements for autonomous mode.

    In autonomous mode (appfix/godo), web smoke verification is MANDATORY
    when code changes are made. Backend-only changes are NOT exempt -
    they can still break the frontend.

    CRITICAL: If web_testing_done is claimed as TRUE, Surf artifacts MUST exist.
    This prevents bypassing validation by manually setting the boolean.

    Returns (failures, checkpoint_modified)
    """
    failures = []
    report = checkpoint.get("self_report", {})
    checkpoint_modified = False

    if not is_autonomous_mode_active(cwd):
        return failures, checkpoint_modified

    # Use both git detection AND self-reported code_changes_made
    # This prevents bypasses when git detection fails to catch changes
    code_changes_claimed = report.get("code_changes_made", False)
    any_code_changes = has_app_code or has_infra_changes or code_changes_claimed

    # CRITICAL CROSS-VALIDATION: If web_testing_done is claimed TRUE,
    # artifacts MUST exist regardless of detected code changes.
    # This prevents the bypass: "Backend-only change - no frontend UI to test"
    web_testing_claimed = report.get("web_testing_done", False)

    if web_testing_claimed:
        artifact_valid, artifact_errors = validate_web_smoke_artifacts(cwd)
        if not artifact_valid:
            # FALSE CLAIM DETECTED - reset the boolean
            failures.append(
                "web_testing_done is TRUE but no valid Surf artifacts exist.\n"
                "Cannot claim web testing done without proof. Auto-resetting to FALSE."
            )
            report["web_testing_done"] = False
            report["web_testing_done_at_version"] = ""
            checkpoint_modified = True

            failures.extend([f"  → {err}" for err in artifact_errors])

    # If no code changes at all, and we've handled any false claims above,
    # no further validation needed
    if not any_code_changes:
        return failures, checkpoint_modified

    # Infrastructure-only changes (hooks, skills, docs) don't require web smoke.
    # This is when code_changes_claimed is true but has_app_code is false -
    # meaning all changed files matched infrastructure patterns.
    if not has_app_code and not has_infra_changes:
        # Self-reported changes but no actual app code detected = infrastructure only
        return failures, checkpoint_modified

    # Code changes were made - artifact-based verification is MANDATORY
    artifact_valid, artifact_errors = validate_web_smoke_artifacts(cwd)

    if artifact_valid:
        # Auto-set web_testing_done from artifact evidence
        if not report.get("web_testing_done", False):
            report["web_testing_done"] = True
            report["web_testing_done_at_version"] = get_code_version(cwd)
            checkpoint_modified = True
    else:
        # CRITICAL: In autonomous mode, web smoke is NOT optional
        failures.append(
            "WEB SMOKE VERIFICATION REQUIRED (Autonomous Mode)\n"
            "Even backend-only changes can break the frontend.\n"
            "Run: python3 ~/.claude/hooks/surf-verify.py --urls 'https://your-app.com'"
        )
        # Only add artifact errors if not already added above (from cross-validation)
        if not web_testing_claimed:
            failures.extend([f"  → {err}" for err in artifact_errors])

    # Check URLs tested
    evidence = checkpoint.get("evidence", {})
    urls_tested = evidence.get("urls_tested", [])

    if report.get("web_testing_done", False) and not urls_tested:
        failures.append(
            "web_testing_done is true but evidence.urls_tested is empty."
        )

    return failures, checkpoint_modified


# ============================================================================
# Main Orchestrator
# ============================================================================


def validate_checkpoint(
    checkpoint: dict, modified_files: list[str], cwd: str = ""
) -> tuple[bool, list[str]]:
    """Validate checkpoint booleans deterministically.

    Orchestrates all sub-validators and auto-resets stale fields.
    Returns (is_valid, list_of_failures)
    """
    failures = []
    report = checkpoint.get("self_report", {})
    reflection = checkpoint.get("reflection", {})
    checkpoint_modified = False

    # 1. Version staleness (with auto-reset)
    stale_modified, stale_failures, _ = validate_version_staleness(checkpoint, cwd)
    failures.extend(stale_failures)
    if stale_modified:
        checkpoint_modified = True

    # 2. Core completion checks
    failures.extend(validate_core_completion(report, reflection))

    # 3. Code requirements (if app code changed)
    has_app_code = has_code_changes(modified_files)
    has_frontend = has_frontend_changes(modified_files)
    failures.extend(validate_code_requirements(report, has_app_code, has_frontend))

    # 4. Web testing requirements (autonomous mode)
    has_infra = report.get("az_cli_changes_made", False)
    web_failures, web_modified = validate_web_testing(
        checkpoint, has_app_code, has_infra, cwd
    )
    failures.extend(web_failures)
    if web_modified:
        checkpoint_modified = True

    # 5. Fix-specific tests (warning only, not blocking)
    tests_valid, test_warnings = validate_fix_specific_tests(cwd, checkpoint)
    if not tests_valid:
        for w in test_warnings:
            print(f"  ⚠ WARNING: {w}", file=sys.stderr)

    # Save modified checkpoint
    if checkpoint_modified:
        save_checkpoint(cwd, checkpoint)

    return len(failures) == 0, failures
