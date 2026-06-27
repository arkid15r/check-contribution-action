"""Issue linking, reference, assignee, and branch contribution check."""

from dataclasses import dataclass
import logging
import re

from github import Github, PullRequest
from github.Issue import Issue as GitHubIssue

from check_contribution_action.checks.base import CheckContext
from check_contribution_action.config import Config
from check_contribution_action.failure_reasons import (
    ASSIGNEE_MISMATCH_REASON,
    GITHUB_CLOSING_LINK_ERROR,
    ISSUE_HAS_NO_ASSIGNEE_REASON,
    NO_CORRESPONDING_ISSUE_REASON,
    NO_ISSUE_FOR_ASSIGNEE_REASON,
    NO_LINKED_ISSUE_REASON,
    TARGET_BRANCH_REASON_PREFIX,
)
from check_contribution_action.models import CheckResult

logger = logging.getLogger(__name__)

CLOSING_REFERENCE_RE = re.compile(
    r"\b(close|closes|closed|fix|fixes|fixed|resolve|resolves|resolved)\b"
    r"(?:\s+|:\s*)"
    r"#([0-9]+)",
    re.IGNORECASE,
)

LINKED_ISSUES_QUERY = """
query GetLinkedIssues($owner: String!, $repo: String!, $pullRequestNumber: Int!) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $pullRequestNumber) {
      closingIssuesReferences(first: 10, userLinkedOnly: false) {
        edges {
          node {
            number
            title
            url
            assignees(first: 10) {
              edges {
                node {
                  login
                }
              }
            }
          }
        }
      }
    }
  }
}
"""

ISSUE_BY_NUMBER_QUERY = """
query GetIssue($owner: String!, $repo: String!, $issueNumber: Int!) {
  repository(owner: $owner, name: $repo) {
    issue(number: $issueNumber) {
      number
      title
      url
      assignees(first: 10) {
        edges {
          node {
            login
          }
        }
      }
    }
  }
}
"""


@dataclass
class IssueLookupResult:
    """Internal result for issue discovery steps."""

    passed: bool
    reason: str | None = None
    issue: GitHubIssue | None = None
    issue_number: int | None = None


def success_check_name(config: Config) -> str:
    """Return the public check name for a successful issue-related result."""
    if config.check_issue_reference:
        return "issue_reference"
    if config.check_issue_assignee:
        return "issue_assignee"
    return "target_branch"


