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
  bash .github/scripts/integration/run_case.sh issue-linking-pass
  ```

Integration cases pass `validate_bot_authors=true` so PRs created by `github-actions[bot]` are validated.

## Cases

| Case | Checks enabled | Expected result |
|------|----------------|-----------------|
| `issue-linking-pass` | `check_issue_linking` | pass |
| `issue-linking-fail` | `check_issue_linking` | fail |
| `issue-reference-pass` | `check_issue_reference` | pass |
| `issue-reference-fail` | `check_issue_reference` | fail |
| `assignee-fail` | `check_issue_linking`, `require_assignee` | fail (linked issue, no assignee) |
| `sign-off-pass` | `check_sign_off` | pass |
| `sign-off-fail` | `check_sign_off` | fail |
| `signature-fail` | `check_commit_signature` | fail |
| `target-branch-pass` | `target_branches` | pass |
| `target-branch-fail` | `target_branches` | fail |

## Omitted: `assignee-pass`

There is no `assignee-pass` integration case.

Integration PRs are authored by `github-actions[bot]`. The assignee check requires the linked issue assignee to match the PR author. GitHub does not allow assigning bot accounts such as `github-actions[bot]` to issues, so a passing assignee scenario cannot be set up with the default Actions token.

`assignee-fail` still covers the failure path (linked issue without a matching assignee). The success path is covered by unit tests in `tests/test_issue_check.py`.
