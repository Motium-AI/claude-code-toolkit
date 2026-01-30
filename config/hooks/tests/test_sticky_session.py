#!/usr/bin/env python3
"""
Comprehensive tests for Sticky Session Mode + Session Guard implementation.

Tests the following features:
1. State persistence across task completions (cleanup_checkpoint_only)
2. State reset between tasks (reset_state_for_next_task)
3. TTL expiry (8-hour window)
4. Session binding (session_id validation)
5. Session guard (concurrent session detection)
6. Deactivation commands (/appfix off, /godo off)
7. Backward compatibility (old state files without session_id)
8. Cross-repo detection (user-level state)

Run with: python3 -m pytest tests/test_sticky_session.py -v
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

# Hook scripts directory
HOOKS_DIR = Path(__file__).parent.parent


def run_hook(
    hook_name: str, stdin_data: dict, cwd: str | None = None
) -> subprocess.CompletedProcess:
    """Run a hook script as a subprocess with JSON stdin."""
    hook_path = HOOKS_DIR / hook_name
    return subprocess.run(
        [sys.executable, str(hook_path)],
        input=json.dumps(stdin_data),
        capture_output=True,
        text=True,
        timeout=10,
        cwd=cwd,
    )


def make_state_dir(
    tmpdir: str, state: dict, filename: str = "appfix-state.json"
) -> Path:
    """Create .claude/ directory with a state file in tmpdir."""
    claude_dir = Path(tmpdir) / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    state_path = claude_dir / filename
    state_path.write_text(json.dumps(state))
    return state_path


def find_state_file(tmpdir: str, base_name: str = "appfix-state") -> Path | None:
    """Find a state file (PID-scoped or legacy) in .claude/ directory."""
    claude_dir = Path(tmpdir) / ".claude"
    if not claude_dir.exists():
        return None
    scoped = sorted(claude_dir.glob(f"{base_name}.*.json"))
    if scoped:
        return scoped[0]
    legacy = claude_dir / f"{base_name}.json"
    return legacy if legacy.exists() else None


def make_checkpoint(tmpdir: str, checkpoint: dict) -> Path:
    """Create completion-checkpoint.json in .claude/."""
    claude_dir = Path(tmpdir) / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = claude_dir / "completion-checkpoint.json"
    checkpoint_path.write_text(json.dumps(checkpoint))
    return checkpoint_path


def now_iso() -> str:
    """Return current timestamp in ISO format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def hours_ago_iso(hours: int) -> str:
    """Return ISO timestamp from N hours ago."""
    dt = datetime.now(timezone.utc) - timedelta(hours=hours)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


# ============================================================================
# Direct Function Tests (_common.py utilities)
# ============================================================================


class TestTTLExpiry:
    """Tests for is_state_expired() function."""

    def setup_method(self):
        # Import _common functions for direct testing
        sys.path.insert(0, str(HOOKS_DIR))
        from _common import is_state_expired

        self.is_state_expired = is_state_expired

    def test_fresh_state_not_expired(self):
        """State with recent last_activity_at should not be expired."""
        state = {"last_activity_at": now_iso()}
        assert not self.is_state_expired(state)

    def test_old_state_expired(self):
        """State older than 8 hours should be expired."""
        state = {"last_activity_at": hours_ago_iso(9)}
        assert self.is_state_expired(state)

    def test_just_under_8_hours_not_expired(self):
        """State just under 8 hours should NOT be expired (boundary test)."""
        # 7 hours 59 minutes = not expired (using > not >=)
        # Note: We use 7 hours because exact 8 hours has race conditions due to test timing
        state = {"last_activity_at": hours_ago_iso(7)}
        assert not self.is_state_expired(state)

    def test_fallback_to_started_at(self):
        """Should use started_at if last_activity_at is missing."""
        state = {"started_at": hours_ago_iso(9)}
        assert self.is_state_expired(state)

    def test_missing_timestamps_expired(self):
        """State with no timestamps should be treated as expired."""
        state = {}
        assert self.is_state_expired(state)

    def test_malformed_timestamp_expired(self):
        """State with invalid timestamp format should be treated as expired."""
        state = {"last_activity_at": "not-a-timestamp"}
        assert self.is_state_expired(state)

    def test_custom_ttl(self):
        """Should respect custom TTL parameter."""
        state = {"last_activity_at": hours_ago_iso(3)}
        assert not self.is_state_expired(state, ttl_hours=4)
        assert self.is_state_expired(state, ttl_hours=2)


