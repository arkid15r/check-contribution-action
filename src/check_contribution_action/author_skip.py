"""Helpers for skipping contribution checks based on PR author."""

from github import PullRequest

from check_contribution_action.config import Config


def skip_author(pull_request: PullRequest, config: Config) -> str | None:
    """Return a skip reason for the PR author, or None if checks should run."""
    if config.skip_bot_authors and pull_request.user.type == "Bot":
        return f"bot author: {pull_request.user.login}"
    if pull_request.user.login in config.skip_users:
        return f"user in skip list: {pull_request.user.login}"
    return None
