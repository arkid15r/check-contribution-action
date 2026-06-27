"""PR closure trigger definitions for failed contribution checks."""

from check_contribution_action.check_for import CHECK_FOR_NAMES
from check_contribution_action.models import CheckResult

# close_on accepts the same check names as check_for.
CLOSE_PR_TRIGGER_NAMES = CHECK_FOR_NAMES


def failure_matches_close_trigger(result: CheckResult, trigger: str) -> bool:
    """Return whether a failed check result matches a configured close trigger."""
    return trigger in CHECK_FOR_NAMES and result.name == trigger
