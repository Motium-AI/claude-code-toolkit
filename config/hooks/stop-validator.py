#!/usr/bin/env python3
"""
Global Stop Hook Validator - Deterministic Boolean Checkpoints

Two-phase stop flow with completion checkpoint validation:
1. First stop (stop_hook_active=false): Block + require checkpoint file
2. Second stop (stop_hook_active=true): Validate checkpoint booleans

The model MUST fill out .claude/completion-checkpoint.json with honest
boolean answers. The hook deterministically checks these booleans.

Exit codes:
  0 - Allow stop
  2 - Block stop (stderr shown to Claude)
"""
import hashlib
import json
import os
import sys
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

# Debug logging
DEBUG_LOG = Path(tempfile.gettempdir()) / "stop-hook-debug.log"

# Files/patterns excluded from version tracking (dirty calculation)
# These don't represent code changes requiring re-deployment
# IMPORTANT: Use both root and nested patterns for directories like .claude/
# because :(exclude).claude/ only matches at root, not nested paths
VERSION_TRACKING_EXCLUSIONS = [
    # Base path required for exclude patterns to work correctly
    ".",
    # .claude directory at any depth (checkpoint files, state files)
    ":(exclude).claude",
    ":(exclude).claude/*",
    ":(exclude)*/.claude",
    ":(exclude)*/.claude/*",
    # Lock files
    ":(exclude)*.lock",
    ":(exclude)package-lock.json",
    ":(exclude)yarn.lock",
    ":(exclude)pnpm-lock.yaml",
    ":(exclude)poetry.lock",
    ":(exclude)Pipfile.lock",
    ":(exclude)Cargo.lock",
    # Git metadata
    ":(exclude).gitmodules",
    # Python artifacts
    ":(exclude)*.pyc",
    ":(exclude)__pycache__",
    ":(exclude)*/__pycache__",
    # Environment and logs
    ":(exclude).env*",
    ":(exclude)*.log",
    # OS and editor artifacts
    ":(exclude).DS_Store",
    ":(exclude)*.swp",
    ":(exclude)*.swo",
    ":(exclude)*.orig",
    ":(exclude).idea",
    ":(exclude).idea/*",
    ":(exclude).vscode",
    ":(exclude).vscode/*",
]


def log_debug(message: str, raw_input: str = "", parsed_data: dict | None = None) -> None:
    """Log diagnostic info for debugging."""
    try:
        with open(DEBUG_LOG, "a") as f:
            f.write(f"\n{'='*60}\n")
            f.write(f"Timestamp: {datetime.now().isoformat()}\n")
            f.write(f"Message: {message}\n")
            if raw_input:
                f.write(f"Raw stdin ({len(raw_input)} bytes): {repr(raw_input)}\n")
            if parsed_data is not None:
                f.write(f"Parsed data: {json.dumps(parsed_data, indent=2)}\n")
            f.write(f"{'='*60}\n")
    except Exception:
        pass


