# Integration tests

GitHub Actions workflow: [integration-tests.yml](../../workflows/integration-tests.yml)

Scripts create real issues, branches, and pull requests in the repository, run the action Docker image against a synthetic `pull_request` event, and clean up artifacts after each case and workflow run.

## Running

- **CI:** runs on `workflow_dispatch`, pushes to `main`, and PRs that touch action sources or these scripts.
- **Locally:** requires `GH_TOKEN` (or `GITHUB_TOKEN`), `GITHUB_RUN_ID`, `GITHUB_WORKSPACE`, and `GITHUB_REPOSITORY`. Example:

  ```bash
  export GH_TOKEN=...
  export GITHUB_RUN_ID=local
  export GITHUB_WORKSPACE="$PWD"
  export GITHUB_REPOSITORY=owner/repo
  bash .github/scripts/integration/run_case.sh issue-linked-pass
  ```

Integration cases pass `validate_bot_authors=true` so PRs created by `github-actions[bot]` are validated.

## Cases

Case IDs mirror `check_for` / `close_on` names (`_` → `-`) with a `-pass` or `-fail` suffix.

| Case | `check_for` | Expected result |
|------|-------------|-----------------|
| `commit-sign-off-fail` | `commit_sign_off` | fail |
| `commit-sign-off-pass` | `commit_sign_off` | pass |
| `commit-signature-fail` | `commit_signature` | fail |
| `issue-assignee-fail` | `issue_assignee, issue_reference` | fail (linked issue, no assignee) |
| `issue-linked-fail` | `issue_reference` (no linked issue or reference) | fail |
| `issue-linked-pass` | `issue_reference` (GitHub closing link) | pass |
| `issue-reference-fail` | `issue_reference` (invalid description reference) | fail |
| `issue-reference-pass` | `issue_reference` (PR description reference only) | pass |
| `target-branch-fail` | `target_branch` (+ `target_branches`) | fail |
| `target-branch-pass` | `target_branch` (+ `target_branches`) | pass |

## Omitted: `issue-assignee-pass`

There is no `issue-assignee-pass` integration case.

Integration PRs are authored by `github-actions[bot]`. The assignee check requires the linked issue assignee to match the PR author. GitHub does not allow assigning bot accounts such as `github-actions[bot]` to issues, so a passing assignee scenario cannot be set up with the default Actions token.

`issue-assignee-fail` still covers the failure path (linked issue without a matching assignee). The success path is covered by unit tests in `tests/test_issue_check.py`.

## GraphQL link errors

GitHub closing-link lookup failures (API errors) do not fall back to PR description parsing. That behavior is verified in unit tests (`test_resolve_corresponding_issue_returns_linking_error_without_fallback` and related cases), not via integration tests, because CI cannot force GraphQL errors against the live GitHub API.
