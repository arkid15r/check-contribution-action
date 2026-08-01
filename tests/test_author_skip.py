"""Tests for author skip helpers."""

from unittest.mock import Mock

from check_contribution_action.author_skip import skip_author


def make_config(
    *,
    skip_bot_authors: bool = True,
    skip_users: list[str] | None = None,
) -> Mock:
    config = Mock()
    config.skip_bot_authors = skip_bot_authors
    config.skip_users = skip_users or []
    return config


class TestSkipAuthor:
    """Test cases for skip_author."""

    def test_skips_bot_author_when_enabled(self):
        """Test bot authors are skipped when skip_bot_authors is true."""
        reason = skip_author("dependabot[bot]", "Bot", make_config())
        assert reason == "bot author: dependabot[bot]"

    def test_does_not_skip_bot_when_disabled(self):
        """Test bot authors are validated when skip_bot_authors is false."""
        reason = skip_author(
            "dependabot[bot]",
            "Bot",
            make_config(skip_bot_authors=False),
        )
        assert reason is None

    def test_skips_user_in_skip_list(self):
        """Test authors in skip_users are skipped."""
        reason = skip_author(
            "allowed-user",
            "User",
            make_config(skip_users=["allowed-user"]),
        )
        assert reason == "user in skip list: allowed-user"

    def test_skip_users_matching_is_case_insensitive(self):
        """Test skip_users comparison ignores login case."""
        reason = skip_author(
            "Allowed-User",
            "User",
            make_config(skip_users=["allowed-user"]),
        )
        assert reason == "user in skip list: Allowed-User"

    def test_does_not_skip_human_author(self):
        """Test human authors outside the skip list are not skipped."""
        reason = skip_author(
            "contributor",
            "User",
            make_config(skip_users=["other-user"]),
        )
        assert reason is None

    def test_bot_skip_takes_precedence_over_skip_list(self):
        """Test bot skip is checked before skip_users."""
        reason = skip_author(
            "dependabot[bot]",
            "Bot",
            make_config(skip_users=["dependabot[bot]"]),
        )
        assert reason == "bot author: dependabot[bot]"
