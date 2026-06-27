"""Signed-off-by contribution check."""

import logging

from check_contribution_action.checks.base import CheckContext
from check_contribution_action.config import Config
from check_contribution_action.failure_reasons import (
    MISSING_SIGN_OFF_REASON,
    SIGN_OFF_MISMATCH_REASON,
)
from check_contribution_action.models import CheckResult, CommitInfo

logger = logging.getLogger(__name__)


class SignOffCheck:
    """Require Signed-off-by trailers on every commit in the PR range."""

    @property
    def name(self) -> str:
        """Return the check identifier."""
        return "commit_sign_off"

    def is_enabled(self, config: Config) -> bool:
        """Return whether sign-off checking is enabled."""
        return config.check_commit_sign_off

    def run(self, context: CheckContext) -> CheckResult:
        """Verify sign-off trailers on all commits in the context."""
        if not context.commits:
            logger.info("No commits in range; skipping sign-off check")
            return CheckResult(name=self.name, passed=True)

        missing_sign_off = [
            commit.sha for commit in context.commits if not commit.sign_offs
        ]
        if missing_sign_off:
            logger.warning(
                "Found %s commit(s) missing Signed-off-by", len(missing_sign_off)
            )
            return CheckResult(
                name=self.name,
                passed=False,
                reason=MISSING_SIGN_OFF_REASON,
                details=missing_sign_off,
            )

        if context.config.sign_off_strict_match:
            mismatched = [
                commit.sha
                for commit in context.commits
                if not sign_off_matches_author(commit)
            ]
            if mismatched:
                logger.warning(
                    "Found %s commit(s) with sign-off mismatch", len(mismatched)
                )
                return CheckResult(
                    name=self.name,
                    passed=False,
                    reason=SIGN_OFF_MISMATCH_REASON,
                    details=mismatched,
                )

        logger.info("All %s commit(s) have valid sign-off", len(context.commits))
        return CheckResult(name=self.name, passed=True)


def sign_off_matches_author(commit: CommitInfo) -> bool:
    """Return whether any sign-off matches the commit author identity."""
    for name, email in commit.sign_offs:
        if name == commit.author_name and email.lower() == commit.author_email.lower():
            return True
    return False