class TestSessionBinding:
    """Tests for is_state_for_session() function."""

    def setup_method(self):
        sys.path.insert(0, str(HOOKS_DIR))
        from _common import is_state_for_session

        self.is_state_for_session = is_state_for_session

    def test_matching_session_id(self):
        """State with matching session_id should return True."""
        state = {"session_id": "abc123"}
        assert self.is_state_for_session(state, "abc123")

    def test_different_session_id(self):
        """State with different session_id should return False."""
        state = {"session_id": "abc123"}
        assert not self.is_state_for_session(state, "xyz789")

    def test_no_session_id_in_state_backward_compat(self):
        """Old state without session_id should match any session (backward compat)."""
        state = {"iteration": 1, "started_at": now_iso()}
        assert self.is_state_for_session(state, "any-session")

    def test_empty_session_id_arg_matches_all(self):
        """Empty session_id argument should match all states."""
        state = {"session_id": "abc123"}
        assert self.is_state_for_session(state, "")

    def test_empty_session_id_in_state(self):
        """Empty session_id in state should match (backward compat)."""
        state = {"session_id": ""}
        assert self.is_state_for_session(state, "any-session")


class TestCleanupCheckpointOnly:
    """Tests for cleanup_checkpoint_only() function."""

    def setup_method(self):
        sys.path.insert(0, str(HOOKS_DIR))
        from _common import cleanup_checkpoint_only

        self.cleanup_checkpoint_only = cleanup_checkpoint_only
        self.tmpdir = tempfile.mkdtemp(prefix="test-cleanup-")

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_deletes_checkpoint_only(self):
        """Should delete only completion-checkpoint.json, not mode state."""
        # Create state file and checkpoint
        make_state_dir(self.tmpdir, {"iteration": 1})
        make_checkpoint(self.tmpdir, {"is_job_complete": True})

        state_path = Path(self.tmpdir) / ".claude" / "appfix-state.json"
        checkpoint_path = Path(self.tmpdir) / ".claude" / "completion-checkpoint.json"

        assert state_path.exists()
        assert checkpoint_path.exists()

        deleted = self.cleanup_checkpoint_only(self.tmpdir)

        # cleanup_checkpoint_only returns full paths
        assert len(deleted) == 1
        assert "completion-checkpoint.json" in deleted[0]
        assert not checkpoint_path.exists()
        assert state_path.exists()  # State file should survive!

    def test_no_checkpoint_returns_empty(self):
        """Should return empty list if no checkpoint exists."""
        make_state_dir(self.tmpdir, {"iteration": 1})
        deleted = self.cleanup_checkpoint_only(self.tmpdir)
        assert deleted == []


class TestResetStateForNextTask:
    """Tests for reset_state_for_next_task() function."""

    def setup_method(self):
        sys.path.insert(0, str(HOOKS_DIR))
        from _common import reset_state_for_next_task

        self.reset_state_for_next_task = reset_state_for_next_task
        self.tmpdir = tempfile.mkdtemp(prefix="test-reset-")

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_increments_iteration(self):
        """Should increment iteration counter."""
        state = {"iteration": 1, "plan_mode_completed": True}
        make_state_dir(self.tmpdir, state)

        result = self.reset_state_for_next_task(self.tmpdir)
        assert result is True

        state_path = Path(self.tmpdir) / ".claude" / "appfix-state.json"
        updated = json.loads(state_path.read_text())
        assert updated["iteration"] == 2

    def test_resets_plan_mode_completed(self):
        """Should reset plan_mode_completed to False."""
        state = {"iteration": 1, "plan_mode_completed": True}
        make_state_dir(self.tmpdir, state)

        self.reset_state_for_next_task(self.tmpdir)

        state_path = Path(self.tmpdir) / ".claude" / "appfix-state.json"
        updated = json.loads(state_path.read_text())
        assert updated["plan_mode_completed"] is False

    def test_updates_last_activity_at(self):
        """Should update last_activity_at timestamp."""
        old_time = hours_ago_iso(1)
        state = {"iteration": 1, "last_activity_at": old_time}
        make_state_dir(self.tmpdir, state)

        self.reset_state_for_next_task(self.tmpdir)

        state_path = Path(self.tmpdir) / ".claude" / "appfix-state.json"
        updated = json.loads(state_path.read_text())
        assert updated["last_activity_at"] != old_time

    def test_clears_per_task_fields(self):
        """Should clear verification_evidence and services."""
        state = {
            "iteration": 1,
            "verification_evidence": {"url": "test"},
            "services": {"frontend": {"healthy": True}},
        }
        make_state_dir(self.tmpdir, state)

        self.reset_state_for_next_task(self.tmpdir)

        state_path = Path(self.tmpdir) / ".claude" / "appfix-state.json"
        updated = json.loads(state_path.read_text())
        assert updated.get("verification_evidence") is None
        assert updated.get("services") == {}

    def test_no_state_returns_false(self):
        """Should return False if no state file exists."""
        result = self.reset_state_for_next_task(self.tmpdir)
        assert result is False


