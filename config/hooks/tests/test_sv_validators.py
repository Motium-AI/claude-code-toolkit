#!/usr/bin/env python3
"""
Unit tests for stop-validator modules.

Run with: python3 -m pytest tests/test_sv_validators.py -v
"""

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

# Add hooks directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from _sv_validators import (
    validate_version_staleness,
    validate_core_completion,
    validate_code_requirements,
    validate_web_testing,
    has_code_changes,
    has_frontend_changes,
)
from _common import (
    load_checkpoint,
    save_checkpoint,
    is_worktree,
    cleanup_autonomous_state,
    get_fields_to_invalidate,
)


class TestHasCodeChanges:
    """Tests for has_code_changes function."""

    def test_detects_python_files(self):
        files = ["src/main.py", "README.md"]
        assert has_code_changes(files) is True

    def test_detects_typescript_files(self):
        files = ["src/App.tsx", "package.json"]
        assert has_code_changes(files) is True

    def test_ignores_config_hooks(self):
        files = ["config/hooks/stop-validator.py", "config/skills/appfix/SKILL.md"]
        assert has_code_changes(files) is False

    def test_ignores_claude_directory(self):
        files = [".claude/completion-checkpoint.json", ".claude/state.json"]
        assert has_code_changes(files) is False

    def test_empty_list(self):
        assert has_code_changes([]) is False


class TestHasFrontendChanges:
    """Tests for has_frontend_changes function."""

    def test_detects_tsx_files(self):
        files = ["src/App.tsx"]
        assert has_frontend_changes(files) is True

    def test_detects_components_directory(self):
        files = ["components/Button.js"]
        assert has_frontend_changes(files) is True

    def test_detects_src_hooks(self):
        files = ["src/hooks/useAuth.ts"]
        assert has_frontend_changes(files) is True

    def test_ignores_config_hooks(self):
        # config/hooks is NOT frontend
        files = ["config/hooks/stop-validator.py"]
        assert has_frontend_changes(files) is False


class TestFieldDependencies:
    """Tests for field dependency cascade via get_fields_to_invalidate."""

    def test_deployed_depends_on_linters(self):
        fields = get_fields_to_invalidate("linters_pass")
        assert "deployed" in fields

    def test_web_testing_depends_on_deployed(self):
        fields = get_fields_to_invalidate("deployed")
        assert "web_testing_done" in fields

    def test_transitive_dependency(self):
        # linters_pass -> deployed -> web_testing_done
        fields = get_fields_to_invalidate("linters_pass")
        assert "web_testing_done" in fields

    def test_only_3_fields_in_cascade(self):
        fields = get_fields_to_invalidate("linters_pass")
        assert fields == {"linters_pass", "deployed", "web_testing_done"}


class TestValidateCoreCompletion:
    """Tests for validate_core_completion function."""

    def test_job_incomplete_fails(self):
        report = {"is_job_complete": False}
        reflection = {"what_remains": "none"}
        failures = validate_core_completion(report, reflection)
        assert len(failures) == 1
        assert "is_job_complete" in failures[0]

    def test_what_remains_not_empty_fails(self):
        report = {"is_job_complete": True}
        reflection = {"what_remains": "Need to add tests"}
        failures = validate_core_completion(report, reflection)
        assert len(failures) == 1
        assert "what_remains" in failures[0]

    def test_valid_checkpoint_passes(self):
        report = {"is_job_complete": True}
        reflection = {"what_remains": "none"}
        failures = validate_core_completion(report, reflection)
        assert len(failures) == 0

    def test_what_remains_nothing_passes(self):
        report = {"is_job_complete": True}
        reflection = {"what_remains": "nothing"}
        failures = validate_core_completion(report, reflection)
        assert len(failures) == 0


