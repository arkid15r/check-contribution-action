"""Tests for commits module."""

from pathlib import Path
from unittest.mock import Mock

import pytest

from check_contribution_action.commits import (
    commit_info_from_github,
    commit_is_verified,
    is_merge_commit,
    load_pull_request_commits,
    looks_like_merge_message,
    parse_raw_commit_object,
    parse_sign_offs,
    split_headers_and_message,
    without_merge_commits,
)
from check_contribution_action.models import CommitInfo

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "commits"


def load_fixture(name: str) -> str:
    """Load a raw commit object fixture."""
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


def make_github_commit(
    *,
    sha: str = "abc123",
    message: str = "Add feature",
    author_name: str = "Jane Doe",
    author_email: str = "jane@example.com",
    verified: bool = False,
    parents: list[Mock] | None = None,
) -> Mock:
    """Build a PyGithub-like commit object."""
    commit = Mock()
    commit.sha = sha
    commit.commit.message = message
    commit.commit.author.name = author_name
    commit.commit.author.email = author_email
    commit.commit.verification.verified = verified
    commit.parents = [Mock()] if parents is None else parents
    commit.raw_data = {}
    return commit


class TestCommitInfoFromGithub:
    """Test cases for GitHub API commit conversion."""

    def test_maps_verified_signature(self):
        """Test verified commits are marked signed."""
        commit = make_github_commit(verified=True)

        info = commit_info_from_github(commit)

        assert info.signed is True

    def test_maps_unsigned_commit(self):
        """Test unverified commits are marked unsigned."""
        commit = make_github_commit(verified=False)

        info = commit_info_from_github(commit)

        assert info.signed is False

    def test_maps_verified_from_raw_data(self):
        """Test verification is read from API payload when PyGithub omits it."""
        commit = Mock()
        commit.sha = "abc123"
        commit.commit.message = "Add feature"
        commit.commit.author.name = "Jane Doe"
        commit.commit.author.email = "jane@example.com"
        del commit.commit.verification
        commit.raw_data = {
            "commit": {
                "message": "Add feature",
                "verification": {"verified": True, "reason": "valid"},
            }
        }

        assert commit_is_verified(commit) is True
        assert commit_info_from_github(commit).signed is True

    def test_unverified_when_raw_data_lacks_verification(self):
        """Test commits without verification metadata are treated as unsigned."""
        commit = Mock()
        commit.sha = "abc123"
        commit.commit.message = "Add feature"
        commit.commit.author.name = "Jane Doe"
        commit.commit.author.email = "jane@example.com"
        del commit.commit.verification
        commit.raw_data = {"commit": {"message": "Add feature"}}

        assert commit_is_verified(commit) is False
        assert commit_info_from_github(commit).signed is False

    def test_parses_sign_off_from_message(self):
        """Test sign-off trailers are parsed from the commit message."""
        commit = make_github_commit(
            message="Add feature\n\nSigned-off-by: Jane Doe <jane@example.com>"
        )

        info = commit_info_from_github(commit)

        assert info.sign_offs == [("Jane Doe", "jane@example.com")]

    def test_marks_multi_parent_commit_as_merge(self):
        """Test commits with multiple parents are marked as merges."""
        commit = make_github_commit(parents=[Mock(), Mock()])

        assert commit_info_from_github(commit).is_merge is True

    def test_single_parent_merge_message_is_not_merge(self):
        """Test known single-parent commits are not reclassified by message."""
        commit = make_github_commit(
            message="Merge branch 'main' into feature",
            parents=[Mock()],
        )

        assert commit_info_from_github(commit).is_merge is False

    def test_marks_merge_from_raw_parents_when_parents_attr_missing(self):
        """Test parent count falls back to raw_data parents."""
        commit = make_github_commit()
        commit.parents = None
        commit.raw_data = {"parents": [{"sha": "a"}, {"sha": "b"}]}

        assert commit_info_from_github(commit).is_merge is True

    def test_message_fallback_when_parents_unavailable(self):
        """Test merge subject is used when parent count cannot be read."""
        commit = make_github_commit(
            message="Merge branch 'main' into feature\n\nUpdate branch"
        )
        commit.parents = None
        commit.raw_data = {}

        assert commit_info_from_github(commit).is_merge is True


class TestIsMergeCommit:
    """Test cases for merge commit detection."""

    def test_parent_count_greater_than_one(self):
        """Test multiple parents mark a commit as a merge."""
        assert is_merge_commit(parent_count=2, message="Add feature") is True

    def test_single_parent_ignores_merge_message(self):
        """Test message fallback is not used when parent count is known."""
        assert (
            is_merge_commit(
                parent_count=1,
                message="Merge branch 'main' into feature",
            )
            is False
        )

    def test_fallback_when_parents_unknown(self):
        """Test merge subject fallback when parent count is None."""
        assert (
            is_merge_commit(
                parent_count=None,
                message="Merge remote-tracking branch 'origin/main'",
            )
            is True
        )

    def test_fallback_rejects_generic_merge_word(self):
        """Test subjects that merely mention merge are not treated as merges."""
        assert (
            is_merge_commit(parent_count=None, message="Document how to merge PRs")
            is False
        )

    def test_looks_like_merge_message(self):
        """Test GitHub-style merge subjects are recognized."""
        assert looks_like_merge_message("Merge branch 'main' into feature") is True
        assert looks_like_merge_message('Merge branch "main" into feature') is True
        assert (
            looks_like_merge_message("Merge remote-tracking branch 'origin/main'")
            is True
        )
        assert (
            looks_like_merge_message("Merge pull request #12 from org/branch") is True
        )
        assert looks_like_merge_message("Add merge helper") is False