def get_git_diff_files() -> list[str]:
    """Get list of modified files (staged + unstaged)."""
    try:
        staged = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True, text=True, timeout=5,
        )
        unstaged = subprocess.run(
            ["git", "diff", "--name-only"],
            capture_output=True, text=True, timeout=5,
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
    code_extensions = {'.py', '.ts', '.tsx', '.js', '.jsx', '.go', '.rs', '.java', '.rb', '.php'}
    # Infrastructure paths that don't require deployment
    # These are tooling, documentation utilities, not deployed application code
    infrastructure_patterns = [
        'config/hooks/',
        'config/skills/',
        'config/commands/',
        '.claude/',
        'prompts/config/',
        'prompts/scripts/',
        'scripts/',  # Documentation processing scripts
    ]
    for f in files:
        # Skip infrastructure/toolkit files
        if any(pattern in f for pattern in infrastructure_patterns):
            continue
        ext = Path(f).suffix.lower()
        if ext in code_extensions:
            return True
    return False


def has_frontend_changes(files: list[str]) -> bool:
    """Check if any frontend files were modified."""
    frontend_patterns = ['.tsx', '.jsx', 'components/', 'app/', 'pages/']
    # Hooks pattern needs special handling - only match src/hooks, not config/hooks
    hooks_pattern = 'src/hooks/'

    for f in files:
        for pattern in frontend_patterns:
            if pattern in f or f.endswith(pattern.rstrip('/')):
                return True
        # Check for React hooks specifically (src/hooks), not Claude Code hooks (config/hooks)
        if hooks_pattern in f:
            return True
    return False


def get_diff_hash(cwd: str = "") -> str:
    """
    Get hash of current git diff (excluding metadata files).

    Used to detect if THIS session made changes by comparing against
    the snapshot taken at session start.

    Excludes lock files, IDE config, and other non-code files that
    shouldn't affect version tracking.
    """
    try:
        result = subprocess.run(
            ["git", "diff", "HEAD", "--"] + VERSION_TRACKING_EXCLUSIONS,
            capture_output=True, text=True, timeout=5,
            cwd=cwd or None,
        )
        return hashlib.sha1(result.stdout.encode()).hexdigest()[:12]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return "unknown"


def get_code_version(cwd: str = "") -> str:
    """
    Get current code version (git HEAD + dirty state hash).

    Excludes metadata files (lock files, IDE config, .claude/, etc.) from
    dirty calculation. This prevents version-dependent checkpoint fields
    from becoming stale when only metadata changes (not actual code).

    Returns format:
    - "abc1234" - clean commit
    - "abc1234-dirty-def5678" - commit with uncommitted code changes
    - "unknown" - not a git repo
    """
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
            ["git", "diff", "HEAD", "--"] + VERSION_TRACKING_EXCLUSIONS,
            capture_output=True, text=True, timeout=5,
            cwd=cwd or None,
        )
        if diff.stdout:
            dirty_hash = hashlib.sha1(diff.stdout.encode()).hexdigest()[:7]
            return f"{head_hash}-dirty-{dirty_hash}"

        return head_hash
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return "unknown"


# Fields that are invalidated when code changes after they were set
# Ordered by dependency: upstream fields come first
VERSION_DEPENDENT_FIELDS = [
    "linters_pass",        # Must pass before deploy
    "deployed",            # Must deploy before testing
    "web_testing_done",    # Depends on deployed
    "console_errors_checked",  # Depends on deployed
    "api_testing_done",    # Depends on deployed
]

# Health endpoint URL patterns - these don't count as real app pages
HEALTH_URL_PATTERNS = [
    '/health', '/healthz', '/api/health', '/ping', '/ready', '/live',
    '/readiness', '/liveness', '/_health', '/status', '/api/status'
]


def has_real_app_urls(urls: list[str]) -> bool:
    """
    Check if any URLs are actual app pages (not just health endpoints).

    Health endpoints like /health, /ping don't prove the app works -
    they only prove the server is responding. Real verification requires
    testing actual user-facing pages like /dashboard, /login, etc.
    """
    if not urls:
        return False

    for url in urls:
        url_lower = url.lower()
        is_health = any(pattern in url_lower for pattern in HEALTH_URL_PATTERNS)
        if not is_health:
            return True
    return False

# Dependency graph: field -> list of fields it depends on
# If a dependency is stale, this field is also stale
FIELD_DEPENDENCIES = {
    "linters_pass": [],                          # Base field, only depends on code
    "deployed": ["linters_pass"],                # Can't deploy unlinted code
    "web_testing_done": ["deployed"],            # Can't test undeployed code
    "console_errors_checked": ["deployed"],      # Can't check console of undeployed code
    "api_testing_done": ["deployed"],            # Can't test APIs of undeployed code
}


def load_checkpoint(cwd: str) -> dict | None:
    """Load completion checkpoint file."""
    if not cwd:
        return None
    checkpoint_path = Path(cwd) / ".claude" / "completion-checkpoint.json"
    if not checkpoint_path.exists():
        return None
    try:
        return json.loads(checkpoint_path.read_text())
    except (json.JSONDecodeError, IOError):
        return None


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


