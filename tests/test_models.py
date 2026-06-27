"""Tests for models module."""

from check_contribution_action.models import CheckResult, ValidationResult


class TestModels:
    """Test cases for shared data models."""

    def test_validation_result_failed_results(self):
        """Test filtering failed check results."""
        results = [
            CheckResult(name="signature", passed=True),
            CheckResult(name="commit_sign_off", passed=False, reason="missing"),
        ]
        validation = ValidationResult(passed=False, results=results)

        assert validation.failed_results == [results[1]]
