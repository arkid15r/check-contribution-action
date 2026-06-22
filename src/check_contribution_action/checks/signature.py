"""Commit signature contribution check."""

import logging

from check_contribution_action.checks.base import CheckContext
from check_contribution_action.config import Config
from check_contribution_action.models import CheckResult

logger = logging.getLogger(__name__)


class SignatureCheck:
    """Require gpgsig headers on every commit in the PR range."""

    @property
    def name(self) -> str:
        """Return the check identifier."""
        return "commit_signature"

    def is_enabled(self, config: Config) -> bool:
        """Return whether commit signature checking is enabled."""
        return config.check_commit_signature

    def run(self, context: CheckContext) -> CheckResult:
        """Verify all commits in the context are signed."""
        if not context.commits:
            logger.info("No commits in range; skipping signature check")
            return CheckResult(name=self.name, passed=True)

        unsigned_shas = [commit.sha for commit in context.commits if not commit.signed]
        if unsigned_shas:
            logger.warning("Found %s unsigned commit(s)", len(unsigned_shas))
            return CheckResult(
                name=self.name,
                passed=False,
                reason="Unsigned commits",
                details=unsigned_shas,
            )

        logger.info("All %s commit(s) are signed", len(context.commits))
        return CheckResult(name=self.name, passed=True)
