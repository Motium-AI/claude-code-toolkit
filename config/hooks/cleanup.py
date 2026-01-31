#!/usr/bin/env python3
"""
Cleanup Script - Reclaim disk space from Claude Code session data.

This script cleans up old session transcripts, debug logs, and other accumulated
data that can slow down Claude Code over time.

Usage:
    python3 cleanup.py [--dry-run] [--aggressive] [--sessions N] [--days N]

Options:
    --dry-run       Show what would be deleted without actually deleting
    --aggressive    Use aggressive settings (10 sessions, 14 days)
    --sessions N    Keep N most recent sessions per project (default: 20)
    --days N        Delete sessions older than N days (default: 30)
"""

from __future__ import annotations

import argparse
import shutil
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class CleanupStats:
    """Track cleanup statistics."""
    files_deleted: int = 0
    dirs_deleted: int = 0
    bytes_freed: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def mb_freed(self) -> float:
        return self.bytes_freed / (1024 * 1024)

    @property
    def gb_freed(self) -> float:
        return self.bytes_freed / (1024 * 1024 * 1024)


def cleanup_sessions(
    max_per_project: int = 20,
    max_age_days: int = 30,
    dry_run: bool = False,
) -> CleanupStats:
    """Clean up old session transcript .jsonl files."""
    stats = CleanupStats()
    projects_dir = Path.home() / ".claude" / "projects"

    if not projects_dir.exists():
        return stats

    cutoff_time = time.time() - (max_age_days * 24 * 60 * 60)

    for project_dir in projects_dir.iterdir():
        if not project_dir.is_dir():
            continue

        # Get all session .jsonl files sorted by mtime (newest first)
        session_files = []
        for f in project_dir.glob("*.jsonl"):
            try:
                stat = f.stat()
                session_files.append((f, stat.st_mtime, stat.st_size))
            except OSError as e:
                stats.errors.append(f"Error accessing {f}: {e}")
                continue

        session_files.sort(key=lambda x: x[1], reverse=True)

        # Delete excess sessions and old sessions
        for i, (session_file, mtime, size) in enumerate(session_files):
            should_delete = i >= max_per_project or mtime < cutoff_time
            if should_delete:
                if dry_run:
                    print(f"  Would delete: {session_file.name} ({size / 1024 / 1024:.1f} MB)")
                    stats.files_deleted += 1
                    stats.bytes_freed += size
                else:
                    try:
                        session_file.unlink()
                        stats.files_deleted += 1
                        stats.bytes_freed += size

                        # Also delete corresponding session directory if exists
                        session_dir = project_dir / session_file.stem
                        if session_dir.is_dir():
                            dir_size = sum(f.stat().st_size for f in session_dir.rglob("*") if f.is_file())
                            shutil.rmtree(session_dir, ignore_errors=True)
                            stats.dirs_deleted += 1
                            stats.bytes_freed += dir_size
                    except OSError as e:
                        stats.errors.append(f"Error deleting {session_file}: {e}")

    return stats


def cleanup_debug_files(max_age_days: int = 7, dry_run: bool = False) -> CleanupStats:
    """Clean up old debug log files."""
    stats = CleanupStats()
    debug_dir = Path.home() / ".claude" / "debug"

    if not debug_dir.exists():
        return stats

    cutoff_time = time.time() - (max_age_days * 24 * 60 * 60)

    for item in debug_dir.iterdir():
        try:
            stat = item.stat()
            if stat.st_mtime < cutoff_time:
                if item.is_file():
                    size = stat.st_size
                    if dry_run:
                        print(f"  Would delete: debug/{item.name}")
                    else:
                        item.unlink()
                    stats.files_deleted += 1
                    stats.bytes_freed += size
                elif item.is_dir():
                    size = sum(f.stat().st_size for f in item.rglob("*") if f.is_file())
                    if dry_run:
                        print(f"  Would delete: debug/{item.name}/")
                    else:
                        shutil.rmtree(item, ignore_errors=True)
                    stats.dirs_deleted += 1
                    stats.bytes_freed += size
        except OSError as e:
            stats.errors.append(f"Error processing {item}: {e}")

    return stats


def cleanup_session_env(dry_run: bool = False) -> CleanupStats:
    """Clean up empty session-env directories."""
    stats = CleanupStats()
    session_env_dir = Path.home() / ".claude" / "session-env"

    if not session_env_dir.exists():
        return stats

    for session_dir in session_env_dir.iterdir():
        try:
            if session_dir.is_dir() and not any(session_dir.iterdir()):
                if dry_run:
                    print(f"  Would delete: session-env/{session_dir.name}/")
                else:
                    session_dir.rmdir()
                stats.dirs_deleted += 1
        except OSError:
            pass

    return stats


def cleanup_todos(max_age_days: int = 30, dry_run: bool = False) -> CleanupStats:
    """Clean up old todo files."""
    stats = CleanupStats()
    todos_dir = Path.home() / ".claude" / "todos"

    if not todos_dir.exists():
        return stats

    cutoff_time = time.time() - (max_age_days * 24 * 60 * 60)

    for todo_file in todos_dir.iterdir():
        try:
            if todo_file.is_file():
                stat = todo_file.stat()
                if stat.st_mtime < cutoff_time:
                    if dry_run:
                        print(f"  Would delete: todos/{todo_file.name}")
                    else:
                        todo_file.unlink()
                    stats.files_deleted += 1
                    stats.bytes_freed += stat.st_size
        except OSError as e:
            stats.errors.append(f"Error processing {todo_file}: {e}")

    return stats


