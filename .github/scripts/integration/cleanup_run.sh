#!/usr/bin/env bash
# Remove leftover integration test artifacts for a workflow run.

set -euo pipefail

export GH_TOKEN="${GH_TOKEN:-${GITHUB_TOKEN:-}}"
if [[ -z "${GH_TOKEN}" ]]; then
  echo "[integration-cleanup] ERROR: GH_TOKEN or GITHUB_TOKEN is required" >&2
  exit 1
fi

RUN_ID="${1:?Usage: cleanup_run.sh <run-id>}"
INTEGRATION_LABEL="integration-test"
RUN_LABEL="integration-run-${RUN_ID}"
ARTIFACT_PREFIX="[integration-test-${RUN_ID}]"

log() {
  echo "[integration-cleanup] $*"
}

# Use gh api for listing so we do not rely on --json flags on gh list/search.
close_labeled_pull_requests() {
  local numbers
  numbers="$(
    gh api "repos/${GITHUB_REPOSITORY}/issues" \
      -f labels="${RUN_LABEL}" \
      -f state=all \
      -f per_page=100 \
      --jq '.[] | select(.pull_request != null) | .number' 2>/dev/null || true
  )"
  if [[ -z "${numbers}" ]]; then
    return
  fi
  while read -r number; do
    [[ -z "${number}" ]] && continue
    log "Closing PR #${number}"
    gh pr close "${number}" --delete-branch 2>/dev/null || \
      gh pr close "${number}" 2>/dev/null || true
  done <<<"${numbers}"
}

close_labeled_issues() {
  local numbers
  numbers="$(
    gh api "repos/${GITHUB_REPOSITORY}/issues" \
      -f labels="${RUN_LABEL}" \
      -f state=all \
      -f per_page=100 \
      --jq '.[] | select(.pull_request == null) | .number' 2>/dev/null || true
  )"
  if [[ -z "${numbers}" ]]; then
    return
  fi
  while read -r number; do
    [[ -z "${number}" ]] && continue
    log "Closing issue #${number}"
    gh issue close "${number}" 2>/dev/null || true
  done <<<"${numbers}"
}

delete_run_branches() {
  local branches
  branches="$(
    git ls-remote --heads origin "integration-test/${RUN_ID}/*" \
      | awk '{print $2}' \
      | sed 's|refs/heads/||' || true
  )"
  if [[ -z "${branches}" ]]; then
    return
  fi
  while read -r branch; do
    [[ -z "${branch}" ]] && continue
    log "Deleting branch ${branch}"
    git push origin --delete "${branch}" 2>/dev/null || true
  done <<<"${branches}"
}

close_prefixed_pull_requests_without_labels() {
  local numbers
  numbers="$(
    gh api "search/issues" \
      -f q="${ARTIFACT_PREFIX} in:title repo:${GITHUB_REPOSITORY} is:pr" \
      --jq '.items[].number' 2>/dev/null || true
  )"
  if [[ -z "${numbers}" ]]; then
    return
  fi
  while read -r number; do
    [[ -z "${number}" ]] && continue
    log "Closing prefixed PR #${number}"
    gh pr close "${number}" --delete-branch 2>/dev/null || \
      gh pr close "${number}" 2>/dev/null || true
  done <<<"${numbers}"
}

close_prefixed_issues_without_labels() {
  local numbers
  numbers="$(
    gh api "search/issues" \
      -f q="${ARTIFACT_PREFIX} in:title repo:${GITHUB_REPOSITORY} is:issue" \
      --jq '.items[].number' 2>/dev/null || true
  )"
  if [[ -z "${numbers}" ]]; then
    return
  fi
  while read -r number; do
    [[ -z "${number}" ]] && continue
    log "Closing prefixed issue #${number}"
    gh issue close "${number}" 2>/dev/null || true
  done <<<"${numbers}"
}

delete_integration_run_label() {
  gh label delete "${RUN_LABEL}" --yes 2>/dev/null || true
}

main() {
  close_labeled_pull_requests
  close_labeled_issues
  delete_run_branches
  close_prefixed_pull_requests_without_labels
  close_prefixed_issues_without_labels
  delete_integration_run_label
  log "cleanup complete for run ${RUN_ID}"
}

main "$@"
