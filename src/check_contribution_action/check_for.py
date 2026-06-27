"""Contribution check names enabled via the check_for input."""

CHECK_FOR_NAMES: frozenset[str] = frozenset(
    {
        "commit_sign_off",
        "commit_signature",
        "issue_assignee",
        "issue_reference",
        "target_branch",
    }
)

DEFAULT_ERROR_MESSAGES: dict[str, str] = {
    "commit_sign_off": (
        "One or more commits are missing or have an invalid Signed-off-by trailer."
    ),
    "commit_signature": "One or more commits are not signed.",
    "issue_assignee": (
        "The linked issue must be assigned to the PR author before this PR can be merged."
    ),
    "issue_reference": (
        "This PR must be linked to an issue or include a valid closing issue "
        "reference in the description."
    ),
    "target_branch": "This PR must target one of the allowed branches.",
}
