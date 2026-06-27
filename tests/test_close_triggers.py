"""Tests for close trigger matching."""

from check_contribution_action.close_triggers import failure_matches_close_trigger
from check_contribution_action.failure_reasons import (
    ASSIGNEE_MISMATCH_REASON,
    ISSUE_HAS_NO_ASSIGNEE_REASON,
    NO_CORRESPONDING_ISSUE_REASON,
    UNSIGNED_COMMITS_REASON,
)
from check_contribution_action.models import CheckResult


class TestCloseTriggers:
    """Test cases for close trigger matching."""

    def test_assignee_mismatch(self):
        result = CheckResult(
            name="issue_assignee",
            passed=False,
            reason=ASSIGNEE_MISMATCH_REASON,
        )

        assert failure_matches_close_trigger(result, "issue_assignee") is True

    def test_issue_without_assignee(self):
        result = CheckResult(
            name="issue_assignee",
            passed=False,
            reason=ISSUE_HAS_NO_ASSIGNEE_REASON,
        )

        assert failure_matches_close_trigger(result, "issue_assignee") is True

    def test_commit_signature(self):
        result = CheckResult(
            name="commit_signature",
            passed=False,
            reason=UNSIGNED_COMMITS_REASON,
        )

        assert failure_matches_close_trigger(result, "commit_signature") is True

    def test_commit_sign_off(self):
        result = CheckResult(
            name="commit_sign_off",
            passed=False,
            reason="Missing sign-off",
        )

        assert failure_matches_close_trigger(result, "commit_sign_off") is True

    def test_issue_linking_without_corresponding_issue(self):
        result = CheckResult(
            name="issue_reference",
            passed=False,
            reason=NO_CORRESPONDING_ISSUE_REASON,
        )

        assert failure_matches_close_trigger(result, "issue_reference") is True

    def test_target_branch(self):
        result = CheckResult(
            name="target_branch",
            passed=False,
            reason="PR must target one of the allowed branches: main",
        )

        assert failure_matches_close_trigger(result, "target_branch") is True

    def test_unknown_trigger(self):
        result = CheckResult(
            name="issue_reference",
            passed=False,
            reason=NO_CORRESPONDING_ISSUE_REASON,
        )

        assert failure_matches_close_trigger(result, "unknown") is False