def validate_web_smoke_artifacts(cwd: str) -> tuple[bool, list[str]]:
    """
    Check if web smoke artifacts exist and pass conditions.

    This provides ARTIFACT-BASED proof of web verification, replacing
    the trust-based web_testing_done: true boolean.

    Returns (is_valid, list_of_errors)
    """
    errors = []
    artifact_dir = Path(cwd) / ".claude" / "web-smoke" if cwd else Path(".claude/web-smoke")
    summary_path = artifact_dir / "summary.json"
    screenshots_dir = artifact_dir / "screenshots"

    # Check summary exists
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

    # Check version freshness (artifacts become stale when code changes)
    current_version = get_code_version(cwd)
    tested_version = summary.get("tested_at_version", "")
    if tested_version and current_version != "unknown" and tested_version != current_version:
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
            error_msg += f"\n  Failing requests: {failing_requests[:3]}"  # Show first 3
            if len(failing_requests) > 3:
                error_msg += f" ... and {len(failing_requests) - 3} more"
        errors.append(error_msg)
        return False, errors

    # Check screenshots exist
    screenshot_count = summary.get("screenshot_count", 0)
    if screenshot_count < 1:
        # Also check filesystem in case summary is outdated
        actual_screenshots = list(screenshots_dir.glob("*.png")) if screenshots_dir.exists() else []
        if not actual_screenshots:
            errors.append(
                "web_smoke: No screenshots captured. At least 1 screenshot required.\n"
                "Screenshots prove the page actually loaded and rendered."
            )
            return False, errors

    # Check URLs were actually tested
    urls_tested = summary.get("urls_tested", [])
    if not urls_tested:
        errors.append(
            "web_smoke: urls_tested is empty. You must verify actual URLs.\n"
            "Add URLs to test in service-topology.md under web_smoke_urls"
        )
        return False, errors

    return True, []


def save_checkpoint(cwd: str, checkpoint: dict) -> bool:
    """Save checkpoint file back to disk."""
    if not cwd:
        return False
    checkpoint_path = Path(cwd) / ".claude" / "completion-checkpoint.json"
    try:
        checkpoint_path.write_text(json.dumps(checkpoint, indent=2))
        return True
    except IOError:
        return False


def is_appfix_mode(cwd: str = "") -> bool:
    """
    Check if appfix mode is active.

    Checks user-level state first (~/.claude/appfix-state.json) to handle
    cross-repo scenarios where appfix was started in one repo but work
    is being done in another (e.g., Terraform infra repo).

    Falls back to project-level state for backward compatibility.
    """
    # User-level state takes precedence (cross-repo compatible)
    user_state = Path.home() / ".claude" / "appfix-state.json"
    if user_state.exists():
        return True

    # Fall back to project-level state (backward compatibility)
    if cwd:
        project_state = Path(cwd) / ".claude" / "appfix-state.json"
        if project_state.exists():
            return True

    return False


def is_godo_mode(cwd: str = "") -> bool:
    """
    Check if godo mode is active.

    Checks user-level state first (~/.claude/godo-state.json) to handle
    cross-repo scenarios.

    Falls back to project-level state for backward compatibility.
    """
    # User-level state takes precedence (cross-repo compatible)
    user_state = Path.home() / ".claude" / "godo-state.json"
    if user_state.exists():
        return True

    # Fall back to project-level state (backward compatibility)
    if cwd:
        project_state = Path(cwd) / ".claude" / "godo-state.json"
        if project_state.exists():
            return True

    return False


def is_autonomous_mode(cwd: str = "") -> bool:
    """
    Check if any autonomous execution mode is active (godo or appfix).

    This unified check determines if strict completion validation applies.
    """
    return is_godo_mode(cwd) or is_appfix_mode(cwd)


def get_dependent_fields(field: str) -> list[str]:
    """
    Get all fields that depend on a given field (transitively).
    If field X is stale, all fields that depend on X are also stale.
    """
    dependents = []
    for f, deps in FIELD_DEPENDENCIES.items():
        if field in deps:
            dependents.append(f)
            # Recursively get fields that depend on this dependent
            dependents.extend(get_dependent_fields(f))
    return list(set(dependents))