class TestWithoutMergeCommits:
    """Test cases for filtering merge commits."""

    def test_removes_merge_commits_only(self):
        """Test merge commits are dropped while regular commits remain."""
        commits = [
            CommitInfo(
                sha="feature",
                author_name="Jane",
                author_email="jane@example.com",
                message="Add feature",
                signed=True,
            ),
            CommitInfo(
                sha="merge",
                author_name="Jane",
                author_email="jane@example.com",
                message="Merge branch 'main' into feature",
                signed=False,
                is_merge=True,
            ),
        ]

        assert [commit.sha for commit in without_merge_commits(commits)] == ["feature"]


class TestLoadPullRequestCommits:
    """Test cases for loading commits from a pull request."""

    def test_loads_all_pull_request_commits(self):
        """Test commits are loaded from the pull request API."""
        pull_request = Mock()
        pull_request.number = 42
        pull_request.get_commits.return_value = [
            make_github_commit(sha="sha1"),
            make_github_commit(sha="sha2", verified=True),
        ]

        commits = load_pull_request_commits(pull_request)

        assert len(commits) == 2
        assert commits[0].sha == "sha1"
        assert commits[1].signed is True
        pull_request.get_commits.assert_called_once_with()

    def test_excludes_merge_commits(self):
        """Test merge commits are omitted from the returned list."""
        pull_request = Mock()
        pull_request.number = 42
        pull_request.get_commits.return_value = [
            make_github_commit(sha="feature", verified=True),
            make_github_commit(
                sha="merge",
                message="Merge branch 'main' into feature",
                parents=[Mock(), Mock()],
                verified=False,
            ),
        ]

        commits = load_pull_request_commits(pull_request)

        assert [commit.sha for commit in commits] == ["feature"]


class TestSplitHeadersAndMessage:
    """Test cases for raw commit object header parsing."""

    def test_split_headers_without_message_body(self):
        """Test commit objects with headers only and no blank-line separator."""
        headers, message = split_headers_and_message(
            "tree abc\nauthor Jane <jane@example.com> 1700000000 +0000"
        )

        assert headers == [
            "tree abc",
            "author Jane <jane@example.com> 1700000000 +0000",
        ]
        assert message == ""

    def test_split_headers_with_continuation_lines(self):
        """Test folded header lines continued with leading whitespace."""
        raw = (
            "tree abc\n"
            "gpgsig -----BEGIN PGP SIGNATURE-----\n"
            " folded-signature-line\n"
            "author Jane Doe <jane@example.com> 1700000000 +0000\n"
            "\n"
            "subject"
        )

        headers, message = split_headers_and_message(raw)

        assert headers == [
            "tree abc",
            "gpgsig -----BEGIN PGP SIGNATURE-----",
            " folded-signature-line",
            "author Jane Doe <jane@example.com> 1700000000 +0000",
        ]
        assert message == "subject"


class TestParseRawCommitObject:
    """Test cases for parsing raw git commit objects."""

    def test_unsigned_commit_with_sign_off(self):
        """Test parsing an unsigned commit with a Signed-off-by trailer."""
        commit = parse_raw_commit_object(
            "abc123", load_fixture("unsigned_with_sign_off.txt")
        )

        assert commit == CommitInfo(
            sha="abc123",
            author_name="Jane Doe",
            author_email="jane@example.com",
            message="Add feature\n\nSigned-off-by: Jane Doe <jane@example.com>",
            signed=False,
            sign_offs=[("Jane Doe", "jane@example.com")],
            is_merge=False,
        )

    def test_gpg_signed_commit(self):
        """Test detecting a GPG signature from the gpgsig header."""
        commit = parse_raw_commit_object("abc123", load_fixture("signed_gpg.txt"))

        assert commit.signed is True

    def test_two_parent_raw_commit_is_merge(self):
        """Test raw commits with two parent headers are merges."""
        raw = (
            "tree 0123456789abcdef0123456789abcdef012345\n"
            "parent 0123456789abcdef0123456789abcdef012346\n"
            "parent 0123456789abcdef0123456789abcdef012347\n"
            "author Jane Doe <jane@example.com> 1700000000 +0000\n"
            "committer Jane Doe <jane@example.com> 1700000000 +0000\n"
            "\n"
            "Merge branch 'main' into feature\n"
        )

        commit = parse_raw_commit_object("merge123", raw)

        assert commit.is_merge is True

    def test_case_insensitive_sign_off(self):
        """Test parsing sign-off trailers case-insensitively."""
        commit = parse_raw_commit_object(
            "abc123", load_fixture("case_insensitive_sign_off.txt")
        )

        assert commit.sign_offs == [("Jane Doe", "jane@example.com")]

    def test_missing_author_raises(self):
        """Test that commits without an author header raise ValueError."""
        raw = "tree abc\ncommitter Jane <jane@example.com> 1 +0000\n\nmsg"
        with pytest.raises(ValueError, match="missing an author header"):
            parse_raw_commit_object("abc123", raw)


class TestParseSignOffs:
    """Test cases for sign-off trailer parsing."""

    def test_parse_sign_offs(self):
        """Test sign-off parsing from a plain message."""
        message = "Subject\n\nSigned-off-by: Jane Doe <jane@example.com>"

        assert parse_sign_offs(message) == [("Jane Doe", "jane@example.com")]
