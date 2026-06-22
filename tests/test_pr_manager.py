"""Tests for pr_manager module."""

from check_contribution_action.models import CheckResult, ValidationResult
from check_contribution_action.pr_manager import PrManager


def make_validation_result(*results: CheckResult) -> ValidationResult:
    """Build a validation result from check results."""
    return ValidationResult(
        passed=all(result.passed for result in results),
        results=list(results),
    )


class TestPrManager:
    """Test cases for PrManager."""

    def test_handle_validation_failure_with_close_on_assignee_mismatch(
        self, mock_config, mock_pr
    ):
        """Test closing PR when assignee mismatch is configured."""
        mock_config.close_pr_on_assignee_mismatch = True
        validation_result = make_validation_result(
            CheckResult(name="issue", passed=False, reason="Assignee mismatch")
        )

        pr_manager = PrManager(mock_config)
        result = pr_manager.handle_validation_failure(mock_pr, validation_result)

        assert result is True
        mock_pr.create_issue_comment.assert_called_once()
        mock_pr.edit.assert_called_once_with(state="closed")

    def test_handle_validation_failure_without_close(self, mock_config, mock_pr):
        """Test failure handling without closing the PR."""
        mock_config.close_pr_on_assignee_mismatch = False
        validation_result = make_validation_result(
            CheckResult(name="issue", passed=False, reason="Assignee mismatch")
        )

        pr_manager = PrManager(mock_config)
        result = pr_manager.handle_validation_failure(mock_pr, validation_result)

        assert result is True
        mock_pr.create_issue_comment.assert_called_once()
        mock_pr.edit.assert_not_called()

    def test_does_not_close_for_non_assignee_failures(self, mock_config, mock_pr):
        """Test PR is not closed for non-assignee validation failures."""
        mock_config.close_pr_on_assignee_mismatch = True
        validation_result = make_validation_result(
            CheckResult(name="issue", passed=False, reason="No linked issue")
        )

        pr_manager = PrManager(mock_config)
        result = pr_manager.handle_validation_failure(mock_pr, validation_result)

        assert result is True
        mock_pr.edit.assert_not_called()

    def test_build_failure_message_aggregates_checks(self, mock_config):
        """Test aggregated failure comment includes all failed checks."""
        validation_result = make_validation_result(
            CheckResult(
                name="commit_signature",
                passed=False,
                reason="Unsigned commits",
                details=["abc123"],
            ),
            CheckResult(
                name="sign_off",
                passed=False,
                reason="Missing sign-off",
                details=["def456"],
            ),
        )

        pr_manager = PrManager(mock_config)
        message = pr_manager.build_failure_message(validation_result)

        assert "commit_signature" in message
        assert "sign_off" in message
        assert "abc123" in message
        assert "def456" in message

    def test_get_issue_message_no_issue(self, mock_config):
        """Test issue message mapping for missing linked issue."""
        result = CheckResult(name="issue", passed=False, reason="No linked issue")
        pr_manager = PrManager(mock_config)

        assert pr_manager.get_issue_message(result) == mock_config.no_issue_message

    def test_get_issue_message_assignee_mismatch(self, mock_config):
        """Test issue message mapping for assignee mismatch."""
        result = CheckResult(name="issue", passed=False, reason="Assignee mismatch")
        pr_manager = PrManager(mock_config)

        assert pr_manager.get_issue_message(result) == mock_config.no_assignee_message

    def test_get_issue_message_invalid_branch(self, mock_config):
        """Test issue message mapping for invalid branch."""
        result = CheckResult(
            name="issue",
            passed=False,
            reason="PR must target one of the allowed branches: main",
        )
        pr_manager = PrManager(mock_config)

        assert (
            pr_manager.get_issue_message(result) == mock_config.invalid_branch_message
        )

    def test_get_check_message_sign_off_mismatch(self, mock_config):
        """Test sign-off mismatch uses configured message."""
        result = CheckResult(name="sign_off", passed=False, reason="Sign-off mismatch")
        pr_manager = PrManager(mock_config)

        assert (
            pr_manager.get_check_message(result)
            == mock_config.sign_off_mismatch_message
        )

    def test_post_comment_success(self, mock_config, mock_pr):
        """Test successful comment posting."""
        pr_manager = PrManager(mock_config)
        assert pr_manager.post_comment(mock_pr, "Test message") is True
        mock_pr.create_issue_comment.assert_called_once_with("Test message")

    def test_post_comment_failure(self, mock_config, mock_pr):
        """Test comment posting failure."""
        mock_pr.create_issue_comment.side_effect = Exception("API Error")
        pr_manager = PrManager(mock_config)

        assert pr_manager.post_comment(mock_pr, "Test message") is False

    def test_close_pr_success(self, mock_config, mock_pr):
        """Test successful PR closure."""
        pr_manager = PrManager(mock_config)
        assert pr_manager.close_pr(mock_pr) is True
        mock_pr.edit.assert_called_once_with(state="closed")

    def test_close_pr_failure(self, mock_config, mock_pr):
        """Test PR closure failure."""
        mock_pr.edit.side_effect = Exception("API Error")
        pr_manager = PrManager(mock_config)

        assert pr_manager.close_pr(mock_pr) is False

    def test_handle_validation_failure_comment_error(self, mock_config, mock_pr):
        """Test failure when comment posting fails."""
        mock_pr.create_issue_comment.side_effect = Exception("Comment API Error")
        validation_result = make_validation_result(
            CheckResult(name="issue", passed=False, reason="No linked issue")
        )

        pr_manager = PrManager(mock_config)
        assert pr_manager.handle_validation_failure(mock_pr, validation_result) is False

    def test_should_close_pr_for_issue_without_assignee(self, mock_config):
        """Test closure applies to issues with no assignee."""
        mock_config.close_pr_on_assignee_mismatch = True
        validation_result = make_validation_result(
            CheckResult(name="issue", passed=False, reason="Issue has no assignee")
        )
        pr_manager = PrManager(mock_config)

        assert pr_manager.should_close_pr(validation_result) is True
