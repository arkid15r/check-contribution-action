"""Contribution check implementations."""

from check_contribution_action.checks.base import CheckContext, ContributionCheck
from check_contribution_action.checks.issue import IssueCheck
from check_contribution_action.checks.sign_off import SignOffCheck
from check_contribution_action.checks.signature import SignatureCheck

ALL_CHECKS: list[ContributionCheck] = [
    IssueCheck(),
    SignatureCheck(),
    SignOffCheck(),
]

__all__ = [
    "ALL_CHECKS",
    "CheckContext",
    "ContributionCheck",
    "IssueCheck",
    "SignOffCheck",
    "SignatureCheck",
]
