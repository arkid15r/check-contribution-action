#!/usr/bin/env python3
"""Main entry point for the check-contribution-action."""

import json
import logging
import os
import sys

from github import Github, PullRequest

from check_contribution_action.checks import ALL_CHECKS, CheckContext
from check_contribution_action.commits import load_pull_request_commits
from check_contribution_action.config import Config
from check_contribution_action.models import CheckResult, ValidationResult
from check_contribution_action.pr_manager import PrManager

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def load_event_data() -> dict:
    """Load GitHub event payload from GITHUB_EVENT_PATH."""
    event_path = os.getenv("GITHUB_EVENT_PATH")
    if not event_path:
        logger.error("GITHUB_EVENT_PATH environment variable not set")
        sys.exit(1)

    with open(event_path, encoding="utf-8") as file:
        return json.load(file)


def needs_commit_checks(config: Config) -> bool:
    """Return whether PR commit inspection is required."""
    return config.check_commit_signature or config.check_commit_sign_off


def needs_github_client(config: Config) -> bool:
    """Return whether a GitHub API client is required."""
    return (
        config.check_issue_reference
        or config.check_issue_assignee
        or config.check_target_branch
        or needs_commit_checks(config)
    )


def run_checks(
    config: Config,
    pull_request: PullRequest | None = None,
    github: Github | None = None,
) -> ValidationResult:
    """Run all enabled contribution checks and aggregate the results.

    Checks run in registration order (issue, commit signature, sign-off).
    Issue-related validations short-circuit on the first failure inside
    :class:`~check_contribution_action.checks.issue.IssueCheck`.
    """
    commits = (
        load_pull_request_commits(pull_request)
        if pull_request is not None and needs_commit_checks(config)
        else []
    )
    context = CheckContext(
        config=config,
        commits=commits,
        pull_request=pull_request,
        github=github,
    )

    results: list[CheckResult] = []
    for check in ALL_CHECKS:
        if check.is_enabled(config):
            logger.info("Running check: %s", check.name)
            results.append(check.run(context))

    passed = all(result.passed for result in results)
    return ValidationResult(passed=passed, results=results)


def main() -> None:
    """Main function to run the GitHub Action."""
    try:
        config = Config()
        logger.info("Configuration loaded successfully")

        event_data = load_event_data()
        pull_request_data = event_data.get("pull_request")
        if not pull_request_data:
            logger.error("No pull request data found in event")
            sys.exit(1)

        pr_number = pull_request_data["number"]
        repo_name = event_data["repository"]["full_name"]
        logger.info("Processing PR #%s in repository %s", pr_number, repo_name)

        if not config.has_enabled_checks:
            logger.error("No contribution checks are enabled")
            sys.exit(1)

        logger.info("Enabled checks: %s", ", ".join(config.enabled_check_names()))

        pull_request: PullRequest | None = None
        github: Github | None = None
        if needs_github_client(config):
            github = Github(config.github_token)
            repo = github.get_repo(repo_name)
            pull_request = repo.get_pull(pr_number)

        validation_result = run_checks(
            config,
            pull_request=pull_request,
            github=github,
        )

        if validation_result.passed:
            logger.info("PR #%s passed all contribution checks", pr_number)
            sys.exit(0)

        logger.warning(
            "PR #%s failed %s check(s)",
            pr_number,
            len(validation_result.failed_results),
        )

        if pull_request is None:
            for result in validation_result.failed_results:
                logger.error(
                    "Check '%s' failed: %s %s",
                    result.name,
                    result.reason,
                    result.details,
                )
            sys.exit(1)

        pr_manager = PrManager(config)
        pr_manager.handle_validation_failure(pull_request, validation_result)
        sys.exit(1)

    except Exception as error:
        logger.error("Unexpected error: %s", error)
        sys.exit(1)


if __name__ == "__main__":
    main()
