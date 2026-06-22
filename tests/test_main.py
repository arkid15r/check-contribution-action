"""Tests for main module."""

import json
import os
from pathlib import Path
import sys
from unittest.mock import Mock, mock_open, patch

import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from check_contribution_action.main import (  # noqa: E402
    is_fork_pr,
    load_event_data,
    main,
    needs_git_commits,
    needs_github_client,
    run_checks,
)
from check_contribution_action.models import CheckResult, ValidationResult  # noqa: E402


class TestIsForkPr:
    """Test cases for fork pull request detection."""

    def test_same_repo_is_not_fork(self):
        """Test that same-repository PRs are not treated as forks."""
        event_data = {
            "repository": {"full_name": "owner/repo"},
            "pull_request": {
                "head": {"repo": {"full_name": "owner/repo"}},
            },
        }
        assert is_fork_pr(event_data) is False

    def test_different_head_repo_is_fork(self):
        """Test that fork PRs are detected."""
        event_data = {
            "repository": {"full_name": "owner/repo"},
            "pull_request": {
                "head": {"repo": {"full_name": "forker/repo"}},
            },
        }
        assert is_fork_pr(event_data) is True

    def test_missing_repo_data_is_not_fork(self):
        """Test that incomplete event data is not treated as a fork."""
        event_data = {"pull_request": {"head": {}}}
        assert is_fork_pr(event_data) is False


class TestLoadEventData:
    """Test cases for event payload loading."""

    @patch.dict(os.environ, {"GITHUB_EVENT_PATH": "/fake/event/path"})
    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data='{"pull_request": {"number": 1}}',
    )
    def test_load_event_data_success(self, mock_file):
        """Test successful event payload loading."""
        event_data = load_event_data()
        assert event_data["pull_request"]["number"] == 1
        mock_file.assert_called_once_with("/fake/event/path", encoding="utf-8")

    @patch.dict(os.environ, {}, clear=True)
    def test_load_event_data_missing_path(self):
        """Test missing GITHUB_EVENT_PATH exits."""
        with pytest.raises(SystemExit) as exc_info:
            load_event_data()
        assert exc_info.value.code == 1


def make_event_data(*, fork: bool = False) -> dict:
    head_repo = "forker/repo" if fork else "owner/repo"
    return {
        "pull_request": {
            "number": 123,
            "head": {
                "repo": {"full_name": head_repo},
                "sha": "headsha1234567890123456789012345678901234",
            },
            "base": {
                "sha": "basesha1234567890123456789012345678901234",
            },
        },
        "repository": {"full_name": "owner/repo"},
    }


