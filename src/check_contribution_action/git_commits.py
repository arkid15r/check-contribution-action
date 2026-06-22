"""Git commit inspection utilities for contribution checks."""

import logging
import os
from pathlib import Path
import re
import subprocess

from check_contribution_action.models import CommitInfo

logger = logging.getLogger(__name__)

AUTHOR_RE = re.compile(r"^author (.+) <([^>]+)>")
SIGN_OFF_RE = re.compile(
    r"^Signed-off-by:\s*(.+?)\s*<([^>]+)>\s*$",
    re.IGNORECASE | re.MULTILINE,
)


class GitError(Exception):
    """Raised when a git command fails."""


def resolve_workspace(workspace: Path | None = None) -> Path:
    """Return the git workspace directory."""
    if workspace is not None:
        return workspace
    return Path(os.getenv("GITHUB_WORKSPACE", os.getcwd()))


def list_commit_shas(
    base_sha: str,
    head_sha: str,
    *,
    workspace: Path | None = None,
) -> list[str]:
    """Return commit SHAs in ``base_sha..head_sha`` from oldest to newest."""
    output = run_git(
        ["rev-list", "--reverse", f"{base_sha}..{head_sha}"],
        workspace=workspace,
    )
    shas = [line.strip() for line in output.splitlines() if line.strip()]
    logger.info(
        "Found %s commit(s) in range %s..%s",
        len(shas),
        base_sha,
        head_sha,
    )
    return shas


def read_commit_object(sha: str, *, workspace: Path | None = None) -> str:
    """Return the raw commit object for ``sha``."""
    return run_git(["cat-file", "commit", sha], workspace=workspace)


def parse_commit_object(sha: str, raw: str) -> CommitInfo:
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


def get_commits_in_range(
    base_sha: str,
    head_sha: str,
    *,
    workspace: Path | None = None,
) -> list[CommitInfo]:
    """Load and parse all commits in ``base_sha..head_sha``."""
    commits: list[CommitInfo] = []
    for sha in list_commit_shas(base_sha, head_sha, workspace=workspace):
        raw = read_commit_object(sha, workspace=workspace)
        commits.append(parse_commit_object(sha, raw))
    return commits


def run_git(args: list[str], *, workspace: Path | None = None) -> str:
    """Run a git command and return stdout."""
    cwd = resolve_workspace(workspace)
    # Mounted workspaces in Actions are owned by the runner user, not the container.
    command = ["git", "-c", f"safe.directory={cwd}", *args]
    logger.debug("Running git %s in %s", " ".join(args), cwd)
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as error:
        stderr = error.stderr.strip() if error.stderr else str(error)
        logger.error("git %s failed: %s", " ".join(args), stderr)
        raise GitError(stderr) from error
    return result.stdout


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


def parse_sign_offs(message: str) -> list[tuple[str, str]]:
    """Extract Signed-off-by trailers from a commit message."""
    return [
        (name.strip(), email.strip()) for name, email in SIGN_OFF_RE.findall(message)
    ]
