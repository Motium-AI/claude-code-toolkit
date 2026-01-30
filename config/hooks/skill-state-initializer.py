#!/usr/bin/env python3
"""
UserPromptSubmit hook that creates state files for autonomous execution skills.

When the user's prompt matches appfix or godo triggers, this hook immediately
creates the appropriate state file BEFORE Claude starts processing. This ensures
the auto-approval hooks can detect autonomous mode from the very first tool call.

Hook event: UserPromptSubmit

Why this hook exists:
- Auto-approval hooks check for .claude/appfix-state.json or .claude/godo-state.json
- Without the state file, PermissionRequest hooks exit silently (no auto-approval)
- Previously, state file creation was an instruction in SKILL.md that Claude had
  to execute via Bash - but by then, EnterPlanMode's PermissionRequest had already fired
- This hook creates the file BEFORE Claude processes anything, fixing the race condition
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add hooks directory to path for shared imports
sys.path.insert(0, str(Path(__file__).parent))

from _common import (
    cleanup_autonomous_state,
    is_state_expired,
    is_state_for_session,
    load_state_file,
    log_debug,
    _scoped_filename,
)

# Deactivation patterns - checked BEFORE activation
# /repair and /forge are the two primary autonomous skills
DEACTIVATION_PATTERNS = [
    r"(?:^|\s)/repair\s+off\b",  # Primary debugging skill
    r"(?:^|\s)/forge\s+off\b",  # Primary task execution skill
    r"(?:^|\s)/burndown\s+off\b",  # Tech debt elimination skill
    r"(?:^|\s)/appfix\s+off\b",  # Internal web debugging
    r"(?:^|\s)/mobileappfix\s+off\b",  # Internal mobile debugging
    r"(?:^|\s)/godo\s+off\b",  # Legacy alias
    r"\bstop autonomous mode\b",
    r"\bdisable auto[- ]?approval\b",
    r"\bturn off (repair|forge|burndown|appfix|mobileappfix|godo)\b",
]

# Trigger patterns for each skill
# /repair is the PRIMARY debugging skill (creates appfix-state.json internally)
# /forge is the PRIMARY task execution skill
# Patterns that indicate mobile app vs web app
MOBILE_REPAIR_PATTERNS = [
    r"(?:^|\s)/mobileappfix\b",
    r"\bfix the mobile app\b",
    r"\bmaestro (tests? )?(failing|broken|not working)\b",
    r"\bsimulator (crash|fail|not working)\b",
    r"\breact native\b",
    r"\bexpo\b.*\b(crash|fail|broken|fix)\b",
    r"\bios (app|build|crash|fail)\b",
    r"\bandroid (app|build|crash|fail)\b",
]

SKILL_TRIGGERS = {
    "repair": [  # PRIMARY debugging skill - unified entry point
        r"(?:^|\s)/repair\b",  # Primary slash command
        r"(?:^|\s)/appfix\b",  # Web variant (internal)
        r"(?:^|\s)/mobileappfix\b",  # Mobile variant (internal)
        r"\bfix the app\b",  # Natural language
        r"\bfix the mobile app\b",  # Mobile variant
        r"\bdebug production\b",
        r"\bcheck staging\b",
        r"\bwhy is it broken\b",
        r"\bapp is broken\b",
        r"\bapp is down\b",
        r"\bapp crashed\b",
        r"\bproduction (is )?(down|broken|failing)\b",
        r"\bstaging (is )?(down|broken|failing)\b",
        r"\bmaestro (tests? )?(failing|broken|not working)\b",  # Mobile E2E triggers
        r"\bsimulator (crash|fail|not working)\b",  # Mobile-specific
    ],
    "forge": [  # PRIMARY task execution skill
        r"(?:^|\s)/forge\b",  # Primary slash command
        r"(?:^|\s)/godo\b",  # Legacy alias
        r"\bgo do\b",  # Natural language
        r"\bjust do it\b",
        r"\bexecute this\b",
        r"\bmake it happen\b",
    ],
    "burndown": [  # Tech debt elimination skill
        r"(?:^|\s)/burndown\b",  # Primary slash command
        r"\bburn down debt\b",  # Natural language
        r"\bburn down tech debt\b",
        r"\bclean up the codebase\b",
        r"\bfix (the )?(code )?slop\b",
        r"\bremove ai slop\b",
        r"\bcodebase cleanup\b",
        r"\btech debt (cleanup|removal|elimination)\b",
    ],
}


def detect_deactivation(prompt: str) -> bool:
    """Detect if the prompt is requesting deactivation of autonomous mode.

    Returns True if deactivation is requested.
    """
    prompt_lower = prompt.lower().strip()
    for pattern in DEACTIVATION_PATTERNS:
        if re.search(pattern, prompt_lower, re.IGNORECASE):
            return True
    return False


def detect_skill(prompt: str) -> str | None:
    """Detect which autonomous skill should be activated based on prompt.

    Returns 'repair', 'forge', or None.
    Note: 'repair' triggers create appfix-state.json internally for backwards compatibility.
    """
    prompt_lower = prompt.lower().strip()

    for skill_name, patterns in SKILL_TRIGGERS.items():
        for pattern in patterns:
            if re.search(pattern, prompt_lower, re.IGNORECASE):
                return skill_name

    return None


def detect_mobile_mode(prompt: str) -> bool:
    """Detect if this is a mobile app fix (vs web app fix).

    Returns True if any mobile-specific patterns match.
    Used by /repair to determine whether to route to web or mobile debugging.
    """
    prompt_lower = prompt.lower().strip()
    for pattern in MOBILE_REPAIR_PATTERNS:
        if re.search(pattern, prompt_lower, re.IGNORECASE):
            return True
    return False


def _has_valid_existing_state(cwd: str, skill_name: str, session_id: str) -> bool:
    """Check if a valid (same session, not expired) state file already exists.

    Used to skip re-creation when autonomous mode is already active
    for the current session (sticky session reuse).

    Args:
        cwd: Working directory
        skill_name: 'repair' or 'forge'
        session_id: Current session ID

    Returns:
        True if valid state exists for this session
    """
    # Map repair -> appfix for state file (backwards compatibility)
    state_skill_name = "appfix" if skill_name == "repair" else skill_name
    state = load_state_file(cwd, f"{state_skill_name}-state.json")
    if state is None:
        return False
    if is_state_expired(state):
        return False
    if not is_state_for_session(state, session_id):
        return False
    return True


def _detect_worktree_context(cwd: str) -> tuple[bool, str | None, str | None]:
    """Detect if running in a worktree and extract agent info.

    Returns:
        (is_coordinator, agent_id, worktree_path)
        - is_coordinator: True if main repo, False if in worktree
        - agent_id: Agent ID if in worktree, None otherwise
        - worktree_path: Worktree path if in worktree, None otherwise
    """
    try:
        from worktree_manager import is_worktree, get_worktree_info

        if is_worktree(cwd):
            info = get_worktree_info(cwd)
            if info and info.get("is_claude_worktree"):
                return False, info.get("agent_id"), info.get("path")
            return False, None, cwd  # Worktree but not Claude-created
        return True, None, None  # Main repo - coordinator
    except ImportError:
        return True, None, None  # Can't detect, assume coordinator


def _cleanup_expired_sessions(sessions: dict, ttl_hours: int = 8) -> dict:
    """Remove expired sessions from the sessions dict.

    Args:
        sessions: Dict mapping session_id to session info
        ttl_hours: Hours before a session expires (default: 8)

    Returns:
        Cleaned sessions dict with expired entries removed
    """
    from _common import is_state_expired

    cleaned = {}
    for session_id, session_info in sessions.items():
        if not is_state_expired(session_info, ttl_hours):
            cleaned[session_id] = session_info
    return cleaned


def create_state_file(cwd: str, skill_name: str, session_id: str = "", is_mobile: bool = False) -> bool:
    """Create the state file for the given skill.

    Creates both project-level (.claude/) and user-level (~/.claude/) state files.
    Includes session_id and last_activity_at for sticky session support.

    NOTE: 'repair' skill uses appfix-state.json internally for backwards compatibility.
    This allows existing hooks and sessions to work without changes.

    MULTI-SESSION SUPPORT: User-level state uses a "sessions" dict that maps
    session_id to session info. This allows multiple parallel Claude sessions
    to coexist without overwriting each other's state.

    Detects if running in a worktree (subagent) vs main repo (coordinator):
    - Coordinator: Can deploy, runs in main repo
    - Subagent: Cannot deploy, runs in worktree

    Returns True if successful.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Map repair -> appfix for state file (backwards compatibility)
    state_skill_name = "appfix" if skill_name == "repair" else skill_name
    state_filename = f"{state_skill_name}-state.json"

    # Detect if we're in a worktree (subagent) or main repo (coordinator)
    is_coordinator, agent_id, worktree_path = _detect_worktree_context(cwd)

    # Project-level state (in cwd/.claude/)
    project_state = {
        "iteration": 1,
        "started_at": now,
        "last_activity_at": now,
        "session_id": session_id,
        "skill_type": "mobile" if is_mobile else "web",
        "plan_mode_completed": False,
        "parallel_mode": not is_coordinator,  # True if in worktree
        "agent_id": agent_id,
        "worktree_path": worktree_path,
        "coordinator": is_coordinator,
        "services": {},
        "fixes_applied": [],
        "verification_evidence": None,
    }

    # Add skill-specific fields
    if skill_name == "forge":
        project_state["task"] = "Detected from user prompt"

    success = True

    # Create project-level state file (PID-scoped for multi-agent isolation)
    try:
        project_claude_dir = Path(cwd) / ".claude"
        project_claude_dir.mkdir(parents=True, exist_ok=True)
        scoped_state_filename = _scoped_filename(state_filename)
        project_state_path = project_claude_dir / scoped_state_filename
        project_state_path.write_text(json.dumps(project_state, indent=2))
    except (OSError, IOError) as e:
        print(f"Warning: Failed to create project state file: {e}", file=sys.stderr)
        success = False

    # Create/update user-level state file with MULTI-SESSION support
    # Instead of overwriting, we ADD this session to the sessions dict
    try:
        user_claude_dir = Path.home() / ".claude"
        user_claude_dir.mkdir(parents=True, exist_ok=True)
        user_state_path = user_claude_dir / state_filename

        # Load existing state or create new
        existing_state = {}
        if user_state_path.exists():
            try:
                existing_state = json.loads(user_state_path.read_text())
            except json.JSONDecodeError:
                existing_state = {}

        # Get or create sessions dict
        sessions = existing_state.get("sessions", {})

        # Clean up expired sessions (>8 hours old)
        sessions = _cleanup_expired_sessions(sessions)

        # Add this session to the sessions dict
        sessions[session_id] = {
            "origin_project": cwd,
            "started_at": now,
            "last_activity_at": now,
            "plan_mode_completed": False,
        }

        # Build user-level state with multi-session format
        user_state = {
            "sessions": sessions,
            # Legacy fields for backward compatibility with old code
            # that reads session_id directly from root level
            "started_at": now,
            "last_activity_at": now,
            "session_id": session_id,
            "origin_project": cwd,
            "plan_mode_completed": False,
        }

        user_state_path.write_text(json.dumps(user_state, indent=2))
    except (OSError, IOError) as e:
        print(f"Warning: Failed to create user state file: {e}", file=sys.stderr)
        success = False

    return success