class TestCleanupExpiredState:
    """Tests for cleanup_expired_state() function."""

    def setup_method(self):
        sys.path.insert(0, str(HOOKS_DIR))
        from _common import cleanup_expired_state

        self.cleanup_expired_state = cleanup_expired_state
        self.tmpdir = tempfile.mkdtemp(prefix="test-expired-")
        # Also track user-level state for cleanup
        self.user_state_dir = Path.home() / ".claude"

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        # Clean up any test user-level state
        for f in ["appfix-state.json", "forge-state.json"]:
            p = self.user_state_dir / f
            if p.exists():
                try:
                    state = json.loads(p.read_text())
                    if state.get("session_id", "").startswith("test-"):
                        p.unlink()
                except Exception:
                    pass

    def test_deletes_expired_state(self):
        """Should delete state that has expired (TTL exceeded)."""
        state = {"last_activity_at": hours_ago_iso(9)}
        make_state_dir(self.tmpdir, state)

        deleted = self.cleanup_expired_state(self.tmpdir, "current-session")

        state_path = Path(self.tmpdir) / ".claude" / "appfix-state.json"
        assert not state_path.exists()
        assert len(deleted) > 0

    def test_deletes_foreign_session_state(self):
        """Should delete state from different session (even if not expired)."""
        state = {"session_id": "old-session", "last_activity_at": now_iso()}
        make_state_dir(self.tmpdir, state)

        deleted = self.cleanup_expired_state(self.tmpdir, "new-session")

        state_path = Path(self.tmpdir) / ".claude" / "appfix-state.json"
        assert not state_path.exists()
        assert len(deleted) > 0

    def test_keeps_same_session_state(self):
        """Should keep state from same session."""
        state = {"session_id": "my-session", "last_activity_at": now_iso()}
        make_state_dir(self.tmpdir, state)

        deleted = self.cleanup_expired_state(self.tmpdir, "my-session")

        state_path = Path(self.tmpdir) / ".claude" / "appfix-state.json"
        assert state_path.exists()
        assert deleted == []

    def test_keeps_old_format_within_ttl(self):
        """Should keep old format state (no session_id) if within TTL."""
        state = {"iteration": 1, "last_activity_at": now_iso()}  # No session_id
        make_state_dir(self.tmpdir, state)

        deleted = self.cleanup_expired_state(self.tmpdir, "any-session")

        state_path = Path(self.tmpdir) / ".claude" / "appfix-state.json"
        assert state_path.exists()
        assert deleted == []


class TestPidAlive:
    """Tests for is_pid_alive() function."""

    def setup_method(self):
        sys.path.insert(0, str(HOOKS_DIR))
        from _common import is_pid_alive

        self.is_pid_alive = is_pid_alive

    def test_current_process_alive(self):
        """Current process should be alive."""
        assert self.is_pid_alive(os.getpid())

    def test_nonexistent_pid_dead(self):
        """Non-existent PID should be dead."""
        # Use a very high PID that's unlikely to exist
        assert not self.is_pid_alive(999999999)

    def test_pid_zero_dead(self):
        """PID 0 should be treated as dead (invalid)."""
        assert not self.is_pid_alive(0)

    def test_negative_pid_dead(self):
        """Negative PID should be treated as dead."""
        assert not self.is_pid_alive(-1)


# ============================================================================
# Integration Tests (Hook Subprocess)
# ============================================================================


