"""Tests for pr_manager module."""

from unittest.mock import patch

from check_contribution_action.failure_reasons import (
    ASSIGNEE_MISMATCH_REASON,
    ISSUE_HAS_NO_ASSIGNEE_REASON,
    NO_CORRESPONDING_ISSUE_REASON,
    UNSIGNED_COMMITS_REASON,
)
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
        mock_config.close_on = frozenset({"issue_assignee"})
        validation_result = make_validation_result(
            CheckResult(
                name="issue_assignee",
                passed=False,
                reason=ASSIGNEE_MISMATCH_REASON,
            )
        )

        pr_manager = PrManager(mock_config)
        result = pr_manager.handle_validation_failure(mock_pr, validation_result)

        assert result is True
        mock_pr.create_issue_comment.assert_called_once()
        mock_pr.edit.assert_called_once_with(state="closed")

    def test_handle_validation_failure_without_close(self, mock_config, mock_pr):
        """Test failure handling without closing the PR."""
        mock_config.close_on = frozenset()
        validation_result = make_validation_result(
            CheckResult(
                name="issue_assignee",
                passed=False,
                reason=ASSIGNEE_MISMATCH_REASON,
            )
        )

        pr_manager = PrManager(mock_config)
        result = pr_manager.handle_validation_failure(mock_pr, validation_result)

        assert result is True
        mock_pr.create_issue_comment.assert_called_once()
        mock_pr.edit.assert_not_called()

    def test_does_not_close_for_unconfigured_failures(self, mock_config, mock_pr):
        """Test PR is not closed when the failure is not in close_on."""
        mock_config.close_on = frozenset({"issue_assignee"})
        validation_result = make_validation_result(
            CheckResult(
                name="issue_reference",
                passed=False,
                reason=NO_CORRESPONDING_ISSUE_REASON,
            )
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
                reason=UNSIGNED_COMMITS_REASON,
                details=["abc123"],
            ),
            CheckResult(
                name="commit_sign_off",
                passed=False,
                reason="Missing sign-off",
                details=["def456"],
            ),
        )

        pr_manager = PrManager(mock_config)
        message = pr_manager.build_failure_message(validation_result)

        assert "commit_signature" in message
        assert "commit_sign_off" in message
        assert "abc123" in message
        assert "def456" in message

    def test_get_check_message_issue_reference(self, mock_config):
        """Test issue reference failures use the configured message."""
        result = CheckResult(
            name="issue_reference",
            passed=False,
            reason=NO_CORRESPONDING_ISSUE_REASON,
        )
        pr_manager = PrManager(mock_config)

        assert (
            pr_manager.get_check_message(result)
            == mock_config.errors["issue_reference"]
        )

    def test_get_check_message_issue_assignee(self, mock_config):
        """Test assignee failures use the configured message."""
        result = CheckResult(
            name="issue_assignee",
            passed=False,
            reason=ASSIGNEE_MISMATCH_REASON,
        )
        pr_manager = PrManager(mock_config)

        assert (
            pr_manager.get_check_message(result) == mock_config.errors["issue_assignee"]
        )

    def test_get_check_message_target_branch(self, mock_config):
        """Test target branch failures use the configured message."""
        result = CheckResult(
            name="target_branch",
            passed=False,
            reason="PR must target one of the allowed branches: main",
        )
        pr_manager = PrManager(mock_config)

        assert (
            pr_manager.get_check_message(result) == mock_config.errors["target_branch"]
        )

    def test_get_check_message_sign_off(self, mock_config):
        """Test sign-off failures use the commit_sign_off message."""
        result = CheckResult(
            name="commit_sign_off",
            passed=False,
            reason="Sign-off mismatch",
        )
        pr_manager = PrManager(mock_config)

        assert (
            pr_manager.get_check_message(result)
            == mock_config.errors["commit_sign_off"]
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
            CheckResult(
                name="issue_reference",
                passed=False,
                reason=NO_CORRESPONDING_ISSUE_REASON,
            )
        )

        pr_manager = PrManager(mock_config)
        assert pr_manager.handle_validation_failure(mock_pr, validation_result) is False

    def test_should_close_pr_for_issue_without_assignee(self, mock_config):
        """Test closure applies to issues with no assignee."""
        mock_config.close_on = frozenset({"issue_assignee"})
        validation_result = make_validation_result(
            CheckResult(
                name="issue_assignee",
                passed=False,
                reason=ISSUE_HAS_NO_ASSIGNEE_REASON,
            )
        )
        pr_manager = PrManager(mock_config)

        assert pr_manager.should_close_pr(validation_result) is True

    def test_handle_validation_failure_close_pr_failure(self, mock_config, mock_pr):
        """Test failure handling when PR closure fails."""
        mock_config.close_on = frozenset({"issue_assignee"})
        mock_pr.edit.side_effect = Exception("Close API Error")
        validation_result = make_validation_result(
            CheckResult(
                name="issue_assignee",
                passed=False,
                reason=ASSIGNEE_MISMATCH_REASON,
            )
        )

        pr_manager = PrManager(mock_config)
        result = pr_manager.handle_validation_failure(mock_pr, validation_result)

        assert result is False
        mock_pr.create_issue_comment.assert_called_once()

    def test_handle_validation_failure_unexpected_error(self, mock_config, mock_pr):
        """Test failure handling when an unexpected error occurs."""
        validation_result = make_validation_result(
            CheckResult(
                name="issue_reference",
                passed=False,
                reason=NO_CORRESPONDING_ISSUE_REASON,
            )
        )

        pr_manager = PrManager(mock_config)
        with patch.object(
            pr_manager,
            "build_failure_message",
            side_effect=RuntimeError("Unexpected"),
        ):
            result = pr_manager.handle_validation_failure(mock_pr, validation_result)

        assert result is False

    def test_get_check_message_unknown_check(self, mock_config):
        """Test fallback message for unknown check types."""
        result = CheckResult(name="custom", passed=False, reason="Custom failure")
        pr_manager = PrManager(mock_config)

        assert pr_manager.get_check_message(result) == "Custom failure"

    def test_get_check_message_unknown_check_without_reason(self, mock_config):
        """Test default fallback when an unknown check has no reason."""
        result = CheckResult(name="custom", passed=False)
        pr_manager = PrManager(mock_config)

        assert pr_manager.get_check_message(result) == "Validation failed"

    def test_should_close_pr_for_commit_signature(self, mock_config):
        """Test closure applies to unsigned commits when configured."""
        mock_config.close_on = frozenset({"commit_signature"})
        validation_result = make_validation_result(
            CheckResult(
                name="commit_signature",
                passed=False,
                reason=UNSIGNED_COMMITS_REASON,
                details=["abc123"],
            )
        )
        pr_manager = PrManager(mock_config)

        assert pr_manager.should_close_pr(validation_result) is True

    def test_should_not_close_for_unconfigured_issue_failures(self, mock_config):
        """Test issue reference failures do not close when only assignee is configured."""
        mock_config.close_on = frozenset({"issue_assignee"})
        validation_result = make_validation_result(
            CheckResult(
                name="issue_reference",
                passed=False,
                reason=NO_CORRESPONDING_ISSUE_REASON,
            )
        )
        pr_manager = PrManager(mock_config)

        assert pr_manager.should_close_pr(validation_result) is False