def validate_checkpoint(checkpoint: dict, modified_files: list[str], cwd: str = "") -> tuple[bool, list[str]]:
    """
    Validate checkpoint booleans deterministically.

    Auto-resets stale version-dependent fields and cascades to dependents.
    Writes checkpoint back to disk after modifications.

    Returns (is_valid, list_of_failures)
    """
    failures = []
    report = checkpoint.get("self_report", {})
    reflection = checkpoint.get("reflection", {})
    checkpoint_modified = False  # Track if we need to save
    fields_to_reset = set()  # Track all fields that need resetting

    # Phase 1: Identify stale fields based on version mismatch
    current_version = get_code_version(cwd)
    for field in VERSION_DEPENDENT_FIELDS:
        if report.get(field, False):
            field_version = report.get(f"{field}_at_version", "")
            if field_version and field_version != current_version:
                fields_to_reset.add(field)
                failures.append(
                    f"{field} is STALE - set at version '{field_version}', "
                    f"but code is now at '{current_version}'. Code changed since this checkpoint was set. Re-run and update."
                )
            elif not field_version and current_version != "unknown":
                fields_to_reset.add(field)
                failures.append(
                    f"{field} is true but missing version tracking - "
                    f"Re-do and include {field}_at_version."
                )

    # Phase 2: Cascade to dependent fields
    # If linters_pass is stale, deployed is also stale (can't deploy unlinted code)
    # If deployed is stale, web_testing_done is also stale (can't test undeployed code)
    cascade_fields = set()
    for stale_field in fields_to_reset:
        dependents = get_dependent_fields(stale_field)
        for dep in dependents:
            if report.get(dep, False) and dep not in fields_to_reset:
                cascade_fields.add(dep)
                failures.append(
                    f"{dep} CASCADE INVALIDATED - depends on {stale_field} which is stale. "
                    f"Re-do after fixing upstream."
                )

    fields_to_reset.update(cascade_fields)

    # Phase 3: Reset all identified stale fields
    for field in fields_to_reset:
        if report.get(field, False):
            report[field] = False
            report[f"{field}_at_version"] = ""
            checkpoint_modified = True

    # Save modified checkpoint back to disk
    if checkpoint_modified:
        save_checkpoint(cwd, checkpoint)

    # Check: is_job_complete must be true
    if not report.get("is_job_complete", False):
        failures.append("is_job_complete is false - YOU said the job isn't done")

    # Check for actual APPLICATION code changes (not infrastructure/toolkit)
    # This determines if deployment, linting, and web testing are required
    has_app_code = has_code_changes(modified_files)
    has_frontend = has_frontend_changes(modified_files)

    # Only require web_testing, deployment, linting if APPLICATION code was changed
    # Infrastructure/toolkit changes (hooks, skills, scripts) don't require these
    if has_app_code:
        # Check: web_testing_done required if frontend changes
        if has_frontend and not report.get("web_testing_done", False):
            failures.append("web_testing_done is false - frontend changes require browser testing")

        # Check: if app code changes made, should be deployed
        if not report.get("deployed", False):
            failures.append("deployed is false - you made application code changes but didn't deploy")

        # Check: console_errors_checked should be true if frontend changes
        if has_frontend and not report.get("console_errors_checked", False):
            failures.append("console_errors_checked is false - check browser console for errors")

        # Check: linters_pass required if app code was changed
        if not report.get("linters_pass", False):
            failures.append(
                "linters_pass is false - run linters and fix ALL errors (including pre-existing ones). "
                "You cannot claim 'these errors aren't related to our code' - fix them ALL"
            )

        # Check: preexisting_issues_fixed - no excuses allowed
        if report.get("linters_pass", False) and not report.get("preexisting_issues_fixed", True):
            # Only check if linters_pass is claimed but preexisting marked false
            failures.append(
                "preexisting_issues_fixed is false - you acknowledged pre-existing issues but didn't fix them. "
                "POLICY: Fix ALL linter errors, no exceptions. 'Not my code' is not an excuse."
            )

    # Check: docs_read_at_start required for appfix mode (not godo - that's appfix-specific)
    if is_appfix_mode(cwd):
        if not report.get("docs_read_at_start", False):
            failures.append(
                "docs_read_at_start is false - you must read docs/index.md and TECHNICAL_OVERVIEW.md "
                "before starting appfix work"
            )

    # Check: In autonomous mode (godo or appfix), browser verification is ALWAYS required
    # (regardless of code_changes_made - all changes need verification)
    if is_autonomous_mode(cwd):
        # Artifact-based verification is MANDATORY - booleans alone are NOT sufficient
        # Check for Surf CLI artifacts in .claude/web-smoke/
        artifact_valid, artifact_errors = validate_web_smoke_artifacts(cwd)

        if artifact_valid:
            # Artifacts exist and pass - this is sufficient proof
            # Auto-set the boolean fields for backward compatibility
            if not report.get("web_testing_done", False):
                report["web_testing_done"] = True
                report["web_testing_done_at_version"] = get_code_version(cwd)
                checkpoint_modified = True
            if not report.get("console_errors_checked", False):
                report["console_errors_checked"] = True
                report["console_errors_checked_at_version"] = get_code_version(cwd)
                checkpoint_modified = True
        else:
            # NO FALLBACK - artifacts are REQUIRED in autonomous mode
            # Block REGARDLESS of boolean values - setting web_testing_done: true
            # without actual proof is NOT allowed
            failures.append(
                "web_testing_done requires PROOF via Surf CLI artifacts.\n"
                "Setting the boolean to true without artifacts is NOT allowed.\n"
                "Run: python3 ~/.claude/hooks/surf-verify.py --urls 'https://your-app.com'\n"
                "Or use Chrome MCP and manually create .claude/web-smoke/summary.json with passing results."
            )
            # Add artifact error details
            for err in artifact_errors:
                failures.append(f"  → {err}")

            # Also fail console_errors_checked since artifacts would have validated this
            if report.get("console_errors_checked", False):
                failures.append(
                    "console_errors_checked is true but no Surf artifacts exist.\n"
                    "Artifacts provide deterministic proof of console check. Run Surf CLI."
                )
            else:
                failures.append(
                    "console_errors_checked is false - appfix requires checking browser "
                    "console for errors. Run Surf CLI for deterministic proof."
                )

        # Check: urls_tested must contain REAL app pages, not just health endpoints
        evidence = checkpoint.get("evidence", {})
        urls_tested = evidence.get("urls_tested", [])

        if report.get("web_testing_done", False):
            if not urls_tested:
                failures.append(
                    "web_testing_done is true but evidence.urls_tested is empty.\n"
                    "You must actually navigate to the app and record the URLs tested.\n"
                    "Run Surf CLI which automatically tracks URLs tested."
                )
            elif not has_real_app_urls(urls_tested):
                failures.append(
                    "urls_tested contains ONLY health endpoints, not actual app pages.\n"
                    f"URLs found: {urls_tested}\n"
                    "Health endpoints (/health, /ping, etc.) don't prove the app works.\n"
                    "You MUST verify real user-facing pages like /dashboard, /login, /profile, etc.\n"
                    "Run: python3 ~/.claude/hooks/surf-verify.py --urls 'https://your-app.com/dashboard'"
                )

    # Check: infra PR required if az CLI changes were made
    if report.get("az_cli_changes_made", False):
        if not report.get("infra_pr_created", False):
            failures.append(
                "infra_pr_created is false - you made infrastructure changes with az CLI but didn't "
                "create a PR to the infra repo. Sync your changes with IaC files."
            )

    # Check: what_remains should be empty or "none"
    what_remains = reflection.get("what_remains", "")
    if what_remains and what_remains.lower() not in ["none", "nothing", "n/a", ""]:
        failures.append(f"what_remains is not empty: '{what_remains}'")

    return len(failures) == 0, failures


