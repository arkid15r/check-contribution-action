#!/usr/bin/env bash
# Remove leftover integration test artifacts for a workflow run.

set -euo pipefail

RUN_ID="${1:?Usage: cleanup_run.sh <run-id>}"
INTEGRATION_LABEL="integration-test"
RUN_LABEL="integration-run-${RUN_ID}"
ARTIFACT_PREFIX="[integration-test-${RUN_ID}]"

log() {
  echo "[integration-cleanup] $*"
}

close_labeled_pull_requests() {
  local numbers
  numbers="$(
    gh pr list \
      --state all \
      --label "${RUN_LABEL}" \
      --json number \
      --jq '.[].number' 2>/dev/null || true
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
    gh issue list \
      --state all \
      --label "${RUN_LABEL}" \
      --json number \
      --jq '.[].number' 2>/dev/null || true
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
    gh search prs "${ARTIFACT_PREFIX} in:title repo:${GITHUB_REPOSITORY}" \
      --json number \
      --jq '.[].number' 2>/dev/null || true
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
    gh search issues "${ARTIFACT_PREFIX} in:title repo:${GITHUB_REPOSITORY}" \
      --json number \
      --jq '.[].number' 2>/dev/null || true
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
