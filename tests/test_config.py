"""Tests for config module."""

import os
from unittest.mock import patch

import pytest

from check_contribution_action.check_for import DEFAULT_ERROR_MESSAGES
from check_contribution_action.config import Config

BASE_ENV = {
    "INPUT_GITHUB_TOKEN": "test_token",
    "INPUT_CHECK_FOR": "issue_reference",
}


class TestConfig:
    """Test cases for Config class."""

    def test_required_input_missing(self):
        """Test that missing required input raises ValueError."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(
                ValueError, match="Required input 'github_token' is not provided"
            ):
                Config()

    def test_check_for_missing(self):
        """Test that missing check_for raises ValueError."""
        with patch.dict(os.environ, {"INPUT_GITHUB_TOKEN": "test_token"}, clear=True):
            with pytest.raises(
                ValueError, match="Required input 'check_for' is not provided"
            ):
                Config()

    def test_required_input_present(self):
        """Test that required inputs are loaded correctly."""
        with patch.dict(os.environ, BASE_ENV):
            config = Config()
            assert config.github_token == "test_token"
            assert config.check_for == frozenset({"issue_reference"})

    def test_optional_inputs_with_defaults(self):
        """Test that optional inputs use correct defaults."""
        with patch.dict(os.environ, BASE_ENV):
            config = Config()
            assert config.skip_users == []
            assert config.check_for == frozenset({"issue_reference"})
            assert config.check_issue_reference is True
            assert config.check_issue_assignee is False
            assert config.check_commit_signature is False
            assert config.check_commit_sign_off is False
            assert config.check_target_branch is False
            assert config.sign_off_strict_match is False
            assert config.close_on == frozenset()
            assert config.validate_bot_authors is False
            assert config.has_enabled_checks is True
            assert config.errors == DEFAULT_ERROR_MESSAGES

    def test_skip_users_parsing(self):
        """Test parsing of comma-separated skip users."""
        with patch.dict(
            os.environ,
            {
                **BASE_ENV,
                "INPUT_SKIP_USERS": "user1, user2, user3",
            },
        ):
            config = Config()
            assert config.skip_users == ["user1", "user2", "user3"]

    def test_skip_users_empty(self):
        """Test handling of empty skip users."""
        with patch.dict(os.environ, {**BASE_ENV, "INPUT_SKIP_USERS": ""}):
            config = Config()
            assert config.skip_users == []

    def test_check_for_parsing(self):
        """Test parsing of check_for values."""
        with patch.dict(
            os.environ,
            {
                "INPUT_GITHUB_TOKEN": "test_token",
                "INPUT_CHECK_FOR": "commit_sign_off, commit_signature, issue_reference",
                "INPUT_SIGN_OFF_STRICT_MATCH": "true",
            },
        ):
            config = Config()
            assert config.check_for == frozenset(
                {"issue_reference", "commit_signature", "commit_sign_off"}
            )
            assert config.check_issue_reference is True
            assert config.check_commit_signature is True
            assert config.check_commit_sign_off is True
            assert config.sign_off_strict_match is True
            assert config.has_enabled_checks is True
            assert config.enabled_check_names() == [
                "commit_sign_off",
                "commit_signature",
                "issue_reference",
            ]

    def test_check_for_ignores_unknown_values(self):
        """Test unknown check_for values are ignored."""
        with patch.dict(
            os.environ,
            {
                **BASE_ENV,
                "INPUT_CHECK_FOR": "issue_reference,not_real",
            },
        ):
            config = Config()
            assert config.check_for == frozenset({"issue_reference"})

    def test_check_for_issue_reference(self):
        """Test issue_reference enables the corresponding check."""
        with patch.dict(
            os.environ,
            {
                "INPUT_GITHUB_TOKEN": "test_token",
                "INPUT_CHECK_FOR": "issue_reference",
            },
        ):
            config = Config()
            assert config.check_issue_reference is True
            assert config.has_enabled_checks is True

    def test_close_on_parsing(self):
        """Test parsing of close_on triggers."""
        with patch.dict(
            os.environ,
            {
                **BASE_ENV,
                "INPUT_CHECK_FOR": "commit_signature, issue_assignee, issue_reference",
                "INPUT_CLOSE_ON": "issue_assignee, commit_signature",
            },
        ):
            config = Config()
            assert config.close_on == frozenset({"issue_assignee", "commit_signature"})

    def test_close_on_ignores_unknown_triggers(self):
        """Test unknown close_on values are ignored."""
        with patch.dict(
            os.environ,
            {
                **BASE_ENV,
                "INPUT_CHECK_FOR": "issue_assignee, issue_reference",
                "INPUT_CLOSE_ON": "issue_assignee,not_real",
            },
        ):
            config = Config()
            assert config.close_on == frozenset({"issue_assignee"})

    def test_custom_errors(self):
        """Test custom error messages."""
        with patch.dict(
            os.environ,
            {
                **BASE_ENV,
                "INPUT_ERROR_ISSUE_REFERENCE": "Custom reference message",
                "INPUT_ERROR_ISSUE_ASSIGNEE": "Custom assignee message",
                "INPUT_ERROR_COMMIT_SIGNATURE": "Custom signature message",
            },
        ):
            config = Config()
            assert config.errors["issue_reference"] == "Custom reference message"
            assert config.errors["issue_assignee"] == "Custom assignee message"
            assert config.errors["commit_signature"] == "Custom signature message"

    def test_skip_users_file_path_only(self, tmp_path):
        """Test parsing of skip users from file only."""
        skip_users_file = tmp_path / "skip_users.txt"
        skip_users_file.write_text("user1\nuser2\nuser3\n")

        with patch.dict(
            os.environ,
            {
                **BASE_ENV,
                "INPUT_SKIP_USERS_FILE_PATH": str(skip_users_file),
            },
        ):
            config = Config()
            assert config.skip_users == ["user1", "user2", "user3"]

    def test_skip_users_combined(self, tmp_path):
        """Test combining skip_users and skip_users_file_path."""
        skip_users_file = tmp_path / "skip_users.txt"
        skip_users_file.write_text("user2\nuser3\nuser4\n")

        with patch.dict(
            os.environ,
            {
                **BASE_ENV,
                "INPUT_SKIP_USERS": "user1, user2",
                "INPUT_SKIP_USERS_FILE_PATH": str(skip_users_file),
            },
        ):
            config = Config()
            assert sorted(config.skip_users) == ["user1", "user2", "user3", "user4"]

    def test_skip_users_file_not_found(self):
        """Test handling of a non-existent skip users file."""
        with patch.dict(
            os.environ,
            {
                **BASE_ENV,
                "INPUT_SKIP_USERS_FILE_PATH": "non_existent_file.txt",
            },
        ):
            config = Config()
            assert config.skip_users == []

    def test_skip_users_empty_file(self, tmp_path):
        """Test handling of an empty skip users file."""
        skip_users_file = tmp_path / "skip_users.txt"
        skip_users_file.write_text("")

        with patch.dict(
            os.environ,
            {
                **BASE_ENV,
                "INPUT_SKIP_USERS_FILE_PATH": str(skip_users_file),
            },
        ):
            config = Config()
            assert config.skip_users == []

    def test_resolve_file_path_preserves_github_workspace_path(self):
        """Test skip users file paths under /github/workspace are kept as-is."""
        with patch.dict(os.environ, BASE_ENV):
            config = Config()
            path = config.resolve_file_path("/github/workspace/config/skip_users.txt")
            assert path == "/github/workspace/config/skip_users.txt"

    def test_skip_users_file_read_error(self, tmp_path):
        """Test handling of OS errors when reading skip users file."""
        skip_users_file = tmp_path / "skip_users.txt"
        skip_users_file.write_text("user1\n")

        with patch.dict(
            os.environ,
            {
                **BASE_ENV,
                "INPUT_SKIP_USERS_FILE_PATH": str(skip_users_file),
            },
        ):
            with patch("builtins.open", side_effect=OSError("Permission denied")):
                config = Config()
                assert config.skip_users == []

    def test_target_branches_parsing(self):
        """Test parsing of newline-separated target branches."""
        with patch.dict(
            os.environ,
            {
                **BASE_ENV,
                "INPUT_TARGET_BRANCHES": "main\ndevelop\n",
            },
        ):
            config = Config()
            assert config.target_branches == ["main", "develop"]

    def test_issue_assignee_enables_check(self):
        """Test that issue_assignee in check_for counts as an enabled check."""
        with patch.dict(
            os.environ,
            {
                "INPUT_GITHUB_TOKEN": "test_token",
                "INPUT_CHECK_FOR": "issue_assignee",
            },
        ):
            config = Config()
            assert config.has_enabled_checks is True
            assert "issue_assignee" in config.enabled_check_names()

    def test_validate_bot_authors_input(self):
        """Test validate_bot_authors boolean input."""
        with patch.dict(
            os.environ,
            {
                **BASE_ENV,
                "INPUT_VALIDATE_BOT_AUTHORS": "true",
            },
        ):
            config = Config()
            assert config.validate_bot_authors is True

    def test_validate_close_on_rejects_disabled_checks(self):
        """Test close_on raises when triggers are not enabled in check_for."""
        with patch.dict(
            os.environ,
            {
                **BASE_ENV,
                "INPUT_CHECK_FOR": "issue_reference",
                "INPUT_CLOSE_ON": "commit_signature",
            },
        ):
            with pytest.raises(
                ValueError,
                match="close_on includes checks that are not enabled in check_for",
            ):
                Config()

    def test_target_branch_requires_target_branches(self):
        """Test target_branch check requires a non-empty target_branches list."""
        with patch.dict(
            os.environ,
            {
                "INPUT_GITHUB_TOKEN": "test_token",
                "INPUT_CHECK_FOR": "target_branch",
            },
        ):
            with pytest.raises(
                ValueError,
                match="check_for includes target_branch but target_branches is not set",
            ):
                Config()

        with patch.dict(
            os.environ,
            {
                "INPUT_GITHUB_TOKEN": "test_token",
                "INPUT_CHECK_FOR": "target_branch",
                "INPUT_TARGET_BRANCHES": "main\n",
            },
        ):
            config = Config()
            assert config.check_target_branch is True
            assert config.has_enabled_checks is True
            assert "target_branch" in config.enabled_check_names()
