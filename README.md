# Check Contribution Action

GitHub Action for validating contribution requirements: issue linkage, commit signatures (GPG/SSH), and DCO sign-off trailers.

All checks are **disabled by default** — enable only what your repository needs.

## Usage

```yaml
name: Check Contribution
on:
  pull_request:
    types:
      - opened
      - synchronize
      - reopened
      - edited

jobs:
  check-contribution:
    if: github.event.pull_request.head.repo.full_name == github.repository
    runs-on: ubuntu-latest
    permissions:
      contents: read
      issues: read
      pull-requests: write
    steps:
      - uses: actions/checkout@v6
        with:
          fetch-depth: 0
      - uses: arkid15r/check-contribution-action@v1
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          check_commit_signature: 'true'
          check_sign_off: 'true'
```

## Development

```bash
make install-dev
make test
```

See [design/check-contribution-action.md](design/check-contribution-action.md) for architecture and implementation phases.

## License

MIT
