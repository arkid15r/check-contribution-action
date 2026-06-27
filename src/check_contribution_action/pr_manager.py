"""PR management for posting failure comments and optional closure."""

import logging

from github import PullRequest

from check_contribution_action.close_triggers import (
    failure_matches_close_trigger,
)
from check_contribution_action.config import Config
from check_contribution_action.models import CheckResult, ValidationResult

logger = logging.getLogger(__name__)


class PrManager:
    """Manage PR comments and optional closure after validation failures."""

    def __init__(self, config: Config) -> None:
        self.config = config

    def handle_validation_failure(
        self, pull_request: PullRequest, validation_result: ValidationResult
    ) -> bool:
        """Post a failure comment and optionally close the PR."""
        try:
            message = self.build_failure_message(validation_result)
            comment_success = self.post_comment(pull_request, message)

            close_success = True
            if self.should_close_pr(validation_result):
                close_success = self.close_pr(pull_request)
                if close_success:
                    logger.info(
                        "PR #%s closed due to configured validation failure",
                        pull_request.number,
                    )
                else:
                    logger.error("Failed to close PR #%s", pull_request.number)
            else:
                logger.info(
                    "PR #%s validation failed but was not closed",
                    pull_request.number,
                )

            return comment_success and close_success
        except Exception as error:
            logger.error(
                "Error handling validation failure for PR #%s: %s",
                pull_request.number,
                error,
            )
            return False

    def should_close_pr(self, validation_result: ValidationResult) -> bool:
        """Return whether the PR should be closed for configured failure triggers."""
        if not self.config.close_on:
            return False
        return any(
            failure_matches_close_trigger(result, trigger)
            for result in validation_result.failed_results
            for trigger in self.config.close_on
        )

    def build_failure_message(self, validation_result: ValidationResult) -> str:
        """Build an aggregated comment listing all failed checks."""
        lines = ["Contribution validation failed:", ""]
        for result in validation_result.failed_results:
            lines.append(f"- {result.name}: {self.get_check_message(result)}")
            for detail in result.details:
                lines.append(f"  - {detail}")
            lines.append("")
        return "\n".join(lines).rstrip()

    def get_check_message(self, result: CheckResult) -> str:
        """Map a failed check result to a user-facing message."""
        if result.name in self.config.errors:
            return self.config.errors[result.name]
        return result.reason or "Validation failed"

    def post_comment(self, pull_request: PullRequest, message: str) -> bool:
        """Post a comment on the pull request."""
        try:
            pull_request.create_issue_comment(message)
            logger.info("Posted comment to PR #%s", pull_request.number)
            return True
        except Exception as error:
            logger.error(
                "Failed to post comment to PR #%s: %s",
                pull_request.number,
                error,
            )
            return False

    def close_pr(self, pull_request: PullRequest) -> bool:
        """Close the pull request."""
        try:
            pull_request.edit(state="closed")
            logger.info("Closed PR #%s", pull_request.number)
            return True
        except Exception as error:
            logger.error("Failed to close PR #%s: %s", pull_request.number, error)
            return False