def main():
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)  # Non-blocking on error

    prompt = input_data.get("prompt", "")
    cwd = input_data.get("cwd", os.getcwd())
    session_id = input_data.get("session_id", "")

    if not prompt:
        sys.exit(0)

    # 1. Check deactivation FIRST
    if detect_deactivation(prompt):
        deleted = cleanup_autonomous_state(cwd)
        if deleted:
            print("[skill-state-initializer] Autonomous mode deactivated.")
            print(f"Cleaned up {len(deleted)} state file(s).")
            print("Auto-approval hooks are now disabled.")
            log_debug(
                "Autonomous mode deactivated by user",
                hook_name="skill-state-initializer",
                parsed_data={"deleted": deleted},
            )
        else:
            print("[skill-state-initializer] No autonomous mode was active.")
        sys.exit(0)

    # 2. Detect if this prompt triggers an autonomous skill
    skill_name = detect_skill(prompt)

    if not skill_name:
        sys.exit(0)  # No autonomous skill detected

    # 3. Check for existing valid state (sticky session reuse)
    if _has_valid_existing_state(cwd, skill_name, session_id):
        print(
            f"[skill-state-initializer] Autonomous mode already active: {skill_name} "
            f"(reusing existing session state)"
        )
        print("Auto-approval hooks remain active.")
        log_debug(
            f"Reusing existing {skill_name} state for session",
            hook_name="skill-state-initializer",
            parsed_data={"skill": skill_name, "session_id": session_id},
        )
        sys.exit(0)

    # 4. Detect if mobile mode for repair skill
    is_mobile = skill_name == "repair" and detect_mobile_mode(prompt)

    # 5. Create new state file with session binding
    success = create_state_file(cwd, skill_name, session_id, is_mobile)

    if success:
        # Output message (added to context for Claude)
        # Map repair -> appfix for state file name (internal detail)
        state_skill_name = "appfix" if skill_name == "repair" else skill_name
        scoped_name = _scoped_filename(f"{state_skill_name}-state.json")
        print(f"[skill-state-initializer] Autonomous mode activated: {skill_name}")
        print(f"State file created: .claude/{scoped_name}")
        print("Auto-approval hooks are now active.")

    sys.exit(0)


if __name__ == "__main__":
    main()
