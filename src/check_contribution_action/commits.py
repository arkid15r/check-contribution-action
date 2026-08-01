"""Pull request commit inspection utilities for contribution checks."""

import logging
import re

from github.Commit import Commit
from github.PullRequest import PullRequest

from check_contribution_action.models import CommitInfo

logger = logging.getLogger(__name__)

AUTHOR_RE = re.compile(r"^author (.+) <([^>]+)>")
PARENT_RE = re.compile(r"^parent [0-9a-f]+", re.IGNORECASE)
SIGN_OFF_RE = re.compile(
    r"^Signed-off-by:\s*(.+?)\s*<([^>]+)>\s*$",
    re.IGNORECASE | re.MULTILINE,
)
# GitHub "Update branch" / local merges of base into head, and merges of other PRs.
MERGE_SUBJECT_RE = re.compile(
    r"^(?:"
    r"Merge (?:branch|remote-tracking branch) ['\"].+?['\"]"
    r"|Merge pull request #\d+ from \S+"
    r")"
)


def load_pull_request_commits(pull_request: PullRequest) -> list[CommitInfo]:
    """Load PR commits from the GitHub API, excluding merge commits."""
    commits = [commit_info_from_github(commit) for commit in pull_request.get_commits()]
    commits = without_merge_commits(commits)
    logger.info(
        "Loaded %s commit(s) from pull request #%s",
        len(commits),
        pull_request.number,
    )
    return commits


def without_merge_commits(commits: list[CommitInfo]) -> list[CommitInfo]:
    """Return commits with merge commits removed."""
    merge_commits = [commit for commit in commits if commit.is_merge]
    if merge_commits:
        logger.info(
            "Excluding %s merge commit(s) from contribution checks: %s",
            len(merge_commits),
            ", ".join(commit.sha for commit in merge_commits),
        )
    return [commit for commit in commits if not commit.is_merge]


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


def github_parent_count(commit: Commit) -> int | None:
    """Return the number of parents from a GitHub commit, if available."""
    parents = getattr(commit, "parents", None)
    if parents is not None:
        try:
            return len(parents)
        except TypeError:
            pass

    raw_parents = commit.raw_data.get("parents")
    if isinstance(raw_parents, list):
        return len(raw_parents)

    return None


def count_parent_headers(header_lines: list[str]) -> int:
    """Count ``parent`` headers in a raw commit object."""
    return sum(1 for line in header_lines if PARENT_RE.match(line))


def looks_like_merge_message(message: str) -> bool:
    """Return whether the commit subject looks like a GitHub merge commit."""
    subject = message.splitlines()[0] if message else ""
    return bool(MERGE_SUBJECT_RE.match(subject))


def is_merge_commit(*, parent_count: int | None, message: str) -> bool:
    """Return whether a commit should be treated as a merge commit.

    Parent count is authoritative when known. The message fallback applies
    only when parent information is unavailable.
    """
    if parent_count is not None:
        return parent_count > 1
    return looks_like_merge_message(message)


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
        is_merge=is_merge_commit(
            parent_count=github_parent_count(commit),
            message=message,
        ),
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
        is_merge=is_merge_commit(
            parent_count=count_parent_headers(header_lines),
            message=message,
        ),
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
