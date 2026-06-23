"""Tests for signature contribution check."""

from pathlib import Path
from unittest.mock import Mock

import pytest

from check_contribution_action.checks.base import CheckContext
from check_contribution_action.checks.signature import SignatureCheck
from check_contribution_action.commits import parse_raw_commit_object
from check_contribution_action.models import CheckResult, CommitInfo

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "commits"


@pytest.fixture
def signature_check() -> SignatureCheck:
    """Return a signature check instance."""
    return SignatureCheck()


@pytest.fixture
def enabled_config():
    """Return a config with commit signature checking enabled."""
    config = Mock()
    config.check_commit_signature = True
    return config


def load_commit(name: str, sha: str = "abc123") -> CommitInfo:
    """Load a CommitInfo from a raw commit fixture."""
    raw = (FIXTURES_DIR / name).read_text(encoding="utf-8")
    return parse_raw_commit_object(sha, raw)


class TestSignatureCheck:
    """Test cases for SignatureCheck."""

    def test_name(self, signature_check):
        """Test check name."""
        assert signature_check.name == "commit_signature"

    def test_is_enabled(self, signature_check, enabled_config):
        """Test enabled flag follows config."""
        assert signature_check.is_enabled(enabled_config) is True

        disabled_config = Mock()
        disabled_config.check_commit_signature = False
        assert signature_check.is_enabled(disabled_config) is False

    def test_passes_when_no_commits(self, signature_check, enabled_config):
        """Test empty commit range passes."""
        context = CheckContext(config=enabled_config, commits=[])

        result = signature_check.run(context)

        assert result == CheckResult(name="commit_signature", passed=True)

    def test_passes_when_all_signed(self, signature_check, enabled_config):
        """Test all signed commits pass."""
        commits = [
            load_commit("signed_gpg.txt", "gpg123"),
            load_commit("signed_ssh.txt", "ssh456"),
        ]
        context = CheckContext(config=enabled_config, commits=commits)

        result = signature_check.run(context)

        assert result == CheckResult(name="commit_signature", passed=True)

    def test_fails_with_unsigned_commits(self, signature_check, enabled_config):
        """Test unsigned commits fail with SHA details."""
        commits = [
            load_commit("signed_gpg.txt", "signed123"),
            load_commit("unsigned_no_sign_off.txt", "unsigned456"),
        ]
        context = CheckContext(config=enabled_config, commits=commits)

        result = signature_check.run(context)

        assert result == CheckResult(
            name="commit_signature",
            passed=False,
            reason="Unsigned commits",
            details=["unsigned456"],
        )

    def test_fails_with_multiple_unsigned_commits(
        self, signature_check, enabled_config
    ):
        """Test all unsigned SHAs are collected."""
        commits = [
            load_commit("unsigned_no_sign_off.txt", "unsigned1"),
            load_commit("unsigned_with_sign_off.txt", "unsigned2"),
        ]
        context = CheckContext(config=enabled_config, commits=commits)

        result = signature_check.run(context)

        assert result.passed is False
        assert result.details == ["unsigned1", "unsigned2"]
