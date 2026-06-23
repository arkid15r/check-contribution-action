# Check Contribution Action

GitHub Action for validating contribution requirements: issue linkage, commit signatures (GPG/SSH), and DCO sign-off trailers.

All checks are **disabled by default** — enable only what your repository needs.

Sign-off and signature checks load **PR commits from the GitHub API** (`pulls/{number}/commits`). No `actions/checkout` step is required unless you use `skip_users_file_path`.

Fork PRs should be excluded in the workflow job `if` (see usage example below).

## Usage

```yaml
name: Check Contribution
on:
  pull_request:
    types:
      - edited
      - opened
      - reopened
      - synchronize

jobs:
  check-contribution:
    if: github.event.pull_request.head.repo.fork == false
    runs-on: ubuntu-latest
    permissions:
      contents: read
      issues: read
      pull-requests: write
    steps:
      - uses: arkid15r/check-contribution-action@v0.1.1
        with:
          check_commit_signature: 'true'
          check_sign_off: 'true'
          require_assignee: 'true'
          close_pr_on_assignee_mismatch: 'true'
          github_token: ${{ secrets.GITHUB_TOKEN }}
```

Set `close_pr_on_assignee_mismatch: 'true'` to close the PR when assignee validation fails (the linked issue has no assignee, or the assignee does not match the PR author). Other validation failures only receive a comment.

## Development

```bash
make install-dev
make test
```

Integration tests: [.github/scripts/integration/README.md](.github/scripts/integration/README.md)

## Releasing

Each git tag pins a matching immutable Docker image tag in `action.yml`. Consumers on `@v0.1.1` always get the `v0.1.1` image, even after `v0.2.0` ships.

1. Update the Docker image tag in `action.yml` to the version you are releasing:

   ```yaml
   image: docker://ghcr.io/arkid15r/check-contribution-action/check-contribution-action:v0.1.1
   ```

2. Commit, push to `main`, then tag and push:

   ```bash
   git tag -a v0.1.1 -m "Release v0.1.1"
   git push origin v0.1.1
   ```

The [Release workflow](.github/workflows/release.yml) runs tests, verifies `action.yml` matches the git tag, publishes the Docker image as `v0.1.1` (and a moving `v0` major alias on GHCR), and creates a GitHub Release.

Pin `@v0.1.1` for an immutable release. Use a moving git tag such as `@v0` only if you retag it on each minor release and update `action.yml` to point at the latest `v0.x.x` image.

## License

MIT
