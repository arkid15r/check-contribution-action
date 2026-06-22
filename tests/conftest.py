"""Pytest configuration and fixtures for check-contribution-action tests."""

from unittest.mock import Mock

import pytest

from check_contribution_action.config import Config


@pytest.fixture
def mock_config():
    """Create a mock configuration for testing."""
    config = Mock(spec=Config)
    config.skip_users = ["testuser1", "testuser2"]
    config.check_issue_linking = True
    config.check_issue_reference = False
    config.require_assignee = True
    config.check_commit_signature = False
    config.check_sign_off = False
    config.sign_off_strict_match = False
    config.close_pr_on_assignee_mismatch = False
    config.no_issue_message = "No issue message"
    config.no_assignee_message = "No assignee message"
    config.target_branches = []
    config.invalid_branch_message = "Invalid branch message"
    config.unsigned_commits_message = "Unsigned commits message"
    config.missing_sign_off_message = "Missing sign-off message"
    config.sign_off_mismatch_message = "Sign-off mismatch message"
    config.has_enabled_checks = False
    config.enabled_check_names.return_value = []
    return config


@pytest.fixture
def mock_github_client():
    """Create a mock GitHub client for testing."""
    return Mock()


@pytest.fixture
def mock_pr():
    """Create a mock pull request for testing."""
    pr = Mock()
    pr.number = 123
    pr.user.login = "testuser"
    pr.user.type = "User"
    pr.base.ref = "main"
    pr.base.repo.default_branch = "main"
    pr.base.repo.full_name = "testowner/testrepo"
    pr.body = "This is a test PR"
    return pr


@pytest.fixture
def mock_bot_pr():
    """Create a mock bot pull request for testing."""
    pr = Mock()
    pr.number = 124
    pr.user.login = "dependabot[bot]"
    pr.user.type = "Bot"
    return pr


@pytest.fixture
def mock_issue():
    """Create a mock issue for testing."""
    issue = Mock()
    issue.number = 456
    issue.assignees = []
    return issue


@pytest.fixture
def mock_issue_with_assignee():
    """Create a mock issue with assignee for testing."""
    assignee = Mock()
    assignee.login = "testuser"

    issue = Mock()
    issue.number = 456
    issue.assignees = [assignee]
    return issue


@pytest.fixture
def mock_issue_with_different_assignee():
    """Create a mock issue with different assignee for testing."""
    assignee = Mock()
    assignee.login = "differentuser"

    issue = Mock()
    issue.number = 456
    issue.assignees = [assignee]
    return issue
