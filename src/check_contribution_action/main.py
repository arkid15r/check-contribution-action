#!/usr/bin/env python3
"""Main entry point for the check-contribution-action."""

import json
import logging
import os
import sys

from github import Github, PullRequest

from check_contribution_action.checks import ALL_CHECKS, CheckContext
from check_contribution_action.config import Config
from check_contribution_action.git_commits import get_commits_in_range
from check_contribution_action.models import CheckResult, ValidationResult
from check_contribution_action.pr_manager import PrManager

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def is_fork_pr(event_data: dict) -> bool:
    """Return True when the pull request originates from a fork."""
    pull_request = event_data.get("pull_request", {})
    head_repo = pull_request.get("head", {}).get("repo", {}).get("full_name")
    base_repo = event_data.get("repository", {}).get("full_name")
    return bool(head_repo and base_repo and head_repo != base_repo)


def load_event_data() -> dict:
    """Load GitHub event payload from GITHUB_EVENT_PATH."""
    event_path = os.getenv("GITHUB_EVENT_PATH")
    if not event_path:
        logger.error("GITHUB_EVENT_PATH environment variable not set")
        sys.exit(1)

    with open(event_path, encoding="utf-8") as file:
        return json.load(file)


def needs_git_commits(config: Config) -> bool:
    """Return whether git commit inspection is required."""
    return config.check_commit_signature or config.check_sign_off


def needs_github_client(config: Config) -> bool:
    """Return whether a GitHub API client is required."""
    return (
        config.check_issue_linking
        or config.check_issue_reference
        or config.require_assignee
        or bool(config.target_branches)
    )


def load_commits(event_data: dict) -> list:
    """Load commits in the pull request range from the local git workspace."""
    pull_request = event_data["pull_request"]
    base_sha = pull_request["base"]["sha"]
    head_sha = pull_request["head"]["sha"]
    return get_commits_in_range(base_sha, head_sha)


def run_checks(
    config: Config,
    event_data: dict,
    pull_request: PullRequest | None = None,
    github: Github | None = None,
) -> ValidationResult:
    """Run all enabled contribution checks and aggregate the results."""
    commits = load_commits(event_data) if needs_git_commits(config) else []
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

        if is_fork_pr(event_data):
            logger.info("Skipping fork pull request")
            sys.exit(0)

        pr_number = pull_request_data["number"]
        repo_name = event_data["repository"]["full_name"]
        logger.info("Processing PR #%s in repository %s", pr_number, repo_name)

        if not config.has_enabled_checks:
            logger.warning("No contribution checks are enabled; nothing to validate")
            sys.exit(0)

        logger.info("Enabled checks: %s", ", ".join(config.enabled_check_names()))

        pull_request: PullRequest | None = None
        github: Github | None = None
        if needs_github_client(config):
            github = Github(config.github_token)
            repo = github.get_repo(repo_name)
            pull_request = repo.get_pull(pr_number)

        validation_result = run_checks(
            config,
            event_data,
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
