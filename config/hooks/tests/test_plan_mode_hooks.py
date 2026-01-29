#!/usr/bin/env python3
"""
Integration tests for plan-mode hooks (enforcer, tracker, state initializer).

Tests hooks as subprocesses with simulated JSON stdin, matching the pattern
from test_sv_validators.py. Each test creates an isolated temp directory
with `.claude/` state files and verifies hook behavior via stdout/exit code.

Run with: python3 -m pytest tests/test_plan_mode_hooks.py -v
"""

import json
import subprocess
import sys
import tempfile
import shutil
from datetime import datetime, timezone
from pathlib import Path

# Hook scripts directory
HOOKS_DIR = Path(__file__).parent.parent


def run_hook(
    hook_name: str, stdin_data: dict, cwd: str | None = None
) -> subprocess.CompletedProcess:
    """Run a hook script as a subprocess with JSON stdin.

    Args:
        hook_name: Name of the hook script (e.g., 'plan-mode-enforcer.py')
        stdin_data: Dictionary to pass as JSON via stdin
        cwd: Working directory for the subprocess

    Returns:
        CompletedProcess with stdout, stderr, returncode
    """
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


def enforcer_input(cwd: str, tool_name: str, file_path: str) -> dict:
    """Build PreToolUse input for plan-mode-enforcer."""
    return {
        "cwd": cwd,
        "tool_name": tool_name,
        "tool_input": {"file_path": file_path},
    }


def tracker_input(cwd: str, tool_name: str = "ExitPlanMode") -> dict:
    """Build PostToolUse input for plan-mode-tracker."""
    return {
        "cwd": cwd,
        "tool_name": tool_name,
    }


def initializer_input(cwd: str, prompt: str) -> dict:
    """Build UserPromptSubmit input for skill-state-initializer."""
    return {
        "cwd": cwd,
        "prompt": prompt,
    }


# ============================================================================
# Plan Mode Enforcer Tests
# ============================================================================


