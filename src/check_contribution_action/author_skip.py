"""Helpers for skipping contribution checks based on PR author."""

from check_contribution_action.config import Config


def skip_author(login: str, user_type: str, config: Config) -> str | None:
    """Return a skip reason for the PR author, or None if checks should run."""
    if config.skip_bot_authors and user_type == "Bot":
        return f"bot author: {login}"

    skip_logins = {user.lower() for user in config.skip_users}
    if login.lower() in skip_logins:
        return f"user in skip list: {login}"

    return None
