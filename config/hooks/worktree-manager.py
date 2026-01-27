#!/usr/bin/env python3
"""
Git Worktree Manager for Parallel Agent Isolation

Provides utilities for creating and managing git worktrees to isolate
parallel agent operations. Each agent gets its own worktree with a
dedicated branch, preventing git operation conflicts.

Usage:
    # Create worktree for an agent
    python3 worktree-manager.py create <agent-id>

    # Cleanup worktree after agent completes
    python3 worktree-manager.py cleanup <agent-id>

    # Merge agent's work back to main branch
    python3 worktree-manager.py merge <agent-id>

    # List all active agent worktrees
    python3 worktree-manager.py list

    # Get worktree path for an agent (returns path to stdout)
    python3 worktree-manager.py path <agent-id>

    # Check if current directory is a worktree
    python3 worktree-manager.py is-worktree

Exit codes:
    0 - Success
    1 - Error (message on stderr)
    2 - Conflict detected (for merge command)
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

# Base directory for all Claude agent worktrees
WORKTREE_BASE = Path(tempfile.gettempdir()) / "claude-worktrees"

# Branch prefix for agent branches
BRANCH_PREFIX = "claude-agent"

# State file tracking active worktrees
STATE_FILE = Path.home() / ".claude" / "worktree-state.json"


def run_git(args: list[str], cwd: str | None = None, check: bool = True) -> subprocess.CompletedProcess:
    """Run a git command and return the result."""
    result = subprocess.run(
        ["git"] + args,
        capture_output=True,
        text=True,
        cwd=cwd,
        timeout=30,
    )
    if check and result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr}")
    return result


def get_main_repo_root(cwd: str | None = None) -> Path:
    """Get the root of the main git repository (not worktree)."""
    result = run_git(["rev-parse", "--git-common-dir"], cwd=cwd)
    git_common = Path(result.stdout.strip())

    # git-common-dir returns the path to .git (or .git/worktrees/xxx for worktrees)
    # We want the parent of .git for the main repo
    if git_common.name == ".git":
        return git_common.parent
    elif "worktrees" in git_common.parts:
        # This is a worktree, find the main repo
        # .git/worktrees/xxx -> .git -> parent
        return git_common.parent.parent.parent
    else:
        return git_common.parent


def is_worktree(cwd: str | None = None) -> bool:
    """Check if the current directory is a git worktree (not the main repo)."""
    try:
        result = run_git(["rev-parse", "--is-inside-work-tree"], cwd=cwd, check=False)
        if result.returncode != 0:
            return False

        # Check if this is the main worktree or a linked worktree
        git_dir = run_git(["rev-parse", "--git-dir"], cwd=cwd)
        git_common = run_git(["rev-parse", "--git-common-dir"], cwd=cwd)

        # If git-dir != git-common-dir, this is a linked worktree
        return git_dir.stdout.strip() != git_common.stdout.strip()
    except (RuntimeError, subprocess.TimeoutExpired):
        return False


def get_worktree_info(cwd: str | None = None) -> dict | None:
    """Get information about the current worktree if in one."""
    if not is_worktree(cwd):
        return None

    try:
        # Get the branch name
        branch = run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd)
        branch_name = branch.stdout.strip()

        # Extract agent ID from branch name if it matches our pattern
        agent_id = None
        if branch_name.startswith(f"{BRANCH_PREFIX}/"):
            agent_id = branch_name[len(f"{BRANCH_PREFIX}/"):]

        # Get worktree path
        worktree_path = run_git(["rev-parse", "--show-toplevel"], cwd=cwd)

        return {
            "branch": branch_name,
            "agent_id": agent_id,
            "path": worktree_path.stdout.strip(),
            "is_claude_worktree": agent_id is not None,
        }
    except (RuntimeError, subprocess.TimeoutExpired):
        return None


def load_state() -> dict:
    """Load worktree state from disk."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except (json.JSONDecodeError, IOError):
            pass
    return {"worktrees": {}}