class TestValidateCodeRequirements:
    """Tests for validate_code_requirements function."""

    def test_no_app_code_passes(self):
        report = {"linters_pass": False}
        failures = validate_code_requirements(
            report, has_app_code=False, has_frontend=False
        )
        assert len(failures) == 0

    def test_app_code_requires_linters(self):
        report = {"linters_pass": False, "deployed": True}
        failures = validate_code_requirements(
            report, has_app_code=True, has_frontend=False
        )
        assert any("linters_pass" in f for f in failures)

    def test_app_code_requires_deployed(self):
        report = {"linters_pass": True, "deployed": False}
        failures = validate_code_requirements(
            report, has_app_code=True, has_frontend=False
        )
        assert any("deployed" in f for f in failures)

    def test_frontend_requires_web_testing(self):
        report = {"linters_pass": True, "deployed": True, "web_testing_done": False}
        failures = validate_code_requirements(
            report, has_app_code=True, has_frontend=True
        )
        assert any("web_testing_done" in f for f in failures)


class TestVersionStaleness:
    """Tests for validate_version_staleness function."""

    @patch("_sv_validators.get_code_version")
    def test_detects_stale_field(self, mock_version):
        mock_version.return_value = "def5678"
        checkpoint = {
            "self_report": {
                "deployed": True,
                "deployed_at_version": "abc1234",  # Different version
            }
        }
        modified, failures, reset_fields = validate_version_staleness(
            checkpoint, "/tmp"
        )
        assert modified is True
        assert "deployed" in reset_fields
        assert checkpoint["self_report"]["deployed"] is False  # Was reset

    @patch("_sv_validators.get_code_version")
    def test_cascades_to_dependents(self, mock_version):
        mock_version.return_value = "def5678"
        checkpoint = {
            "self_report": {
                "linters_pass": True,
                "linters_pass_at_version": "abc1234",  # Stale
                "deployed": True,
                "deployed_at_version": "def5678",  # Current version
                "web_testing_done": True,
                "web_testing_done_at_version": "def5678",  # Current version
            }
        }
        modified, failures, reset_fields = validate_version_staleness(
            checkpoint, "/tmp"
        )
        # linters_pass is stale, so deployed (which depends on it) should cascade
        assert "linters_pass" in reset_fields
        assert "deployed" in reset_fields  # Cascade!


class TestCheckpointIO:
    """Tests for checkpoint file operations."""

    def test_load_missing_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = load_checkpoint(tmpdir)
            assert result is None

    def test_save_and_load_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            claude_dir = Path(tmpdir) / ".claude"
            claude_dir.mkdir()

            checkpoint = {"self_report": {"is_job_complete": True}}
            save_checkpoint(tmpdir, checkpoint)

            loaded = load_checkpoint(tmpdir)
            assert loaded == checkpoint


class TestWorktreeDetection:
    """Tests for worktree detection."""

    def test_non_git_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Not a git repo
            assert is_worktree(tmpdir) is False