class TestPlanModeEnforcer:
    """Tests for plan-mode-enforcer.py PreToolUse hook."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp(prefix="test-enforcer-")
        self.base_state = {
            "iteration": 1,
            "started_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "plan_mode_completed": False,
        }

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_allows_claude_artifacts_when_plan_incomplete(self):
        """`.claude/` paths should ALWAYS be allowed, even before plan mode."""
        make_state_dir(self.tmpdir, self.base_state)
        result = run_hook(
            "plan-mode-enforcer.py",
            enforcer_input(
                self.tmpdir,
                "Write",
                f"{self.tmpdir}/.claude/validation-tests/summary.json",
            ),
        )
        assert result.returncode == 0
        assert result.stdout.strip() == "", (
            f"Expected passthrough, got: {result.stdout}"
        )

    def test_allows_relative_claude_path(self):
        """Relative `.claude/` paths should also be allowed."""
        make_state_dir(self.tmpdir, self.base_state)
        result = run_hook(
            "plan-mode-enforcer.py",
            enforcer_input(self.tmpdir, "Write", ".claude/completion-checkpoint.json"),
        )
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_blocks_code_files_when_plan_incomplete(self):
        """Code files should be BLOCKED when plan_mode_completed=false."""
        make_state_dir(self.tmpdir, self.base_state)
        result = run_hook(
            "plan-mode-enforcer.py",
            enforcer_input(self.tmpdir, "Edit", f"{self.tmpdir}/src/main.py"),
        )
        assert result.returncode == 0
        assert "PLAN MODE REQUIRED" in result.stdout

    def test_blocks_write_to_code_files(self):
        """Write tool to code files should also be blocked."""
        make_state_dir(self.tmpdir, self.base_state)
        result = run_hook(
            "plan-mode-enforcer.py",
            enforcer_input(self.tmpdir, "Write", f"{self.tmpdir}/src/app.tsx"),
        )
        assert result.returncode == 0
        assert "PLAN MODE REQUIRED" in result.stdout

    def test_allows_code_files_after_plan_complete(self):
        """Code files should be allowed after plan_mode_completed=true."""
        state = {**self.base_state, "plan_mode_completed": True}
        make_state_dir(self.tmpdir, state)
        result = run_hook(
            "plan-mode-enforcer.py",
            enforcer_input(self.tmpdir, "Edit", f"{self.tmpdir}/src/main.py"),
        )
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_allows_iteration_gt_1(self):
        """Iteration > 1 should skip enforcement entirely."""
        state = {**self.base_state, "iteration": 2, "plan_mode_completed": False}
        make_state_dir(self.tmpdir, state)
        result = run_hook(
            "plan-mode-enforcer.py",
            enforcer_input(self.tmpdir, "Edit", f"{self.tmpdir}/src/main.py"),
        )
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_passthrough_without_state_file(self):
        """No state file = not in autonomous mode, passthrough."""
        # Don't create any state file
        result = run_hook(
            "plan-mode-enforcer.py",
            enforcer_input(self.tmpdir, "Edit", f"{self.tmpdir}/src/main.py"),
        )
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_allows_plan_files(self):
        """Plan files should always be allowed."""
        make_state_dir(self.tmpdir, self.base_state)
        result = run_hook(
            "plan-mode-enforcer.py",
            enforcer_input(
                self.tmpdir,
                "Write",
                "/Users/test/.claude/plans/my-plan.md",
            ),
        )
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_ignores_non_edit_write_tools(self):
        """Non-Edit/Write tools should always pass through."""
        make_state_dir(self.tmpdir, self.base_state)
        result = run_hook(
            "plan-mode-enforcer.py",
            {"cwd": self.tmpdir, "tool_name": "Read", "tool_input": {}},
        )
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_godo_state_also_enforces(self):
        """godo-state.json should also trigger enforcement."""
        make_state_dir(self.tmpdir, self.base_state, filename="godo-state.json")
        result = run_hook(
            "plan-mode-enforcer.py",
            enforcer_input(self.tmpdir, "Edit", f"{self.tmpdir}/src/main.py"),
        )
        assert result.returncode == 0
        assert "PLAN MODE REQUIRED" in result.stdout


# ============================================================================
# Plan Mode Tracker Tests
# ============================================================================


class TestPlanModeTracker:
    """Tests for plan-mode-tracker.py PostToolUse hook."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp(prefix="test-tracker-")
        self.base_state = {
            "iteration": 1,
            "started_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "plan_mode_completed": False,
        }

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_updates_state_on_exit_plan_mode(self):
        """ExitPlanMode should set plan_mode_completed=true in state file."""
        state_path = make_state_dir(self.tmpdir, self.base_state)
        result = run_hook(
            "plan-mode-tracker.py",
            tracker_input(self.tmpdir, "ExitPlanMode"),
        )
        assert result.returncode == 0

        # Verify state file was updated
        updated_state = json.loads(state_path.read_text())
        assert updated_state["plan_mode_completed"] is True

    def test_no_stdout_on_success(self):
        """Tracker should produce no stdout (avoids hookSpecificOutput issues)."""
        make_state_dir(self.tmpdir, self.base_state)
        result = run_hook(
            "plan-mode-tracker.py",
            tracker_input(self.tmpdir, "ExitPlanMode"),
        )
        assert result.stdout.strip() == "", f"Expected no stdout, got: {result.stdout}"

    def test_ignores_non_exit_plan_mode(self):
        """Non-ExitPlanMode tools should be ignored."""
        state_path = make_state_dir(self.tmpdir, self.base_state)
        result = run_hook(
            "plan-mode-tracker.py",
            tracker_input(self.tmpdir, "Edit"),
        )
        assert result.returncode == 0

        # State should NOT be updated
        state = json.loads(state_path.read_text())
        assert state["plan_mode_completed"] is False

    def test_handles_missing_state_file(self):
        """Missing state file should result in silent exit (not crash)."""
        result = run_hook(
            "plan-mode-tracker.py",
            tracker_input(self.tmpdir, "ExitPlanMode"),
        )
        assert result.returncode == 0

    def test_preserves_other_state_fields(self):
        """Updating plan_mode_completed should not erase other fields."""
        state = {**self.base_state, "services": {"frontend": {"healthy": True}}}
        state_path = make_state_dir(self.tmpdir, state)
        run_hook("plan-mode-tracker.py", tracker_input(self.tmpdir, "ExitPlanMode"))

        updated = json.loads(state_path.read_text())
        assert updated["plan_mode_completed"] is True
        assert updated["services"]["frontend"]["healthy"] is True
        assert updated["iteration"] == 1

    def test_updates_godo_state(self):
        """Should update godo-state.json when that's the active state."""
        state_path = make_state_dir(
            self.tmpdir, self.base_state, filename="godo-state.json"
        )
        run_hook("plan-mode-tracker.py", tracker_input(self.tmpdir, "ExitPlanMode"))

        updated = json.loads(state_path.read_text())
        assert updated["plan_mode_completed"] is True


# ============================================================================
# Skill State Initializer Tests
# ============================================================================