def save_state(state: dict) -> None:
    """Save worktree state to disk."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def create_worktree(agent_id: str, main_repo: str | None = None) -> Path:
    """
    Create a new git worktree for an agent.

    Args:
        agent_id: Unique identifier for the agent
        main_repo: Path to main repo (defaults to cwd)

    Returns:
        Path to the created worktree
    """
    if main_repo is None:
        main_repo = os.getcwd()

    # Ensure we're in the main repo, not a worktree
    main_repo_root = get_main_repo_root(main_repo)

    branch_name = f"{BRANCH_PREFIX}/{agent_id}"
    worktree_path = WORKTREE_BASE / agent_id

    # Clean up any existing worktree with same ID
    if worktree_path.exists():
        cleanup_worktree(agent_id, main_repo=str(main_repo_root))

    # Ensure worktree base exists
    WORKTREE_BASE.mkdir(parents=True, exist_ok=True)

    # Get current HEAD commit
    head = run_git(["rev-parse", "HEAD"], cwd=str(main_repo_root))
    head_commit = head.stdout.strip()

    # Create branch from current HEAD
    # Delete if exists (from failed previous run)
    run_git(["branch", "-D", branch_name], cwd=str(main_repo_root), check=False)
    run_git(["branch", branch_name, head_commit], cwd=str(main_repo_root))

    # Create worktree
    run_git(["worktree", "add", str(worktree_path), branch_name], cwd=str(main_repo_root))

    # Create .claude directory in worktree for checkpoint isolation
    worktree_claude_dir = worktree_path / ".claude"
    worktree_claude_dir.mkdir(parents=True, exist_ok=True)

    # Create agent-specific state file
    agent_state = {
        "agent_id": agent_id,
        "created_at": datetime.now(timezone.utc).isoformat() + "Z",
        "main_repo": str(main_repo_root),
        "branch": branch_name,
        "base_commit": head_commit,
    }
    (worktree_claude_dir / "worktree-agent-state.json").write_text(
        json.dumps(agent_state, indent=2)
    )

    # Update global state
    state = load_state()
    state["worktrees"][agent_id] = {
        "path": str(worktree_path),
        "branch": branch_name,
        "main_repo": str(main_repo_root),
        "base_commit": head_commit,
        "created_at": agent_state["created_at"],
    }
    save_state(state)

    return worktree_path


def cleanup_worktree(agent_id: str, main_repo: str | None = None) -> bool:
    """
    Remove a worktree and its branch.

    Args:
        agent_id: Unique identifier for the agent
        main_repo: Path to main repo (defaults to finding it from state)

    Returns:
        True if cleanup succeeded
    """
    state = load_state()
    worktree_info = state.get("worktrees", {}).get(agent_id)

    if worktree_info:
        main_repo = worktree_info.get("main_repo", main_repo)
        worktree_path = Path(worktree_info.get("path", WORKTREE_BASE / agent_id))
        branch_name = worktree_info.get("branch", f"{BRANCH_PREFIX}/{agent_id}")
    else:
        worktree_path = WORKTREE_BASE / agent_id
        branch_name = f"{BRANCH_PREFIX}/{agent_id}"
        if main_repo is None:
            main_repo = os.getcwd()
        main_repo = str(get_main_repo_root(main_repo))

    # Remove worktree
    if worktree_path.exists():
        try:
            run_git(["worktree", "remove", "--force", str(worktree_path)], cwd=main_repo, check=False)
        except (RuntimeError, subprocess.TimeoutExpired):
            pass

        # Force remove if git worktree remove failed
        if worktree_path.exists():
            shutil.rmtree(worktree_path, ignore_errors=True)

    # Delete branch
    try:
        run_git(["branch", "-D", branch_name], cwd=main_repo, check=False)
    except (RuntimeError, subprocess.TimeoutExpired):
        pass

    # Update state
    if agent_id in state.get("worktrees", {}):
        del state["worktrees"][agent_id]
        save_state(state)

    return True


def merge_worktree(agent_id: str, main_repo: str | None = None) -> tuple[bool, str]:
    """
    Merge agent's work back to the main branch.

    Uses fast-forward merge if possible, otherwise regular merge.
    If conflict detected, aborts and returns False.

    Args:
        agent_id: Unique identifier for the agent
        main_repo: Path to main repo

    Returns:
        (success, message) tuple
    """
    state = load_state()
    worktree_info = state.get("worktrees", {}).get(agent_id)

    if not worktree_info:
        return False, f"No worktree found for agent {agent_id}"

    main_repo = worktree_info.get("main_repo", main_repo)
    if main_repo is None:
        main_repo = os.getcwd()
    main_repo = str(get_main_repo_root(main_repo))

    branch_name = worktree_info.get("branch", f"{BRANCH_PREFIX}/{agent_id}")

    # Get current branch in main repo
    current = run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=main_repo)
    current_branch = current.stdout.strip()

    # Check for uncommitted changes in main repo
    status = run_git(["status", "--porcelain"], cwd=main_repo)
    if status.stdout.strip():
        return False, "Main repo has uncommitted changes. Commit or stash first."

    # Try fast-forward merge first
    result = run_git(["merge", "--ff-only", branch_name], cwd=main_repo, check=False)
    if result.returncode == 0:
        return True, f"Fast-forward merged {branch_name} into {current_branch}"

    # Try regular merge
    result = run_git(["merge", branch_name, "--no-edit"], cwd=main_repo, check=False)
    if result.returncode == 0:
        return True, f"Merged {branch_name} into {current_branch}"

    # Conflict detected - abort
    run_git(["merge", "--abort"], cwd=main_repo, check=False)
    return False, f"Merge conflict detected between {branch_name} and {current_branch}. Aborting."


def list_worktrees() -> list[dict]:
    """List all active agent worktrees."""
    state = load_state()
    worktrees = []

    for agent_id, info in state.get("worktrees", {}).items():
        worktree_path = Path(info.get("path", ""))
        exists = worktree_path.exists()

        worktrees.append({
            "agent_id": agent_id,
            "path": str(worktree_path),
            "branch": info.get("branch"),
            "main_repo": info.get("main_repo"),
            "created_at": info.get("created_at"),
            "exists": exists,
        })

    return worktrees


def get_worktree_path(agent_id: str) -> Path | None:
    """Get the worktree path for an agent."""
    state = load_state()
    info = state.get("worktrees", {}).get(agent_id)
    if info:
        path = Path(info.get("path", ""))
        if path.exists():
            return path
    return None


def main():
    if len(sys.argv) < 2:
        print("Usage: worktree-manager.py <command> [args]", file=sys.stderr)
        print("Commands: create, cleanup, merge, list, path, is-worktree", file=sys.stderr)
        sys.exit(1)

    command = sys.argv[1]

    try:
        if command == "create":
            if len(sys.argv) < 3:
                print("Usage: worktree-manager.py create <agent-id>", file=sys.stderr)
                sys.exit(1)
            agent_id = sys.argv[2]
            main_repo = sys.argv[3] if len(sys.argv) > 3 else None
            path = create_worktree(agent_id, main_repo)
            print(f"Created worktree at: {path}")
            print(str(path))  # Machine-readable output on last line

        elif command == "cleanup":
            if len(sys.argv) < 3:
                print("Usage: worktree-manager.py cleanup <agent-id>", file=sys.stderr)
                sys.exit(1)
            agent_id = sys.argv[2]
            main_repo = sys.argv[3] if len(sys.argv) > 3 else None
            cleanup_worktree(agent_id, main_repo)
            print(f"Cleaned up worktree for agent: {agent_id}")

        elif command == "merge":
            if len(sys.argv) < 3:
                print("Usage: worktree-manager.py merge <agent-id>", file=sys.stderr)
                sys.exit(1)
            agent_id = sys.argv[2]
            main_repo = sys.argv[3] if len(sys.argv) > 3 else None
            success, message = merge_worktree(agent_id, main_repo)
            print(message)
            sys.exit(0 if success else 2)

        elif command == "list":
            worktrees = list_worktrees()
            if not worktrees:
                print("No active worktrees")
            else:
                for wt in worktrees:
                    status = "active" if wt["exists"] else "missing"
                    print(f"  {wt['agent_id']}: {wt['path']} ({status})")

        elif command == "path":
            if len(sys.argv) < 3:
                print("Usage: worktree-manager.py path <agent-id>", file=sys.stderr)
                sys.exit(1)
            agent_id = sys.argv[2]
            path = get_worktree_path(agent_id)
            if path:
                print(str(path))
            else:
                print(f"No worktree found for agent: {agent_id}", file=sys.stderr)
                sys.exit(1)

        elif command == "is-worktree":
            cwd = sys.argv[2] if len(sys.argv) > 2 else None
            if is_worktree(cwd):
                info = get_worktree_info(cwd)
                print(json.dumps(info, indent=2))
                sys.exit(0)
            else:
                print("Not a worktree")
                sys.exit(1)

        else:
            print(f"Unknown command: {command}", file=sys.stderr)
            sys.exit(1)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
