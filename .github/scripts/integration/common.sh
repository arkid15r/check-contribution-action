#!/usr/bin/env bash
# Shared helpers for GitHub integration tests.

set -euo pipefail

# gh reads GH_TOKEN; GitHub Actions sets GITHUB_TOKEN automatically.
export GH_TOKEN="${GH_TOKEN:-${GITHUB_TOKEN:-}}"
if [[ -z "${GH_TOKEN}" ]]; then
  echo "[integration:${CASE_ID:-?}] ERROR: GH_TOKEN or GITHUB_TOKEN is required" >&2
  exit 1
fi

INTEGRATION_LABEL="integration-test"
RUN_ID="${GITHUB_RUN_ID:?GITHUB_RUN_ID is required}"
CASE_ID="${CASE_ID:?CASE_ID is required}"
ARTIFACT_PREFIX="[integration-test-${RUN_ID}]"
CASE_PREFIX="${ARTIFACT_PREFIX} ${CASE_ID}"
BRANCH_PREFIX="integration-test/${RUN_ID}/${CASE_ID}"
INTEGRATION_DIR="${GITHUB_WORKSPACE}/.integration"
EVENT_PATH="${INTEGRATION_DIR}/event.json"
IMAGE_NAME="check-contribution-action:integration-test"
BOT_NAME="github-actions[bot]"
BOT_EMAIL="41898282+github-actions[bot]@users.noreply.github.com"

PR_NUMBER=""
ISSUE_NUMBER=""
HEAD_BRANCH=""
PR_BASE=""
CREATED_BRANCHES=()

log() {
  echo "[integration:${CASE_ID}] $*"
}

fail() {
  echo "[integration:${CASE_ID}] ERROR: $*" >&2
  exit 1
}

setup_run() {
  mkdir -p "${INTEGRATION_DIR}"
  gh label create "${INTEGRATION_LABEL}" --color "BFD4F2" \
    --description "Temporary integration test artifact" 2>/dev/null || true
  gh label create "integration-run-${RUN_ID}" --color "F9D0C4" \
    --description "Integration test run ${RUN_ID}" 2>/dev/null || true

  git config user.name "${BOT_NAME}"
  git config user.email "${BOT_EMAIL}"

  if [[ "${INTEGRATION_SKIP_DOCKER_BUILD:-}" == "true" ]]; then
    if ! docker image inspect "${IMAGE_NAME}" >/dev/null 2>&1; then
      fail "pre-built image ${IMAGE_NAME} is not available"
    fi
    log "Using pre-built Docker image ${IMAGE_NAME}"
  else
    log "Building action Docker image"
    docker build -t "${IMAGE_NAME}" "${GITHUB_WORKSPACE}" >/dev/null
  fi
}

sign_off_trailer() {
  printf 'Signed-off-by: %s <%s>' "${BOT_NAME}" "${BOT_EMAIL}"
}

track_branch() {
  CREATED_BRANCHES+=("$1")
}

# gh issue/pr create print a resource URL on stdout; take the number from the path.
resource_number_from_url() {
  echo "${1##*/}"
}

create_issue() {
  local title="$1"
  local body="${2:-Integration test issue for ${CASE_ID}.}"
  local issue_url

  issue_url="$(
    gh issue create \
      --title "${CASE_PREFIX} issue: ${title}" \
      --body "${body}" \
      --label "${INTEGRATION_LABEL}" \
      --label "integration-run-${RUN_ID}"
  )"
  ISSUE_NUMBER="$(resource_number_from_url "${issue_url}")"
  log "Created issue #${ISSUE_NUMBER}"
}

