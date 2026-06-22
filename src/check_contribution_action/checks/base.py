"""Base types for contribution checks."""

from dataclasses import dataclass, field
from typing import Protocol

from github import Github, PullRequest

from check_contribution_action.config import Config
from check_contribution_action.models import CheckResult, CommitInfo


@dataclass
class CheckContext:
    """Runtime context shared by contribution checks."""

    config: Config
    commits: list[CommitInfo] = field(default_factory=list)
    pull_request: PullRequest | None = None
    github: Github | None = None


class ContributionCheck(Protocol):
    """Protocol implemented by each contribution check."""

    @property
    def name(self) -> str:
        """Return the check identifier."""
        ...

    def is_enabled(self, config: Config) -> bool:
        """Return whether this check is enabled in configuration."""
        ...

    def run(self, context: CheckContext) -> CheckResult:
        """Execute the check and return its result."""
        ...
