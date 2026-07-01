"""Tests for skip_users_file module."""

from unittest.mock import MagicMock, patch

from github import GithubException
import pytest

from check_contribution_action.skip_users_file import (
    SkipUsersFileLocation,
    fetch_skip_users_from_github,
    is_local_filesystem_path,
    load_skip_users_from_file_path,
    parse_skip_users_content,
    parse_skip_users_file_location,
    read_skip_users_from_local_file,
)

REPOSITORY = "OWASP/Nest"


class TestParseSkipUsersContent:
    """Tests for skip users file content parsing."""

    def test_parses_lines(self):
        """Test one username per line."""
        assert parse_skip_users_content("user1\n\n user2 \n") == ["user1", "user2"]


class TestParseSkipUsersFileLocation:
    """Tests for skip users path resolution."""

    def test_repository_relative_path(self):
        """Test repository-relative paths."""
        location = parse_skip_users_file_location(".github/skip_users.txt", REPOSITORY)
        assert location == SkipUsersFileLocation(
            "OWASP", "Nest", ".github/skip_users.txt"
        )

    def test_full_github_path(self):
        """Test full owner/repo/file paths."""
        location = parse_skip_users_file_location(
            "OWASP/Nest/.github/skip_users.txt", REPOSITORY
        )
        assert location == SkipUsersFileLocation(
            "OWASP", "Nest", ".github/skip_users.txt"
        )

    def test_cross_repository_path(self):
        """Test explicit owner/repo paths for another repository."""
        location = parse_skip_users_file_location(
            "OtherOrg/other-repo/config/skip_users.txt", REPOSITORY
        )
        assert location == SkipUsersFileLocation(
            "OtherOrg", "other-repo", "config/skip_users.txt"
        )

    def test_empty_path_raises(self):
        """Test empty paths are rejected."""
        with pytest.raises(ValueError, match="must not be empty"):
            parse_skip_users_file_location("  ", REPOSITORY)

    def test_invalid_repository_name_raises(self):
        """Test repository names without an owner/repo separator are rejected."""
        with pytest.raises(ValueError, match="Invalid repository name"):
            parse_skip_users_file_location(".github/skip_users.txt", "invalid")


class TestLoadSkipUsersFromFilePath:
    """Tests for loading skip users from local or GitHub paths."""

    def test_local_file(self, tmp_path):
        """Test local absolute paths still work."""
        skip_users_file = tmp_path / "skip_users.txt"
        skip_users_file.write_text("user1\nuser2\n")

        users = load_skip_users_from_file_path(
            str(skip_users_file),
            github_token="token",
            repository_full_name=REPOSITORY,
        )

        assert users == ["user1", "user2"]

    def test_local_file_not_found_returns_empty(self, tmp_path):
        """Test missing local skip files return an empty list."""
        users = load_skip_users_from_file_path(
            str(tmp_path / "missing.txt"),
            github_token="token",
            repository_full_name=REPOSITORY,
        )

        assert users == []

    def test_local_file_read_error_returns_empty(self, tmp_path):
        """Test local read failures return an empty list."""
        users = load_skip_users_from_file_path(
            str(tmp_path),
            github_token="token",
            repository_full_name=REPOSITORY,
        )

        assert users == []

    def test_github_relative_path(self):
        """Test repository-relative paths use the GitHub API."""
        with patch(
            "check_contribution_action.skip_users_file.fetch_skip_users_from_github",
            return_value=["bot1"],
        ) as fetch_mock:
            users = load_skip_users_from_file_path(
                ".github/skip_users.txt",
                github_token="token",
                repository_full_name=REPOSITORY,
                ref="main",
            )

        assert users == ["bot1"]
        fetch_mock.assert_called_once_with(
            "token",
            SkipUsersFileLocation("OWASP", "Nest", ".github/skip_users.txt"),
            ref="main",
        )

    def test_missing_repository_name(self):
        """Test missing GITHUB_REPOSITORY prevents API fetch."""
        users = load_skip_users_from_file_path(
            ".github/skip_users.txt",
            github_token="token",
            repository_full_name="",
        )

        assert users == []

    def test_github_fetch_failure(self):
        """Test API failures return an empty list."""
        with patch(
            "check_contribution_action.skip_users_file.fetch_skip_users_from_github",
            side_effect=GithubException(404, {"message": "Not Found"}, {}),
        ):
            users = load_skip_users_from_file_path(
                ".github/missing.txt",
                github_token="token",
                repository_full_name=REPOSITORY,
            )

        assert users == []

    def test_github_fetch_value_error_returns_empty(self):
        """Test fetch validation errors return an empty list."""
        with patch(
            "check_contribution_action.skip_users_file.fetch_skip_users_from_github",
            side_effect=ValueError("must point to a file"),
        ):
            users = load_skip_users_from_file_path(
                ".github",
                github_token="token",
                repository_full_name=REPOSITORY,
            )

        assert users == []

    def test_github_fetch_os_error_returns_empty(self):
        """Test fetch I/O errors return an empty list."""
        with patch(
            "check_contribution_action.skip_users_file.fetch_skip_users_from_github",
            side_effect=OSError("network down"),
        ):
            users = load_skip_users_from_file_path(
                ".github/skip_users.txt",
                github_token="token",
                repository_full_name=REPOSITORY,
            )

        assert users == []


