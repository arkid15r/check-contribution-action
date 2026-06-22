"""Tests for git_commits module."""

from pathlib import Path
import subprocess
from unittest.mock import patch

import pytest

from check_contribution_action.git_commits import (
    GitError,
    get_commits_in_range,
    list_commit_shas,
    parse_commit_object,
    read_commit_object,
    resolve_workspace,
    split_headers_and_message,
)
from check_contribution_action.models import CommitInfo

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "commits"


def load_fixture(name: str) -> str:
    """Load a raw commit object fixture."""
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


def run_git(cwd: Path, *args: str) -> str:
    """Run a git command in a temporary repository."""
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


class TestResolveWorkspace:
    """Test cases for workspace resolution."""

    def test_resolve_workspace_explicit_path(self, tmp_path: Path):
        """Test explicit workspace path is returned unchanged."""
        assert resolve_workspace(tmp_path) == tmp_path

    def test_resolve_workspace_from_github_workspace_env(self):
        """Test workspace falls back to GITHUB_WORKSPACE."""
        with patch.dict(
            "os.environ", {"GITHUB_WORKSPACE": "/custom/workspace"}, clear=False
        ):
            assert resolve_workspace() == Path("/custom/workspace")


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

    def test_split_headers_with_gpgsig_continuation_lines(self):
        """Test multiline gpgsig headers with indented continuation lines."""
        raw = (
            "tree abc\n"
            "author Jane <jane@example.com> 1700000000 +0000\n"
            "gpgsig -----BEGIN PGP SIGNATURE-----\n"
            " \n"
            " signature-data\n"
            " -----END PGP SIGNATURE-----\n"
            "\n"
            "Signed commit message"
        )
        headers, message = split_headers_and_message(raw)

        assert headers[0] == "tree abc"
        assert headers[1].startswith("author Jane")
        assert headers[2].startswith("gpgsig")
        assert " signature-data" in headers
        assert message == "Signed commit message"


class TestParseCommitObject:
    """Test cases for parsing raw commit objects."""

    def test_unsigned_commit_with_sign_off(self):
        """Test parsing an unsigned commit with a Signed-off-by trailer."""
        commit = parse_commit_object(
            "abc123", load_fixture("unsigned_with_sign_off.txt")
        )

        assert commit == CommitInfo(
            sha="abc123",
            author_name="Jane Doe",
            author_email="jane@example.com",
            message="Add feature\n\nSigned-off-by: Jane Doe <jane@example.com>",
            signed=False,
            sign_offs=[("Jane Doe", "jane@example.com")],
        )

    def test_unsigned_commit_without_sign_off(self):
        """Test parsing an unsigned commit without sign-off."""
        commit = parse_commit_object("abc123", load_fixture("unsigned_no_sign_off.txt"))

        assert commit.signed is False
        assert commit.sign_offs == []
        assert commit.message == "Add feature"

    def test_gpg_signed_commit(self):
        """Test detecting a GPG signature from the gpgsig header."""
        commit = parse_commit_object("abc123", load_fixture("signed_gpg.txt"))

        assert commit.signed is True
        assert commit.sign_offs == [("Jane Doe", "jane@example.com")]

    def test_ssh_signed_commit(self):
        """Test detecting an SSH signature from the gpgsig header."""
        commit = parse_commit_object("abc123", load_fixture("signed_ssh.txt"))

        assert commit.signed is True

    def test_case_insensitive_sign_off(self):
        """Test parsing sign-off trailers case-insensitively."""
        commit = parse_commit_object(
            "abc123", load_fixture("case_insensitive_sign_off.txt")
        )

        assert commit.sign_offs == [("Jane Doe", "jane@example.com")]

    def test_missing_author_raises(self):
        """Test that commits without an author header raise ValueError."""
        raw = "tree abc\ncommitter Jane <jane@example.com> 1 +0000\n\nmsg"
        with pytest.raises(ValueError, match="missing an author header"):
            parse_commit_object("abc123", raw)


class TestGitIntegration:
    """Integration tests using a temporary git repository."""

    @pytest.fixture
    def git_repo(self, tmp_path: Path) -> dict[str, str | Path]:
        """Create a small repository with two commits on a feature branch."""
        repo = tmp_path / "repo"
        repo.mkdir()

        run_git(repo, "init")
        run_git(repo, "config", "user.name", "Test User")
        run_git(repo, "config", "user.email", "test@example.com")
        run_git(repo, "config", "commit.gpgsign", "false")

        run_git(repo, "commit", "--allow-empty", "-m", "Base commit")
        base_sha = run_git(repo, "rev-parse", "HEAD")

        run_git(
            repo,
            "commit",
            "--allow-empty",
            "-m",
            "Feature commit\n\nSigned-off-by: Test User <test@example.com>",
        )
        head_sha = run_git(repo, "rev-parse", "HEAD")

        return {
            "workspace": repo,
            "base_sha": base_sha,
            "head_sha": head_sha,
        }

    def test_list_commit_shas_returns_range(self, git_repo):
        """Test listing commits in a PR-style range."""
        shas = list_commit_shas(
            str(git_repo["base_sha"]),
            str(git_repo["head_sha"]),
            workspace=Path(git_repo["workspace"]),
        )

        assert len(shas) == 1

    def test_list_commit_shas_empty_range(self, git_repo):
        """Test that an empty range returns no commits."""
        shas = list_commit_shas(
            str(git_repo["head_sha"]),
            str(git_repo["head_sha"]),
            workspace=Path(git_repo["workspace"]),
        )

        assert shas == []

    def test_read_commit_object(self, git_repo):
        """Test reading a raw commit object from git."""
        shas = list_commit_shas(
            str(git_repo["base_sha"]),
            str(git_repo["head_sha"]),
            workspace=Path(git_repo["workspace"]),
        )
        raw = read_commit_object(shas[0], workspace=Path(git_repo["workspace"]))

        assert "author Test User <test@example.com>" in raw
        assert "Signed-off-by: Test User <test@example.com>" in raw

    def test_get_commits_in_range(self, git_repo):
        """Test loading parsed commits for a range."""
        commits = get_commits_in_range(
            str(git_repo["base_sha"]),
            str(git_repo["head_sha"]),
            workspace=Path(git_repo["workspace"]),
        )

        assert len(commits) == 1
        assert commits[0].author_email == "test@example.com"
        assert commits[0].sign_offs == [("Test User", "test@example.com")]
        assert commits[0].signed is False

    def test_invalid_sha_raises_git_error(self, git_repo):
        """Test that invalid SHAs raise GitError."""
        with pytest.raises(GitError):
            read_commit_object("not-a-valid-sha", workspace=Path(git_repo["workspace"]))
