"""Tests for sign-off contribution check."""

from pathlib import Path
from unittest.mock import Mock

import pytest

from check_contribution_action.checks.base import CheckContext
from check_contribution_action.checks.sign_off import SignOffCheck
from check_contribution_action.git_commits import parse_commit_object
from check_contribution_action.models import CheckResult, CommitInfo

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "commits"


@pytest.fixture
def sign_off_check() -> SignOffCheck:
    """Return a sign-off check instance."""
    return SignOffCheck()


def load_commit(name: str, sha: str = "abc123") -> CommitInfo:
    """Load a CommitInfo from a raw commit fixture."""
    raw = (FIXTURES_DIR / name).read_text(encoding="utf-8")
    return parse_commit_object(sha, raw)


def make_config(*, strict_match: bool = False) -> Mock:
    """Return a config with sign-off checking enabled."""
    config = Mock()
    config.check_sign_off = True
    config.sign_off_strict_match = strict_match
    return config


class TestSignOffCheck:
    """Test cases for SignOffCheck."""

    def test_name(self, sign_off_check):
        """Test check name."""
        assert sign_off_check.name == "sign_off"

    def test_is_enabled(self, sign_off_check):
        """Test enabled flag follows config."""
        assert sign_off_check.is_enabled(make_config()) is True

        disabled_config = Mock()
        disabled_config.check_sign_off = False
        assert sign_off_check.is_enabled(disabled_config) is False

    def test_passes_when_no_commits(self, sign_off_check):
        """Test empty commit range passes."""
        context = CheckContext(config=make_config(), commits=[])

        result = sign_off_check.run(context)

        assert result == CheckResult(name="sign_off", passed=True)

    def test_passes_with_sign_off_present(self, sign_off_check):
        """Test commits with Signed-off-by pass in presence-only mode."""
        commits = [load_commit("unsigned_with_sign_off.txt")]
        context = CheckContext(config=make_config(), commits=commits)

        result = sign_off_check.run(context)

        assert result == CheckResult(name="sign_off", passed=True)

    def test_passes_with_case_insensitive_sign_off(self, sign_off_check):
        """Test case-insensitive Signed-off-by trailers pass."""
        commits = [load_commit("case_insensitive_sign_off.txt")]
        context = CheckContext(config=make_config(), commits=commits)

        result = sign_off_check.run(context)

        assert result == CheckResult(name="sign_off", passed=True)

    def test_fails_when_sign_off_missing(self, sign_off_check):
        """Test commits without sign-off fail."""
        commits = [load_commit("unsigned_no_sign_off.txt", "missing123")]
        context = CheckContext(config=make_config(), commits=commits)

        result = sign_off_check.run(context)

        assert result == CheckResult(
            name="sign_off",
            passed=False,
            reason="Missing sign-off",
            details=["missing123"],
        )

    def test_strict_match_passes_when_sign_off_matches_author(self, sign_off_check):
        """Test strict mode passes when sign-off matches commit author."""
        commits = [load_commit("unsigned_with_sign_off.txt", "match123")]
        context = CheckContext(config=make_config(strict_match=True), commits=commits)

        result = sign_off_check.run(context)

        assert result == CheckResult(name="sign_off", passed=True)

    def test_strict_match_fails_when_sign_off_differs(self, sign_off_check):
        """Test strict mode fails when sign-off does not match author."""
        commit = CommitInfo(
            sha="mismatch123",
            author_name="Jane Doe",
            author_email="jane@example.com",
            message="Change",
            signed=False,
            sign_offs=[("Other Person", "other@example.com")],
        )
        context = CheckContext(config=make_config(strict_match=True), commits=[commit])

        result = sign_off_check.run(context)

        assert result == CheckResult(
            name="sign_off",
            passed=False,
            reason="Sign-off mismatch",
            details=["mismatch123"],
        )

    def test_strict_match_ignores_email_case(self, sign_off_check):
        """Test strict mode compares emails case-insensitively."""
        commit = CommitInfo(
            sha="case123",
            author_name="Jane Doe",
            author_email="Jane@Example.com",
            message="Change",
            signed=False,
            sign_offs=[("Jane Doe", "jane@example.com")],
        )
        context = CheckContext(config=make_config(strict_match=True), commits=[commit])

        result = sign_off_check.run(context)

        assert result == CheckResult(name="sign_off", passed=True)

    def test_missing_sign_off_checked_before_strict_match(self, sign_off_check):
        """Test missing sign-off is reported before strict mismatch."""
        commits = [
            load_commit("unsigned_no_sign_off.txt", "missing123"),
            CommitInfo(
                sha="mismatch123",
                author_name="Jane Doe",
                author_email="jane@example.com",
                message="Change",
                signed=False,
                sign_offs=[("Other Person", "other@example.com")],
            ),
        ]
        context = CheckContext(config=make_config(strict_match=True), commits=commits)

        result = sign_off_check.run(context)

        assert result.reason == "Missing sign-off"
        assert result.details == ["missing123"]