class IssueCheck:
    """Validate issue linkage, references, assignee, and target branch rules.

    Enabled validations run in order: target branch, issue resolution, then
    assignee. Returns a single :class:`CheckResult` for the first failure or
    for combined success.
    """

    @property
    def name(self) -> str:
        """Return the check identifier used for logging."""
        return "issue"

    def is_enabled(self, config: Config) -> bool:
        """Return whether any issue-related validation is enabled."""
        return (
            config.check_issue_reference
            or config.check_issue_assignee
            or config.check_target_branch
        )

    def run(self, context: CheckContext) -> CheckResult:
        """Validate PR issue requirements configured in the action inputs."""
        if context.pull_request is None or context.github is None:
            return CheckResult(
                name=success_check_name(context.config),
                passed=False,
                reason="Missing pull request context",
            )

        pull_request = context.pull_request
        config = context.config
        github = context.github

        logger.info(
            "Validating PR #%s by %s", pull_request.number, pull_request.user.login
        )

        if pull_request.user.type == "Bot" and not config.validate_bot_authors:
            logger.info("Skipping validation for bot user: %s", pull_request.user.login)
            return CheckResult(
                name=success_check_name(config),
                passed=True,
                reason="Bot user",
            )

        if pull_request.user.login in config.skip_users:
            logger.info(
                "Skipping validation for user in skip list: %s",
                pull_request.user.login,
            )
            return CheckResult(
                name=success_check_name(config),
                passed=True,
                reason="User in skip list",
            )

        if config.check_target_branch:
            branch_result = self.validate_target_branch(pull_request, config)
            if not branch_result.passed:
                return branch_result

        if not (config.check_issue_reference or config.check_issue_assignee):
            return CheckResult(
                name="target_branch",
                passed=True,
                reason="Branch validation passed",
            )

        lookup_result = self.resolve_corresponding_issue(pull_request, github)
        if not lookup_result.passed:
            return self.to_check_result(lookup_result, config)

        issue = lookup_result.issue
        if issue is None:
            return self.to_check_result(
                IssueLookupResult(
                    passed=False,
                    reason=NO_CORRESPONDING_ISSUE_REASON,
                ),
                config,
            )

        if config.check_issue_assignee:
            assignee_result = self.validate_assignee(pull_request, issue)
            if not assignee_result.passed:
                return assignee_result

        logger.info("PR #%s issue validation passed", pull_request.number)
        return CheckResult(
            name=success_check_name(config),
            passed=True,
            reason="All validations passed",
        )

    def resolve_corresponding_issue(
        self, pull_request: PullRequest, github: Github
    ) -> IssueLookupResult:
        """Find the PR's corresponding issue via GitHub linking or description reference."""
        linking_result = self.validate_github_closing_link(pull_request, github)
        if linking_result.issue:
            return linking_result

        if linking_result.reason and linking_result.reason != NO_LINKED_ISSUE_REASON:
            return linking_result

        reference_result = self.parse_closing_reference_in_description(pull_request)
        if not reference_result.passed or reference_result.issue_number is None:
            return IssueLookupResult(
                passed=False,
                reason=NO_CORRESPONDING_ISSUE_REASON,
            )

        issue = self.get_issue_by_number(
            pull_request, github, reference_result.issue_number
        )
        if issue is None:
            logger.warning(
                "PR #%s references issue #%s but it was not found",
                pull_request.number,
                reference_result.issue_number,
            )
            return IssueLookupResult(
                passed=False,
                reason=NO_CORRESPONDING_ISSUE_REASON,
            )

        logger.info(
            "PR #%s resolved issue #%s from description reference",
            pull_request.number,
            issue.number,
        )
        return IssueLookupResult(passed=True, issue=issue)

    def validate_target_branch(
        self, pull_request: PullRequest, config: Config
    ) -> CheckResult:
        """Validate that the PR targets an allowed branch."""
        target_branch = pull_request.base.ref
        logger.info(
            "PR #%s is targeting branch: %s", pull_request.number, target_branch
        )

        if not config.target_branches:
            return CheckResult(
                name="target_branch",
                passed=True,
                reason="No branch restrictions",
            )

        try:
            default_branch = pull_request.base.repo.default_branch
            allowed_branches = set(config.target_branches)
            if default_branch not in allowed_branches:
                allowed_branches.add(default_branch)
                logger.info(
                    "Added default branch '%s' to allowed branches",
                    default_branch,
                )
        except Exception as error:
            logger.warning("Could not get default branch: %s", error)
            allowed_branches = set(config.target_branches)

        if target_branch in allowed_branches:
            logger.info("Target branch '%s' is in allowed list", target_branch)
            return CheckResult(
                name="target_branch",
                passed=True,
                reason="Target branch allowed",
            )

        allowed = ", ".join(sorted(allowed_branches))
        logger.warning(
            "Target branch '%s' is not in allowed list: %s",
            target_branch,
            sorted(allowed_branches),
        )
        return CheckResult(
            name="target_branch",
            passed=False,
            reason=f"{TARGET_BRANCH_REASON_PREFIX}: {allowed}",
        )

    def parse_closing_reference_in_description(
        self, pull_request: PullRequest
    ) -> IssueLookupResult:
        """Parse a closing issue reference from the PR description."""
        description = pull_request.body or ""
        if not description.strip():
            logger.warning(
                "PR #%s has no linked issue and empty description for reference check",
                pull_request.number,
            )
            return IssueLookupResult(
                passed=False,
                reason=NO_CORRESPONDING_ISSUE_REASON,
            )

        match = CLOSING_REFERENCE_RE.search(description)
        if match:
            issue_number = int(match.group(2))
            logger.info(
                "PR #%s has a valid closing issue reference in description",
                pull_request.number,
            )
            return IssueLookupResult(
                passed=True,
                reason="Valid closing issue reference found in PR description",
                issue_number=issue_number,
            )

        logger.warning(
            "PR #%s has no linked issue and no valid closing issue reference",
            pull_request.number,
        )
        return IssueLookupResult(
            passed=False,
            reason=NO_CORRESPONDING_ISSUE_REASON,
        )

    def validate_github_closing_link(
        self, pull_request: PullRequest, github: Github
    ) -> IssueLookupResult:
        """Validate that the PR is linked to an issue using GraphQL."""
        try:
            linked_issues = get_linked_issues_via_graphql(pull_request, github)
            if linked_issues is None:
                return IssueLookupResult(
                    passed=False,
                    reason=GITHUB_CLOSING_LINK_ERROR,
                )
            if linked_issues:
                issue_number = linked_issues[0]["number"]
                issue = pull_request.base.repo.get_issue(issue_number)
                logger.info(
                    "PR #%s is linked to issue #%s",
                    pull_request.number,
                    issue.number,
                )
                return IssueLookupResult(passed=True, issue=issue)
            logger.warning("PR #%s is not linked to any issue", pull_request.number)
            return IssueLookupResult(passed=False, reason=NO_LINKED_ISSUE_REASON)
        except Exception as error:
            logger.error(
                "Error checking issue linking for PR #%s: %s",
                pull_request.number,
                error,
            )
            return IssueLookupResult(
                passed=False,
                reason=GITHUB_CLOSING_LINK_ERROR,
            )

    def get_issue_by_number(
        self, pull_request: PullRequest, github: Github, issue_number: int
    ) -> GitHubIssue | None:
        """Fetch an issue by number from the same repository."""
        try:
            repo = pull_request.base.repo
            owner, repo_name = repo.full_name.split("/")
            variables = {
                "owner": owner,
                "repo": repo_name,
                "issueNumber": issue_number,
            }
            requester = github._Github__requester
            _, response = requester.requestJsonAndCheck(
                "POST",
                "/graphql",
                input={"query": ISSUE_BY_NUMBER_QUERY, "variables": variables},
            )

            if "errors" in response:
                logger.error(
                    "GraphQL errors when fetching issue #%s: %s",
                    issue_number,
                    response["errors"],
                )
                return None

            issue_data = response.get("data", {}).get("repository", {}).get("issue")
            if not issue_data:
                logger.warning(
                    "Issue #%s not found in repository %s",
                    issue_number,
                    repo.full_name,
                )
                return None

            issue = repo.get_issue(issue_number)
            logger.info(
                "Successfully fetched issue #%s for assignee validation",
                issue_number,
            )
            return issue
        except Exception as error:
            logger.error(
                "Error fetching issue #%s via GraphQL: %s",
                issue_number,
                error,
            )
            return None

    def validate_assignee(
        self, pull_request: PullRequest, issue: GitHubIssue | None
    ) -> CheckResult:
        """Validate that the issue assignee matches the PR author."""
        if issue is None:
            return CheckResult(
                name="issue_assignee",
                passed=False,
                reason=NO_ISSUE_FOR_ASSIGNEE_REASON,
            )

        assignees = issue.assignees
        if not assignees:
            logger.warning("Issue #%s has no assignees", issue.number)
            return CheckResult(
                name="issue_assignee",
                passed=False,
                reason=ISSUE_HAS_NO_ASSIGNEE_REASON,
            )

        author = pull_request.user.login
        assignee_logins = {assignee.login for assignee in assignees}
        if author in assignee_logins:
            logger.info(
                "Issue #%s assignee matches PR author: %s",
                issue.number,
                author,
            )
            return CheckResult(
                name="issue_assignee", passed=True, reason="Assignee matches"
            )

        logger.warning(
            "Issue #%s assignees %s do not include PR author %s",
            issue.number,
            assignee_logins,
            author,
        )
        return CheckResult(
            name="issue_assignee",
            passed=False,
            reason=ASSIGNEE_MISMATCH_REASON,
        )

    def to_check_result(self, result: IssueLookupResult, config: Config) -> CheckResult:
        """Convert an internal issue lookup result to a check result."""
        check_name = (
            "issue_reference" if config.check_issue_reference else "issue_assignee"
        )
        reason = result.reason
        if not config.check_issue_reference:
            if reason == NO_CORRESPONDING_ISSUE_REASON:
                reason = NO_ISSUE_FOR_ASSIGNEE_REASON
            elif reason == GITHUB_CLOSING_LINK_ERROR:
                reason = NO_ISSUE_FOR_ASSIGNEE_REASON
        return CheckResult(
            name=check_name,
            passed=result.passed,
            reason=reason,
        )


def get_linked_issues_via_graphql(
    pull_request: PullRequest, github: Github
) -> list[dict] | None:
    """Return linked issues from GitHub GraphQL closingIssuesReferences."""
    try:
        repo = pull_request.base.repo
        owner, repo_name = repo.full_name.split("/")
        variables = {
            "owner": owner,
            "repo": repo_name,
            "pullRequestNumber": pull_request.number,
        }
        requester = github._Github__requester
        _, response = requester.requestJsonAndCheck(
            "POST",
            "/graphql",
            input={"query": LINKED_ISSUES_QUERY, "variables": variables},
        )

        if "errors" in response:
            logger.error("GraphQL errors: %s", response["errors"])
            return None

        edges = (
            response.get("data", {})
            .get("repository", {})
            .get("pullRequest", {})
            .get("closingIssuesReferences", {})
            .get("edges", [])
        )
        linked_issues = [edge.get("node", {}) for edge in edges]
        logger.info(
            "Found %s closing issues for PR #%s",
            len(linked_issues),
            pull_request.number,
        )
        return linked_issues
    except Exception as error:
        logger.error("Error fetching linked issues via GraphQL: %s", error)
        return None