class TestCleanupAutonomousState:
    """Tests for cleanup_autonomous_state function."""

    def test_cleans_nested_state_files(self):
        """Should clean state files from all .claude/ directories walking up."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create nested .claude directories
            root_claude = Path(tmpdir) / ".claude"
            nested_claude = Path(tmpdir) / "subdir" / ".claude"
            root_claude.mkdir(parents=True)
            nested_claude.mkdir(parents=True)

            # Create state files in both
            (root_claude / "appfix-state.json").write_text('{"test": true}')
            (nested_claude / "appfix-state.json").write_text('{"test": true}')

            # Clean from nested directory
            deleted = cleanup_autonomous_state(str(Path(tmpdir) / "subdir"))

            # Both should be deleted
            assert len(deleted) >= 2
            assert not (root_claude / "appfix-state.json").exists()
            assert not (nested_claude / "appfix-state.json").exists()

    def test_cleans_both_godo_and_appfix(self):
        """Should clean both godo-state.json and appfix-state.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            claude_dir = Path(tmpdir) / ".claude"
            claude_dir.mkdir(parents=True)

            (claude_dir / "appfix-state.json").write_text('{"test": true}')
            (claude_dir / "godo-state.json").write_text('{"test": true}')

            deleted = cleanup_autonomous_state(tmpdir)

            assert len(deleted) >= 2
            assert not (claude_dir / "appfix-state.json").exists()
            assert not (claude_dir / "godo-state.json").exists()

    def test_returns_empty_list_when_no_state_files(self):
        """Should return empty list when no state files exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            deleted = cleanup_autonomous_state(tmpdir)
            # May include user-level cleanup, but at least no error
            assert isinstance(deleted, list)


class TestWebTestingBypassPrevention:
    """Tests for preventing web testing bypass via false claims."""

    @patch("_sv_validators.is_autonomous_mode_active")
    @patch("_sv_validators.validate_web_smoke_artifacts")
    def test_rejects_claim_without_artifacts(self, mock_artifacts, mock_autonomous):
        """web_testing_done=true without artifacts should fail and be reset."""
        mock_autonomous.return_value = True
        mock_artifacts.return_value = (False, ["No summary.json found"])

        checkpoint = {
            "self_report": {
                "web_testing_done": True,
                "web_testing_done_at_version": "abc123",
                "code_changes_made": False,  # "Backend-only" claim
            },
            "evidence": {"urls_tested": []},
        }

        failures, modified = validate_web_testing(
            checkpoint, has_app_code=False, has_infra_changes=False, cwd="/tmp"
        )

        # Should fail validation
        assert len(failures) > 0
        assert any(
            "web_testing_done is TRUE but no valid Surf artifacts" in f
            for f in failures
        )

        # Should auto-reset the false claim
        assert modified is True
        assert checkpoint["self_report"]["web_testing_done"] is False
        assert checkpoint["self_report"]["web_testing_done_at_version"] == ""

    @patch("_sv_validators.is_autonomous_mode_active")
    @patch("_sv_validators.validate_web_smoke_artifacts")
    def test_backend_only_still_requires_verification(
        self, mock_artifacts, mock_autonomous
    ):
        """Backend-only changes (has_app_code=true) still need Surf verification.

        Note: has_app_code must be True to test actual backend code changes.
        When has_app_code=False AND has_infra_changes=False, changes are
        considered infrastructure-only (hooks, skills, docs) and don't
        require web smoke verification by design.
        """
        mock_autonomous.return_value = True
        mock_artifacts.return_value = (False, ["No summary.json found"])

        checkpoint = {
            "self_report": {
                "web_testing_done": False,
                "code_changes_made": True,  # Backend change claimed
            },
            "evidence": {"urls_tested": []},
        }

        # has_app_code=True indicates actual backend code was changed
        failures, modified = validate_web_testing(
            checkpoint, has_app_code=True, has_infra_changes=False, cwd="/tmp"
        )

        # Should require web smoke verification
        assert any("WEB SMOKE VERIFICATION REQUIRED" in f for f in failures)

    @patch("_sv_validators.is_autonomous_mode_active")
    @patch("_sv_validators.validate_web_smoke_artifacts")
    @patch("_sv_validators.get_code_version")
    def test_valid_artifacts_auto_set_web_testing(
        self, mock_version, mock_artifacts, mock_autonomous
    ):
        """Valid artifacts should auto-set web_testing_done."""
        mock_autonomous.return_value = True
        mock_artifacts.return_value = (True, [])
        mock_version.return_value = "abc123"

        checkpoint = {
            "self_report": {
                "web_testing_done": False,
                "code_changes_made": True,
            },
            "evidence": {"urls_tested": ["https://app.com/dashboard"]},
        }

        failures, modified = validate_web_testing(
            checkpoint, has_app_code=True, has_infra_changes=False, cwd="/tmp"
        )

        # Should pass and auto-set web_testing_done
        assert len(failures) == 0
        assert modified is True
        assert checkpoint["self_report"]["web_testing_done"] is True


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
