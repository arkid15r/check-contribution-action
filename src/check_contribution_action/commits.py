"""Pull request commit inspection utilities for contribution checks."""

import logging
import re

from github.Commit import Commit
from github.PullRequest import PullRequest

from check_contribution_action.models import CommitInfo

logger = logging.getLogger(__name__)

AUTHOR_RE = re.compile(r"^author (.+) <([^>]+)>")
SIGN_OFF_RE = re.compile(
    r"^Signed-off-by:\s*(.+?)\s*<([^>]+)>\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def load_pull_request_commits(pull_request: PullRequest) -> list[CommitInfo]:
    """Load PR commits from the GitHub API."""
    commits = [commit_info_from_github(commit) for commit in pull_request.get_commits()]
    logger.info(
        "Loaded %s commit(s) from pull request #%s",
        len(commits),
        pull_request.number,
    )
    return commits


def commit_is_verified(commit: Commit) -> bool:
    """Return whether GitHub verified the commit signature."""
    verification = getattr(commit.commit, "verification", None)
    if verification is not None:
        return bool(getattr(verification, "verified", False))

    nested = commit.raw_data.get("commit")
    if isinstance(nested, dict):
        raw_verification = nested.get("verification")
        if isinstance(raw_verification, dict):
            return bool(raw_verification.get("verified"))

    return False


def commit_info_from_github(commit: Commit) -> CommitInfo:
    """Convert a GitHub API commit into :class:`CommitInfo`."""
    git_commit = commit.commit
    author = git_commit.author
    message = git_commit.message or ""

    return CommitInfo(
        sha=commit.sha,
        author_name=author.name if author and author.name else "",
        author_email=author.email if author and author.email else "",
        message=message,
        signed=commit_is_verified(commit),
        sign_offs=parse_sign_offs(message),
    )


def parse_sign_offs(message: str) -> list[tuple[str, str]]:
    """Extract Signed-off-by trailers from a commit message."""
    return [
        (name.strip(), email.strip()) for name, email in SIGN_OFF_RE.findall(message)
    ]


def parse_raw_commit_object(sha: str, raw: str) -> CommitInfo:
    """Parse a raw ``git cat-file commit`` object into :class:`CommitInfo`."""
    header_lines, message = split_headers_and_message(raw)
    author_name, author_email = parse_author(header_lines)
    signed = any(line.startswith("gpgsig") for line in header_lines)
    sign_offs = parse_sign_offs(message)

    return CommitInfo(
        sha=sha,
        author_name=author_name,
        author_email=author_email,
        message=message,
        signed=signed,
        sign_offs=sign_offs,
    )


def split_headers_and_message(raw: str) -> tuple[list[str], str]:
    """Split a raw commit object into header lines and message body."""
    lines = raw.splitlines()
    header_lines: list[str] = []
    index = 0

    while index < len(lines):
        line = lines[index]
        if line == "":
            return header_lines, "\n".join(lines[index + 1 :])

        header_lines.append(line)
        index += 1

        while index < len(lines) and lines[index] and lines[index][0] in " \t":
            header_lines.append(lines[index])
            index += 1

    return header_lines, ""


def parse_author(header_lines: list[str]) -> tuple[str, str]:
    """Extract author name and email from commit header lines."""
    for line in header_lines:
        if match := AUTHOR_RE.match(line):
            return match.group(1), match.group(2)
    raise ValueError("Commit object is missing an author header")