def cleanup_history(max_entries: int = 1000, dry_run: bool = False) -> CleanupStats:
    """Truncate history.jsonl to keep only recent entries."""
    stats = CleanupStats()
    history_file = Path.home() / ".claude" / "history.jsonl"

    if not history_file.exists():
        return stats

    try:
        original_size = history_file.stat().st_size
        lines = history_file.read_text().splitlines()

        if len(lines) > max_entries:
            entries_to_remove = len(lines) - max_entries
            if dry_run:
                print(f"  Would truncate history from {len(lines)} to {max_entries} entries")
                stats.files_deleted = entries_to_remove
                # Estimate size reduction
                avg_line_size = original_size / len(lines)
                stats.bytes_freed = int(entries_to_remove * avg_line_size)
            else:
                # Keep the most recent entries
                new_content = "\n".join(lines[-max_entries:]) + "\n"
                history_file.write_text(new_content)
                new_size = history_file.stat().st_size
                stats.bytes_freed = original_size - new_size
                stats.files_deleted = entries_to_remove
    except OSError as e:
        stats.errors.append(f"Error processing history: {e}")

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Clean up Claude Code session data to reclaim disk space."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting",
    )
    parser.add_argument(
        "--aggressive",
        action="store_true",
        help="Use aggressive settings (10 sessions, 14 days)",
    )
    parser.add_argument(
        "--sessions",
        type=int,
        default=None,
        help="Keep N most recent sessions per project (default: 20)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=None,
        help="Delete sessions older than N days (default: 30)",
    )
    args = parser.parse_args()

    # Determine settings
    if args.aggressive:
        max_sessions = 10
        max_days = 14
    else:
        max_sessions = args.sessions or 20
        max_days = args.days or 30

    dry_run = args.dry_run
    mode = "DRY RUN" if dry_run else "CLEANUP"

    print(f"\n{'=' * 60}")
    print(f"Claude Code Cleanup - {mode}")
    print(f"{'=' * 60}")
    print(f"Settings: Keep {max_sessions} sessions/project, delete >{max_days} days old")
    print()

    total_stats = CleanupStats()

    # 1. Session transcripts
    print("Session transcripts (~/.claude/projects/)...")
    stats = cleanup_sessions(max_sessions, max_days, dry_run)
    total_stats.files_deleted += stats.files_deleted
    total_stats.dirs_deleted += stats.dirs_deleted
    total_stats.bytes_freed += stats.bytes_freed
    total_stats.errors.extend(stats.errors)
    print(f"  -> {stats.files_deleted} files, {stats.dirs_deleted} dirs, {stats.mb_freed:.1f} MB")

    # 2. Debug logs
    print("\nDebug logs (~/.claude/debug/)...")
    stats = cleanup_debug_files(7, dry_run)
    total_stats.files_deleted += stats.files_deleted
    total_stats.dirs_deleted += stats.dirs_deleted
    total_stats.bytes_freed += stats.bytes_freed
    total_stats.errors.extend(stats.errors)
    print(f"  -> {stats.files_deleted} files, {stats.dirs_deleted} dirs, {stats.mb_freed:.1f} MB")

    # 3. Empty session-env directories
    print("\nEmpty session-env directories...")
    stats = cleanup_session_env(dry_run)
    total_stats.dirs_deleted += stats.dirs_deleted
    print(f"  -> {stats.dirs_deleted} empty directories")

    # 4. Old todos
    print("\nOld todo files (~/.claude/todos/)...")
    stats = cleanup_todos(max_days, dry_run)
    total_stats.files_deleted += stats.files_deleted
    total_stats.bytes_freed += stats.bytes_freed
    total_stats.errors.extend(stats.errors)
    print(f"  -> {stats.files_deleted} files, {stats.mb_freed:.1f} MB")

    # 5. History truncation
    print("\nHistory file (~/.claude/history.jsonl)...")
    stats = cleanup_history(1000, dry_run)
    if stats.files_deleted > 0:
        total_stats.bytes_freed += stats.bytes_freed
        print(f"  -> Removed {stats.files_deleted} old entries, {stats.mb_freed:.1f} MB")
    else:
        print("  -> Already within limit")

    # Summary
    print()
    print(f"{'=' * 60}")
    print("SUMMARY")
    print(f"{'=' * 60}")
    action = "Would free" if dry_run else "Freed"
    if total_stats.gb_freed >= 1:
        print(f"{action}: {total_stats.gb_freed:.2f} GB")
    else:
        print(f"{action}: {total_stats.mb_freed:.1f} MB")
    print(f"Files: {total_stats.files_deleted}")
    print(f"Directories: {total_stats.dirs_deleted}")

    if total_stats.errors:
        print(f"\nErrors encountered: {len(total_stats.errors)}")
        for error in total_stats.errors[:5]:
            print(f"  - {error}")
        if len(total_stats.errors) > 5:
            print(f"  ... and {len(total_stats.errors) - 5} more")

    if dry_run:
        print("\nRun without --dry-run to actually delete these files.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
