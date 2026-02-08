#!/usr/bin/env python3
"""
Session Start Hook - Snapshot Git Diff State + Session Guard

Creates .claude/session-snapshot.json with the git diff hash at session start.
The stop hook compares against this to detect if THIS session made changes.

Session Guard:
- Claims session ownership via .claude/session-owner.json
- Detects concurrent Claude instances in the same directory
- Warns (but doesn't block) if another live session is detected
- Takes over from dead sessions silently

Expired State Cleanup:
- At session start, cleans up expired or foreign-session autonomous state files
- This is the session boundary cleanup for sticky session mode

This solves the "pre-existing changes" loop:
- Session A makes changes but doesn't commit
- Session B (research-only) starts and saves the current diff hash
- Session B stops - diff hash unchanged, so no checkpoint required
- Without this, Session B would be blocked because git diff shows changes from A
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add hooks directory to path for shared imports
sys.path.insert(0, str(Path(__file__).parent))

from _common import (
    get_diff_hash,
    is_pid_alive,
    log_debug,
    timed_hook,
)
from _session import cleanup_expired_state, cleanup_checkpoint_only


def _check_and_claim_session_ownership(cwd: str, session_id: str) -> None:
    """Check for concurrent sessions and claim ownership."""
    if not cwd or not session_id:
        return

    owner_path = Path(cwd) / ".claude" / "session-owner.json"
    owner_path.parent.mkdir(parents=True, exist_ok=True)

    if owner_path.exists():
        try:
            existing = json.loads(owner_path.read_text())
            existing_session = existing.get("session_id", "")
            existing_pid = existing.get("pid", 0)

            if existing_session == session_id:
                pass  # Same session resuming
            elif existing_pid and is_pid_alive(existing_pid):
                print(
                    f"[session-guard] WARNING: Another Claude session is active "
                    f"in this directory (PID {existing_pid}, session "
                    f"{existing_session[:8]}...). State files may conflict."
                )
                log_debug(
                    f"Concurrent session detected: PID {existing_pid} alive",
                    hook_name="session-init",
                    parsed_data={
                        "existing_session": existing_session,
                        "existing_pid": existing_pid,
                        "new_session": session_id,
                    },
                )
            else:
                log_debug(
                    f"Taking over from dead session (PID {existing_pid})",
                    hook_name="session-init",
                    parsed_data={
                        "dead_session": existing_session,
                        "dead_pid": existing_pid,
                        "new_session": session_id,
                    },
                )
        except (json.JSONDecodeError, IOError):
            pass

    owner_data = {
        "session_id": session_id,
        "pid": os.getpid(),
        "started_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    try:
        owner_path.write_text(json.dumps(owner_data, indent=2))
    except IOError as e:
        log_debug(f"Failed to write session-owner.json: {e}", hook_name="session-init")


def main():
    input_data = json.loads(sys.stdin.read() or "{}")
    cwd = input_data.get("cwd", "")
    session_id = input_data.get("session_id", "")

    if not cwd:
        sys.exit(0)

    # 1. Create session snapshot
    claude_dir = Path(cwd) / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = claude_dir / "session-snapshot.json"

    snapshot = {
        "diff_hash_at_start": get_diff_hash(cwd),
        "session_started_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "session_id": session_id,
    }

    snapshot_path.write_text(json.dumps(snapshot, indent=2))

    # 2. Session guard - check and claim ownership
    _check_and_claim_session_ownership(cwd, session_id)

    # 3. Clean up stale checkpoint from previous session
    checkpoint_deleted = cleanup_checkpoint_only(cwd)
    if checkpoint_deleted:
        log_debug(
            "Cleaned up stale checkpoint from previous session",
            hook_name="session-init",
            parsed_data={"deleted": checkpoint_deleted},
        )

    # 4. Clean up expired/foreign-session autonomous state files
    deleted = cleanup_expired_state(cwd, session_id)
    if deleted:
        log_debug(
            "Cleaned up expired/foreign state at session start",
            hook_name="session-init",
            parsed_data={"deleted": deleted},
        )
        log_debug(
            f"Cleaned up {len(deleted)} expired state file(s) from previous session",
            hook_name="session-init",
        )

    # Write health cleanup metrics sidecar (read by _health.py)
    try:
        cleanup_metrics = {
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "expired_state_cleaned": len(deleted) if deleted else 0,
        }
    except Exception:
        cleanup_metrics = {"ts": "", "expired_state_cleaned": 0}

    # 5. Garbage collect stale worktrees (from crashed coordinators)
    try:
        from worktree_manager import gc_worktrees

        gc_cleaned = gc_worktrees(ttl_hours=8)
        if gc_cleaned:
            log_debug(
                "Garbage collected stale worktrees",
                hook_name="session-init",
                parsed_data={"cleaned": gc_cleaned},
            )
            log_debug(
                f"Cleaned up {len(gc_cleaned)} stale worktree(s)",
                hook_name="session-init",
            )
    except ImportError:
        pass

    # 6. Clean up stale async-tasks files (older than 7 days)
    import time

    async_tasks_dir = claude_dir / "async-tasks"
    if async_tasks_dir.exists():
        seven_days_ago = time.time() - (7 * 24 * 60 * 60)
        cleaned_tasks = []
        for task_file in async_tasks_dir.glob("*.json"):
            try:
                if task_file.stat().st_mtime < seven_days_ago:
                    task_file.unlink()
                    cleaned_tasks.append(task_file.name)
            except (IOError, OSError):
                continue
        if cleaned_tasks:
            log_debug(
                "Cleaned up stale async-tasks",
                hook_name="session-init",
                parsed_data={"cleaned": len(cleaned_tasks)},
            )
            log_debug(
                f"Cleaned up {len(cleaned_tasks)} stale async-task(s)",
                hook_name="session-init",
            )

    # 7. Clean up old session transcript files (prevents ~/.claude bloat)
    _cleanup_old_sessions()

    # 8. Clean up old debug files (older than 7 days)
    _cleanup_debug_files()

    # 9. Clean up empty session-env directories
    _cleanup_session_env()

    # 10. Write health cleanup metrics sidecar
    try:
        metrics_path = claude_dir / "health-cleanup-metrics.json"
        metrics_path.write_text(json.dumps(cleanup_metrics, indent=2))
    except Exception:
        pass

    # 11. Rotate hook execution metrics
    _rotate_hook_metrics()

    # 12. Clean up old doc-debt entries
    _cleanup_doc_debt(cwd)

    # 13. Warn if project settings.json duplicates global hooks
    _check_hook_overlap(cwd)

    # 14. Validate hook health (all referenced scripts exist and parse)
    _validate_hook_health()

    sys.exit(0)


def _cleanup_old_sessions(max_per_project: int = 10, max_age_days: int = 21) -> None:
    """Clean up old session transcript .jsonl files to prevent disk bloat."""
    import shutil
    import time

    projects_dir = Path.home() / ".claude" / "projects"
    if not projects_dir.exists():
        return

    cutoff_time = time.time() - (max_age_days * 24 * 60 * 60)
    total_deleted_files = 0
    total_deleted_dirs = 0
    total_bytes_freed = 0

    for project_dir in projects_dir.iterdir():
        if not project_dir.is_dir():
            continue

        session_files = []
        for f in project_dir.glob("*.jsonl"):
            try:
                stat = f.stat()
                session_files.append((f, stat.st_mtime, stat.st_size))
            except OSError:
                continue

        session_files.sort(key=lambda x: x[1], reverse=True)

        for i, (session_file, mtime, size) in enumerate(session_files):
            should_delete = i >= max_per_project or mtime < cutoff_time
            if should_delete:
                try:
                    session_file.unlink()
                    total_deleted_files += 1
                    total_bytes_freed += size

                    session_dir = project_dir / session_file.stem
                    if session_dir.is_dir():
                        shutil.rmtree(session_dir, ignore_errors=True)
                        total_deleted_dirs += 1
                except OSError:
                    continue

    if total_deleted_files > 0:
        mb_freed = total_bytes_freed / (1024 * 1024)
        log_debug(
            "Cleaned up old session transcripts",
            hook_name="session-init",
            parsed_data={
                "files_deleted": total_deleted_files,
                "dirs_deleted": total_deleted_dirs,
                "mb_freed": round(mb_freed, 1),
            },
        )
        log_debug(
            f"Removed {total_deleted_files} old session(s), freed {mb_freed:.1f} MB",
            hook_name="session-init",
        )


def _cleanup_debug_files(max_age_days: int = 7) -> None:
    """Clean up old debug log files."""
    import time

    debug_dir = Path.home() / ".claude" / "debug"
    if not debug_dir.exists():
        return

    cutoff_time = time.time() - (max_age_days * 24 * 60 * 60)
    deleted_count = 0
    bytes_freed = 0

    for debug_file in debug_dir.iterdir():
        try:
            stat = debug_file.stat()
            if stat.st_mtime < cutoff_time:
                size = stat.st_size
                if debug_file.is_file():
                    debug_file.unlink()
                elif debug_file.is_dir():
                    import shutil
                    shutil.rmtree(debug_file, ignore_errors=True)
                deleted_count += 1
                bytes_freed += size
        except OSError:
            continue

    if deleted_count > 0:
        mb_freed = bytes_freed / (1024 * 1024)
        log_debug(
            "Cleaned up old debug files",
            hook_name="session-init",
            parsed_data={"deleted": deleted_count, "mb_freed": round(mb_freed, 1)},
        )
        log_debug(
            f"Removed {deleted_count} old debug file(s), freed {mb_freed:.1f} MB",
            hook_name="session-init",
        )


def _cleanup_session_env() -> None:
    """Clean up empty session-env directories."""
    session_env_dir = Path.home() / ".claude" / "session-env"
    if not session_env_dir.exists():
        return

    deleted_count = 0
    for session_dir in session_env_dir.iterdir():
        try:
            if session_dir.is_dir() and not any(session_dir.iterdir()):
                session_dir.rmdir()
                deleted_count += 1
        except OSError:
            continue

    if deleted_count > 0:
        log_debug(
            "Cleaned up empty session-env directories",
            hook_name="session-init",
            parsed_data={"deleted": deleted_count},
        )
        log_debug(
            f"Removed {deleted_count} empty session-env dir(s)",
            hook_name="session-init",
        )


def _normalize_hook_cmd(cmd: str) -> str:
    """Normalize hook command paths for comparison (resolve ~, $HOME, quotes)."""
    home = str(Path.home())
    c = cmd.replace('"', "").replace("'", "")
    c = c.replace("$HOME", home).replace("~", home)
    # Extract just the script basename for fuzzy matching
    parts = c.split()
    for p in parts:
        if p.endswith(".py") or p.endswith(".sh"):
            return Path(p).name
    return c


def _extract_hook_commands(settings: dict) -> set[str]:
    """Extract all normalized hook script names from a settings dict."""
    commands: set[str] = set()
    hooks = settings.get("hooks", {})
    for _event, entries in hooks.items():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            for hook in entry.get("hooks", []):
                cmd = hook.get("command", "")
                if cmd:
                    commands.add(_normalize_hook_cmd(cmd))
    return commands


def _check_hook_overlap(cwd: str) -> None:
    """Warn if project .claude/settings.json duplicates global hooks."""
    if not cwd:
        return
    project_settings = Path(cwd) / ".claude" / "settings.json"
    global_settings = Path.home() / ".claude" / "settings.json"
    if not project_settings.exists() or not global_settings.exists():
        return
    # Don't warn if project settings is a symlink (intentional)
    if project_settings.is_symlink():
        return
    try:
        proj = json.loads(project_settings.read_text())
        glob = json.loads(global_settings.resolve().read_text())
    except (json.JSONDecodeError, IOError):
        return
    proj_cmds = _extract_hook_commands(proj)
    glob_cmds = _extract_hook_commands(glob)
    overlap = proj_cmds & glob_cmds
    if overlap:
        names = ", ".join(sorted(overlap))
        print(
            f"[session-init] Warning: .claude/settings.json duplicates {len(overlap)} "
            f"global hook(s): {names}. Remove from project settings to prevent "
            f"double execution."
        )
        log_debug(
            f"Hook overlap detected: {names}",
            hook_name="session-init",
            parsed_data={"overlap": sorted(overlap)},
        )


def _cleanup_doc_debt(cwd: str, max_age_days: int = 7) -> None:
    """Remove doc-debt entries older than max_age_days."""
    if not cwd:
        return
    debt_path = Path(cwd) / ".claude" / "doc-debt.json"
    if not debt_path.exists():
        return
    try:
        debt = json.loads(debt_path.read_text())
        entries = debt.get("entries", [])
        if not entries:
            return

        from datetime import timedelta
        cutoff = (
            datetime.now(timezone.utc) - timedelta(days=max_age_days)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        kept = [e for e in entries if e.get("ts", "") > cutoff]
        if len(kept) < len(entries):
            debt["entries"] = kept
            debt_path.write_text(json.dumps(debt, indent=2))
            log_debug(
                f"Cleaned doc-debt: {len(entries) - len(kept)} old entries removed",
                hook_name="session-init",
            )
    except (json.JSONDecodeError, IOError):
        pass


def _rotate_hook_metrics(max_entries: int = 100) -> None:
    """Rotate hook-metrics.jsonl to keep only the most recent entries."""
    metrics_path = Path.home() / ".claude" / "hook-metrics.jsonl"
    if not metrics_path.exists():
        return
    try:
        lines = metrics_path.read_text().strip().split("\n")
        if len(lines) <= max_entries:
            return
        kept = lines[-max_entries:]
        metrics_path.write_text("\n".join(kept) + "\n")
        log_debug(
            f"Rotated hook metrics: {len(lines)} -> {len(kept)}",
            hook_name="session-init",
        )
    except (IOError, OSError):
        pass


def _validate_hook_health() -> None:
    """Validate that all hooks referenced in settings.json exist and parse.

    Catches _common.py breakage (single point of failure for 11+ hooks)
    and missing hook files before they cause cascading failures during
    the session.
    """
    import ast

    global_settings = Path.home() / ".claude" / "settings.json"
    if not global_settings.exists():
        return

    try:
        settings = json.loads(global_settings.resolve().read_text())
    except (json.JSONDecodeError, IOError):
        return

    hooks_dir = Path.home() / ".claude" / "hooks"
    broken = []
    checked = 0

    hooks_config = settings.get("hooks", {})
    for _event, entries in hooks_config.items():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            for hook in entry.get("hooks", []):
                if hook.get("type") != "command":
                    continue
                cmd = hook.get("command", "")
                if not cmd:
                    continue
                # Extract Python script path from command
                parts = cmd.replace('"', "").replace("'", "").split()
                script_path = None
                for p in parts:
                    if p.endswith(".py"):
                        expanded = p.replace("$HOME", str(Path.home())).replace(
                            "~", str(Path.home())
                        )
                        script_path = Path(expanded)
                        break
                if not script_path:
                    continue

                checked += 1
                if not script_path.exists():
                    broken.append(f"{script_path.name} (missing)")
                    continue

                # Syntax check (catches _common.py import-chain failures)
                try:
                    ast.parse(script_path.read_text())
                except SyntaxError as e:
                    broken.append(f"{script_path.name} (syntax error: {e.msg} line {e.lineno})")

    if broken:
        names = "; ".join(broken[:5])
        print(
            f"[hook-health] WARNING: {len(broken)} hook(s) have problems: {names}. "
            "Fix before they cause silent failures during the session."
        )
        log_debug(
            f"Hook health check found {len(broken)} problems",
            hook_name="session-init",
            parsed_data={"broken": broken, "total_checked": checked},
        )

    # Also validate shared modules (single point of failure)
    for module_name in ("_common.py", "_session.py", "_memory.py", "_scoring.py"):
        module_path = hooks_dir / module_name
        if module_path.exists():
            try:
                ast.parse(module_path.read_text())
            except SyntaxError as e:
                print(
                    f"[hook-health] CRITICAL: {module_name} has syntax error "
                    f"(line {e.lineno}: {e.msg}). ALL hooks will fail."
                )


if __name__ == "__main__":
    with timed_hook("session-init"):
        main()
