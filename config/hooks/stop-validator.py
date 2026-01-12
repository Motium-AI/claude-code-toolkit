#!/usr/bin/env python3
"""
Global Stop Hook Validator

Two-phase stop flow:
1. First stop (stop_hook_active=false): Show FULL compliance checklist, block
2. Second stop (stop_hook_active=true): Enforce status file freshness, then allow

Detects change types from git diff and shows relevant testing requirements.

Exit codes:
  0 - Allow stop
  2 - Block stop (stderr shown to Claude)
"""
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path


# Status file must be updated within this many seconds to be considered fresh
STATUS_FILE_MAX_AGE_SECONDS = 300  # 5 minutes

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


def check_status_file(cwd: str, session_id: str = "") -> tuple[bool, str]:
    """
    Check if status file exists and was recently updated.

    Checks for session-specific file first (status.<session_id>.md),
    then falls back to legacy project-level file (status.md).

    Returns:
        (is_valid, error_message) - is_valid=True if status file is fresh
    """
    if not cwd:
        return True, ""  # No cwd provided, skip check

    claude_dir = Path(cwd) / ".claude"

    # Try session-specific file first if session_id is available
    if session_id:
        session_status_path = claude_dir / f"status.{session_id}.md"
        if session_status_path.exists():
            return check_file_freshness(session_status_path)

    # Fall back to legacy project-level file
    legacy_status_path = claude_dir / "status.md"
    if legacy_status_path.exists():
        return check_file_freshness(legacy_status_path)

    # Neither file exists
    if session_id:
        expected_path = claude_dir / f"status.{session_id}.md"
    else:
        expected_path = legacy_status_path

    return False, f"MISSING: {expected_path}\nYou MUST create this file before stopping."


def check_file_freshness(status_path: Path) -> tuple[bool, str]:
    """Check if a status file was recently modified."""
    try:
        mtime = status_path.stat().st_mtime
        age_seconds = datetime.now().timestamp() - mtime

        if age_seconds > STATUS_FILE_MAX_AGE_SECONDS:
            age_minutes = int(age_seconds / 60)
            return False, f"STALE: {status_path}\nLast modified {age_minutes} minutes ago. You MUST update it before stopping."
    except OSError as e:
        return False, f"ERROR reading {status_path}: {e}"

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


def format_change_specific_tests(change_types: list[str]) -> str:
    """Format testing requirements for detected change types."""
    if not change_types:
        return ""

    lines = ["\n4. CHANGE-SPECIFIC TESTING REQUIRED:"]

    for change_type in change_types:
        config = CHANGE_PATTERNS[change_type]
        lines.append(f"\n   ⚠️  {config['name']} DETECTED:")
        for test in config["tests"]:
            lines.append(f"      - {test}")

    return "\n".join(lines)


def main():
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        # If we can't parse input, allow stop to prevent blocking
        sys.exit(0)

    cwd = input_data.get("cwd", "")
    session_id = input_data.get("session_id", "")
    stop_hook_active = input_data.get("stop_hook_active", False)

    # =========================================================================
    # SECOND STOP (stop_hook_active=True): Only enforce status, then allow
    # =========================================================================
    if stop_hook_active:
        status_ok, status_msg = check_status_file(cwd, session_id)
        if not status_ok:
            # Status still stale - block until updated
            instructions = f"""🚫 STATUS FILE STILL NOT UPDATED

{status_msg}

You MUST update the status file with your completion status:

```markdown
---
status: completed  # or: error, blocked, idle
updated: <current timestamp>
task: <final task description>
---

## Summary
<What was accomplished>
```

Write the status file now, then try to stop again."""
            print(instructions, file=sys.stderr)
            sys.exit(2)
        # Status OK - allow stop
        sys.exit(0)

    # =========================================================================
    # FIRST STOP (stop_hook_active=False): Show FULL checklist
    # =========================================================================

    # Gather all context
    status_ok, status_msg = check_status_file(cwd, session_id)
    file_diffs = get_git_diff()
    change_types = detect_change_types(file_diffs)
    change_specific_tests = format_change_specific_tests(change_types)

    # Build status section (item 0) - only shown if status check failed
    status_section = ""
    if not status_ok:
        status_section = f"""
0. 🚫 STATUS FILE UPDATE REQUIRED:
   {status_msg}

   Update the status file with:
   ```markdown
   ---
   status: completed
   updated: <timestamp>
   task: <what was done>
   ---
   ## Summary
   <accomplishments>
   ```
"""

    # First stop - block and give FULL instructions
    instructions = f"""Before stopping, complete these checks:
{status_section}
1. CLAUDE.md COMPLIANCE (if code written):
   - boring over clever, local over abstract
   - small composable units, stateless with side effects at edges
   - fail loud never silent, tests are truth
   - type hints everywhere, snake_case files, absolute imports
   - Pydantic for contracts, files < 400 lines, functions < 60 lines

2. DOCUMENTATION (if code written):
   - Read docs/index.md to understand the documentation structure
   - Identify ALL docs affected by your changes (architecture, API, operations, etc.)
   - Update those docs to reflect current implementation
   - Docs are the authoritative source - keep them accurate and current
   - Add new docs if you created new components/patterns not yet documented

3. UPDATE PROJECT .claude/MEMORIES.md (create if needed):
   This is NOT a changelog. Only add HIGH-VALUE entries:
   - User preferences that affect future work style
   - Architectural decisions with WHY (not what)
   - Non-obvious gotchas not documented elsewhere
   - Consolidate/update existing entries rather than append duplicates
   - If nothing significant learned, skip this step{change_specific_tests}

5. COMMIT AND PUSH:
   - Stage all changes: git add -A
   - Commit with descriptive message summarizing the work
   - Push to remote: git push
   - If on a feature branch, consider opening a PR

After completing these checks, you may stop."""

    print(instructions, file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    main()
