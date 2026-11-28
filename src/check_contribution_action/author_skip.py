"""Helpers for skipping contribution checks based on PR author or assignee."""

from check_contribution_action.config import Config


def _is_skip_user(login: str, config: Config) -> bool:
    """Return whether login is in the configured skip list."""
    if not login:
        return False
    skip_logins = {user.lower() for user in config.skip_users}
    return login.lower() in skip_logins


def skip_author(login: str, user_type: str, config: Config) -> str | None:
    """Return a skip reason for the PR author, or None if checks should run."""
    if config.skip_bot_authors and user_type == "Bot":
        return f"bot author: {login}"

    if _is_skip_user(login, config):
        return f"user in skip list: {login}"

    return None


def skip_assignee(logins: list[str], config: Config) -> str | None:
    """Return a skip reason when a PR assignee is on the skip list.

    Maintainers on the skip list can assign the PR to themselves to accept
    commits that cannot satisfy sign-off or signature checks without a rewrite.
    """
    for login in logins:
        if _is_skip_user(login, config):
            return f"assignee in skip list: {login}"

    return None
