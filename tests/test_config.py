"""Tests for config module."""

import os
from unittest.mock import patch

import pytest

from check_contribution_action.config import Config


class TestConfig:
    """Test cases for Config class."""

    def test_required_input_missing(self):
        """Test that missing required input raises ValueError."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(
                ValueError, match="Required input 'github_token' is not provided"
            ):
                Config()

    def test_required_input_present(self):
        """Test that required input is loaded correctly."""
        with patch.dict(os.environ, {"INPUT_GITHUB_TOKEN": "test_token"}):
            config = Config()
            assert config.github_token == "test_token"

    def test_optional_inputs_with_defaults(self):
        """Test that optional inputs use correct defaults."""
        with patch.dict(os.environ, {"INPUT_GITHUB_TOKEN": "test_token"}):
            config = Config()
            assert config.skip_users == []
            assert config.check_issue_linking is False
            assert config.check_issue_reference is False
            assert config.require_assignee is False
            assert config.check_commit_signature is False
            assert config.check_sign_off is False
            assert config.sign_off_strict_match is False
            assert config.close_pr_on_assignee_mismatch is False
            assert config.validate_bot_authors is False
            assert config.has_enabled_checks is False
            assert (
                config.no_issue_message
                == "This PR must be linked to an issue before it can be merged."
            )
            assert (
                config.no_assignee_message
                == "The linked issue must be assigned to the PR author before this PR can be merged."
            )
            assert (
                config.unsigned_commits_message == "One or more commits are not signed."
            )
            assert (
                config.missing_sign_off_message
                == "One or more commits are missing a Signed-off-by trailer."
            )
            assert (
                config.sign_off_mismatch_message
                == "One or more Signed-off-by trailers do not match the commit author."
            )

    def test_skip_users_parsing(self):
        """Test parsing of comma-separated skip users."""
        with patch.dict(
            os.environ,
            {
                "INPUT_GITHUB_TOKEN": "test_token",
                "INPUT_SKIP_USERS": "user1, user2, user3",
            },
        ):
            config = Config()
            assert config.skip_users == ["user1", "user2", "user3"]

    def test_skip_users_empty(self):
        """Test handling of empty skip users."""
        with patch.dict(
            os.environ, {"INPUT_GITHUB_TOKEN": "test_token", "INPUT_SKIP_USERS": ""}
        ):
            config = Config()
            assert config.skip_users == []

    def test_boolean_inputs(self):
        """Test parsing of boolean inputs."""
        with patch.dict(
            os.environ,
            {
                "INPUT_GITHUB_TOKEN": "test_token",
                "INPUT_CHECK_ISSUE_LINKING": "true",
                "INPUT_CHECK_COMMIT_SIGNATURE": "true",
                "INPUT_CHECK_SIGN_OFF": "true",
                "INPUT_SIGN_OFF_STRICT_MATCH": "true",
                "INPUT_CLOSE_PR_ON_ASSIGNEE_MISMATCH": "true",
            },
        ):
            config = Config()
            assert config.check_issue_linking is True
            assert config.check_commit_signature is True
            assert config.check_sign_off is True
            assert config.sign_off_strict_match is True
            assert config.close_pr_on_assignee_mismatch is True
            assert config.has_enabled_checks is True
            assert config.enabled_check_names() == [
                "issue_linking",
                "commit_signature",
                "sign_off",
            ]

    def test_check_issue_reference_input(self):
        """Test parsing of check_issue_reference input."""
        with patch.dict(
            os.environ,
            {
                "INPUT_GITHUB_TOKEN": "test_token",
                "INPUT_CHECK_ISSUE_REFERENCE": "true",
            },
        ):
            config = Config()
            assert config.check_issue_reference is True
            assert config.has_enabled_checks is True

        with patch.dict(
            os.environ,
            {
                "INPUT_GITHUB_TOKEN": "test_token",
                "INPUT_CHECK_ISSUE_REFERENCE": "false",
            },
        ):
            config = Config()
            assert config.check_issue_reference is False

    def test_custom_messages(self):
        """Test custom error messages."""
        with patch.dict(
            os.environ,
            {
                "INPUT_GITHUB_TOKEN": "test_token",
                "INPUT_NO_ISSUE_MESSAGE": "Custom no issue message",
                "INPUT_NO_ASSIGNEE_MESSAGE": "Custom assignee message",
                "INPUT_UNSIGNED_COMMITS_MESSAGE": "Custom unsigned message",
            },
        ):
            config = Config()
            assert config.no_issue_message == "Custom no issue message"
            assert config.no_assignee_message == "Custom assignee message"
            assert config.unsigned_commits_message == "Custom unsigned message"

    def test_skip_users_file_path_only(self, tmp_path):
        """Test parsing of skip users from file only."""
        skip_users_file = tmp_path / "skip_users.txt"
        skip_users_file.write_text("user1\nuser2\nuser3\n")

        with patch.dict(
            os.environ,
            {
                "INPUT_GITHUB_TOKEN": "test_token",
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
                "INPUT_GITHUB_TOKEN": "test_token",
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
                "INPUT_GITHUB_TOKEN": "test_token",
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
                "INPUT_GITHUB_TOKEN": "test_token",
                "INPUT_SKIP_USERS_FILE_PATH": str(skip_users_file),
            },
        ):
            config = Config()
            assert config.skip_users == []

    def test_resolve_file_path_preserves_github_workspace_path(self):
        """Test skip users file paths under /github/workspace are kept as-is."""
        with patch.dict(os.environ, {"INPUT_GITHUB_TOKEN": "test_token"}):
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
                "INPUT_GITHUB_TOKEN": "test_token",
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
                "INPUT_GITHUB_TOKEN": "test_token",
                "INPUT_TARGET_BRANCHES": "main\ndevelop\n",
            },
        ):
            config = Config()
            assert config.target_branches == ["main", "develop"]

    def test_require_assignee_enables_check(self):
        """Test that require_assignee counts as an enabled check."""
        with patch.dict(
            os.environ,
            {
                "INPUT_GITHUB_TOKEN": "test_token",
                "INPUT_REQUIRE_ASSIGNEE": "true",
            },
        ):
            config = Config()
            assert config.has_enabled_checks is True
            assert "assignee" in config.enabled_check_names()

    def test_validate_bot_authors_input(self):
        """Test validate_bot_authors boolean input."""
        with patch.dict(
            os.environ,
            {
                "INPUT_GITHUB_TOKEN": "test_token",
                "INPUT_VALIDATE_BOT_AUTHORS": "true",
            },
        ):
            config = Config()
            assert config.validate_bot_authors is True

    def test_target_branches_enables_check(self):
        """Test that target_branches counts as an enabled check."""
        with patch.dict(
            os.environ,
            {
                "INPUT_GITHUB_TOKEN": "test_token",
                "INPUT_TARGET_BRANCHES": "main\n",
            },
        ):
            config = Config()
            assert config.has_enabled_checks is True
            assert "target_branches" in config.enabled_check_names()