class TestSkillStateInitializerDeactivation:
    """Tests for /appfix off and /godo off deactivation."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp(prefix="test-deactivate-")

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        # Clean up user-level state too
        for f in ["appfix-state.json", "forge-state.json"]:
            p = Path.home() / ".claude" / f
            if p.exists():
                try:
                    p.unlink()
                except Exception:
                    pass

    def test_appfix_off_deletes_state(self):
        """'/appfix off' should delete appfix state files."""
        make_state_dir(self.tmpdir, {"iteration": 1})

        result = run_hook(
            "skill-state-initializer.py",
            {"cwd": self.tmpdir, "prompt": "/appfix off", "session_id": "test-sess"},
        )

        state_path = Path(self.tmpdir) / ".claude" / "appfix-state.json"
        assert not state_path.exists()
        assert (
            "deactivated" in result.stdout.lower()
            or "cleaned up" in result.stdout.lower()
        )

    def test_forge_off_deletes_state(self):
        """'/forge off' should delete forge state files."""
        make_state_dir(self.tmpdir, {"iteration": 1}, filename="forge-state.json")

        run_hook(
            "skill-state-initializer.py",
            {"cwd": self.tmpdir, "prompt": "/forge off", "session_id": "test-sess"},
        )

        state_path = Path(self.tmpdir) / ".claude" / "forge-state.json"
        assert not state_path.exists()

    def test_stop_autonomous_mode_deletes_state(self):
        """'stop autonomous mode' should delete state files."""
        make_state_dir(self.tmpdir, {"iteration": 1})

        run_hook(
            "skill-state-initializer.py",
            {
                "cwd": self.tmpdir,
                "prompt": "stop autonomous mode",
                "session_id": "test",
            },
        )

        state_path = Path(self.tmpdir) / ".claude" / "appfix-state.json"
        assert not state_path.exists()


class TestSkillStateInitializerActivation:
    """Tests for skill activation with session binding."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp(prefix="test-activate-")

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        # Clean up user-level state
        for f in ["appfix-state.json", "forge-state.json"]:
            p = Path.home() / ".claude" / f
            if p.exists():
                try:
                    p.unlink()
                except Exception:
                    pass

    def test_appfix_creates_state_with_session_id(self):
        """'/appfix' should create state with session_id."""
        run_hook(
            "skill-state-initializer.py",
            {"cwd": self.tmpdir, "prompt": "/appfix", "session_id": "test-session-123"},
        )

        state_file = find_state_file(self.tmpdir, "appfix-state")
        assert state_file is not None, "State file not created"

        state = json.loads(state_file.read_text())
        assert state.get("session_id") == "test-session-123"
        assert "last_activity_at" in state

    def test_reuses_existing_valid_state(self):
        """Should reuse existing state for same session."""
        # Create existing state
        existing_state = {
            "iteration": 3,
            "session_id": "test-session-123",
            "last_activity_at": now_iso(),
        }
        make_state_dir(self.tmpdir, existing_state)

        result = run_hook(
            "skill-state-initializer.py",
            {"cwd": self.tmpdir, "prompt": "/appfix", "session_id": "test-session-123"},
        )

        # Should reuse, not recreate
        assert (
            "reusing" in result.stdout.lower()
            or "already active" in result.stdout.lower()
        )

        # Iteration should still be 3
        state_path = Path(self.tmpdir) / ".claude" / "appfix-state.json"
        state = json.loads(state_path.read_text())
        assert state["iteration"] == 3


