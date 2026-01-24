#!/usr/bin/env python3
"""
Global Stop Hook Validator

Two-phase stop flow:
1. First stop (stop_hook_active=false): Show FULL compliance checklist, block
2. Second stop (stop_hook_active=true): Allow stop (loop prevention)

Detects change types from git diff and shows relevant testing requirements.

Exit codes:
  0 - Allow stop
  2 - Block stop (stderr shown to Claude)

Note: Status file hooks were removed in January 2025. Anthropic's native Tasks
feature now provides better session tracking and coordination.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

# Debug logging - helps diagnose Claude Code bug where stop hooks fail silently
DEBUG_LOG = Path(tempfile.gettempdir()) / "stop-hook-debug.log"


def log_debug(message: str, raw_input: str = "", parsed_data: dict | None = None) -> None:
    """
    Log diagnostic info to help debug Claude Code stop hook issues.

    Per GitHub Issue #17805, Claude Code 2.1.x has a bug where stop hooks
    fail silently. This logging captures what we actually receive.
    """
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
    except Exception as e:
        # Don't let logging failures break the hook
        pass


def write_checklist_file(cwd: str, checklist: str) -> Path:
    """Write full checklist to .claude/compliance-checklist.md"""
    checklist_path = Path(cwd) / ".claude" / "compliance-checklist.md"
    checklist_path.parent.mkdir(exist_ok=True)
    checklist_path.write_text(checklist)
    return checklist_path

# Plan file patterns for detecting deployment requirements
PLAN_DEPLOY_PATTERNS = [
    # Explicit deploy phrases
    "deploy to", "deploy the", "run deploy", "execute deploy",
    "push to azure", "deploy changes", "release to",
    # Script-based deployment
    "deploy.sh", "deploy.py", "deploy script",
    "./scripts/deploy", "scripts/deploy",
    # Action words with deploy
    "redeploy", "re-deploy",
    # Common deploy commands
    "npm run deploy", "yarn deploy", "pnpm deploy",
    "make deploy", "kubectl apply", "terraform apply",
    "az deployment", "aws deploy", "gcloud deploy",
    # CI/CD triggers
    "trigger deploy", "start deploy", "initiate deploy",
]
PLAN_TEST_PATTERNS = [
    "/webtest", "test in browser", "verify in browser",
    "test the changes", "browser test", "e2e test"
]

# Regex patterns for deployment detection (more flexible)
PLAN_DEPLOY_REGEX = [
    r"deploy\s+to\s+\w+",        # "deploy to staging", "deploy to prod"
    r"--env[=\s]*(staging|prod|production)",  # "--env=staging", "--env prod"
    r"deploy\.(sh|py|ts|js)",    # script files
    r"scripts?/deploy",          # scripts/deploy or script/deploy
]

# Patterns that only apply to specific file types (reduces false positives)
# If not listed here, pattern applies to all files
PYTHON_ONLY_PATTERNS = {"orm_boundary", "database", "datetime_boundary", "serialization_boundary"}
JS_TS_ONLY_PATTERNS = {"link", "websocket"}  # React/Next.js patterns

# Files/directories to exclude from pattern matching (contain pattern strings as literals)
EXCLUDED_PATHS = {
    "hooks/",
    ".claude/",
    "node_modules/",
    "__pycache__/",
}

# Patterns that indicate architectural changes requiring TECHNICAL_OVERVIEW.md update
ARCHITECTURAL_CHANGE_PATTERNS = [
    r"class\s+\w+Service",      # New service classes
    r"class\s+\w+Router",       # New routers
    r"class\s+\w+Handler",      # New handlers
    r"@app\.(get|post|put|delete|patch)\s*\(['\"]\/(?!api)",  # New root routes
    r"def\s+main\s*\(",         # New entry points
    r"index_patterns",          # Elasticsearch template changes
    r"pauwels_\w+\.json",       # Entity template changes
    r"mappings.*properties",    # Schema changes
    r"APIRouter\s*\(",          # New API routers
]

# Change type patterns and their testing requirements
CHANGE_PATTERNS: dict[str, dict] = {
    "env_var": {
        "patterns": [
            r"NEXT_PUBLIC_",
            r"process\.env\.",
            r"\.env",
            r"os\.environ",
            r"os\.getenv",
        ],
        "name": "ENV VAR CHANGES",
        "tests": [
            "Grep for fallback patterns: || 'http://localhost'",
            "Test with production config: NEXT_PUBLIC_API_BASE='' npm run dev",
            "Check Network tab for any localhost requests",
            "Run /config-audit for deeper analysis",
        ],
    },
    "auth": {
        "patterns": [
            r"clearToken",
            r"removeToken",
            r"deleteToken",
            r"logout",
            r"signOut",
            r"useAuth",
            r"AuthContext",
            r"token.*clear",
            r"session.*destroy",
        ],
        "name": "AUTH CHANGES",
        "tests": [
            "Trace all paths to token clearing functions",
            "Test auth cascade: what happens on 401 response?",
            "Verify network failures don't incorrectly clear auth state",
            "Test login/logout flow end-to-end",
        ],
    },
    "link": {
        "patterns": [
            r"<Link",
            r'href="/',
            r"href='/'",
            r"router\.push",
            r"router\.replace",
            r"navigate\(",
            r"useNavigate",
        ],
        "name": "LINK/ROUTE CHANGES",
        "tests": [
            "Run: python tools/validate_links.py <frontend_dir>",
            "Verify target routes exist in app/ directory",
            "Test navigation in browser",
        ],
    },
    "api_route": {
        "patterns": [
            r"@app\.(get|post|put|delete|patch)",
            r"@router\.(get|post|put|delete|patch)",
            r"APIRouter",
            r"app/api/.*route",
            r"FastAPI",
        ],
        "name": "API ROUTE CHANGES",
        "tests": [
            "Test through proxy (not direct localhost)",
            "Check for 307 trailing slash redirects",
            "Verify Authorization headers survive redirects",
            "Test with curl through actual endpoint",
        ],
    },
    "websocket": {
        "patterns": [
            r"WebSocket",
            r"wss://",
            r"ws://",
            r"useWebSocket",
            r"socket\.on",
            r"socket\.emit",
        ],
        "name": "WEBSOCKET CHANGES",
        "tests": [
            "Test with production WebSocket URL, not localhost",
            "Check for fallback patterns in WS URL construction",
            "Verify reconnection logic works",
            "Check browser console for WS connection errors",
        ],
    },
    "database": {
        "patterns": [
            r"CREATE TABLE",
            r"ALTER TABLE",
            r"DROP TABLE",
            r"migration",
            r"\.sql$",
            r"prisma migrate",
            r"alembic",
        ],
        "name": "DATABASE CHANGES",
        "tests": [
            "Run migrations in dev environment first",
            "Verify rollback works",
            "Check for data integrity after migration",
            "Test with production-like data volume",
        ],
    },
    "proxy": {
        "patterns": [
            r"proxy",
            r"rewrites",
            r"next\.config",
            r"nginx",
            r"CORS",
            r"Access-Control",
        ],
        "name": "PROXY/CORS CHANGES",
        "tests": [
            "Test full request flow through proxy",
            "Verify headers are preserved (especially Authorization)",
            "Check for redirect loops",
            "Test from browser, not just curl",
        ],
    },
    "datetime_boundary": {
        "patterns": [
            r"datetime",
            r"timezone",
            r"tzinfo",
            r"openpyxl",
            r"xlsxwriter",
            r"pandas.*to_excel",
            r"\.xls",
        ],
        "name": "DATETIME/EXCEL BOUNDARY CHANGES",
        "tests": [
            "Use tz-aware datetimes in tests: datetime.now(timezone.utc)",
            "Test with real DB objects, not mocks (PostgreSQL returns tz-aware)",
            "Add contract test: assert dt.tzinfo is None before Excel export",
            "Check: does code handle both naive and tz-aware inputs?",
        ],
    },
    "serialization_boundary": {
        "patterns": [
            r"\.to_dict",
            r"\.model_dump",
            r"json\.dumps",
            r"jsonify",
            r"StreamingResponse",
            r"FileResponse",
            r"BytesIO",
        ],
        "name": "SERIALIZATION BOUNDARY CHANGES",
        "tests": [
            "Test with production data types (UUID objects, Decimal, datetime)",
            "Verify JSON serialization doesn't lose type info",
            "Check: custom encoders for non-JSON-native types?",
            "E2E test: parse the actual output, not just status code",
        ],
    },
    "orm_boundary": {
        "patterns": [
            r"\.query\(",
            r"\.filter\(",
            r"\.all\(\)",
            r"\.first\(\)",
            r"session\.",
            r"db_session",
            r"AsyncSession",
        ],
        "name": "ORM/DATABASE BOUNDARY CHANGES",
        "tests": [
            "Integration test with real DB, not mocked queries",
            "Test data should match DB column types exactly",
            "Check: datetime columns -> tz-aware in PostgreSQL",
            "Check: UUID columns -> UUID objects, not strings",
        ],
    },
    "file_export": {
        "patterns": [
            r"build_excel",
            r"to_csv",
            r"to_excel",
            r"write.*xlsx",
            r"Workbook\(",
            r"csv\.writer",
        ],
        "name": "FILE EXPORT CHANGES",
        "tests": [
            "Test export with production-like data (tz-aware dates, UUIDs)",
            "Actually parse the output file in tests, don't just check size",
            "Property test: handle both naive and tz-aware datetime inputs",
            "Boundary test: verify data survives round-trip (export -> import)",
        ],
    },
}


def get_active_plan() -> dict:
    """
    Get the active plan file and its content.

    Returns dict with:
        - exists: bool
        - path: str (plan file path)
        - content: str (full plan content, max 2000 chars)
        - deploy_required: bool
        - test_required: bool
        - env: str
    """
    plans_dir = Path.home() / ".claude" / "plans"

    if not plans_dir.exists():
        return {"exists": False, "path": "", "content": "", "deploy_required": False, "test_required": False, "env": "dev"}

    # Get most recently modified plan
    plan_files = sorted(plans_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not plan_files:
        return {"exists": False, "path": "", "content": "", "deploy_required": False, "test_required": False, "env": "dev"}

    plan_path = plan_files[0]
    plan_content_raw = plan_path.read_text()
    plan_content_lower = plan_content_raw.lower()

    # Truncate content for display (keep first 2000 chars)
    plan_content_display = plan_content_raw[:2000]
    if len(plan_content_raw) > 2000:
        plan_content_display += "\n\n[... truncated, see full plan file ...]"

    # Detect environment target
    env = "dev"
    if "prod" in plan_content_lower or "production" in plan_content_lower:
        env = "prod"
    elif "staging" in plan_content_lower:
        env = "staging"

    # Check string patterns
    deploy_by_string = any(p in plan_content_lower for p in PLAN_DEPLOY_PATTERNS)

    # Check regex patterns
    deploy_by_regex = any(re.search(p, plan_content_lower) for p in PLAN_DEPLOY_REGEX)

    return {
        "exists": True,
        "path": str(plan_path),
        "content": plan_content_display,
        "deploy_required": deploy_by_string or deploy_by_regex,
        "test_required": any(p in plan_content_lower for p in PLAN_TEST_PATTERNS),
        "env": env,
    }


def parse_plan_requirements(cwd: str) -> dict:
    """Extract deployment and testing requirements from active plan file."""
    plan = get_active_plan()
    return {
        "deploy_required": plan["deploy_required"],
        "test_required": plan["test_required"],
        "env": plan["env"],
        "plan_file": plan["path"]
    }


def check_plan_execution(cwd: str) -> tuple[bool, str]:
    """Validate that plan requirements were actually executed."""
    requirements = parse_plan_requirements(cwd)

    issues = []

    # Check deployment requirement - remind user to deploy if plan requires it
    if requirements["deploy_required"]:
        issues.append(f"""🚫 DEPLOYMENT NOT EXECUTED