class TestFetchSkipUsersFromGithub:
    """Tests for GitHub contents API fetch."""

    def test_fetch_file_content(self):
        """Test decoding repository file contents."""
        content_file = MagicMock()
        content_file.decoded_content = b"bot1\nbot2\n"

        repository = MagicMock()
        repository.get_contents.return_value = content_file

        github = MagicMock()
        github.get_repo.return_value = repository

        with patch(
            "check_contribution_action.skip_users_file.Github",
            return_value=github,
        ):
            users = fetch_skip_users_from_github(
                "token",
                SkipUsersFileLocation("OWASP", "Nest", ".github/skip_users.txt"),
                ref="main",
            )

        assert users == ["bot1", "bot2"]
        github.get_repo.assert_called_once_with("OWASP/Nest")
        repository.get_contents.assert_called_once_with(
            ".github/skip_users.txt", ref="main"
        )

    def test_fetch_without_ref(self):
        """Test default-branch fetch omits ref (PyGithub rejects ref=None)."""
        content_file = MagicMock()
        content_file.decoded_content = b"bot1\n"

        repository = MagicMock()
        repository.get_contents.return_value = content_file

        github = MagicMock()
        github.get_repo.return_value = repository

        with patch(
            "check_contribution_action.skip_users_file.Github",
            return_value=github,
        ):
            users = fetch_skip_users_from_github(
                "token",
                SkipUsersFileLocation("OWASP", "Nest", ".github/skip_users.txt"),
            )

        assert users == ["bot1"]
        repository.get_contents.assert_called_once_with(".github/skip_users.txt")

    def test_rejects_directory_path(self):
        """Test directory paths raise a clear error."""
        repository = MagicMock()
        repository.get_contents.return_value = [MagicMock()]

        github = MagicMock()
        github.get_repo.return_value = repository

        with patch(
            "check_contribution_action.skip_users_file.Github",
            return_value=github,
        ):
            with pytest.raises(ValueError, match="must point to a file"):
                fetch_skip_users_from_github(
                    "token",
                    SkipUsersFileLocation("OWASP", "Nest", ".github"),
                )


class TestLocalFilesystemPath:
    """Tests for local path detection."""

    def test_absolute_path_is_local(self, tmp_path):
        """Test absolute runner paths are treated as local."""
        assert is_local_filesystem_path(str(tmp_path / "skip_users.txt")) is True

    def test_github_workspace_path_is_local(self):
        """Test /github/workspace paths are treated as local."""
        assert (
            is_local_filesystem_path("/github/workspace/.github/skip_users.txt") is True
        )

    def test_repository_relative_path_is_not_local(self):
        """Test repository-relative paths are fetched from GitHub."""
        assert is_local_filesystem_path(".github/skip_users.txt") is False

    def test_read_skip_users_from_local_file(self, tmp_path):
        """Test reading skip users from disk."""
        skip_users_file = tmp_path / "skip_users.txt"
        skip_users_file.write_text("user1\n")

        assert read_skip_users_from_local_file(str(skip_users_file)) == ["user1"]
