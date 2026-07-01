# Check Contribution Action

GitHub Action for validating contribution requirements: issue linkage, commit signatures (GPG/SSH), and DCO sign-off trailers.

Configure which checks run via the required `check_for` input.

Sign-off and signature checks load **PR commits from the GitHub API** (`pulls/{number}/commits`). No `actions/checkout` step is required.

## Usage

Use `pull_request_target` so fork contributions get a token that can comment and close PRs. Skip PRs whose base is not this repository (PRs opened entirely inside a fork).

```yaml
name: Check Contribution
on:
  pull_request_target:
    types:
      - edited
      - opened
      - reopened
      - synchronize

jobs:
  check-contribution:
    if: github.event.pull_request.base.repo.full_name == github.repository
    runs-on: ubuntu-latest
    permissions:
      contents: read
      issues: read
      pull-requests: write
    steps:
      - uses: arkid15r/check-contribution-action@v0.1.4
        with:
          check_for: commit_sign_off, commit_signature, issue_assignee, issue_reference
          close_on: issue_assignee
          skip_users_file_path: .github/skip_users.txt
          github_token: ${{ secrets.GITHUB_TOKEN }}
```

Do not check out the PR head ref or run code from the PR branch in this job. This action only reads PR data via the GitHub API.

`skip_users_file_path` is fetched at runtime from the repository. Supported formats:

- `.github/skip_users.txt` — path relative to the workflow repository
- `OWASP/Nest/.github/skip_users.txt` — full GitHub path (owner included)

`.github/skip_users.txt` lists GitHub usernames to skip, one per line:

```text
dependabot[bot]
renovate[bot]
```

`check_for` is **required**. Set it to the contribution checks you want to run. Supported values:

- `commit_sign_off` — all commits must include a Signed-off-by trailer
- `commit_signature` — all commits must be GPG or SSH signed
- `issue_assignee` — linked issue assignee must match the PR author (resolves the issue the same way as `issue_reference`)
- `issue_reference` — PR must reference a corresponding issue via GitHub linking or a closing reference in the PR description. When GitHub closing-link lookup fails (API error), the action does not fall back to parsing the PR description.
- `target_branch` — PR must target one of the branches listed in `target_branches` (also requires `target_branches`)

Set `close_on` to close the PR when specific checks fail. Supported values:

- `commit_sign_off` — missing or mismatched Signed-off-by trailers
- `commit_signature` — one or more commits are unsigned
- `issue_assignee` — referenced issue has no assignee, or assignee does not match the PR author
- `issue_reference` — no corresponding issue found via linking or PR description reference
- `target_branch` — PR targets a disallowed branch

Other validation failures only receive a comment unless listed in `close_on`.

Customize failure comments with `error_{check_name}` inputs (for example `error_issue_reference`, `error_commit_sign_off`). Each input maps to the same name used in `check_for` and `close_on`.

### Check execution

Enabled checks run in a fixed order: issue-related rules (branch, issue resolution, assignee), then commit signature, then sign-off. Within issue validation, the action stops at the first failure (for example, a bad target branch is reported before issue resolution runs). Each check class returns one result; multiple independent checks (such as `commit_signature` and `commit_sign_off`) can fail in the same run.

When GitHub closing-link lookup fails with an API error, the action does not fall back to parsing the PR description. That path is covered by unit tests in `tests/test_issue_check.py` (not integration tests, because real GitHub API errors cannot be triggered reliably in CI).

## Development

```bash
make install-dev
make test
```

Integration tests: [.github/scripts/integration/README.md](.github/scripts/integration/README.md)

## Releasing

Each git tag pins a matching immutable Docker image tag in `action.yml`. Consumers on `@v0.1.3` always get the `v0.1.3` image, even after a later release ships.

1. Update the Docker image tag in `action.yml` to the version you are releasing:

   ```yaml
   image: docker://ghcr.io/arkid15r/check-contribution-action/check-contribution-action:v0.1.3
   ```

2. Commit, push to `main`, then tag and push:

   ```bash
   git tag -a v0.1.3 -m "Release v0.1.3"
   git push origin v0.1.3
   ```

The [Release workflow](.github/workflows/release.yml) runs tests, verifies `action.yml` matches the git tag, publishes multi-arch Docker images (`linux/amd64`, `linux/arm64`) as `v0.1.3` (and a moving `v0` major alias on GHCR), and creates a GitHub Release.

Pin `@v0.1.3` for an immutable release. Use a moving git tag such as `@v0` only if you retag it on each minor release and update `action.yml` to point at the latest `v0.x.x` image.

## License

MIT