Your plan requires deployment to {requirements['env']} but you haven't run it.

You MUST:
1. Find and run the deploy script (e.g., ./scripts/deploy.sh, npm run deploy)
2. Do NOT ask the user to deploy - YOU must do it

Look for deploy scripts in: scripts/, package.json scripts, Makefile""")

    # Check testing requirement
    if requirements["test_required"]:
        issues.append("""🚫 TESTING NOT EXECUTED

Your plan requires browser testing but /webtest was not run.

You MUST:
1. Run /webtest skill to verify changes work in browser
2. Do NOT ask the user to test - YOU must do it""")

    if issues:
        return False, "\n\n".join(issues)
    return True, ""


def is_excluded_path(filepath: str) -> bool:
    """Check if a file path should be excluded from pattern matching."""
    for excluded in EXCLUDED_PATHS:
        if excluded in filepath:
            return True
    return False


def get_git_diff() -> dict[str, str]:
    """
    Get structured git diff with file awareness.

    Returns:
        dict mapping filename -> changed lines content (only +/- lines)
    """
    try:
        # Get list of changed files (staged + unstaged)
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
        all_files = set(staged_files + unstaged_files)

        # Filter out excluded paths
        filtered_files = [f for f in all_files if not is_excluded_path(f)]

        # Get diff content for each file, extracting only changed lines
        file_diffs: dict[str, str] = {}
        for filename in filtered_files:
            # Try staged first, then unstaged
            diff = subprocess.run(
                ["git", "diff", "--cached", "--", filename],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=5,
            )
            if not diff.stdout:
                diff = subprocess.run(
                    ["git", "diff", "--", filename],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=5,
                )

            # Extract only added/removed lines (skip diff headers and context)
            changed_lines = []
            for line in diff.stdout.split("\n"):
                if line.startswith("+") and not line.startswith("+++"):
                    changed_lines.append(line[1:])  # Remove + prefix
                elif line.startswith("-") and not line.startswith("---"):
                    changed_lines.append(line[1:])  # Remove - prefix

            if changed_lines:
                file_diffs[filename] = "\n".join(changed_lines)

        return file_diffs
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return {}


def detect_change_types(file_diffs: dict[str, str]) -> list[str]:
    """
    Detect change types with file-extension awareness to reduce false positives.

    Args:
        file_diffs: dict mapping filename -> changed lines content
    """
    detected: set[str] = set()

    for filename, content in file_diffs.items():
        ext = Path(filename).suffix.lower()

        for change_type, config in CHANGE_PATTERNS.items():
            # Skip Python-only patterns for non-Python files
            if change_type in PYTHON_ONLY_PATTERNS and ext != ".py":
                continue

            # Skip JS/TS-only patterns for non-JS/TS files
            if change_type in JS_TS_ONLY_PATTERNS and ext not in {".js", ".jsx", ".ts", ".tsx"}:
                continue

            for pattern in config["patterns"]:
                if re.search(pattern, content, re.IGNORECASE):
                    detected.add(change_type)
                    break  # Only add each type once per file

    return list(detected)


def detect_architectural_changes(file_diffs: dict[str, str]) -> bool:
    """
    Detect if changes include architectural modifications requiring TECHNICAL_OVERVIEW.md update.
    """
    for filename, content in file_diffs.items():
        for pattern in ARCHITECTURAL_CHANGE_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                return True
        # Also check if the filename itself indicates architectural change
        if re.search(r"pauwels_\w+\.json$", filename):
            return True
    return False


def format_change_specific_tests(change_types: list[str]) -> str:
    """Format testing requirements for detected change types."""
    if not change_types:
        return ""

    lines = ["\n\n5. CHANGE-SPECIFIC TESTING REQUIRED:"]

    for change_type in change_types:
        config = CHANGE_PATTERNS[change_type]
        lines.append(f"\n   ⚠️  {config['name']} DETECTED:")
        for test in config["tests"]:
            lines.append(f"      - {test}")

    return "\n".join(lines)


def main():
    # Skip for automation roles (knowledge sync, scheduled jobs)
    fleet_role = os.environ.get("FLEET_ROLE", "")
    if fleet_role in ("knowledge_sync", "scheduled_job"):
        log_debug("Skipping: automation role", parsed_data={"fleet_role": fleet_role})
        sys.exit(0)

    # Read raw stdin first for diagnostic logging (Claude Code bug #17805)
    raw_input = sys.stdin.read()
    log_debug("Stop hook invoked", raw_input=raw_input)

    # Parse the input
    try:
        input_data = json.loads(raw_input) if raw_input else {}
    except json.JSONDecodeError as e:
        # Log the parse failure for debugging
        log_debug(f"JSON parse error: {e}", raw_input=raw_input)
        # If we can't parse input, allow stop to prevent blocking
        sys.exit(0)

    log_debug("Parsed successfully", parsed_data=input_data)

    cwd = input_data.get("cwd", "")
    stop_hook_active = input_data.get("stop_hook_active", False)

    # =========================================================================
    # SECOND STOP (stop_hook_active=True): Allow stop (loop prevention)
    # =========================================================================
    if stop_hook_active:
        log_debug("ALLOWING STOP: stop_hook_active=true (second stop)", parsed_data=input_data)
        sys.exit(0)

    # =========================================================================
    # FIRST STOP (stop_hook_active=False): Show FULL checklist
    # =========================================================================

    # Gather all context
    file_diffs = get_git_diff()
    change_types = detect_change_types(file_diffs)
    change_specific_tests = format_change_specific_tests(change_types)
    has_architectural_changes = detect_architectural_changes(file_diffs)

    # Get active plan content
    plan = get_active_plan()

    # Build plan section for the checklist
    if plan["exists"]:
        plan_section = f"""
