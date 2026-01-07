#!/usr/bin/env python3
"""
Global Stop Hook Validator

Blocks Claude from stopping on first attempt and provides instructions.
Detects change types from git diff and shows relevant testing requirements.

Exit codes:
  0 - Allow stop
  2 - Block stop (stderr shown to Claude)
"""
import json
import re
import subprocess
import sys


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
}


def get_git_diff() -> str:
    """Get combined staged and unstaged git diff."""
    try:
        # Get both staged and unstaged changes
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

        # Also get the actual diff content for pattern matching
        diff_content = subprocess.run(
            ["git", "diff", "--cached"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        unstaged_content = subprocess.run(
            ["git", "diff"],
            capture_output=True,
            text=True,
            timeout=5,
        )

        files = staged.stdout + "\n" + unstaged.stdout
        content = diff_content.stdout + "\n" + unstaged_content.stdout
        return files + "\n" + content
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def detect_change_types(diff: str) -> list[str]:
    """Detect which types of changes were made based on diff content."""
    detected = []

    for change_type, config in CHANGE_PATTERNS.items():
        for pattern in config["patterns"]:
            if re.search(pattern, diff, re.IGNORECASE):
                detected.append(change_type)
                break  # Only add each type once

    return detected


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

    stop_hook_active = input_data.get("stop_hook_active", False)

    # Break the loop - if we already blocked once, allow stop
    if stop_hook_active:
        sys.exit(0)

    # Detect change types
    diff = get_git_diff()
    change_types = detect_change_types(diff)
    change_specific_tests = format_change_specific_tests(change_types)

    # First stop - block and give instructions
    instructions = f"""Use ultrathink to verify all requirements are met.

Before stopping, complete these checks:

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

After completing these checks, you may stop."""

    print(instructions, file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    main()
