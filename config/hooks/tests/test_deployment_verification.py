#!/usr/bin/env python3
"""
Tests for deployment verification hooks and validators.

Run with: python3 -m pytest tests/test_deployment_verification.py -v
"""

import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

# Add hooks directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from _sv_validators import (
    validate_deployment_artifacts,
    validate_checkpoint,
)

HOOKS_DIR = Path(__file__).parent.parent


def run_hook(hook_name, stdin_data, cwd=None):
    """Run a hook script as subprocess and return the result."""
    return subprocess.run(
        [sys.executable, str(HOOKS_DIR / hook_name)],
        input=json.dumps(stdin_data),
        capture_output=True,
        text=True,
        timeout=10,
        cwd=cwd,
    )


# ============================================================================
# validate_deployment_artifacts() tests
# ============================================================================


class TestValidateDeploymentArtifacts:
    """Tests for validate_deployment_artifacts function."""

    def test_missing_summary_json(self):
        """Should fail when no summary.json exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            is_valid, errors = validate_deployment_artifacts(tmpdir)
            assert is_valid is False
            assert len(errors) == 1
            assert "No summary.json found" in errors[0]

    def test_invalid_json(self):
        """Should fail when summary.json is not valid JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_dir = Path(tmpdir) / ".claude" / "deployment"
            artifact_dir.mkdir(parents=True)
            (artifact_dir / "summary.json").write_text("not json")

            is_valid, errors = validate_deployment_artifacts(tmpdir)
            assert is_valid is False
            assert "Cannot parse" in errors[0]

    @patch("_sv_validators.get_code_version")
    def test_stale_version(self, mock_version):
        """Should fail when deployed version doesn't match current."""
        mock_version.return_value = "def5678"

        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_dir = Path(tmpdir) / ".claude" / "deployment"
            artifact_dir.mkdir(parents=True)
            summary = {
                "passed": True,
                "deployed_version": "abc1234",
                "tested_at_version": "abc1234",
                "version_match": True,
            }
            (artifact_dir / "summary.json").write_text(json.dumps(summary))

            is_valid, errors = validate_deployment_artifacts(tmpdir)
            assert is_valid is False
            assert "STALE" in errors[0]

    @patch("_sv_validators.get_code_version")
    def test_failed_deployment(self, mock_version):
        """Should fail when deployment didn't pass."""
        mock_version.return_value = "abc1234"

        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_dir = Path(tmpdir) / ".claude" / "deployment"
            artifact_dir.mkdir(parents=True)
            summary = {
                "passed": False,
                "deployed_version": "abc1234",
                "tested_at_version": "abc1234",
                "conclusion": "failure",
                "run_id": 12345,
                "errors": ["Deployment step failed"],
            }
            (artifact_dir / "summary.json").write_text(json.dumps(summary))

            is_valid, errors = validate_deployment_artifacts(tmpdir)
            assert is_valid is False
            assert "FAILED" in errors[0]

    @patch("_sv_validators.get_code_version")
    def test_version_mismatch_flag(self, mock_version):
        """Should fail when version_match is false."""
        mock_version.return_value = "abc1234"

        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_dir = Path(tmpdir) / ".claude" / "deployment"
            artifact_dir.mkdir(parents=True)
            summary = {
                "passed": True,
                "deployed_version": "abc1234",
                "tested_at_version": "abc1234",
                "version_match": False,
            }
            (artifact_dir / "summary.json").write_text(json.dumps(summary))

            is_valid, errors = validate_deployment_artifacts(tmpdir)
            assert is_valid is False
            assert "Version match is false" in errors[0]

    @patch("_sv_validators.get_code_version")
    def test_valid_deployment_passes(self, mock_version):
        """Should pass with valid deployment artifacts."""
        mock_version.return_value = "abc1234"

        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_dir = Path(tmpdir) / ".claude" / "deployment"
            artifact_dir.mkdir(parents=True)
            summary = {
                "passed": True,
                "deployed_version": "abc1234",
                "tested_at_version": "abc1234",
                "version_match": True,
                "conclusion": "success",
                "run_id": 12345,
            }
            (artifact_dir / "summary.json").write_text(json.dumps(summary))

            is_valid, errors = validate_deployment_artifacts(tmpdir)
            assert is_valid is True
            assert len(errors) == 0


