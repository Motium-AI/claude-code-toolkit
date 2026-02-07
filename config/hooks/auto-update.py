#!/usr/bin/env python3
"""
SessionStart Hook - Toolkit Auto-Update (v2)

Smart auto-update with customization preservation.

Flow:
1. Fast path: If recently checked and up-to-date, exit immediately
2. Slow path: Compare local HEAD vs remote origin/main
3. If outdated:
   a. Detect local modifications (dirty files)
   b. Classify overlap with upstream changes
   c. No dirty files -> git pull --ff-only
   d. Dirty but no overlap -> stash + pull + pop
   e. Dirty with overlap -> backup branch + agent instructions
4. After pull: re-merge settings.local.json if present
5. If settings.json changed: output restart warning

Agent Integration (Deferred Agent Pattern):
  When local modifications overlap with upstream changes, the hook
  outputs structured instructions that the Claude agent executes
  as its first action. The hook is the sensor; the agent is the brain.

Exit codes:
  0 - Success (always non-blocking for SessionStart hooks)

Output (stdout):
  - Nothing if up-to-date
  - Update notification if pulled cleanly
  - Structured agent instructions if merge needed
  - Restart warning if settings.json structure changed
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ============================================================================
# Configuration
# ============================================================================

CHECK_INTERVAL_MINUTES = 5
STATE_FILE = Path.home() / ".claude" / "toolkit-update-state.json"
DEBUG_LOG = Path(tempfile.gettempdir()) / "claude-hooks-debug.log"


def log_debug(message: str) -> None:
    """Append debug message to log file."""
    try:
        with open(DEBUG_LOG, "a") as f:
            timestamp = datetime.now().isoformat()
            f.write(f"[{timestamp}] [auto-update] {message}\n")
    except Exception:
        pass


# ============================================================================
# Toolkit Path Resolution
# ============================================================================


def get_toolkit_repo_path() -> Path | None:
    """Get the toolkit repository path by resolving the hooks symlink."""
    hooks_path = Path.home() / ".claude" / "hooks"

    if not hooks_path.exists():
        log_debug("hooks path does not exist")
        return None

    if not hooks_path.is_symlink():
        log_debug("hooks path is not a symlink (manual install?)")
        return None

    try:
        resolved = hooks_path.resolve()
        repo_path = resolved.parent.parent
        if not (repo_path / ".git").exists():
            log_debug(f"resolved path {repo_path} is not a git repo")
            return None
        log_debug(f"found toolkit repo at {repo_path}")
        return repo_path
    except Exception as e:
        log_debug(f"error resolving toolkit path: {e}")
        return None


# ============================================================================
# State Management
# ============================================================================


def load_state() -> dict:
    """Load update state file, return empty dict if missing/invalid."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except (json.JSONDecodeError, IOError) as e:
            log_debug(f"error loading state file: {e}")
    return {}


def save_state(state: dict) -> None:
    """Save state file back to disk."""
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(state, indent=2))
    except Exception as e:
        log_debug(f"error saving state file: {e}")


def get_settings_hash() -> str:
    """Get SHA256 hash of the effective settings.json content."""
    settings_path = Path.home() / ".claude" / "settings.json"
    try:
        if settings_path.exists():
            actual_path = settings_path.resolve() if settings_path.is_symlink() else settings_path
            content = actual_path.read_text()
            return f"sha256:{hashlib.sha256(content.encode()).hexdigest()[:16]}"
    except Exception as e:
        log_debug(f"error hashing settings.json: {e}")
    return "unknown"


def should_check_for_updates(state: dict) -> bool:
    """Determine if enough time has passed since last check."""
    last_check = state.get("last_check_timestamp")
    if not last_check:
        return True
    try:
        last_check_str = last_check.replace("Z", "+00:00")
        last_check_time = datetime.fromisoformat(last_check_str)
        now = datetime.now(timezone.utc)
        elapsed = now - last_check_time
        should_check = elapsed > timedelta(minutes=CHECK_INTERVAL_MINUTES)
        log_debug(f"last check: {last_check}, elapsed: {elapsed}, should_check: {should_check}")
        return should_check
    except (ValueError, TypeError) as e:
        log_debug(f"error parsing last_check_timestamp: {e}")
        return True


