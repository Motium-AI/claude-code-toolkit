#!/usr/bin/env python3
"""
Unit tests for stop-validator.py.

Tests session code change detection, checkpoint requirements, validation,
memory capture, and blocking messages.

Run with: cd config/hooks && python3 -m pytest tests/test_stop_validator.py -v
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock, call, Mock

# Add hooks directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def load_stop_validator():
    """Load stop-validator.py module dynamically."""
    from importlib.util import spec_from_file_location, module_from_spec
    spec = spec_from_file_location(
        "stop_validator",
        str(Path(__file__).parent.parent / "stop-validator.py"),
    )
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ============================================================================
# Session Detection Tests
# ============================================================================


class TestSessionMadeCodeChanges(unittest.TestCase):
    """Tests for session_made_code_changes function."""

    def setUp(self):
        self.mod = load_stop_validator()

    def test_no_snapshot_file_returns_false(self):
        """No snapshot file should return False (can't determine)."""
        with tempfile.TemporaryDirectory() as td:
            result = self.mod.session_made_code_changes(td)
            self.assertFalse(result)

    def test_snapshot_exists_same_hash_returns_false(self):
        """Snapshot with same diff hash should return False (no changes)."""
        with tempfile.TemporaryDirectory() as td:
            claude_dir = Path(td) / ".claude"
            claude_dir.mkdir()

            snapshot = {"diff_hash_at_start": "abc123def456"}
            (claude_dir / "session-snapshot.json").write_text(json.dumps(snapshot))

            # Mock get_diff_hash to return same hash
            with patch.object(self.mod, "get_diff_hash", return_value="abc123def456"):
                result = self.mod.session_made_code_changes(td)

            self.assertFalse(result)

    def test_snapshot_exists_different_hash_returns_true(self):
        """Snapshot with different diff hash should return True (changes detected)."""
        with tempfile.TemporaryDirectory() as td:
            claude_dir = Path(td) / ".claude"
            claude_dir.mkdir()

            snapshot = {"diff_hash_at_start": "abc123def456"}
            (claude_dir / "session-snapshot.json").write_text(json.dumps(snapshot))

            # Mock get_diff_hash to return different hash
            with patch.object(self.mod, "get_diff_hash", return_value="different_hash"):
                result = self.mod.session_made_code_changes(td)

            self.assertTrue(result)

    def test_malformed_snapshot_returns_false(self):
        """Malformed JSON snapshot should return False."""
        with tempfile.TemporaryDirectory() as td:
            claude_dir = Path(td) / ".claude"
            claude_dir.mkdir()

            (claude_dir / "session-snapshot.json").write_text("not valid json {")
            result = self.mod.session_made_code_changes(td)

            self.assertFalse(result)

    def test_snapshot_with_unknown_hash_returns_false(self):
        """Snapshot with 'unknown' hash should return False."""
        with tempfile.TemporaryDirectory() as td:
            claude_dir = Path(td) / ".claude"
            claude_dir.mkdir()

            snapshot = {"diff_hash_at_start": "unknown"}
            (claude_dir / "session-snapshot.json").write_text(json.dumps(snapshot))

            result = self.mod.session_made_code_changes(td)
            self.assertFalse(result)

    def test_snapshot_missing_diff_hash_returns_false(self):
        """Snapshot without diff_hash_at_start should return False."""
        with tempfile.TemporaryDirectory() as td:
            claude_dir = Path(td) / ".claude"
            claude_dir.mkdir()

            snapshot = {"other_field": "value"}
            (claude_dir / "session-snapshot.json").write_text(json.dumps(snapshot))

            result = self.mod.session_made_code_changes(td)
            self.assertFalse(result)


# ============================================================================
# Checkpoint Requirements Tests
# ============================================================================


class TestRequiresCheckpoint(unittest.TestCase):
    """Tests for requires_checkpoint function."""

    def setUp(self):
        self.mod = load_stop_validator()

    def test_home_directory_returns_false(self):
        """Home directory should not require checkpoint."""
        home = str(Path.home())
        result = self.mod.requires_checkpoint(home)
        self.assertFalse(result)

    def test_no_autonomous_no_code_changes_returns_false(self):
        """No autonomous mode and no code changes should return False."""
        with tempfile.TemporaryDirectory() as td:
            # No snapshot file = no code changes
            with patch.object(self.mod, "is_autonomous_mode_active", return_value=False):
                result = self.mod.requires_checkpoint(td)

            self.assertFalse(result)

    def test_autonomous_mode_code_changes_returns_true(self):
        """Autonomous mode with code changes should return True."""
        with tempfile.TemporaryDirectory() as td:
            # Create snapshot with code changes
            claude_dir = Path(td) / ".claude"
            claude_dir.mkdir()
            snapshot = {"diff_hash_at_start": "old_hash"}
            (claude_dir / "session-snapshot.json").write_text(json.dumps(snapshot))

            with patch.object(self.mod, "is_autonomous_mode_active", return_value=True):
                with patch.object(self.mod, "get_diff_hash", return_value="new_hash"):
                    result = self.mod.requires_checkpoint(td)

            self.assertTrue(result)

    def test_autonomous_mode_no_code_changes_returns_false(self):
        """Autonomous mode without code changes should return False."""
        with tempfile.TemporaryDirectory() as td:
            # Create snapshot with no changes
            claude_dir = Path(td) / ".claude"
            claude_dir.mkdir()
            snapshot = {"diff_hash_at_start": "same_hash"}
            (claude_dir / "session-snapshot.json").write_text(json.dumps(snapshot))

            with patch.object(self.mod, "is_autonomous_mode_active", return_value=True):
                with patch.object(self.mod, "get_diff_hash", return_value="same_hash"):
                    result = self.mod.requires_checkpoint(td)

            self.assertFalse(result)

    def test_no_autonomous_code_changes_returns_true(self):
        """No autonomous mode but code changes should return True."""
        with tempfile.TemporaryDirectory() as td:
            # Create snapshot with code changes
            claude_dir = Path(td) / ".claude"
            claude_dir.mkdir()
            snapshot = {"diff_hash_at_start": "old_hash"}
            (claude_dir / "session-snapshot.json").write_text(json.dumps(snapshot))

            with patch.object(self.mod, "is_autonomous_mode_active", return_value=False):
                with patch.object(self.mod, "get_diff_hash", return_value="new_hash"):
                    result = self.mod.requires_checkpoint(td)

            self.assertTrue(result)


# ============================================================================
# Checkpoint Validation Tests
# ============================================================================


class TestValidateCheckpoint(unittest.TestCase):
    """Tests for validate_checkpoint function."""

    def setUp(self):
        self.mod = load_stop_validator()

    def test_valid_checkpoint_all_fields_correct(self):
        """Valid checkpoint with all fields should pass."""
        checkpoint = {
            "self_report": {
                "is_job_complete": True,
                "code_changes_made": True,
                "linters_pass": True,
                "category": "bugfix"
            },
            "reflection": {
                "what_was_done": "Fixed the authentication bug in login flow by updating token validation",
                "what_remains": "none",
                "key_insight": "Authentication tokens must be validated before state updates to prevent race conditions in concurrent login scenarios",
                "search_terms": ["auth", "token", "race-condition", "login"]
            }
        }

        is_valid, failures = self.mod.validate_checkpoint(checkpoint)
        self.assertTrue(is_valid)
        self.assertEqual(failures, [])

    def test_is_job_complete_false_fails(self):
        """is_job_complete false should fail validation."""
        checkpoint = {
            "self_report": {"is_job_complete": False},
            "reflection": {
                "what_was_done": "Started work on feature",
                "what_remains": "none",
                "key_insight": "Need to complete implementation before wrapping up",
                "search_terms": ["feature", "implementation"]
            }
        }

        is_valid, failures = self.mod.validate_checkpoint(checkpoint)
        self.assertFalse(is_valid)
        self.assertTrue(any("is_job_complete is false" in f for f in failures))

    def test_what_remains_not_none_fails(self):
        """what_remains not 'none' should fail validation."""
        checkpoint = {
            "self_report": {"is_job_complete": True},
            "reflection": {
                "what_was_done": "Completed database migration script",
                "what_remains": "Need to test on staging",
                "key_insight": "Database migrations require careful transaction handling",
                "search_terms": ["database", "migration", "testing"]
            }
        }

        is_valid, failures = self.mod.validate_checkpoint(checkpoint)
        self.assertFalse(is_valid)
        self.assertTrue(any("what_remains is not empty" in f for f in failures))

    def test_what_was_done_too_short_fails(self):
        """what_was_done too short should fail validation."""
        checkpoint = {
            "self_report": {"is_job_complete": True},
            "reflection": {
                "what_was_done": "Fixed bug",
                "what_remains": "none",
                "key_insight": "Bug fixes require thorough testing to ensure no regressions",
                "search_terms": ["bug", "testing"]
            }
        }

        is_valid, failures = self.mod.validate_checkpoint(checkpoint)
        self.assertFalse(is_valid)
        self.assertTrue(any("what_was_done is missing or too brief" in f for f in failures))

    def test_linters_pass_false_when_code_changes_true_fails(self):
        """linters_pass false when code_changes_made true should fail."""
        checkpoint = {
            "self_report": {
                "is_job_complete": True,
                "code_changes_made": True,
                "linters_pass": False
            },
            "reflection": {
                "what_was_done": "Added new authentication middleware for API endpoints",
                "what_remains": "none",
                "key_insight": "Middleware should be stateless to ensure thread safety",
                "search_terms": ["middleware", "auth", "stateless"]
            }
        }

        is_valid, failures = self.mod.validate_checkpoint(checkpoint)
        self.assertFalse(is_valid)
        self.assertTrue(any("linters_pass required" in f for f in failures))

    def test_linters_pass_false_when_code_changes_false_passes(self):
        """linters_pass false when code_changes_made false should not fail."""
        checkpoint = {
            "self_report": {
                "is_job_complete": True,
                "code_changes_made": False,
                "linters_pass": False
            },
            "reflection": {
                "what_was_done": "Researched authentication patterns and documented findings",
                "what_remains": "none",
                "key_insight": "Modern authentication should use JWT with refresh tokens",
                "search_terms": ["auth", "jwt", "security", "patterns"]
            }
        }

        is_valid, failures = self.mod.validate_checkpoint(checkpoint)
        self.assertTrue(is_valid)
        self.assertEqual(failures, [])

    def test_key_insight_too_short_fails(self):
        """key_insight too short should fail validation."""
        checkpoint = {
            "self_report": {"is_job_complete": True},
            "reflection": {
                "what_was_done": "Updated documentation for new API endpoints",
                "what_remains": "none",
                "key_insight": "Document APIs well",
                "search_terms": ["docs", "api"]
            }
        }

        is_valid, failures = self.mod.validate_checkpoint(checkpoint)
        self.assertFalse(is_valid)
        self.assertTrue(any("key_insight is missing or too brief" in f for f in failures))

    def test_key_insight_copies_what_was_done_fails(self):
        """key_insight copying what_was_done should fail validation."""
        what_done = "Fixed the authentication bug in login flow by updating token validation"
        checkpoint = {
            "self_report": {"is_job_complete": True, "code_changes_made": True, "linters_pass": True},
            "reflection": {
                "what_was_done": what_done,
                "what_remains": "none",
                "key_insight": what_done,
                "search_terms": ["auth", "token"]
            }
        }

        is_valid, failures = self.mod.validate_checkpoint(checkpoint)
        self.assertFalse(is_valid)
        self.assertTrue(any("key_insight is a copy of what_was_done" in f for f in failures))

    def test_search_terms_empty_fails(self):
        """Empty search_terms should fail validation."""
        checkpoint = {
            "self_report": {"is_job_complete": True},
            "reflection": {
                "what_was_done": "Completed refactoring of authentication module",
                "what_remains": "none",
                "key_insight": "Refactoring auth code requires careful attention to sessions",
                "search_terms": []
            }
        }

        is_valid, failures = self.mod.validate_checkpoint(checkpoint)
        self.assertFalse(is_valid)
        self.assertTrue(any("search_terms needs 2-7 concept keywords" in f for f in failures))

    def test_search_terms_only_one_fails(self):
        """Only one search term should fail validation."""
        checkpoint = {
            "self_report": {"is_job_complete": True},
            "reflection": {
                "what_was_done": "Completed refactoring of authentication module",
                "what_remains": "none",
                "key_insight": "Refactoring auth code requires careful attention to sessions",
                "search_terms": ["auth"]
            }
        }

        is_valid, failures = self.mod.validate_checkpoint(checkpoint)
        self.assertFalse(is_valid)
        self.assertTrue(any("search_terms needs 2-7 concept keywords" in f for f in failures))

    def test_search_terms_more_than_seven_fails(self):
        """More than 7 search terms should fail validation."""
        checkpoint = {
            "self_report": {"is_job_complete": True},
            "reflection": {
                "what_was_done": "Completed refactoring of authentication module",
                "what_remains": "none",
                "key_insight": "Refactoring auth code requires careful attention to sessions",
                "search_terms": ["auth", "token", "jwt", "refresh", "session", "security", "oauth", "saml"]
            }
        }

        is_valid, failures = self.mod.validate_checkpoint(checkpoint)
        self.assertFalse(is_valid)
        self.assertTrue(any("search_terms has too many entries" in f for f in failures))

    def test_multiple_failures_all_reported(self):
        """Multiple validation failures should all be reported."""
        checkpoint = {
            "self_report": {"is_job_complete": False, "code_changes_made": True, "linters_pass": False},
            "reflection": {
                "what_was_done": "Short",
                "what_remains": "lots to do",
                "key_insight": "Brief",
                "search_terms": []
            }
        }

        is_valid, failures = self.mod.validate_checkpoint(checkpoint)
        self.assertFalse(is_valid)
        self.assertGreater(len(failures), 3)

    def test_category_can_be_any_string(self):
        """Category field can be any string (no blocking validation)."""
        checkpoint = {
            "self_report": {"is_job_complete": True, "category": "custom-category-type"},
            "reflection": {
                "what_was_done": "Analyzed performance bottleneck in query layer",
                "what_remains": "none",
                "key_insight": "Database query optimization requires understanding index usage",
                "search_terms": ["performance", "database", "optimization"]
            }
        }

        is_valid, failures = self.mod.validate_checkpoint(checkpoint)
        self.assertTrue(is_valid)
        self.assertEqual(failures, [])


# ============================================================================
# Memory Capture Tests
# ============================================================================


class TestAutoCaptureMemory(unittest.TestCase):
    """Tests for auto_capture_memory function."""

    def setUp(self):
        self.mod = load_stop_validator()

    def test_short_what_was_done_returns_without_capturing(self):
        """Short what_was_done (<20 chars) should return without capturing."""
        with tempfile.TemporaryDirectory() as td:
            checkpoint = {
                "reflection": {
                    "what_was_done": "Fixed bug",
                    "key_insight": "Always test thoroughly",
                    "search_terms": ["bug", "fix"]
                }
            }

            # Mock the _memory module's append_event
            with patch("_memory.append_event") as mock_append:
                self.mod.auto_capture_memory(td, checkpoint)
                # Should not be called because what_was_done is too short
                self.assertFalse(mock_append.called)

    def test_calls_append_event_with_correct_entities(self):
        """Should call append_event with search_terms and git diff files."""
        with tempfile.TemporaryDirectory() as td:
            checkpoint = {
                "self_report": {"category": "bugfix", "problem_type": "race-condition"},
                "reflection": {
                    "what_was_done": "Fixed authentication token validation race condition",
                    "key_insight": "Token validation must happen before state updates",
                    "search_terms": ["auth", "token", "race-condition"]
                }
            }

            with patch.object(self.mod, "_get_git_diff_files", return_value=["src/auth/validator.py"]):
                with patch("_memory.append_event") as mock_append:
                    self.mod.auto_capture_memory(td, checkpoint)

                    self.assertTrue(mock_append.called)
                    call_kwargs = mock_append.call_args[1]
                    entities = call_kwargs["entities"]
                    self.assertIn("auth", entities)
                    self.assertIn("token", entities)
                    self.assertIn("validator.py", entities)
                    self.assertEqual(call_kwargs["category"], "bugfix")

    def test_handles_core_assertions(self):
        """Should handle core_assertions in checkpoint."""
        with tempfile.TemporaryDirectory() as td:
            checkpoint = {
                "self_report": {"category": "architecture"},
                "reflection": {
                    "what_was_done": "Refactored authentication layer to use DI",
                    "key_insight": "Dependency injection makes testing easier",
                    "search_terms": ["auth", "di", "testing"],
                    "core_assertions": [
                        {"topic": "authentication-patterns", "assertion": "Use DI for auth"}
                    ]
                }
            }

            with patch.object(self.mod, "_get_git_diff_files", return_value=[]):
                with patch("_memory.append_event"):
                    with patch("_memory.append_assertion") as mock_assertion:
                        self.mod.auto_capture_memory(td, checkpoint)
                        self.assertTrue(mock_assertion.called)


# ============================================================================
# Blocking Messages Tests
# ============================================================================


class TestBlockingMessages(unittest.TestCase):
    """Tests for blocking message functions."""

    def setUp(self):
        self.mod = load_stop_validator()

    def test_block_no_checkpoint_exits_with_code_2(self):
        """block_no_checkpoint should exit with code 2."""
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(SystemExit) as cm:
                self.mod.block_no_checkpoint(td)
            self.assertEqual(cm.exception.code, 2)

    def test_block_with_failures_exits_with_code_2(self):
        """block_with_failures should exit with code 2."""
        failures = ["is_job_complete is false", "what_was_done too brief"]
        with self.assertRaises(SystemExit) as cm:
            self.mod.block_with_failures(failures)
        self.assertEqual(cm.exception.code, 2)

    def test_block_uncommitted_changes_exits_with_code_2(self):
        """block_uncommitted_changes should exit with code 2."""
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(SystemExit) as cm:
                self.mod.block_uncommitted_changes(td)
            self.assertEqual(cm.exception.code, 2)


# ============================================================================
# Main Function Tests
# ============================================================================


class TestMain(unittest.TestCase):
    """Tests for main function."""

    def setUp(self):
        self.mod = load_stop_validator()

    def test_fleet_role_knowledge_sync_allows_stop(self):
        """Fleet role knowledge_sync should allow stop (exit 0)."""
        with patch.dict(os.environ, {"FLEET_ROLE": "knowledge_sync"}):
            with patch("sys.stdin", MagicMock(read=MagicMock(return_value=""))):
                with self.assertRaises(SystemExit) as cm:
                    self.mod.main()
                self.assertEqual(cm.exception.code, 0)

    def test_no_checkpoint_required_allows_stop(self):
        """No checkpoint required should allow stop (exit 0)."""
        with tempfile.TemporaryDirectory() as td:
            input_data = json.dumps({"cwd": td})

            with patch.dict(os.environ, {}, clear=True):
                with patch("sys.stdin", MagicMock(read=MagicMock(return_value=input_data))):
                    with patch.object(self.mod, "requires_checkpoint", return_value=False):
                        with patch.object(self.mod, "load_checkpoint", return_value=None):
                            with self.assertRaises(SystemExit) as cm:
                                self.mod.main()
                            self.assertEqual(cm.exception.code, 0)

    def test_valid_checkpoint_allows_stop(self):
        """Valid checkpoint should allow stop (exit 0) and call auto_capture_memory."""
        with tempfile.TemporaryDirectory() as td:
            checkpoint = {
                "self_report": {"is_job_complete": True, "code_changes_made": False},
                "reflection": {
                    "what_was_done": "Refactored authentication module",
                    "what_remains": "none",
                    "key_insight": "DI patterns make authentication code easier to test",
                    "search_terms": ["auth", "refactor", "testing", "di"]
                }
            }

            input_data = json.dumps({"cwd": td})

            with patch.dict(os.environ, {}, clear=True):
                with patch("sys.stdin", MagicMock(read=MagicMock(return_value=input_data))):
                    with patch.object(self.mod, "requires_checkpoint", return_value=True):
                        with patch.object(self.mod, "load_checkpoint", return_value=checkpoint):
                            with patch.object(self.mod, "validate_checkpoint", return_value=(True, [])):
                                with patch.object(self.mod, "auto_capture_memory") as mock_capture:
                                    with patch.object(self.mod, "reset_state_for_next_task"):
                                        with self.assertRaises(SystemExit) as cm:
                                            self.mod.main()
                                        self.assertEqual(cm.exception.code, 0)
                                        self.assertTrue(mock_capture.called)

    def test_missing_checkpoint_blocks_stop(self):
        """Missing checkpoint when required should block stop (exit 2)."""
        with tempfile.TemporaryDirectory() as td:
            input_data = json.dumps({"cwd": td})

            with patch.dict(os.environ, {}, clear=True):
                with patch("sys.stdin", MagicMock(read=MagicMock(return_value=input_data))):
                    with patch.object(self.mod, "requires_checkpoint", return_value=True):
                        with patch.object(self.mod, "load_checkpoint", return_value=None):
                            with self.assertRaises(SystemExit) as cm:
                                self.mod.main()
                            self.assertEqual(cm.exception.code, 2)

    def test_invalid_checkpoint_blocks_stop(self):
        """Invalid checkpoint should block stop (exit 2)."""
        with tempfile.TemporaryDirectory() as td:
            checkpoint = {"self_report": {"is_job_complete": False}}
            input_data = json.dumps({"cwd": td})

            with patch.dict(os.environ, {}, clear=True):
                with patch("sys.stdin", MagicMock(read=MagicMock(return_value=input_data))):
                    with patch.object(self.mod, "requires_checkpoint", return_value=True):
                        with patch.object(self.mod, "load_checkpoint", return_value=checkpoint):
                            with patch.object(self.mod, "validate_checkpoint", return_value=(False, ["failures"])):
                                with self.assertRaises(SystemExit) as cm:
                                    self.mod.main()
                                self.assertEqual(cm.exception.code, 2)

    def test_uncommitted_changes_with_code_changes_made_blocks_stop(self):
        """Uncommitted changes in autonomous mode with code_changes_made should block."""
        with tempfile.TemporaryDirectory() as td:
            checkpoint = {
                "self_report": {"is_job_complete": True, "code_changes_made": True, "linters_pass": True},
                "reflection": {
                    "what_was_done": "Added new feature for user authentication",
                    "what_remains": "none",
                    "key_insight": "Feature implementation requires thorough testing",
                    "search_terms": ["feature", "auth", "testing"]
                }
            }

            input_data = json.dumps({"cwd": td})

            with patch.dict(os.environ, {}, clear=True):
                with patch("sys.stdin", MagicMock(read=MagicMock(return_value=input_data))):
                    with patch.object(self.mod, "requires_checkpoint", return_value=True):
                        with patch.object(self.mod, "load_checkpoint", return_value=checkpoint):
                            with patch.object(self.mod, "validate_checkpoint", return_value=(True, [])):
                                with patch.object(self.mod, "is_autonomous_mode_active", return_value=True):
                                    with patch.object(self.mod, "has_uncommitted_changes", return_value=True):
                                        with self.assertRaises(SystemExit) as cm:
                                            self.mod.main()
                                        self.assertEqual(cm.exception.code, 2)

    def test_uncommitted_changes_without_code_changes_made_allows_stop(self):
        """Uncommitted changes in autonomous mode without code_changes_made should allow stop."""
        with tempfile.TemporaryDirectory() as td:
            checkpoint = {
                "self_report": {"is_job_complete": True, "code_changes_made": False},
                "reflection": {
                    "what_was_done": "Researched authentication patterns and documented findings",
                    "what_remains": "none",
                    "key_insight": "Modern auth should use JWT tokens for stateless sessions",
                    "search_terms": ["auth", "jwt", "research", "patterns"]
                }
            }

            input_data = json.dumps({"cwd": td})

            with patch.dict(os.environ, {}, clear=True):
                with patch("sys.stdin", MagicMock(read=MagicMock(return_value=input_data))):
                    with patch.object(self.mod, "requires_checkpoint", return_value=True):
                        with patch.object(self.mod, "load_checkpoint", return_value=checkpoint):
                            with patch.object(self.mod, "validate_checkpoint", return_value=(True, [])):
                                with patch.object(self.mod, "is_autonomous_mode_active", return_value=True):
                                    with patch.object(self.mod, "has_uncommitted_changes", return_value=True):
                                        with patch.object(self.mod, "auto_capture_memory"):
                                            with patch.object(self.mod, "reset_state_for_next_task"):
                                                with self.assertRaises(SystemExit) as cm:
                                                    self.mod.main()
                                                self.assertEqual(cm.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
