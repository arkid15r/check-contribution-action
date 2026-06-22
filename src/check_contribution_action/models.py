"""Shared data models for contribution checks."""

from dataclasses import dataclass, field


@dataclass
class CommitInfo:
    """Parsed metadata for a single git commit."""

    sha: str
    author_name: str
    author_email: str
    message: str
    signed: bool
    sign_offs: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class CheckResult:
    """Result of a single contribution check."""

    name: str
    passed: bool
    reason: str | None = None
    details: list[str] = field(default_factory=list)


@dataclass
class ValidationResult:
    """Aggregated result of all enabled contribution checks."""

    passed: bool
    results: list[CheckResult] = field(default_factory=list)

    @property
    def failed_results(self) -> list[CheckResult]:
        """Return checks that did not pass."""
        return [result for result in self.results if not result.passed]