class TestSessionSnapshot:
    """Tests for session-snapshot.py SessionStart hook."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp(prefix="test-snapshot-")
        # Initialize as git repo
        subprocess.run(["git", "init", "-q"], cwd=self.tmpdir)
        subprocess.run(
            ["git", "commit", "--allow-empty", "-m", "init", "-q"], cwd=self.tmpdir
        )

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        # Clean up session owner file
        owner_path = Path(self.tmpdir) / ".claude" / "session-owner.json"
        if owner_path.exists():
            try:
                owner_path.unlink()
            except Exception:
                pass

    def test_creates_snapshot_with_session_id(self):
        """Should create snapshot with session_id (PID-scoped or legacy)."""
        run_hook(
            "session-snapshot.py",
            {"cwd": self.tmpdir, "session_id": "test-session-456"},
        )

        snapshot_file = find_state_file(self.tmpdir, "session-snapshot")
        assert snapshot_file is not None, "Snapshot file not created"

        snapshot = json.loads(snapshot_file.read_text())
        assert snapshot.get("session_id") == "test-session-456"
        assert "diff_hash_at_start" in snapshot

    def test_creates_session_owner_file(self):
        """Should create session-owner.json with PID."""
        run_hook(
            "session-snapshot.py",
            {"cwd": self.tmpdir, "session_id": "test-session-789"},
        )

        owner_path = Path(self.tmpdir) / ".claude" / "session-owner.json"
        assert owner_path.exists()

        owner = json.loads(owner_path.read_text())
        assert owner.get("session_id") == "test-session-789"
        assert "pid" in owner
        assert "started_at" in owner

    def test_warns_on_concurrent_session(self):
        """Should warn if another session is active with live PID."""
        # Create existing owner with current process PID (known to be alive)
        owner_dir = Path(self.tmpdir) / ".claude"
        owner_dir.mkdir(parents=True, exist_ok=True)
        existing_owner = {
            "session_id": "old-session",
            "pid": os.getpid(),  # This PID is alive
            "started_at": now_iso(),
        }
        (owner_dir / "session-owner.json").write_text(json.dumps(existing_owner))

        result = run_hook(
            "session-snapshot.py",
            {"cwd": self.tmpdir, "session_id": "new-session"},
        )

        # Should print warning
        assert "warning" in result.stdout.lower() or "another" in result.stdout.lower()

    def test_silent_takeover_dead_session(self):
        """Should silently take over if previous PID is dead."""
        # Create existing owner with dead PID
        owner_dir = Path(self.tmpdir) / ".claude"
        owner_dir.mkdir(parents=True, exist_ok=True)
        existing_owner = {
            "session_id": "dead-session",
            "pid": 999999999,  # Very unlikely to exist
            "started_at": hours_ago_iso(1),
        }
        (owner_dir / "session-owner.json").write_text(json.dumps(existing_owner))

        result = run_hook(
            "session-snapshot.py",
            {"cwd": self.tmpdir, "session_id": "new-session"},
        )

        # Should NOT print warning (silent takeover)
        assert "warning" not in result.stdout.lower()

        # New session should be owner
        owner = json.loads((owner_dir / "session-owner.json").read_text())
        assert owner["session_id"] == "new-session"

    def test_cleans_expired_state_at_start(self):
        """Should clean up expired state files at session start."""
        # Create expired state
        expired_state = {
            "session_id": "old-session",
            "last_activity_at": hours_ago_iso(10),
        }
        make_state_dir(self.tmpdir, expired_state)

        result = run_hook(
            "session-snapshot.py",
            {"cwd": self.tmpdir, "session_id": "new-session"},
        )

        # State should be cleaned
        state_path = Path(self.tmpdir) / ".claude" / "appfix-state.json"
        assert not state_path.exists()
        assert (
            "cleaned up" in result.stdout.lower() or "expired" in result.stdout.lower()
        )


# TestAppfixAutoApprove removed: appfix-auto-approve.py was deleted
# in favor of pretooluse-auto-approve.py (PreToolUse:*)


# ============================================================================
# End-to-End Workflow Tests
# ============================================================================


class TestStickySessionWorkflow:
    """Integration tests for complete sticky session workflow."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp(prefix="test-workflow-")
        # Initialize git repo
        subprocess.run(["git", "init", "-q"], cwd=self.tmpdir)
        subprocess.run(
            ["git", "commit", "--allow-empty", "-m", "init", "-q"], cwd=self.tmpdir
        )
        # Import functions for direct testing
        sys.path.insert(0, str(HOOKS_DIR))
        from _common import (
            cleanup_checkpoint_only,
            reset_state_for_next_task,
            is_autonomous_mode_active,
        )

        self.cleanup_checkpoint_only = cleanup_checkpoint_only
        self.reset_state_for_next_task = reset_state_for_next_task
        self.is_autonomous_mode_active = is_autonomous_mode_active

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_full_sticky_session_lifecycle(self):
        """Test complete lifecycle: activate → task → persist → task → deactivate."""
        session_id = "test-lifecycle-session"

        # 1. Activate appfix mode
        result = run_hook(
            "skill-state-initializer.py",
            {"cwd": self.tmpdir, "prompt": "/appfix", "session_id": session_id},
        )
        assert "activated" in result.stdout.lower() or "active" in result.stdout.lower()

        # 2. Verify mode is active
        assert self.is_autonomous_mode_active(self.tmpdir)

        # 3. Create checkpoint (simulating task completion)
        make_checkpoint(self.tmpdir, {"is_job_complete": True})

        # 4. Simulate stop hook behavior: cleanup checkpoint only
        deleted = self.cleanup_checkpoint_only(self.tmpdir)
        assert len(deleted) >= 1
        assert any("completion-checkpoint" in d for d in deleted)

        # 5. Reset state for next task
        self.reset_state_for_next_task(self.tmpdir)

        # 6. Verify mode STILL active (sticky!)
        assert self.is_autonomous_mode_active(self.tmpdir)

        # 7. Check iteration incremented (PID-scoped or legacy)
        state_file = find_state_file(self.tmpdir, "appfix-state")
        assert state_file is not None
        state = json.loads(state_file.read_text())
        assert state["iteration"] == 2
        assert state["plan_mode_completed"] is False

        # 8. Second task starts - mode should still be active
        result2 = run_hook(
            "skill-state-initializer.py",
            {"cwd": self.tmpdir, "prompt": "/appfix", "session_id": session_id},
        )
        assert (
            "reusing" in result2.stdout.lower()
            or "already active" in result2.stdout.lower()
        )

        # 9. Deactivate
        result3 = run_hook(
            "skill-state-initializer.py",
            {"cwd": self.tmpdir, "prompt": "/appfix off", "session_id": session_id},
        )
        assert (
            "deactivated" in result3.stdout.lower()
            or "cleaned" in result3.stdout.lower()
        )

        # 10. Mode should now be inactive
        assert not self.is_autonomous_mode_active(self.tmpdir)


