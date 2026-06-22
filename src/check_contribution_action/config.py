"""Configuration management for the check-contribution-action."""

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class Config:
    """Configuration class for the GitHub Action."""

    def __init__(self) -> None:
        """Initialize configuration from environment variables."""
        self.github_token = self.get_required_input("github_token")
        self.skip_users = self.parse_skip_users()
        self.check_issue_linking = self.get_boolean_input("check_issue_linking", False)
        self.check_issue_reference = self.get_boolean_input(
            "check_issue_reference", False
        )
        self.require_assignee = self.get_boolean_input("require_assignee", False)
        self.check_commit_signature = self.get_boolean_input(
            "check_commit_signature", False
        )
        self.check_sign_off = self.get_boolean_input("check_sign_off", False)
        self.sign_off_strict_match = self.get_boolean_input(
            "sign_off_strict_match", False
        )
        self.close_pr_on_assignee_mismatch = self.get_boolean_input(
            "close_pr_on_assignee_mismatch", False
        )
        self.no_issue_message = self.get_input(
            "no_issue_message",
            "This PR must be linked to an issue before it can be merged.",
        )
        self.no_assignee_message = self.get_input(
            "no_assignee_message",
            "The linked issue must be assigned to the PR author before this PR can be merged.",
        )
        self.target_branches = self.parse_target_branches()
        self.invalid_branch_message = self.get_input(
            "invalid_branch_message",
            "This PR must target one of the allowed branches.",
        )
        self.unsigned_commits_message = self.get_input(
            "unsigned_commits_message",
            "One or more commits are not signed.",
        )
        self.missing_sign_off_message = self.get_input(
            "missing_sign_off_message",
            "One or more commits are missing a Signed-off-by trailer.",
        )
        self.sign_off_mismatch_message = self.get_input(
            "sign_off_mismatch_message",
            "One or more Signed-off-by trailers do not match the commit author.",
        )

        logger.info(
            "Configuration loaded: skip_users=%s, enabled_checks=%s",
            self.skip_users,
            self.enabled_check_names(),
        )

    @property
    def has_enabled_checks(self) -> bool:
        """Return whether at least one contribution check is enabled."""
        return bool(self.enabled_check_names())

    def enabled_check_names(self) -> list[str]:
        """Return names of enabled contribution checks."""
        names: list[str] = []
        if self.check_issue_linking:
            names.append("issue_linking")
        if self.check_issue_reference:
            names.append("issue_reference")
        if self.require_assignee:
            names.append("assignee")
        if self.check_commit_signature:
            names.append("commit_signature")
        if self.check_sign_off:
            names.append("sign_off")
        if self.target_branches:
            names.append("target_branches")
        return names

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

    def resolve_file_path(self, file_path: str) -> str:
        """Resolve file path relative to GitHub workspace if needed."""
        github_workspace = Path(os.getenv("GITHUB_WORKSPACE", "/github/workspace"))
        file_path_obj = Path(file_path)

        if file_path_obj.as_posix().startswith("/github/workspace"):
            return file_path_obj.as_posix()

        if file_path_obj.is_absolute():
            return file_path_obj.as_posix()

        return str((github_workspace / file_path_obj).resolve())

    def parse_skip_users(self) -> list[str]:
        """Parse skip users from both the skip_users input and skip_users_file_path."""
        users_str = self.get_input("skip_users", "")
        skip_users = [user.strip() for user in users_str.split(",") if user.strip()]

        if file_path := self.get_input("skip_users_file_path", ""):
            resolved_path = self.resolve_file_path(file_path)
            try:
                logger.info("Reading skip users from file: %s", resolved_path)
                with open(resolved_path, encoding="utf-8") as file:
                    file_users = [
                        line.strip() for line in file.readlines() if line.strip()
                    ]
                    skip_users.extend(file_users)
            except FileNotFoundError:
                logger.error(
                    "Skip users file not found: %s (original path: %s)",
                    resolved_path,
                    file_path,
                )
            except OSError as e:
                logger.error("Error reading skip users file: %s", e)

        unique_users = sorted(set(skip_users))
        logger.info("Skip users configured: %s", unique_users)

        return unique_users

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
