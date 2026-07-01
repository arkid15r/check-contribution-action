"""Configuration management for the check-contribution-action."""

import logging
import os

from check_contribution_action.check_for import CHECK_FOR_NAMES, DEFAULT_ERROR_MESSAGES
from check_contribution_action.skip_users_file import load_skip_users_from_file_path

logger = logging.getLogger(__name__)


class Config:
    """Configuration class for the GitHub Action."""

    def __init__(self) -> None:
        """Initialize configuration from environment variables."""
        self.github_token = self.get_required_input("github_token")
        self.skip_users = self.parse_skip_users()
        self.target_branches = self.parse_target_branches()
        self.check_for = self.parse_check_for()
        self.check_issue_reference = "issue_reference" in self.check_for
        self.check_issue_assignee = "issue_assignee" in self.check_for
        self.check_commit_signature = "commit_signature" in self.check_for
        self.check_commit_sign_off = "commit_sign_off" in self.check_for
        self.check_target_branch = "target_branch" in self.check_for and bool(
            self.target_branches
        )
        self.sign_off_strict_match = self.get_boolean_input(
            "sign_off_strict_match", False
        )
        self.close_on = self.parse_close_on()
        self.validate_bot_authors = self.get_boolean_input(
            "validate_bot_authors", False
        )
        self.errors = self.load_errors()
        self.validate_enabled_checks()
        self.validate_close_on()

        logger.info(
            "Configuration loaded: skip_users=%s, enabled_checks=%s, close_on=%s",
            self.skip_users,
            self.enabled_check_names(),
            sorted(self.close_on),
        )

    @property
    def has_enabled_checks(self) -> bool:
        """Return whether at least one contribution check is enabled."""
        return bool(self.enabled_check_names())

    def enabled_check_names(self) -> list[str]:
        """Return names of enabled contribution checks."""
        enabled = set(self.check_for)
        if "target_branch" in enabled and not self.check_target_branch:
            enabled.discard("target_branch")
        return sorted(enabled)

    def get_required_input(self, name: str) -> str:
        """Get a required input from environment variables."""
        value = os.getenv(f"INPUT_{name.upper()}")
        if not value:
            raise ValueError(f"Required input '{name}' is not provided")
        return value

    def get_input(self, name: str, default: str = "") -> str:
        """Get an optional input from environment variables."""
        return os.getenv(f"INPUT_{name.upper()}", default)

    def get_boolean_input(self, name: str, default: bool = False) -> bool:
        """Get a boolean input from environment variables."""
        value = self.get_input(name, str(default)).lower()
        return value in ("true", "1", "yes", "on")

    def validate_enabled_checks(self) -> None:
        """Ensure check_for enables at least one runnable contribution check."""
        if not self.enabled_check_names():
            if "target_branch" in self.check_for:
                raise ValueError(
                    "check_for includes target_branch but target_branches is not set"
                )
            raise ValueError(
                "check_for must include at least one supported check: "
                f"{', '.join(sorted(CHECK_FOR_NAMES))}"
            )

    def validate_close_on(self) -> None:
        """Reject close_on triggers that are not enabled in check_for."""
        if not self.close_on:
            return
        enabled = set(self.enabled_check_names())
        extra = self.close_on - enabled
        if extra:
            raise ValueError(
                "close_on includes checks that are not enabled in check_for: "
                f"{', '.join(sorted(extra))}"
            )

    def load_errors(self) -> dict[str, str]:
        """Load user-facing failure messages keyed by check name."""
        return {
            name: self.get_input(f"error_{name}", DEFAULT_ERROR_MESSAGES[name])
            for name in CHECK_FOR_NAMES
        }

    def parse_skip_users(self) -> list[str]:
        """Parse skip users from both the skip_users input and skip_users_file_path."""
        users_str = self.get_input("skip_users", "")
        skip_users = [user.strip() for user in users_str.split(",") if user.strip()]

        if file_path := self.get_input("skip_users_file_path", ""):
            repository_full_name = os.getenv("GITHUB_REPOSITORY", "")
            file_users = load_skip_users_from_file_path(
                file_path,
                github_token=self.github_token,
                repository_full_name=repository_full_name,
            )
            skip_users.extend(file_users)

        unique_users = sorted(set(skip_users))
        logger.info("Skip users configured: %s", unique_users)

        return unique_users

    def parse_check_for(self) -> frozenset[str]:
        """Parse comma-separated contribution checks to enable."""
        checks_str = self.get_required_input("check_for")
        checks = {
            check.strip().lower() for check in checks_str.split(",") if check.strip()
        }

        unknown = checks - CHECK_FOR_NAMES
        if unknown:
            logger.warning(
                "Ignoring unknown check_for values: %s",
                sorted(unknown),
            )
            checks -= unknown

        if not checks:
            raise ValueError(
                "check_for must include at least one supported check: "
                f"{', '.join(sorted(CHECK_FOR_NAMES))}"
            )

        return frozenset(checks)

    def parse_close_on(self) -> frozenset[str]:
        """Parse comma-separated PR closure triggers."""
        triggers_str = self.get_input("close_on", "")
        triggers = {
            trigger.strip().lower()
            for trigger in triggers_str.split(",")
            if trigger.strip()
        }

        unknown = triggers - CHECK_FOR_NAMES
        if unknown:
            logger.warning(
                "Ignoring unknown close_on triggers: %s",
                sorted(unknown),
            )
            triggers -= unknown

        return frozenset(triggers)

    def parse_target_branches(self) -> list[str]:
        """Parse newline-separated target branches list."""
        branches_str = self.get_input("target_branches", "")
        if not branches_str:
            return []

        branches = [
            branch.strip() for branch in branches_str.split("\n") if branch.strip()
        ]
        logger.info("Target branches configured: %s", branches)
        return branches