class TestMain:
    """Test cases for main function."""

    @patch("check_contribution_action.main.Config")
    @patch("builtins.open", new_callable=mock_open)
    @patch.dict(
        os.environ,
        {"GITHUB_EVENT_PATH": "/fake/event/path", "INPUT_GITHUB_TOKEN": "test_token"},
    )
    def test_main_skips_fork_pr(self, mock_file, mock_config_class):
        """Test that fork PRs exit successfully without running checks."""
        mock_file.return_value.read.return_value = json.dumps(
            make_event_data(fork=True)
        )

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        mock_config_class.assert_called_once()

    @patch("check_contribution_action.main.Config")
    @patch("builtins.open", new_callable=mock_open)
    @patch.dict(
        os.environ,
        {"GITHUB_EVENT_PATH": "/fake/event/path", "INPUT_GITHUB_TOKEN": "test_token"},
    )
    def test_main_no_enabled_checks(self, mock_file, mock_config_class):
        """Test that disabled checks exit successfully with a warning."""
        mock_file.return_value.read.return_value = json.dumps(make_event_data())
        mock_config = mock_config_class.return_value
        mock_config.has_enabled_checks = False

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0

    @patch("check_contribution_action.main.run_checks")
    @patch("check_contribution_action.main.Github")
    @patch("check_contribution_action.main.Config")
    @patch("builtins.open", new_callable=mock_open)
    @patch.dict(
        os.environ,
        {"GITHUB_EVENT_PATH": "/fake/event/path", "INPUT_GITHUB_TOKEN": "test_token"},
    )
    def test_main_validation_passes(
        self, mock_file, mock_config_class, mock_github_class, mock_run_checks
    ):
        """Test successful validation exits with code 0."""
        mock_file.return_value.read.return_value = json.dumps(make_event_data())
        mock_config = mock_config_class.return_value
        mock_config.has_enabled_checks = True
        mock_config.enabled_check_names.return_value = ["commit_signature"]
        mock_config.check_issue_linking = False
        mock_config.check_issue_reference = False
        mock_config.require_assignee = False
        mock_config.target_branches = []
        mock_run_checks.return_value = ValidationResult(passed=True, results=[])

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        mock_run_checks.assert_called_once()

    @patch("check_contribution_action.main.PrManager")
    @patch("check_contribution_action.main.run_checks")
    @patch("check_contribution_action.main.Github")
    @patch("check_contribution_action.main.Config")
    @patch("builtins.open", new_callable=mock_open)
    @patch.dict(
        os.environ,
        {"GITHUB_EVENT_PATH": "/fake/event/path", "INPUT_GITHUB_TOKEN": "test_token"},
    )
    def test_main_validation_fails_with_github(
        self,
        mock_file,
        mock_config_class,
        mock_github_class,
        mock_run_checks,
        mock_pr_manager_class,
    ):
        """Test failed validation posts comment and exits with code 1."""
        mock_file.return_value.read.return_value = json.dumps(make_event_data())
        mock_config = mock_config_class.return_value
        mock_config.has_enabled_checks = True
        mock_config.enabled_check_names.return_value = ["issue_linking"]
        mock_config.check_issue_linking = True
        mock_config.check_issue_reference = False
        mock_config.require_assignee = False
        mock_config.target_branches = []
        mock_config.github_token = "token"

        mock_repo = Mock()
        mock_pull_request = Mock()
        mock_github_class.return_value.get_repo.return_value = mock_repo
        mock_repo.get_pull.return_value = mock_pull_request

        mock_run_checks.return_value = ValidationResult(
            passed=False,
            results=[CheckResult(name="issue", passed=False, reason="No linked issue")],
        )

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1
        mock_pr_manager_class.return_value.handle_validation_failure.assert_called_once()

    @patch("check_contribution_action.main.run_checks")
    @patch("check_contribution_action.main.Config")
    @patch("builtins.open", new_callable=mock_open)
    @patch.dict(
        os.environ,
        {"GITHUB_EVENT_PATH": "/fake/event/path", "INPUT_GITHUB_TOKEN": "test_token"},
    )
    def test_main_git_only_failure_without_github(
        self, mock_file, mock_config_class, mock_run_checks
    ):
        """Test git-only failures exit without PR manager when no GitHub client."""
        mock_file.return_value.read.return_value = json.dumps(make_event_data())
        mock_config = mock_config_class.return_value
        mock_config.has_enabled_checks = True
        mock_config.enabled_check_names.return_value = ["commit_signature"]
        mock_config.check_issue_linking = False
        mock_config.check_issue_reference = False
        mock_config.require_assignee = False
        mock_config.target_branches = []
        mock_run_checks.return_value = ValidationResult(
            passed=False,
            results=[
                CheckResult(
                    name="commit_signature",
                    passed=False,
                    reason="Unsigned commits",
                    details=["abc123"],
                )
            ],
        )

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1

    @patch.dict(os.environ, {}, clear=True)
    @patch("check_contribution_action.main.Config")
    def test_main_missing_event_path(self, mock_config_class):
        """Test main execution with missing GITHUB_EVENT_PATH."""
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1

    @patch("builtins.open", new_callable=mock_open)
    @patch.dict(
        os.environ,
        {"GITHUB_EVENT_PATH": "/fake/event/path", "INPUT_GITHUB_TOKEN": "test_token"},
    )
    def test_main_no_pull_request_data(self, mock_file):
        """Test main execution with no pull request data in event."""
        event_data = {"repository": {"full_name": "test/repo"}}
        mock_file.return_value.read.return_value = json.dumps(event_data)

        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1

    @patch("check_contribution_action.main.Config")
    @patch.dict(
        os.environ,
        {"GITHUB_EVENT_PATH": "/fake/event/path", "INPUT_GITHUB_TOKEN": "test_token"},
    )
    def test_main_config_error(self, mock_config_class):
        """Test main execution with configuration error."""
        mock_config_class.side_effect = ValueError("Config error")

        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1


class TestOrchestration:
    """Test cases for check orchestration helpers."""

    def test_needs_git_commits(self):
        """Test git commit detection follows signature and sign-off flags."""
        config = Mock()
        config.check_commit_signature = True
        config.check_sign_off = False
        assert needs_git_commits(config) is True

        config.check_commit_signature = False
        config.check_sign_off = False
        assert needs_git_commits(config) is False

    def test_needs_github_client(self):
        """Test GitHub client detection follows issue-related flags."""
        config = Mock()
        config.check_issue_linking = False
        config.check_issue_reference = False
        config.require_assignee = False
        config.target_branches = []
        assert needs_github_client(config) is False

        config.target_branches = ["main"]
        assert needs_github_client(config) is True

    @patch("check_contribution_action.main.load_commits")
    def test_run_checks_runs_enabled_checks_only(self, mock_load_commits):
        """Test orchestrator runs only enabled checks."""
        mock_load_commits.return_value = []
        config = Mock()
        config.check_issue_linking = False
        config.check_issue_reference = False
        config.require_assignee = False
        config.target_branches = []
        config.check_commit_signature = True
        config.check_sign_off = False

        signature_check = Mock()
        signature_check.name = "commit_signature"
        signature_check.is_enabled.return_value = True
        signature_check.run.return_value = CheckResult(
            name="commit_signature", passed=True
        )

        issue_check = Mock()
        issue_check.name = "issue"
        issue_check.is_enabled.return_value = False

        with patch(
            "check_contribution_action.main.ALL_CHECKS",
            [issue_check, signature_check],
        ):
            result = run_checks(config, make_event_data())

        assert result.passed is True
        signature_check.run.assert_called_once()
        issue_check.run.assert_not_called()
        mock_load_commits.assert_called_once()
