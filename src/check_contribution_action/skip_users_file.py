"""Load skip-user lists from repository files via the GitHub API."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path

from github import Github, GithubException

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SkipUsersFileLocation:
    """Repository coordinates for a skip-users file."""

    owner: str
    repo: str
    path: str

    @property
    def full_name(self) -> str:
        """Return owner/repo."""
        return f"{self.owner}/{self.repo}"


def parse_skip_users_content(content: str) -> list[str]:
    """Parse usernames from file content (one username per line)."""
    return [line.strip() for line in content.splitlines() if line.strip()]


def parse_skip_users_file_location(
    input_path: str, repository_full_name: str
) -> SkipUsersFileLocation:
    """Resolve a skip-users path to a GitHub repository file location.

    Supports:
    - Repository-relative paths, e.g. ``.github/skip_users.txt``
    - Full GitHub paths, e.g. ``OWASP/Nest/.github/skip_users.txt``
    """
    normalized = input_path.strip().strip("/")
    if not normalized:
        raise ValueError("skip_users_file_path must not be empty")

    if "/" not in repository_full_name:
        raise ValueError(
            f"Invalid repository name for skip users lookup: {repository_full_name}"
        )

    owner, repo = repository_full_name.split("/", 1)
    full_prefix = f"{repository_full_name}/"
    if normalized.startswith(full_prefix):
        return SkipUsersFileLocation(owner, repo, normalized[len(full_prefix) :])

    parts = normalized.split("/", 2)
    if len(parts) == 3:
        path_owner, path_repo, file_path = parts
        if path_owner and path_repo and file_path:
            return SkipUsersFileLocation(path_owner, path_repo, file_path)

    return SkipUsersFileLocation(owner, repo, normalized)


def is_local_filesystem_path(input_path: str) -> bool:
    """Return whether the path refers to a local file on the runner."""
    path = Path(input_path)
    if path.as_posix().startswith("/github/workspace"):
        return True
    return path.is_absolute()


def read_skip_users_from_local_file(file_path: str) -> list[str]:
    """Read skip users from a local filesystem path."""
    with open(file_path, encoding="utf-8") as file:
        return parse_skip_users_content(file.read())


def fetch_skip_users_from_github(
    github_token: str,
    location: SkipUsersFileLocation,
    *,
    ref: str | None = None,
) -> list[str]:
    """Fetch and parse skip users from a file in a GitHub repository."""
    github = Github(github_token)
    repository = github.get_repo(location.full_name)
    content = repository.get_contents(location.path, **({"ref": ref} if ref else {}))
    if isinstance(content, list):
        raise ValueError(
            f"skip_users_file_path must point to a file, not a directory: {location.path}"
        )

    decoded = content.decoded_content.decode("utf-8")
    return parse_skip_users_content(decoded)


def load_skip_users_from_file_path(
    input_path: str,
    *,
    github_token: str,
    repository_full_name: str,
    ref: str | None = None,
) -> list[str]:
    """Load skip users from a local path or a GitHub repository file."""
    if is_local_filesystem_path(input_path):
        try:
            logger.info("Reading skip users from local file: %s", input_path)
            return read_skip_users_from_local_file(input_path)
        except FileNotFoundError:
            logger.exception("Skip users file not found: %s", input_path)
            return []
        except OSError:
            logger.exception("Error reading skip users file: %s", input_path)
            return []

    if not repository_full_name:
        logger.error(
            "Cannot fetch skip users file %s: GITHUB_REPOSITORY is not set",
            input_path,
        )
        return []

    location = parse_skip_users_file_location(input_path, repository_full_name)
    try:
        logger.info(
            "Fetching skip users from %s/%s (ref=%s)",
            location.full_name,
            location.path,
            ref or "default branch",
        )
        return fetch_skip_users_from_github(
            github_token,
            location,
            ref=ref,
        )
    except GithubException:
        logger.exception(
            "Failed to fetch skip users file from %s/%s",
            location.full_name,
            location.path,
        )
        return []
    except OSError, ValueError:
        logger.exception(
            "Failed to read skip users file from %s/%s",
            location.full_name,
            location.path,
        )
        return []