def block_no_checkpoint(cwd: str) -> None:
    """Block stop - no checkpoint file exists."""
    checkpoint_path = Path(cwd) / ".claude" / "completion-checkpoint.json" if cwd else ".claude/completion-checkpoint.json"

    # Get current version for display
    current_version = get_code_version(cwd)
    version_note = f"// Current version: {current_version}" if current_version != "unknown" else ""

    print(f"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║  ❌ COMPLETION CHECKPOINT REQUIRED                                            ║
╚═══════════════════════════════════════════════════════════════════════════════╝

You must create {checkpoint_path} before stopping.

This file requires HONEST self-reporting of what you've done:

{{
  "self_report": {{
    "code_changes_made": true,              // Did you modify any code files?
    "web_testing_done": false,              // Did you verify in browser/Surf?
    "web_testing_done_at_version": "",      // Version when web testing was done {version_note}
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
    "is_job_complete": false                // Is the job ACTUALLY done?
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
}}

VERSION TRACKING:
- Version-dependent fields (deployed, linters_pass, web_testing_done, etc.)
  must include a matching *_at_version field with the git commit hash
- If you make code changes AFTER setting a checkpoint, it becomes STALE
- Get current version: git rev-parse --short HEAD

DOCUMENTATION REQUIREMENTS (docs_updated):
- docs/TECHNICAL_OVERVIEW.md - Update for architectural changes
- Module docs in docs/ directory - Update for feature changes
- .claude/skills/*/references/ - Update service topology, patterns
- .claude/MEMORIES.md - Significant learnings only (not changelog)

If you answer "false" to required fields and try to stop, you'll be blocked.
The only way to stop is to actually do the work OR have a genuine blocker.

Create this file, answer honestly, then stop again.
""", file=sys.stderr)
    sys.exit(2)


def block_with_continuation(failures: list[str], cwd: str = "") -> None:
    """Block stop with specific continuation instructions."""
    failure_list = "\n".join(f"  • {f}" for f in failures)

    # Get current version for guidance
    current_version = get_code_version(cwd)
    version_info = f"Current version: {current_version}" if current_version != "unknown" else "Run: git rev-parse --short HEAD"

    print(f"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║  ❌ COMPLETION CHECKPOINT FAILED - CONTINUE WORKING                           ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Your self-report indicates incomplete work:

{failure_list}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
REQUIRED ACTION: Complete the remaining work.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

If a checkpoint is marked "STALE":
  → The code changed since that checkpoint was set
  → Re-run that step (deploy, test, lint, etc.) with the current code
  → {version_info}
  → Update checkpoint: "field": true, "field_at_version": "<version>"

If web_testing_done is false:
  → Run /webtest or use Chrome MCP to verify in browser
  → Check browser console for errors
  → Update checkpoint with results and version

If deployed is false (and code was changed):
  → Commit and push: git add <files> && git commit -m "fix: ..." && git push
  → Deploy: gh workflow run deploy.yml && gh run watch --exit-status
  → Update checkpoint: deployed: true, deployed_at_version: "<version>"

If linters_pass is false:
  → Auto-detect linters: package.json → npm run lint / eslint
                         pyproject.toml → ruff check --fix
                         tsconfig.json → tsc --noEmit
  → Fix ALL errors - including pre-existing ones
  → "These errors aren't related to our code" is NOT acceptable
  → Update checkpoint: linters_pass: true, linters_pass_at_version: "<version>"

If docs_read_at_start is false (appfix mode):
  → Read docs/index.md and docs/TECHNICAL_OVERVIEW.md
  → Update checkpoint: docs_read_at_start: true

If infra_pr_created is false (but az_cli_changes_made is true):
  → Document az CLI changes in .claude/infra-changes.md
  → Clone infra repo (see service-topology.md for location)
  → Update Terraform/Bicep/ARM templates to match
  → Create PR: gh pr create --title "Sync infra changes from appfix"
  → Update checkpoint: infra_pr_created: true

If is_job_complete is false:
  → You honestly answered that the job isn't done
  → Complete the remaining work, then update checkpoint

If what_remains is not empty:
  → You listed remaining work: do it!

Update .claude/completion-checkpoint.json, then stop again.
""", file=sys.stderr)
    sys.exit(2)


def session_made_code_changes(cwd: str) -> bool:
    """
    Check if THIS session made code changes (not pre-existing changes).

    Compares the current diff hash against the snapshot taken at session start.
    This prevents research-only sessions from being blocked by pre-existing
    uncommitted changes from previous sessions.

    Falls back to git diff check if no snapshot exists (old session format).
    """
    snapshot_path = Path(cwd) / ".claude" / "session-snapshot.json"
    if not snapshot_path.exists():
        # No snapshot = old session format, fall back to git diff check
        return has_code_changes(get_git_diff_files())

    try:
        snapshot = json.loads(snapshot_path.read_text())
        start_hash = snapshot.get("diff_hash_at_start", "")
    except (json.JSONDecodeError, IOError):
        return has_code_changes(get_git_diff_files())

    if not start_hash or start_hash == "unknown":
        # Invalid snapshot, fall back to git diff check
        return has_code_changes(get_git_diff_files())

    current_hash = get_diff_hash(cwd)
    if current_hash == "unknown":
        # Can't determine current state, fall back to git diff check
        return has_code_changes(get_git_diff_files())

    # True if diff changed during this session
    return start_hash != current_hash


def requires_checkpoint(cwd: str, modified_files: list[str]) -> bool:
    """
    Determine if this session requires a completion checkpoint.

    Checkpoint required when:
    - Autonomous mode is active (godo-state.json or appfix-state.json exists)
    - THIS SESSION made code changes (diff hash changed since session start)
    - A plan file exists for this project

    Checkpoint skipped for:
    - Research/exploration sessions (no code changes in THIS session)
    - Sessions with only pre-existing uncommitted changes from previous sessions
    - Simple file reads, documentation queries
    """
    # CRITICAL: If autonomous mode active (godo or appfix), checkpoint is ALWAYS required
    # This ensures all changes are validated before stopping
    if is_autonomous_mode(cwd):
        return True

    # Check if THIS SESSION made code changes (not pre-existing changes)
    # This is the key fix: don't block sessions that inherited uncommitted changes
    if session_made_code_changes(cwd):
        return True

    # If plan file exists in ~/.claude/plans/, checkpoint required
    plans_dir = Path.home() / ".claude" / "plans"
    if plans_dir.exists() and list(plans_dir.glob("*.md")):
        # Check if any plan matches current project
        cwd_path = str(Path(cwd).resolve()) if cwd else ""
        for plan_file in plans_dir.glob("*.md"):
            try:
                content = plan_file.read_text()
                if cwd_path and cwd_path in content:
                    return True
            except IOError:
                continue

    return False


def main():
    # Skip for automation roles
    fleet_role = os.environ.get("FLEET_ROLE", "")
    if fleet_role in ("knowledge_sync", "scheduled_job"):
        log_debug("Skipping: automation role", parsed_data={"fleet_role": fleet_role})
        sys.exit(0)

    # Read and parse stdin
    raw_input = sys.stdin.read()
    log_debug("Stop hook invoked", raw_input=raw_input)

    try:
        input_data = json.loads(raw_input) if raw_input else {}
    except json.JSONDecodeError as e:
        log_debug(f"JSON parse error: {e}", raw_input=raw_input)
        sys.exit(0)

    log_debug("Parsed successfully", parsed_data=input_data)

    cwd = input_data.get("cwd", "")
    stop_hook_active = input_data.get("stop_hook_active", False)

    # Get modified files
    modified_files = get_git_diff_files()

    # Check if checkpoint is required for this session
    if not requires_checkpoint(cwd, modified_files):
        log_debug("ALLOWING STOP: no checkpoint required (no code changes, no active plan)")
        sys.exit(0)

    # Load checkpoint
    checkpoint = load_checkpoint(cwd)

    # =========================================================================
    # FIRST STOP: Require checkpoint file
    # =========================================================================
    if not stop_hook_active:
        if checkpoint is None:
            log_debug("BLOCKING STOP: checkpoint file missing")
            block_no_checkpoint(cwd)

        # Checkpoint exists but first stop - validate and block with checklist
        is_valid, failures = validate_checkpoint(checkpoint, modified_files, cwd)
        if not is_valid:
            log_debug("BLOCKING STOP: checkpoint validation failed", parsed_data={"failures": failures})
            block_with_continuation(failures, cwd)

        # Checkpoint valid - allow stop on first try if everything is complete
        log_debug("ALLOWING STOP: checkpoint valid on first stop")
        sys.exit(0)

    # =========================================================================
    # SECOND STOP (stop_hook_active=True): Re-validate checkpoint
    # =========================================================================
    if checkpoint is None:
        log_debug("BLOCKING STOP: second stop but checkpoint file still missing")
        block_no_checkpoint(cwd)

    is_valid, failures = validate_checkpoint(checkpoint, modified_files, cwd)
    if not is_valid:
        log_debug("BLOCKING STOP: second stop but checkpoint still invalid", parsed_data={"failures": failures})
        block_with_continuation(failures, cwd)

    # All checks pass
    log_debug("ALLOWING STOP: checkpoint valid", parsed_data={"checkpoint": checkpoint})
    sys.exit(0)


if __name__ == "__main__":
    main()
