"""Tests for issue contribution check."""

from unittest.mock import Mock, patch

import pytest

from check_contribution_action.checks.base import CheckContext
from check_contribution_action.checks.issue import (
    IssueCheck,
    IssueLookupResult,
    success_check_name,
)
from check_contribution_action.failure_reasons import (
    ASSIGNEE_MISMATCH_REASON,
    GITHUB_CLOSING_LINK_ERROR,
    ISSUE_HAS_NO_ASSIGNEE_REASON,
    NO_CORRESPONDING_ISSUE_REASON,
    NO_ISSUE_FOR_ASSIGNEE_REASON,
)
from check_contribution_action.models import CheckResult


def make_context(config, github, pull_request) -> CheckContext:
    """Build a check context for issue validation tests."""
    return CheckContext(config=config, github=github, pull_request=pull_request)


@pytest.fixture
def issue_check() -> IssueCheck:
    """Return an issue check instance."""
    return IssueCheck()


class TestIssueCheck:
    """Test cases for IssueCheck."""

    def test_name_property(self, issue_check):
        """Test the check identifier used for logging."""
        assert issue_check.name == "issue"

    def test_success_check_name_target_branch_only(self, mock_config):
        """Test success naming when only target branch validation is enabled."""
        mock_config.check_issue_reference = False
        mock_config.check_issue_assignee = False

        assert success_check_name(mock_config) == "target_branch"

    def test_is_enabled(self, issue_check, mock_config):
        """Test enabled flag follows issue-related config."""
        mock_config.check_issue_reference = False
        mock_config.check_issue_assignee = False
        mock_config.target_branches = []
        mock_config.check_target_branch = False
        assert issue_check.is_enabled(mock_config) is False

        mock_config.check_issue_reference = True
        assert issue_check.is_enabled(mock_config) is True

        mock_config.check_issue_reference = False
        mock_config.check_target_branch = True
        assert issue_check.is_enabled(mock_config) is True

    def test_run_missing_context(self, issue_check, mock_config):
        """Test missing PR context fails the check."""
        context = CheckContext(config=mock_config)

        result = issue_check.run(context)

        assert result == CheckResult(
            name="issue_reference",
            passed=False,
            reason="Missing pull request context",
        )

    def test_validate_bot_pr(
        self, issue_check, mock_config, mock_github_client, mock_bot_pr
    ):
        """Test that bot PRs are skipped by default."""
        mock_config.validate_bot_authors = False
        result = issue_check.run(
            make_context(mock_config, mock_github_client, mock_bot_pr)
        )

        assert result.passed is True
        assert result.reason == "Bot user"

    def test_validate_bot_pr_when_validate_bot_authors_enabled(
        self, issue_check, mock_config, mock_github_client, mock_bot_pr
    ):
        """Test that bot PRs are validated when validate_bot_authors is enabled."""
        mock_config.validate_bot_authors = True
        mock_config.check_issue_reference = True
        mock_config.check_issue_assignee = False
        mock_config.target_branches = []
        mock_bot_pr.base.repo.full_name = "testowner/testrepo"
        mock_bot_pr.body = "Bot PR without issue reference"
        mock_github_client._Github__requester.requestJsonAndCheck.return_value = (
            {},
            {
                "data": {
                    "repository": {
                        "pullRequest": {"closingIssuesReferences": {"edges": []}}
                    }
                }
            },
        )

        result = issue_check.run(
            make_context(mock_config, mock_github_client, mock_bot_pr)
        )

        assert result.passed is False
        assert result.reason == NO_CORRESPONDING_ISSUE_REASON

    def test_validate_skip_user_pr(
        self, issue_check, mock_config, mock_github_client, mock_pr
    ):
        """Test that PRs from skip users are skipped."""
        mock_pr.user.login = "testuser1"
        result = issue_check.run(make_context(mock_config, mock_github_client, mock_pr))

        assert result.passed is True
        assert result.reason == "User in skip list"

    def test_validate_pr_with_linked_issue(
        self,
        issue_check,
        mock_config,
        mock_github_client,
        mock_pr,
        mock_issue_with_assignee,
    ):
        """Test validation of PR with linked issue and matching assignee."""
        mock_github_client._Github__requester.requestJsonAndCheck.return_value = (
            {},
            {
                "data": {
                    "repository": {
                        "pullRequest": {
                            "closingIssuesReferences": {
                                "edges": [
                                    {
                                        "node": {
                                            "number": 456,
                                            "title": "Test Issue",
                                            "url": "https://github.com/testowner/testrepo/issues/456",
                                        }
                                    }
                                ]
                            }
                        }
                    }
                }
            },
        )
        mock_pr.base.repo.get_issue.return_value = mock_issue_with_assignee

        result = issue_check.run(make_context(mock_config, mock_github_client, mock_pr))

        assert result.passed is True
        assert result.reason == "All validations passed"

    def test_validate_pr_no_linked_issue(
        self, issue_check, mock_config, mock_github_client, mock_pr
    ):
        """Test validation of PR with no linked issue."""
        mock_github_client._Github__requester.requestJsonAndCheck.return_value = (
            {},
            {
                "data": {
                    "repository": {
                        "pullRequest": {"closingIssuesReferences": {"edges": []}}
                    }
                }
            },
        )

        result = issue_check.run(make_context(mock_config, mock_github_client, mock_pr))

        assert result.passed is False
        assert result.reason == NO_CORRESPONDING_ISSUE_REASON

    def test_validate_pr_no_linked_issue_with_description_reference_enabled_and_valid(
        self,
        issue_check,
        mock_config,
        mock_github_client,
        mock_pr,
        mock_issue,
    ):
        """Valid description reference should pass when GitHub linking is unavailable."""
        mock_config.check_issue_reference = True
        mock_config.check_issue_assignee = False
        mock_pr.body = "This PR fixes #123"

        def graphql_side_effect(*args, **kwargs):
            input_data = kwargs.get("input", {})
            query = input_data.get("query", "")
            variables = input_data.get("variables", {})

            if "GetIssue" in query and variables.get("issueNumber") == 123:
                return (
                    {},
                    {
                        "data": {
                            "repository": {
                                "issue": {
                                    "number": 123,
                                    "title": "Test Issue",
                                    "url": "https://github.com/testowner/testrepo/issues/123",
                                    "assignees": {"edges": []},
                                }
                            }
                        }
                    },
                )
            return ({}, {"data": {}})

        mock_github_client._Github__requester.requestJsonAndCheck.side_effect = (
            graphql_side_effect
        )
        mock_pr.base.repo.get_issue.return_value = mock_issue

        result = issue_check.run(make_context(mock_config, mock_github_client, mock_pr))

        assert result.passed is True
        assert result.reason == "All validations passed"

    def test_validate_pr_no_linked_issue_with_description_reference_enabled_and_invalid(
        self, issue_check, mock_config, mock_github_client, mock_pr
    ):
        """Invalid description reference should fail."""
        mock_config.check_issue_reference = True
        mock_config.check_issue_assignee = False
        mock_pr.body = "This PR references issue #123 but without closing keyword"
        mock_github_client._Github__requester.requestJsonAndCheck.return_value = (
            {},
            {
                "data": {
                    "repository": {
                        "pullRequest": {"closingIssuesReferences": {"edges": []}}
                    }
                }
            },
        )

        result = issue_check.run(make_context(mock_config, mock_github_client, mock_pr))

        assert result.passed is False
        assert result.reason == NO_CORRESPONDING_ISSUE_REASON

    def test_validate_pr_no_linked_issue_with_invalid_reference_format(
        self, issue_check, mock_config, mock_github_client, mock_pr
    ):
        """Invalid reference format in description should be rejected."""
        mock_config.check_issue_reference = True
        mock_config.check_issue_assignee = False
        mock_pr.body = "Resolves some-org/some-repo#42"
        mock_github_client._Github__requester.requestJsonAndCheck.return_value = (
            {},
            {
                "data": {
                    "repository": {
                        "pullRequest": {"closingIssuesReferences": {"edges": []}}
                    }
                }
            },
        )

        result = issue_check.run(make_context(mock_config, mock_github_client, mock_pr))

        assert result.passed is False
        assert result.reason == NO_CORRESPONDING_ISSUE_REASON

    def test_validate_pr_description_reference_with_assignee_check(
        self,
        issue_check,
        mock_config,
        mock_github_client,
        mock_pr,
        mock_issue_with_assignee,
    ):
        """Description reference with assignee requirement should validate assignee."""
        mock_config.check_issue_reference = False
        mock_config.check_issue_assignee = True
        mock_pr.body = "This PR fixes #456"

        def graphql_side_effect(*args, **kwargs):
            input_data = kwargs.get("input", {})
            query = input_data.get("query", "")
            variables = input_data.get("variables", {})

            if "GetIssue" in query and variables.get("issueNumber") == 456:
                return (
                    {},
                    {
                        "data": {
                            "repository": {
                                "issue": {
                                    "number": 456,
                                    "title": "Test Issue",
                                    "url": "https://github.com/testowner/testrepo/issues/456",
                                    "assignees": {
                                        "edges": [{"node": {"login": "testuser"}}]
                                    },
                                }
                            }
                        }
                    },
                )
            return ({}, {"data": {}})

        mock_github_client._Github__requester.requestJsonAndCheck.side_effect = (
            graphql_side_effect
        )
        mock_pr.base.repo.get_issue.return_value = mock_issue_with_assignee

        result = issue_check.run(make_context(mock_config, mock_github_client, mock_pr))

        assert result.passed is True
        assert result.reason == "All validations passed"

    def test_validate_pr_description_reference_with_assignee_mismatch(
        self,
        issue_check,
        mock_config,
        mock_github_client,
        mock_pr,
        mock_issue_with_different_assignee,
    ):
        """Description reference with assignee mismatch should fail."""
        mock_config.check_issue_reference = False
        mock_config.check_issue_assignee = True
        mock_pr.body = "This PR fixes #456"

        def graphql_side_effect(*args, **kwargs):
            input_data = kwargs.get("input", {})
            query = input_data.get("query", "")
            variables = input_data.get("variables", {})

            if "GetIssue" in query and variables.get("issueNumber") == 456:
                return (
                    {},
                    {
                        "data": {
                            "repository": {
                                "issue": {
                                    "number": 456,
                                    "title": "Test Issue",
                                    "url": "https://github.com/testowner/testrepo/issues/456",
                                    "assignees": {
                                        "edges": [{"node": {"login": "differentuser"}}]
                                    },
                                }
                            }
                        }
                    },
                )
            return ({}, {"data": {}})

        mock_github_client._Github__requester.requestJsonAndCheck.side_effect = (
            graphql_side_effect
        )
        mock_pr.base.repo.get_issue.return_value = mock_issue_with_different_assignee

        result = issue_check.run(make_context(mock_config, mock_github_client, mock_pr))

        assert result.passed is False
        assert result.reason == ASSIGNEE_MISMATCH_REASON

    def test_validate_pr_issue_linking_error(
        self, issue_check, mock_config, mock_github_client, mock_pr
    ):
        """Test handling of GraphQL errors when checking issue linking."""
        mock_github_client._Github__requester.requestJsonAndCheck.return_value = (
            {},
            {"errors": [{"message": "GraphQL API Error"}]},
        )

        result = issue_check.run(make_context(mock_config, mock_github_client, mock_pr))

        assert result.passed is False
        assert result.reason == GITHUB_CLOSING_LINK_ERROR

    def test_validate_pr_assignee_mismatch(
        self,
        issue_check,
        mock_config,
        mock_github_client,
        mock_pr,
        mock_issue_with_different_assignee,
    ):
        """Test validation when assignee does not match PR author."""
        mock_github_client._Github__requester.requestJsonAndCheck.return_value = (
            {},
            {
                "data": {
                    "repository": {
                        "pullRequest": {
                            "closingIssuesReferences": {
                                "edges": [
                                    {
                                        "node": {
                                            "number": 456,
                                            "title": "Test Issue",
                                            "url": "https://github.com/testowner/testrepo/issues/456",
                                        }
                                    }
                                ]
                            }
                        }
                    }
                }
            },
        )
        mock_pr.base.repo.get_issue.return_value = mock_issue_with_different_assignee

        result = issue_check.run(make_context(mock_config, mock_github_client, mock_pr))

        assert result.passed is False
        assert result.reason == ASSIGNEE_MISMATCH_REASON

    def test_validate_pr_no_assignee(
        self, issue_check, mock_config, mock_github_client, mock_pr, mock_issue
    ):
        """Test validation when issue has no assignee."""
        mock_github_client._Github__requester.requestJsonAndCheck.return_value = (
            {},
            {
                "data": {
                    "repository": {
                        "pullRequest": {
                            "closingIssuesReferences": {
                                "edges": [
                                    {
                                        "node": {
                                            "number": 456,
                                            "title": "Test Issue",
                                            "url": "https://github.com/testowner/testrepo/issues/456",
                                        }
                                    }
                                ]
                            }
                        }
                    }
                }
            },
        )
        mock_pr.base.repo.get_issue.return_value = mock_issue

        result = issue_check.run(make_context(mock_config, mock_github_client, mock_pr))

        assert result.passed is False
        assert result.reason == ISSUE_HAS_NO_ASSIGNEE_REASON

    def test_validate_pr_assignee_not_required(
        self, issue_check, mock_github_client, mock_pr, mock_issue
    ):
        """Test validation when assignee requirement is disabled."""
        mock_config = Mock()
        mock_config.skip_users = []
        mock_config.check_issue_reference = True
        mock_config.check_issue_assignee = False
        mock_config.target_branches = []
        mock_github_client._Github__requester.requestJsonAndCheck.return_value = (
            {},
            {
                "data": {
                    "repository": {
                        "pullRequest": {
                            "closingIssuesReferences": {
                                "edges": [
                                    {
                                        "node": {
                                            "number": 456,
                                            "title": "Test Issue",
                                            "url": "https://github.com/testowner/testrepo/issues/456",
                                        }
                                    }
                                ]
                            }
                        }
                    }
                }
            },
        )
        mock_pr.base.repo.get_issue.return_value = mock_issue

        result = issue_check.run(make_context(mock_config, mock_github_client, mock_pr))

        assert result.passed is True
        assert result.reason == "All validations passed"

    def test_validate_pr_graphql_error_handling(
        self, issue_check, mock_config, mock_github_client, mock_pr
    ):
        """Test GraphQL exception handling during issue linking."""
        mock_github_client._Github__requester.requestJsonAndCheck.side_effect = (
            Exception("Network error")
        )

        result = issue_check.run(make_context(mock_config, mock_github_client, mock_pr))

        assert result.passed is False
        assert result.reason == GITHUB_CLOSING_LINK_ERROR

    def test_validate_target_branch_no_restrictions(
        self, issue_check, mock_config, mock_pr
    ):
        """Test branch validation when no target branches are configured."""
        mock_config.target_branches = []
        result = issue_check.validate_target_branch(mock_pr, mock_config)

        assert result.passed is True
        assert result.reason == "No branch restrictions"

    def test_validate_target_branch_allowed(self, issue_check, mock_config, mock_pr):
        """Test branch validation when PR targets an allowed branch."""
        mock_config.target_branches = ["main", "develop", "feature-branch"]
        mock_pr.base.ref = "develop"
        result = issue_check.validate_target_branch(mock_pr, mock_config)

        assert result.passed is True
        assert result.reason == "Target branch allowed"

    def test_validate_target_branch_not_allowed(
        self, issue_check, mock_config, mock_pr
    ):
        """Test branch validation when PR targets a disallowed branch."""
        mock_config.target_branches = ["develop", "release"]
        mock_pr.base.ref = "feature-branch"
        mock_pr.base.repo.default_branch = "main"
        result = issue_check.validate_target_branch(mock_pr, mock_config)

        assert result.passed is False
        assert "PR must target one of the allowed branches" in result.reason
        assert "develop" in result.reason
        assert "release" in result.reason
        assert "main" in result.reason

    def test_validate_target_branch_default_included(
        self, issue_check, mock_config, mock_pr
    ):
        """Test that default branch is automatically included in allowed branches."""
        mock_config.target_branches = ["develop", "release"]
        mock_pr.base.ref = "main"
        mock_pr.base.repo.default_branch = "main"
        result = issue_check.validate_target_branch(mock_pr, mock_config)

        assert result.passed is True
        assert result.reason == "Target branch allowed"

    def test_validate_pr_with_branch_restriction_allowed(
        self,
        issue_check,
        mock_config,
        mock_github_client,
        mock_pr,
        mock_issue_with_assignee,
    ):
        """Test full PR validation with allowed target branch."""
        mock_config.target_branches = ["main", "develop"]
        mock_config.check_target_branch = True
        mock_pr.base.ref = "main"
        mock_github_client._Github__requester.requestJsonAndCheck.return_value = (
            {},
            {
                "data": {
                    "repository": {
                        "pullRequest": {
                            "closingIssuesReferences": {
                                "edges": [
                                    {
                                        "node": {
                                            "number": 456,
                                            "title": "Test Issue",
                                            "url": "https://github.com/testowner/testrepo/issues/456",
                                        }
                                    }
                                ]
                            }
                        }
                    }
                }
            },
        )
        mock_pr.base.repo.get_issue.return_value = mock_issue_with_assignee

        result = issue_check.run(make_context(mock_config, mock_github_client, mock_pr))

        assert result.passed is True
        assert result.reason == "All validations passed"

    def test_validate_pr_with_branch_restriction_not_allowed(
        self, issue_check, mock_config, mock_github_client, mock_pr
    ):
        """Test full PR validation when target branch is not allowed."""
        mock_config.target_branches = ["main", "develop"]
        mock_config.check_target_branch = True
        mock_pr.base.ref = "feature-branch"

        result = issue_check.run(make_context(mock_config, mock_github_client, mock_pr))

        assert result.passed is False
        assert "PR must target one of the allowed branches" in result.reason

    def test_validate_pr_branch_only_enabled(
        self, issue_check, mock_config, mock_github_client, mock_pr
    ):
        """Test branch-only validation when no issue checks are enabled."""
        mock_config.check_issue_reference = False
        mock_config.check_issue_assignee = False
        mock_config.target_branches = ["main"]
        mock_config.check_target_branch = True
        mock_pr.base.ref = "main"

        result = issue_check.run(make_context(mock_config, mock_github_client, mock_pr))

        assert result.passed is True
        assert result.reason == "Branch validation passed"

    def test_parse_closing_reference_in_description_empty_description(
        self, issue_check, mock_pr
    ):
        """Test reference parsing with an empty PR description."""
        mock_pr.body = "   "
        result = issue_check.parse_closing_reference_in_description(mock_pr)

        assert result.passed is False
        assert result.reason == NO_CORRESPONDING_ISSUE_REASON

    def test_validate_target_branch_default_branch_lookup_error(
        self, issue_check, mock_config, mock_pr
    ):
        """Test branch validation when default branch lookup fails."""
        mock_config.target_branches = ["develop"]
        mock_pr.base.ref = "feature-branch"
        repo = Mock()
        type(repo).default_branch = property(
            lambda self: (_ for _ in ()).throw(RuntimeError("API error"))
        )
        mock_pr.base.repo = repo

        result = issue_check.validate_target_branch(mock_pr, mock_config)

        assert result.passed is False
        assert "PR must target one of the allowed branches" in result.reason

    def test_validate_pr_linking_and_reference_both_fail(
        self, issue_check, mock_config, mock_github_client, mock_pr
    ):
        """Test combined failure when linking and reference fallback both fail."""
        mock_config.check_issue_reference = True
        mock_pr.body = "No valid reference here"
        mock_github_client._Github__requester.requestJsonAndCheck.return_value = (
            {},
            {
                "data": {
                    "repository": {
                        "pullRequest": {"closingIssuesReferences": {"edges": []}}
                    }
                }
            },
        )

        result = issue_check.run(make_context(mock_config, mock_github_client, mock_pr))

        assert result.passed is False
        assert result.reason == NO_CORRESPONDING_ISSUE_REASON

    def test_validate_github_closing_link_repo_error(
        self, issue_check, mock_github_client, mock_pr
    ):
        """Test issue linking when fetching the linked issue fails."""
        mock_pr.base.repo.get_issue.side_effect = Exception("Issue fetch failed")
        mock_github_client._Github__requester.requestJsonAndCheck.return_value = (
            {},
            {
                "data": {
                    "repository": {
                        "pullRequest": {
                            "closingIssuesReferences": {
                                "edges": [{"node": {"number": 456}}]
                            }
                        }
                    }
                }
            },
        )

        result = issue_check.validate_github_closing_link(mock_pr, mock_github_client)

        assert result.passed is False
        assert result.reason == GITHUB_CLOSING_LINK_ERROR

    def test_get_issue_by_number_graphql_errors(
        self, issue_check, mock_github_client, mock_pr
    ):
        """Test issue lookup when GraphQL returns errors."""
        mock_github_client._Github__requester.requestJsonAndCheck.return_value = (
            {},
            {"errors": [{"message": "Not found"}]},
        )

        issue = issue_check.get_issue_by_number(mock_pr, mock_github_client, 123)

        assert issue is None

    def test_get_issue_by_number_missing_issue(
        self, issue_check, mock_github_client, mock_pr
    ):
        """Test issue lookup when GraphQL returns no issue data."""
        mock_github_client._Github__requester.requestJsonAndCheck.return_value = (
            {},
            {"data": {"repository": {"issue": None}}},
        )

        issue = issue_check.get_issue_by_number(mock_pr, mock_github_client, 123)

        assert issue is None

    def test_get_issue_by_number_request_error(
        self, issue_check, mock_github_client, mock_pr
    ):
        """Test issue lookup when GraphQL request raises."""
        mock_github_client._Github__requester.requestJsonAndCheck.side_effect = (
            Exception("Network error")
        )

        issue = issue_check.get_issue_by_number(mock_pr, mock_github_client, 123)

        assert issue is None

    def test_validate_assignee_without_issue(self, issue_check, mock_pr):
        """Test assignee validation when no issue is available."""
        result = issue_check.validate_assignee(mock_pr, None)

        assert result.passed is False
        assert result.reason == NO_ISSUE_FOR_ASSIGNEE_REASON

    def test_resolve_corresponding_issue_returns_linking_error_without_fallback(
        self, issue_check, mock_github_client, mock_pr
    ):
        """Test GraphQL linking errors are returned without reference fallback."""
        mock_github_client._Github__requester.requestJsonAndCheck.return_value = (
            {},
            {"errors": [{"message": "GraphQL API Error"}]},
        )

        result = issue_check.resolve_corresponding_issue(mock_pr, mock_github_client)

        assert result.passed is False
        assert result.reason == GITHUB_CLOSING_LINK_ERROR

    def test_resolve_corresponding_issue_referenced_issue_not_found(
        self, issue_check, mock_github_client, mock_pr
    ):
        """Test description references fail when the issue cannot be loaded."""
        mock_pr.body = "This PR fixes #123"

        def graphql_side_effect(*args, **kwargs):
            input_data = kwargs.get("input", {})
            query = input_data.get("query", "")
            variables = input_data.get("variables", {})

            if "GetIssue" in query and variables.get("issueNumber") == 123:
                return ({}, {"data": {"repository": {"issue": None}}})
            return (
                {},
                {
                    "data": {
                        "repository": {
                            "pullRequest": {"closingIssuesReferences": {"edges": []}}
                        }
                    }
                },
            )

        mock_github_client._Github__requester.requestJsonAndCheck.side_effect = (
            graphql_side_effect
        )

        result = issue_check.resolve_corresponding_issue(mock_pr, mock_github_client)

        assert result.passed is False
        assert result.reason == NO_CORRESPONDING_ISSUE_REASON

    def test_run_lookup_passed_without_issue(
        self, issue_check, mock_config, mock_github_client, mock_pr
    ):
        """Test defensive handling when lookup reports success without an issue."""
        mock_config.check_issue_reference = True
        mock_config.check_issue_assignee = False

        with patch.object(
            issue_check,
            "resolve_corresponding_issue",
            return_value=IssueLookupResult(passed=True, issue=None),
        ):
            result = issue_check.run(
                make_context(mock_config, mock_github_client, mock_pr)
            )

        assert result.passed is False
        assert result.reason == NO_CORRESPONDING_ISSUE_REASON

    def test_assignee_only_without_issue_uses_assignee_failure(
        self, issue_check, mock_config, mock_github_client, mock_pr
    ):
        """Test assignee-only config maps missing issue to assignee error."""
        mock_config.check_issue_reference = False
        mock_config.check_issue_assignee = True
        mock_pr.body = "No valid reference here"
        mock_github_client._Github__requester.requestJsonAndCheck.return_value = (
            {},
            {
                "data": {
                    "repository": {
                        "pullRequest": {"closingIssuesReferences": {"edges": []}}
                    }
                }
            },
        )

        result = issue_check.run(make_context(mock_config, mock_github_client, mock_pr))

        assert result.passed is False
        assert result.name == "issue_assignee"
        assert result.reason == NO_ISSUE_FOR_ASSIGNEE_REASON

    def test_assignee_only_graphql_error_uses_assignee_failure(
        self, issue_check, mock_config, mock_github_client, mock_pr
    ):
        """Test assignee-only config maps GraphQL errors to assignee failure."""
        mock_config.check_issue_reference = False
        mock_config.check_issue_assignee = True
        mock_pr.body = "This PR fixes #456"
        mock_github_client._Github__requester.requestJsonAndCheck.return_value = (
            {},
            {"errors": [{"message": "GraphQL API Error"}]},
        )

        result = issue_check.run(make_context(mock_config, mock_github_client, mock_pr))

        assert result.passed is False
        assert result.name == "issue_assignee"
        assert result.reason == NO_ISSUE_FOR_ASSIGNEE_REASON


class TestIssueLookupResult:
    """Test cases for IssueLookupResult helper dataclass."""

    def test_issue_lookup_result_creation(self):
        """Test IssueLookupResult creation."""
        result = IssueLookupResult(passed=True, reason="Test reason", issue=Mock())

        assert result.passed is True
        assert result.reason == "Test reason"
        assert result.issue is not None