wait_for_closing_issue_link() {
  local owner="${GITHUB_REPOSITORY%%/*}"
  local repo="${GITHUB_REPOSITORY##*/}"
  local max_attempts=30
  local attempt=0
  local count

  log "Waiting for closing issue link on PR #${PR_NUMBER}"
  while [[ $attempt -lt $max_attempts ]]; do
    count="$(
      gh api graphql \
        -f query='query($owner: String!, $repo: String!, $pullRequestNumber: Int!) {
          repository(owner: $owner, name: $repo) {
            pullRequest(number: $pullRequestNumber) {
              closingIssuesReferences(first: 1) {
                totalCount
              }
            }
          }
        }' \
        -f owner="${owner}" \
        -f repo="${repo}" \
        -F pullRequestNumber="${PR_NUMBER}" \
        --jq '.data.repository.pullRequest.closingIssuesReferences.totalCount' \
        2>/dev/null || echo 0
    )"

    if [[ "${count}" -gt 0 ]]; then
      log "PR #${PR_NUMBER} is linked to ${count} closing issue(s)"
      return 0
    fi

    attempt=$((attempt + 1))
    sleep 2
  done

  fail "timed out waiting for closing issue link on PR #${PR_NUMBER}"
}

create_branch_with_commit() {
  local branch_name="$1"
  local commit_message="$2"

  git fetch origin main
  git checkout -B "${branch_name}" "origin/main"
  git commit --allow-empty -m "${commit_message}"
  git push -u origin "${branch_name}"
  track_branch "${branch_name}"
  log "Created branch ${branch_name}"
}

create_pull_request() {
  local title="$1"
  local body="$2"
  local base_branch="${3:-main}"
  local head_branch="$4"

  local pr_url
  pr_url="$(
    gh pr create \
      --base "${base_branch}" \
      --head "${head_branch}" \
      --title "${CASE_PREFIX} pr: ${title}" \
      --body "${body}" \
      --label "${INTEGRATION_LABEL}" \
      --label "integration-run-${RUN_ID}"
  )"
  PR_NUMBER="$(resource_number_from_url "${pr_url}")"
  HEAD_BRANCH="${head_branch}"
  PR_BASE="${base_branch}"
  log "Created PR #${PR_NUMBER}"
}

prepare_git_workspace() {
  git fetch origin "${PR_BASE}" "${HEAD_BRANCH}"
  git checkout "${PR_BASE}"
}

build_event_payload() {
  prepare_git_workspace
  gh api "repos/${GITHUB_REPOSITORY}/pulls/${PR_NUMBER}" \
    --jq '{
      action: "synchronize",
      pull_request: .,
      repository: {full_name: "'"${GITHUB_REPOSITORY}"'"}
    }' >"${EVENT_PATH}"
  log "Wrote event payload to ${EVENT_PATH}"
}

run_action() {
  local expected_exit="$1"
  shift

  local -a docker_env=(
    -e "GITHUB_EVENT_PATH=/github/workspace/.integration/event.json"
    -e "GITHUB_WORKSPACE=/github/workspace"
    -e "INPUT_GITHUB_TOKEN=${GH_TOKEN}"
    -e "INPUT_VALIDATE_BOT_AUTHORS=true"
  )

  while [[ $# -gt 0 ]]; do
    local key="${1%%=*}"
    local value="${1#*=}"
    local env_key
    env_key="$(echo "${key}" | tr '[:lower:]' '[:upper:]')"
    docker_env+=(-e "INPUT_${env_key}=${value}")
    shift
  done

  set +e
  docker run --rm "${docker_env[@]}" \
    -v "${GITHUB_WORKSPACE}:/github/workspace" \
    "${IMAGE_NAME}"
  local actual_exit=$?
  set -e

  if [[ "${actual_exit}" -ne "${expected_exit}" ]]; then
    fail "expected exit code ${expected_exit}, got ${actual_exit}"
  fi
  log "Action exited with expected code ${expected_exit}"
}

cleanup_case_artifacts() {
  log "Cleaning up case artifacts"

  if [[ -n "${PR_NUMBER}" ]]; then
    gh pr close "${PR_NUMBER}" --delete-branch 2>/dev/null || \
      gh pr close "${PR_NUMBER}" 2>/dev/null || true
  fi

  if [[ -n "${ISSUE_NUMBER}" ]]; then
    gh issue close "${ISSUE_NUMBER}" 2>/dev/null || true
  fi

  local branch
  if [[ ${#CREATED_BRANCHES[@]} -gt 0 ]]; then
    for branch in "${CREATED_BRANCHES[@]}"; do
      git push origin --delete "${branch}" 2>/dev/null || true
    done
  fi
}