# ============================================================================
# deploy-enforcer.py hook tests
# ============================================================================


class TestDeployEnforcerHook:
    """Tests for deploy-enforcer.py PreToolUse hook."""

    def _make_state_file(self, tmpdir, coordinator=True, state_type="appfix"):
        """Create a state file for testing."""
        claude_dir = Path(tmpdir) / ".claude"
        claude_dir.mkdir(parents=True, exist_ok=True)
        state = {
            "coordinator": coordinator,
            "iteration": 1,
            "plan_mode_completed": True,
            "started_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        state_file = claude_dir / f"{state_type}-state.json"
        state_file.write_text(json.dumps(state))
        return state_file

    def test_allows_non_bash_tool(self):
        """Should silently pass non-Bash tools."""
        result = run_hook(
            "deploy-enforcer.py",
            {"tool_name": "Edit", "tool_input": {}, "cwd": "/tmp"},
        )
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_allows_non_deploy_commands(self):
        """Should silently pass non-deploy Bash commands."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._make_state_file(tmpdir)
            result = run_hook(
                "deploy-enforcer.py",
                {
                    "tool_name": "Bash",
                    "tool_input": {"command": "git status"},
                    "cwd": tmpdir,
                },
            )
            assert result.returncode == 0
            assert result.stdout.strip() == ""

    def test_blocks_subagent_deploy(self):
        """Should block gh workflow run when coordinator: false."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._make_state_file(tmpdir, coordinator=False)
            result = run_hook(
                "deploy-enforcer.py",
                {
                    "tool_name": "Bash",
                    "tool_input": {"command": "gh workflow run deploy.yml"},
                    "cwd": tmpdir,
                },
            )
            assert result.returncode == 0
            output = json.loads(result.stdout)
            decision = output["hookSpecificOutput"]["permissionDecision"]
            assert decision == "deny"
            reason = output["hookSpecificOutput"]["permissionDecisionReason"]
            assert "ubagent" in reason.lower() or "coordinator: false" in reason.lower()

    def test_allows_coordinator_deploy(self):
        """Should allow gh workflow run when coordinator: true."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._make_state_file(tmpdir, coordinator=True)
            result = run_hook(
                "deploy-enforcer.py",
                {
                    "tool_name": "Bash",
                    "tool_input": {"command": "gh workflow run deploy.yml"},
                    "cwd": tmpdir,
                },
            )
            assert result.returncode == 0
            # Should not produce deny output
            stdout = result.stdout.strip()
            if stdout:
                output = json.loads(stdout)
                assert (
                    output.get("hookSpecificOutput", {}).get("permissionDecision")
                    != "deny"
                )
            # Empty stdout = passthrough

    def test_blocks_production_deploy(self):
        """Should block production environment deploys."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._make_state_file(tmpdir, coordinator=True)
            result = run_hook(
                "deploy-enforcer.py",
                {
                    "tool_name": "Bash",
                    "tool_input": {
                        "command": "gh workflow run deploy.yml -f environment=production"
                    },
                    "cwd": tmpdir,
                },
            )
            assert result.returncode == 0
            output = json.loads(result.stdout)
            decision = output["hookSpecificOutput"]["permissionDecision"]
            assert decision == "deny"
            reason = output["hookSpecificOutput"]["permissionDecisionReason"]
            assert "production" in reason.lower()

    def test_allows_staging_deploy(self):
        """Should allow staging environment deploys."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._make_state_file(tmpdir, coordinator=True)
            result = run_hook(
                "deploy-enforcer.py",
                {
                    "tool_name": "Bash",
                    "tool_input": {
                        "command": "gh workflow run deploy.yml -f environment=staging"
                    },
                    "cwd": tmpdir,
                },
            )
            assert result.returncode == 0
            stdout = result.stdout.strip()
            if stdout:
                output = json.loads(stdout)
                assert (
                    output.get("hookSpecificOutput", {}).get("permissionDecision")
                    != "deny"
                )

    def test_no_enforcement_outside_autonomous_mode(self):
        """Should not enforce when not in autonomous mode."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # No state file = not in autonomous mode
            result = run_hook(
                "deploy-enforcer.py",
                {
                    "tool_name": "Bash",
                    "tool_input": {
                        "command": "gh workflow run deploy.yml -f environment=production"
                    },
                    "cwd": tmpdir,
                },
            )
            assert result.returncode == 0
            assert result.stdout.strip() == ""


# ============================================================================
# bash-version-tracker.py GH deploy detection tests
# ============================================================================


import pytest


class TestBashVersionTrackerGhDeploy:
    """Tests for gh deploy pattern detection in bash-version-tracker.py.

    NOTE: These tests are for features not yet implemented.
    Skip until gh deploy detection is added to bash-version-tracker.py.
    """

    def _setup_checkpoint(self, tmpdir):
        """Create a checkpoint with deployed: true for invalidation testing."""
        claude_dir = Path(tmpdir) / ".claude"
        claude_dir.mkdir(parents=True, exist_ok=True)
        checkpoint = {
            "self_report": {
                "deployed": True,
                "deployed_at_version": "abc1234",
                "web_testing_done": True,
                "web_testing_done_at_version": "abc1234",
                "console_errors_checked": True,
                "console_errors_checked_at_version": "abc1234",
            }
        }
        (claude_dir / "completion-checkpoint.json").write_text(json.dumps(checkpoint))
        return claude_dir

    def _init_git_repo(self, tmpdir):
        """Initialize a git repo for version tracking."""
        subprocess.run(["git", "init"], cwd=tmpdir, capture_output=True, timeout=5)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=tmpdir,
            capture_output=True,
            timeout=5,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=tmpdir,
            capture_output=True,
            timeout=5,
        )
        # Create initial commit so HEAD exists
        test_file = Path(tmpdir) / "test.txt"
        test_file.write_text("test")
        subprocess.run(["git", "add", "."], cwd=tmpdir, capture_output=True, timeout=5)
        subprocess.run(
            ["git", "commit", "-m", "init"],
            cwd=tmpdir,
            capture_output=True,
            timeout=5,
        )

    @pytest.mark.skip(reason="gh deploy detection not yet implemented in bash-version-tracker")
    def test_detects_gh_workflow_run(self):
        """Should detect gh workflow run command and invalidate fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_git_repo(tmpdir)
            self._setup_checkpoint(tmpdir)

            result = run_hook(
                "bash-version-tracker.py",
                {
                    "tool_name": "Bash",
                    "tool_input": {"command": "gh workflow run deploy.yml"},
                    "cwd": tmpdir,
                },
                cwd=tmpdir,
            )
            assert result.returncode == 0

            # Check checkpoint was updated
            checkpoint_path = Path(tmpdir) / ".claude" / "completion-checkpoint.json"
            checkpoint = json.loads(checkpoint_path.read_text())
            report = checkpoint["self_report"]

            # deployed should be invalidated
            assert report["deployed"] is False
            assert report["gh_deploy_initiated"] is True

    @pytest.mark.skip(reason="gh deploy detection not yet implemented in bash-version-tracker")
    def test_detects_gh_run_watch(self):
        """Should detect gh run watch command and invalidate fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_git_repo(tmpdir)
            self._setup_checkpoint(tmpdir)

            result = run_hook(
                "bash-version-tracker.py",
                {
                    "tool_name": "Bash",
                    "tool_input": {"command": "gh run watch 12345 --exit-status"},
                    "cwd": tmpdir,
                },
                cwd=tmpdir,
            )
            assert result.returncode == 0

            checkpoint_path = Path(tmpdir) / ".claude" / "completion-checkpoint.json"
            checkpoint = json.loads(checkpoint_path.read_text())
            report = checkpoint["self_report"]

            assert report["deployed"] is False
            assert report["gh_deploy_initiated"] is True

    def test_ignores_non_deploy_commands(self):
        """Should not trigger on regular git/gh commands."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_git_repo(tmpdir)
            self._setup_checkpoint(tmpdir)

            result = run_hook(
                "bash-version-tracker.py",
                {
                    "tool_name": "Bash",
                    "tool_input": {"command": "gh pr list"},
                    "cwd": tmpdir,
                },
                cwd=tmpdir,
            )
            assert result.returncode == 0

            # Checkpoint should be unchanged
            checkpoint_path = Path(tmpdir) / ".claude" / "completion-checkpoint.json"
            checkpoint = json.loads(checkpoint_path.read_text())
            report = checkpoint["self_report"]
            assert report["deployed"] is True  # NOT invalidated


# ============================================================================
# Integration: deployed claim cross-validation
# ============================================================================


class TestDeployedClaimCrossValidation:
    """Integration tests for deployed: true cross-validation in validate_checkpoint.

    NOTE: These tests are for features not yet implemented.
    Skip until deployed cross-validation is added to validate_checkpoint.
    """

    @pytest.mark.skip(reason="deployed cross-validation not yet implemented in validate_checkpoint")
    @patch("_sv_validators.is_autonomous_mode_active")
    @patch("_sv_validators.is_appfix_active")
    @patch("_sv_validators.get_code_version")
    def test_resets_deployed_without_artifacts(
        self, mock_version, mock_appfix, mock_autonomous
    ):
        """deployed=true without artifacts should be reset to false in autonomous mode."""
        mock_version.return_value = "abc1234"
        mock_appfix.return_value = True
        mock_autonomous.return_value = True

        checkpoint = {
            "self_report": {
                "is_job_complete": True,
                "code_changes_made": True,
                "deployed": True,
                "deployed_at_version": "abc1234",
                "linters_pass": True,
                "linters_pass_at_version": "abc1234",
                "web_testing_done": True,
                "web_testing_done_at_version": "abc1234",
                "console_errors_checked": True,
                "console_errors_checked_at_version": "abc1234",
                "docs_read_at_start": True,
            },
            "reflection": {"what_was_done": "Fixed bug", "what_remains": "none"},
            "evidence": {"urls_tested": ["https://app.com/dashboard"]},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            # No deployment artifacts exist
            claude_dir = Path(tmpdir) / ".claude"
            claude_dir.mkdir(parents=True)
            (claude_dir / "completion-checkpoint.json").write_text(
                json.dumps(checkpoint)
            )

            is_valid, failures = validate_checkpoint(
                checkpoint, ["src/main.py"], cwd=tmpdir
            )

            # Should fail because deployed artifacts are missing
            assert is_valid is False
            assert any(
                "deployed is TRUE but no valid deployment artifacts" in f
                for f in failures
            )

            # deployed should be reset to false
            assert checkpoint["self_report"]["deployed"] is False

    @pytest.mark.skip(reason="deployed cross-validation not yet implemented in validate_checkpoint")
    @patch("_sv_validators.is_autonomous_mode_active")
    @patch("_sv_validators.is_appfix_active")
    @patch("_sv_validators.get_code_version")
    def test_cascade_invalidation_on_deploy_reset(
        self, mock_version, mock_appfix, mock_autonomous
    ):
        """Resetting deployed should cascade-invalidate web_testing_done etc."""
        mock_version.return_value = "abc1234"
        mock_appfix.return_value = True
        mock_autonomous.return_value = True

        checkpoint = {
            "self_report": {
                "is_job_complete": True,
                "code_changes_made": True,
                "deployed": True,
                "deployed_at_version": "abc1234",
                "linters_pass": True,
                "linters_pass_at_version": "abc1234",
                "web_testing_done": True,
                "web_testing_done_at_version": "abc1234",
                "console_errors_checked": True,
                "console_errors_checked_at_version": "abc1234",
                "api_testing_done": True,
                "api_testing_done_at_version": "abc1234",
                "docs_read_at_start": True,
            },
            "reflection": {"what_was_done": "Fixed bug", "what_remains": "none"},
            "evidence": {"urls_tested": ["https://app.com/dashboard"]},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            claude_dir = Path(tmpdir) / ".claude"
            claude_dir.mkdir(parents=True)
            (claude_dir / "completion-checkpoint.json").write_text(
                json.dumps(checkpoint)
            )

            is_valid, failures = validate_checkpoint(
                checkpoint, ["src/main.py"], cwd=tmpdir
            )

            # All deployed-dependent fields should be cascade invalidated
            report = checkpoint["self_report"]
            assert report["deployed"] is False
            assert report["web_testing_done"] is False
            assert report["console_errors_checked"] is False
            assert report["api_testing_done"] is False

            # Should have cascade messages
            assert any("CASCADE INVALIDATED" in f for f in failures)


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