# ============================================================================
# Git Helpers
# ============================================================================


def _git(repo_path: Path, args: list[str], timeout: int = 5) -> subprocess.CompletedProcess | None:
    """Run a git command, return CompletedProcess or None on error."""
    try:
        return subprocess.run(
            ["git"] + args,
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        log_debug(f"git {' '.join(args)} failed: {e}")
        return None


def get_local_head(repo_path: Path) -> str | None:
    result = _git(repo_path, ["rev-parse", "HEAD"])
    return result.stdout.strip() if result and result.returncode == 0 else None


def get_remote_head(repo_path: Path) -> str | None:
    result = _git(repo_path, ["ls-remote", "origin", "main"], timeout=15)
    if result and result.returncode == 0 and result.stdout:
        return result.stdout.split()[0]
    return None


def git_fetch(repo_path: Path) -> bool:
    result = _git(repo_path, ["fetch", "origin", "main"], timeout=30)
    return result is not None and result.returncode == 0


def git_pull_ff(repo_path: Path) -> tuple[bool, str]:
    result = _git(repo_path, ["pull", "--ff-only", "origin", "main"], timeout=30)
    if result is None:
        return False, "Git operation timed out"
    if result.returncode == 0:
        return True, result.stdout.strip()
    return False, result.stderr.strip()


def get_commit_summary(repo_path: Path, from_commit: str, to_commit: str) -> str:
    result = _git(repo_path, ["log", "--oneline", f"{from_commit}..{to_commit}"])
    if result and result.returncode == 0 and result.stdout.strip():
        lines = result.stdout.strip().split("\n")
        if len(lines) <= 5:
            return result.stdout.strip()
        return f"{lines[0]}\n{lines[1]}\n{lines[2]}\n... and {len(lines) - 3} more commits"
    return ""


def get_commit_count(repo_path: Path, from_commit: str, to_commit: str) -> int:
    result = _git(repo_path, ["rev-list", "--count", f"{from_commit}..{to_commit}"])
    if result and result.returncode == 0:
        try:
            return int(result.stdout.strip())
        except ValueError:
            pass
    return 0


# ============================================================================
# v1: Dirty File Detection & Classification
# ============================================================================


def get_dirty_files(repo_path: Path) -> list[str]:
    """Get files with uncommitted changes (staged + unstaged + untracked in config/)."""
    dirty = set()

    # Unstaged changes
    result = _git(repo_path, ["diff", "--name-only"])
    if result and result.returncode == 0:
        dirty.update(f for f in result.stdout.strip().split("\n") if f)

    # Staged changes
    result = _git(repo_path, ["diff", "--cached", "--name-only"])
    if result and result.returncode == 0:
        dirty.update(f for f in result.stdout.strip().split("\n") if f)

    return sorted(dirty)


def get_upstream_changed_files(repo_path: Path) -> list[str]:
    """Get files changed between HEAD and FETCH_HEAD (run after git fetch)."""
    result = _git(repo_path, ["diff", "--name-only", "HEAD..FETCH_HEAD"])
    if result and result.returncode == 0:
        return [f for f in result.stdout.strip().split("\n") if f]
    return []


def get_file_diff_stats(repo_path: Path, filepath: str) -> int:
    """Get approximate lines changed for a dirty file."""
    result = _git(repo_path, ["diff", "--numstat", "--", filepath])
    if result and result.returncode == 0:
        for line in result.stdout.strip().split("\n"):
            parts = line.split("\t")
            if len(parts) >= 2:
                try:
                    return int(parts[0]) + int(parts[1])
                except ValueError:
                    pass
    return 0


def classify_file(filepath: str, repo_path: Path) -> dict:
    """Classify a file by its category and template status."""
    if filepath.endswith(".json") and "settings" in filepath:
        category = "config"
    elif "/hooks/" in filepath and os.path.basename(filepath).startswith("_"):
        category = "hook_module"
    elif "/hooks/" in filepath:
        category = "hook"
    elif "/skills/" in filepath:
        category = "skill"
    elif "/commands/" in filepath:
        category = "command"
    elif filepath.endswith("CLAUDE.md"):
        category = "instructions"
    else:
        category = "other"

    # Detect template files by checking upstream for placeholder patterns
    is_template = False
    result = _git(repo_path, ["show", f"FETCH_HEAD:{filepath}"])
    if result and result.returncode == 0:
        is_template = bool(
            re.search(r"\[YOUR_\w+\]|\[ORG\]|example\.com|Fill this out", result.stdout)
        )

    return {"category": category, "is_template": is_template}


def classify_dirty_files(
    repo_path: Path,
    dirty_files: list[str],
    upstream_changed: list[str],
) -> list[dict]:
    """Classify each dirty file with overlap and category info."""
    upstream_set = set(upstream_changed)
    results = []
    for f in dirty_files:
        info = classify_file(f, repo_path)
        lines = get_file_diff_stats(repo_path, f)
        results.append({
            "path": f,
            "overlap": f in upstream_set,
            "category": info["category"],
            "is_template": info["is_template"],
            "lines_changed": lines,
        })
    return results


# ============================================================================
# v1: Backup & Merge Strategies
# ============================================================================


def create_backup_branch(repo_path: Path) -> str | None:
    """Create a backup branch from current state (includes uncommitted via stash ref)."""
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    branch_name = f"toolkit-backup-{ts}"
    result = _git(repo_path, ["branch", branch_name])
    if result and result.returncode == 0:
        log_debug(f"created backup branch: {branch_name}")
        return branch_name
    log_debug(f"failed to create backup branch: {result.stderr if result else 'timeout'}")
    return None


def stash_pull_pop(repo_path: Path) -> tuple[bool, str]:
    """Stash local changes, pull, then pop stash. Returns (success, message)."""
    # Stash
    result = _git(repo_path, ["stash", "push", "-m", "auto-update: preserving local changes"], timeout=10)
    if not result or result.returncode != 0:
        return False, f"Stash failed: {result.stderr if result else 'timeout'}"

    stashed = "No local changes" not in result.stdout

    if not stashed:
        success, msg = git_pull_ff(repo_path)
        return success, msg

    # Pull
    success, pull_msg = git_pull_ff(repo_path)
    if not success:
        # Restore stash on failure
        _git(repo_path, ["stash", "pop"], timeout=10)
        return False, f"Pull failed after stash: {pull_msg}"

    # Pop stash
    pop_result = _git(repo_path, ["stash", "pop"], timeout=10)
    if pop_result and pop_result.returncode == 0:
        return True, f"Updated with stash/pop: {pull_msg}"

    # Pop failed — conflicts. Leave stash, agent will handle.
    return False, f"Stash pop conflict: {pop_result.stderr if pop_result else 'timeout'}"


def verify_upstream_hook(repo_path: Path) -> bool:
    """Verify the upstream auto-update.py compiles (bootstrap safety)."""
    result = _git(repo_path, ["show", "FETCH_HEAD:config/hooks/auto-update.py"])
    if not result or result.returncode != 0:
        return True  # Can't check, assume valid

    try:
        compile(result.stdout, "auto-update.py", "exec")
        log_debug("upstream auto-update.py syntax OK")
        return True
    except SyntaxError as e:
        log_debug(f"upstream auto-update.py syntax error: {e}")
        return False


# ============================================================================
# v2: Settings Merge
# ============================================================================


def deep_merge(base: dict, override: dict) -> dict:
    """Deep merge override into base. Override wins for scalars. Arrays replace."""
    from copy import deepcopy

    result = deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def merge_settings_if_needed(repo_path: Path) -> bool:
    """If settings.local.json exists, deep-merge onto settings.json -> ~/.claude/settings.json.

    Returns True if merge was performed.
    """
    local_path = repo_path / "config" / "settings.local.json"
    if not local_path.exists():
        return False

    base_path = repo_path / "config" / "settings.json"
    target_path = Path.home() / ".claude" / "settings.json"

    try:
        base = json.loads(base_path.read_text())
        local = json.loads(local_path.read_text())

        # Strip comments (keys starting with _)
        local_clean = {k: v for k, v in local.items() if not k.startswith("_")}

        merged = deep_merge(base, local_clean)

        # Replace symlink with real file if needed
        if target_path.is_symlink():
            target_path.unlink()

        target_path.write_text(json.dumps(merged, indent=2) + "\n")
        log_debug(f"merged settings.local.json ({len(local_clean)} override keys)")
        return True
    except (json.JSONDecodeError, IOError) as e:
        log_debug(f"settings merge failed: {e}")
        return False


# ============================================================================
# v1: Agent Instructions Output
# ============================================================================


def get_user_diff_content(repo_path: Path, filepath: str, max_lines: int = 30) -> str:
    """Get the diff content for a dirty file, truncated if long."""
    result = _git(repo_path, ["diff", "--", filepath])
    if result and result.returncode == 0 and result.stdout.strip():
        lines = result.stdout.strip().split("\n")
        if len(lines) > max_lines:
            return "\n".join(lines[: max_lines - 2]) + f"\n... ({len(lines) - max_lines + 2} more lines)"
        return result.stdout.strip()
    return "(no diff available)"


def output_agent_instructions(
    repo_path: Path,
    local_head: str,
    remote_head: str,
    classified_files: list[dict],
    commit_summary: str,
    commit_count: int,
    backup_branch: str | None,
    settings_changed_upstream: bool,
) -> None:
    """Output structured instructions for the Claude agent."""
    overlap_files = [f for f in classified_files if f["overlap"]]
    safe_files = [f for f in classified_files if not f["overlap"]]

    # Build per-file detail blocks
    file_blocks = []
    for f in classified_files:
        block = [
            f"  - path: {f['path']}",
            f"    overlap: {f['overlap']}",
            f"    category: {f['category']}",
            f"    is_template: {f['is_template']}",
            f"    lines_changed: {f['lines_changed']}",
        ]
        if f["overlap"]:
            diff = get_user_diff_content(repo_path, f["path"])
            block.append("    user_diff: |")
            for line in diff.split("\n"):
                block.append(f"      {line}")
        file_blocks.append("\n".join(block))

    settings_note = ""
    if settings_changed_upstream:
        local_settings = repo_path / "config" / "settings.local.json"
        settings_note = (
            f"\n8. settings.json changed upstream. After merge, re-run settings merge:"
            f"\n   Read {local_settings} (if it exists) and deep-merge onto the new"
            f"\n   config/settings.json, writing the result to ~/.claude/settings.json."
            f"\n   This ensures user overrides survive the update."
        )

    print(f"""
---TOOLKIT-UPDATE-ACTION---
MANDATORY: Before starting any user task, execute this toolkit update procedure.

status: merge_required
repo_path: {repo_path}
from_commit: {local_head[:7]}
to_commit: {remote_head[:7]}
commits_behind: {commit_count}
backup_branch: {backup_branch or 'none'}
settings_changed_upstream: {settings_changed_upstream}

dirty_files:
{chr(10).join(file_blocks)}

total_overlap_files: {len(overlap_files)}
total_safe_files: {len(safe_files)}

upstream_commits:
  {commit_summary.replace(chr(10), chr(10) + '  ')}

MERGE PROCEDURE:
1. Create safety: backup branch '{backup_branch}' already exists.
2. For each overlapping file, read BOTH versions:
   - Local: Read the file at {repo_path}/[path]
   - Upstream: Run `git show origin/main:[path]` in {repo_path}
3. Classify each user modification:
   - TEMPLATE_FILL: User replaced [YOUR_*] placeholders -> PRESERVE user values in new version
   - PROJECT_GUARD: User added project-specific conditionals -> RE-ADD to new version
   - FEATURE_ADD: User added new capability -> CHECK if upstream added equivalent; re-implement if not
   - BUG_FIX: User patched a bug -> CHECK if upstream fixed it; drop if yes
   - CONFIG_OVERRIDE: User changed default values -> PRESERVE overrides in new version
4. Run in {repo_path}: git stash push -m "auto-update: preserving customizations"
5. Run in {repo_path}: git pull --ff-only origin main
6. For each overlapping file, apply the classified customization to the new version
7. Stage and commit: git add [files] && git commit -m "merge: preserve user customizations across {local_head[:7]}..{remote_head[:7]}"{settings_note}

After completing, report:
- What customizations were preserved and why
- What was dropped (with explanation)
- Whether a restart is needed (only if settings.json structure changed)
---END-TOOLKIT-UPDATE-ACTION---
""")


# ============================================================================
# Main Logic
# ============================================================================


def main():
    if os.environ.get("CLAUDE_TOOLKIT_AUTO_UPDATE", "").lower() == "false":
        log_debug("auto-update disabled via environment variable")
        sys.exit(0)

    try:
        input_data = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        input_data = {}

    source = input_data.get("source", "startup")
    log_debug(f"SessionStart source: {source}")

    repo_path = get_toolkit_repo_path()
    if not repo_path:
        sys.exit(0)

    state = load_state()
    current_settings_hash = get_settings_hash()

    # Check for pending restart
    pending_restart = state.get("pending_restart_reason")
    if pending_restart:
        stored_hash = state.get("settings_hash_at_session_start")
        if stored_hash and stored_hash != current_settings_hash:
            log_debug("pending restart cleared - settings hash changed")
            state["pending_restart_reason"] = None
            state["settings_hash_at_session_start"] = current_settings_hash
            save_state(state)
        else:
            print(f"""
TOOLKIT RESTART REQUIRED

Namshub updated but settings.json changed. Hooks are captured at startup.
Reason: {pending_restart}

ACTION: Exit this session and start a new one.
""")
            sys.exit(0)

    # Fast path: recently checked
    if not should_check_for_updates(state):
        state["settings_hash_at_session_start"] = current_settings_hash
        save_state(state)
        sys.exit(0)

    # Slow path: check for updates
    log_debug("checking for updates...")
    local_head = get_local_head(repo_path)
    remote_head = get_remote_head(repo_path)
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    if not local_head or not remote_head:
        log_debug(f"version check failed: local={local_head}, remote={remote_head}")
        state["last_check_timestamp"] = now
        state["last_check_result"] = "check_failed"
        state["settings_hash_at_session_start"] = current_settings_hash
        save_state(state)
        sys.exit(0)

    # Up to date
    if local_head == remote_head:
        log_debug(f"up to date at {local_head[:7]}")
        state["last_check_timestamp"] = now
        state["last_check_result"] = "up_to_date"
        state["local_commit_at_check"] = local_head[:7]
        state["remote_commit_at_check"] = remote_head[:7]
        state["settings_hash_at_session_start"] = current_settings_hash
        save_state(state)
        sys.exit(0)

    # ================================================================
    # Updates available
    # ================================================================
    log_debug(f"updates available: {local_head[:7]} -> {remote_head[:7]}")
    settings_hash_before = current_settings_hash

    # Step 1: Fetch
    if not git_fetch(repo_path):
        log_debug("fetch failed")
        state["last_check_timestamp"] = now
        state["last_check_result"] = "fetch_failed"
        state["settings_hash_at_session_start"] = current_settings_hash
        save_state(state)
        sys.exit(0)

    commit_count = get_commit_count(repo_path, local_head, "FETCH_HEAD")

    # Step 2: Bootstrap safety
    if not verify_upstream_hook(repo_path):
        state["last_check_timestamp"] = now
        state["last_check_result"] = "upstream_syntax_error"
        save_state(state)
        print("toolkit update skipped: upstream hook has syntax error. Will retry next session.")
        sys.exit(0)

    # Step 3: Detect dirty files
    dirty_files = get_dirty_files(repo_path)

    if not dirty_files:
        # Clean tree — simple pull
        log_debug("clean working tree, proceeding with ff pull")
        success, message = git_pull_ff(repo_path)
        if not success:
            log_debug(f"pull failed: {message}")
            state["last_check_timestamp"] = now
            state["last_check_result"] = "update_failed"
            state["settings_hash_at_session_start"] = current_settings_hash
            save_state(state)
            print(f"toolkit update failed: {message}")
            sys.exit(0)

        merge_settings_if_needed(repo_path)
        _report_success(repo_path, state, local_head, remote_head, now, settings_hash_before)
        sys.exit(0)

    # Step 4: Classify dirty files
    log_debug(f"dirty files: {dirty_files}")
    upstream_changed = get_upstream_changed_files(repo_path)
    classified = classify_dirty_files(repo_path, dirty_files, upstream_changed)

    overlap_files = [f for f in classified if f["overlap"]]
    safe_files = [f for f in classified if not f["overlap"]]
    log_debug(f"overlap: {len(overlap_files)}, safe: {len(safe_files)}")

    if not overlap_files:
        # No overlap — safe stash + pull + pop
        log_debug("no overlap, attempting stash-pull-pop")
        backup = create_backup_branch(repo_path)

        success, message = stash_pull_pop(repo_path)
        if success:
            merge_settings_if_needed(repo_path)
            extra = (
                f"Your local changes to {len(safe_files)} file(s) were preserved (no upstream conflicts)."
            )
            if backup:
                extra += f" Backup: {backup}"
            _report_success(repo_path, state, local_head, remote_head, now, settings_hash_before, extra)
            sys.exit(0)
        else:
            log_debug(f"stash-pull-pop failed: {message}")
            # Fall through to agent path

    # Step 5: Overlap or stash failure — delegate to agent
    log_debug("delegating to agent for smart merge")
    backup = create_backup_branch(repo_path)

    settings_changed_upstream = "config/settings.json" in set(upstream_changed)
    commit_summary = get_commit_summary(repo_path, local_head[:7], remote_head[:7])

    output_agent_instructions(
        repo_path=repo_path,
        local_head=local_head,
        remote_head=remote_head,
        classified_files=classified,
        commit_summary=commit_summary,
        commit_count=commit_count,
        backup_branch=backup,
        settings_changed_upstream=settings_changed_upstream,
    )

    state["last_check_timestamp"] = now
    state["last_check_result"] = "agent_merge_requested"
    state["local_commit_at_check"] = local_head[:7]
    state["remote_commit_at_check"] = remote_head[:7]
    state["settings_hash_at_session_start"] = current_settings_hash
    save_state(state)
    sys.exit(0)


def _report_success(
    repo_path: Path,
    state: dict,
    local_head: str,
    remote_head: str,
    now: str,
    settings_hash_before: str,
    extra_msg: str = "",
) -> None:
    """Report successful update and persist state."""
    new_local_head = get_local_head(repo_path)

    # HEAD didn't move to expected — local is ahead
    if new_local_head and new_local_head != remote_head:
        state["last_check_timestamp"] = now
        state["last_check_result"] = "local_ahead"
        state["local_commit_at_check"] = new_local_head[:7]
        state["remote_commit_at_check"] = remote_head[:7]
        save_state(state)
        print(f"""
toolkit: local ({new_local_head[:7]}) ahead of remote ({remote_head[:7]}). Auto-update paused.
""")
        return

    settings_hash_after = get_settings_hash()
    settings_changed = settings_hash_before != settings_hash_after
    commit_summary = get_commit_summary(repo_path, local_head[:7], remote_head[:7])

    history = state.get("update_history", [])
    history.insert(0, {
        "timestamp": now,
        "from_commit": local_head[:7],
        "to_commit": remote_head[:7],
        "settings_changed": settings_changed,
    })
    state["update_history"] = history[:5]
    state["last_check_timestamp"] = now
    state["last_check_result"] = "updated"
    state["local_commit_at_check"] = remote_head[:7]
    state["remote_commit_at_check"] = remote_head[:7]
    state["settings_hash_at_session_start"] = settings_hash_after

    if settings_changed:
        state["pending_restart_reason"] = (
            f"settings.json changed in update {local_head[:7]} -> {remote_head[:7]}"
        )
        save_state(state)
        msg = f"toolkit updated {local_head[:7]} -> {remote_head[:7]}. {commit_summary}"
        if extra_msg:
            msg += f"\n{extra_msg}"
        msg += "\nsettings.json changed — restart required for new hook definitions."
        print(msg)
    else:
        save_state(state)
        msg = f"toolkit updated {local_head[:7]} -> {remote_head[:7]}. {commit_summary}"
        if extra_msg:
            msg += f"\n{extra_msg}"
        print(msg)


if __name__ == "__main__":
    main()