═══════════════════════════════════════════════════════════════════════════════
   YOUR ACTIVE PLAN: {plan['path']}
═══════════════════════════════════════════════════════════════════════════════

{plan['content']}

═══════════════════════════════════════════════════════════════════════════════
"""
    else:
        plan_section = """
   [No active plan file found in ~/.claude/plans/]

   Even without a plan file, ask yourself:
   - What did the user ACTUALLY ask for?
   - Did I deliver that, or just part of it?
"""

    # Build deployment/testing reminder if detected in plan
    deploy_test_reminder = ""
    if plan["deploy_required"]:
        deploy_test_reminder += f"""
   🚫 DEPLOYMENT DETECTED IN PLAN → Did you deploy to {plan['env']}? If not, DO IT NOW."""
    if plan["test_required"]:
        deploy_test_reminder += """
   🚫 TESTING DETECTED IN PLAN → Did you run /webtest? If not, DO IT NOW."""

    # First stop - block and give FULL instructions with plan at top
    instructions = f"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║  🛑  MANDATORY COMPLETION CHECK - YOU MUST READ THIS BEFORE STOPPING  🛑      ║
╚═══════════════════════════════════════════════════════════════════════════════╝

This is NOT a suggestion. This is a BLOCKING REQUIREMENT.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. DID YOU COMPLETE THE PLAN? (MANDATORY - CHECK THIS FIRST)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{plan_section}
   ASK YOURSELF:
   ✗ Are there items in this plan I haven't completed? → COMPLETE THEM NOW
   ✗ Am I about to say "next steps would be..."? → Those ARE your job. DO THEM.
   ✗ Am I about to suggest the user do something I could do? → FAILURE. Do it yourself.
   ✗ Did I stop at 70-80% and call it "done"? → NOT ACCEPTABLE. Finish the job.
{deploy_test_reminder}

   The user trusted you to work AUTONOMOUSLY. Stopping early and suggesting
   "next steps" defeats the entire purpose. COMPLETE THE PLAN.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
2. DID YOU MEET THE USER'S ACTUAL GOAL? (MANDATORY)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

   What did the user ACTUALLY ask for in their original message?
   - Not 70% done. Not "mostly working". COMPLETE.
   - If testing was requested or implied, did you TEST?
   - If deployment was mentioned, did you DEPLOY?
   - If the user would need to do anything else to use your work, YOU'RE NOT DONE.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
3. CODE QUALITY (if code was written)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

   CLAUDE.md compliance:
   - Boring over clever, local over abstract
   - Small composable units, fail loud never silent
   - Type hints everywhere, files < 400 lines, functions < 60 lines

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
4. DOCUMENTATION (if code was written)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

   - Update docs affected by your changes
   - Update .claude/MEMORIES.md with significant learnings (not changelog)
   - If architectural changes{': UPDATE docs/TECHNICAL_OVERVIEW.md' if has_architectural_changes else ': not detected'}{change_specific_tests}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
5. COMMIT AND PUSH
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

   - git add, commit with descriptive message, push to remote

╔═══════════════════════════════════════════════════════════════════════════════╗
║  Only after ALL items above are complete may you stop.                        ║
║  If items 1 or 2 are NOT complete, you MUST continue working.                 ║
╚═══════════════════════════════════════════════════════════════════════════════╝"""

    checklist_path = write_checklist_file(cwd, instructions)
    log_debug(
        "BLOCKING STOP: first stop, showing compliance checklist",
        parsed_data={
            "cwd": cwd,
            "stop_hook_active": stop_hook_active,
            "change_types": change_types,
            "has_architectural_changes": has_architectural_changes,
            "plan_exists": plan["exists"],
            "plan_path": plan["path"],
        }
    )
    print(f"⚠️ Compliance check required - see {checklist_path.relative_to(cwd)}", file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    main()