class TestSkillStateInitializer:
    """Tests for skill-state-initializer.py UserPromptSubmit hook."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp(prefix="test-initializer-")

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_creates_appfix_state_on_appfix_prompt(self):
        """'/appfix' prompt should create appfix-state.json."""
        result = run_hook(
            "skill-state-initializer.py",
            initializer_input(self.tmpdir, "/appfix fix the bug"),
        )
        assert result.returncode == 0

        state_path = Path(self.tmpdir) / ".claude" / "appfix-state.json"
        assert state_path.exists(), f"State file not created at {state_path}"

        state = json.loads(state_path.read_text())
        assert state["iteration"] == 1
        assert state["plan_mode_completed"] is False

    def test_creates_godo_state_on_godo_prompt(self):
        """'/godo' prompt should create godo-state.json."""
        result = run_hook(
            "skill-state-initializer.py",
            initializer_input(self.tmpdir, "/godo implement the feature"),
        )
        assert result.returncode == 0

        state_path = Path(self.tmpdir) / ".claude" / "godo-state.json"
        assert state_path.exists()

    def test_creates_appfix_on_natural_language(self):
        """'fix the app' should also create appfix state."""
        run_hook(
            "skill-state-initializer.py",
            initializer_input(self.tmpdir, "fix the app it's broken"),
        )
        assert (Path(self.tmpdir) / ".claude" / "appfix-state.json").exists()

    def test_ignores_unrelated_prompts(self):
        """Regular prompts should NOT create any state file."""
        run_hook(
            "skill-state-initializer.py",
            initializer_input(self.tmpdir, "explain how this code works"),
        )
        claude_dir = Path(self.tmpdir) / ".claude"
        if claude_dir.exists():
            assert not (claude_dir / "appfix-state.json").exists()
            assert not (claude_dir / "godo-state.json").exists()

    def test_state_has_required_fields(self):
        """Created state should have all required fields."""
        run_hook(
            "skill-state-initializer.py",
            initializer_input(self.tmpdir, "/appfix"),
        )
        state = json.loads(
            (Path(self.tmpdir) / ".claude" / "appfix-state.json").read_text()
        )
        required_fields = [
            "iteration",
            "started_at",
            "plan_mode_completed",
            "parallel_mode",
            "coordinator",
            "services",
            "fixes_applied",
            "verification_evidence",
        ]
        for field in required_fields:
            assert field in state, f"Missing required field: {field}"


# ============================================================================
# Full Hook Chain Tests
# ============================================================================


class TestHookChain:
    """Integration tests that exercise the full hook chain."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp(prefix="test-chain-")

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_full_appfix_lifecycle(self):
        """Full lifecycle: init → enforce (block) → track → enforce (allow)."""
        # Step 1: Simulate /appfix creating state
        run_hook(
            "skill-state-initializer.py",
            initializer_input(self.tmpdir, "/appfix debug"),
        )
        state_path = Path(self.tmpdir) / ".claude" / "appfix-state.json"
        assert state_path.exists()

        state = json.loads(state_path.read_text())
        assert state["plan_mode_completed"] is False

        # Step 2: Code file should be BLOCKED (plan mode not done)
        result = run_hook(
            "plan-mode-enforcer.py",
            enforcer_input(self.tmpdir, "Edit", f"{self.tmpdir}/src/main.py"),
        )
        assert "PLAN MODE REQUIRED" in result.stdout

        # Step 3: .claude/ artifact should be ALLOWED (even before plan mode)
        result = run_hook(
            "plan-mode-enforcer.py",
            enforcer_input(
                self.tmpdir,
                "Write",
                f"{self.tmpdir}/.claude/validation-tests/summary.json",
            ),
        )
        assert result.stdout.strip() == ""

        # Step 4: ExitPlanMode updates state
        run_hook(
            "plan-mode-tracker.py",
            tracker_input(self.tmpdir, "ExitPlanMode"),
        )
        state = json.loads(state_path.read_text())
        assert state["plan_mode_completed"] is True

        # Step 5: Code file should now be ALLOWED
        result = run_hook(
            "plan-mode-enforcer.py",
            enforcer_input(self.tmpdir, "Edit", f"{self.tmpdir}/src/main.py"),
        )
        assert result.stdout.strip() == ""

    def test_claude_artifacts_always_allowed_throughout_lifecycle(self):
        """`.claude/` writes should work at every stage of the lifecycle."""
        make_state_dir(
            self.tmpdir,
            {
                "iteration": 1,
                "plan_mode_completed": False,
            },
        )

        claude_paths = [
            f"{self.tmpdir}/.claude/completion-checkpoint.json",
            f"{self.tmpdir}/.claude/validation-tests/summary.json",
            f"{self.tmpdir}/.claude/web-smoke/summary.json",
            f"{self.tmpdir}/.claude/appfix-state.json",
            f"{self.tmpdir}/.claude/infra-changes.md",
            ".claude/session-snapshot.json",
        ]

        for path in claude_paths:
            result = run_hook(
                "plan-mode-enforcer.py",
                enforcer_input(self.tmpdir, "Write", path),
            )
            assert result.stdout.strip() == "", (
                f"BLOCKED write to {path}: {result.stdout[:100]}"
            )

    def test_auto_approval_during_appfix(self):
        """Auto-approval hook should return allow when appfix state exists."""
        make_state_dir(self.tmpdir, {"iteration": 1, "plan_mode_completed": False})

        # appfix-auto-approve may receive empty stdin for PermissionRequest
        result = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "appfix-auto-approve.py")],
            input="",
            capture_output=True,
            text=True,
            timeout=10,
            cwd=self.tmpdir,
        )
        assert result.returncode == 0
        if result.stdout.strip():
            output = json.loads(result.stdout)
            decision = output.get("hookSpecificOutput", {}).get(
                "decision", output.get("hookSpecificOutput", {})
            )
            behavior = decision.get("behavior", "")
            assert behavior == "allow", f"Expected allow, got: {behavior}"
