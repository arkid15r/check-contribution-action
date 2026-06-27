"""Shared failure reason strings for contribution checks."""

NO_LINKED_ISSUE_REASON = "No linked issue"

NO_CORRESPONDING_ISSUE_REASON = (
    "No linked issue or valid closing issue reference in PR description"
)

NO_ISSUE_FOR_ASSIGNEE_REASON = "No issue to validate assignee"

GITHUB_CLOSING_LINK_ERROR = "Error checking GitHub closing issue link"

ASSIGNEE_MISMATCH_REASON = "Assignee mismatch"

ISSUE_HAS_NO_ASSIGNEE_REASON = "Issue has no assignee"

TARGET_BRANCH_REASON_PREFIX = "PR must target one of the allowed branches"

MISSING_SIGN_OFF_REASON = "Missing sign-off"

SIGN_OFF_MISMATCH_REASON = "Sign-off mismatch"

UNSIGNED_COMMITS_REASON = "Unsigned commits"