class TestCornerCases:
    """Tests for edge cases and corner scenarios."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp(prefix="test-corner-")
        sys.path.insert(0, str(HOOKS_DIR))
        from _common import (
            is_state_expired,
            is_state_for_session,
            is_autonomous_mode_active,
        )

        self.is_state_expired = is_state_expired
        self.is_state_for_session = is_state_for_session
        self.is_autonomous_mode_active = is_autonomous_mode_active

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_both_state_files_one_expired(self):
        """When both appfix and forge state exist, only expired one should be cleaned."""
        # Create fresh appfix state
        fresh_state = {"session_id": "sess-1", "last_activity_at": now_iso()}
        make_state_dir(self.tmpdir, fresh_state, filename="appfix-state.json")

        # Create expired forge state
        expired_state = {"session_id": "sess-1", "last_activity_at": hours_ago_iso(10)}
        make_state_dir(self.tmpdir, expired_state, filename="forge-state.json")

        from _common import cleanup_expired_state

        cleanup_expired_state(self.tmpdir, "sess-1")

        # Only forge should be deleted
        appfix_path = Path(self.tmpdir) / ".claude" / "appfix-state.json"
        forge_path = Path(self.tmpdir) / ".claude" / "forge-state.json"
        assert appfix_path.exists()
        assert not forge_path.exists()

    def test_env_var_fallback_no_ttl(self):
        """Environment variable activation should have no TTL check."""
        # This is tested indirectly - env vars are always active
        os.environ["APPFIX_ACTIVE"] = "true"
        try:
            assert self.is_autonomous_mode_active(self.tmpdir)
        finally:
            del os.environ["APPFIX_ACTIVE"]

    def test_unicode_in_session_id(self):
        """Session IDs with unicode should be handled correctly."""
        state = {"session_id": "test-🔥-session", "last_activity_at": now_iso()}
        assert self.is_state_for_session(state, "test-🔥-session")
        assert not self.is_state_for_session(state, "test-session")

    def test_very_long_session_id(self):
        """Very long session IDs should be handled."""
        long_id = "a" * 1000
        state = {"session_id": long_id, "last_activity_at": now_iso()}
        assert self.is_state_for_session(state, long_id)

    def test_concurrent_state_modifications(self):
        """State file modifications during read should not crash."""
        # Create initial state
        state = {"iteration": 1, "last_activity_at": now_iso()}
        make_state_dir(self.tmpdir, state)

        # This tests that the functions handle file I/O correctly
        # (not true concurrency, but basic robustness)
        from _common import reset_state_for_next_task

        result = reset_state_for_next_task(self.tmpdir)
        assert result is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
