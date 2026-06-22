#!/usr/bin/env bash
# Run a single integration test case by ID.

set -euo pipefail

CASE_ID="${1:?Usage: run_case.sh <case-id>}"
export CASE_ID

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=.github/scripts/integration/common.sh
source "${SCRIPT_DIR}/common.sh"

trap cleanup_case_artifacts EXIT

setup_run

case "${CASE_ID}" in
  issue-linking-pass)
    create_issue "issue-linking-pass"
    create_branch_with_commit "${BRANCH_PREFIX}/head" "issue linking pass"
    create_pull_request \
      "issue-linking-pass" \
      "Closes #${ISSUE_NUMBER}" \
      "main" \
      "${BRANCH_PREFIX}/head"
    wait_for_closing_issue_link
    build_event_payload
    run_action 0 check_issue_linking=true
    ;;

  issue-linking-fail)
    create_branch_with_commit "${BRANCH_PREFIX}/head" "issue linking fail"
    create_pull_request \
      "issue-linking-fail" \
      "No linked issue for this integration test." \
      "main" \
      "${BRANCH_PREFIX}/head"
    build_event_payload
    run_action 1 check_issue_linking=true
    ;;

  issue-reference-pass)
    create_issue "issue-reference-pass"
    create_branch_with_commit "${BRANCH_PREFIX}/head" "issue reference pass"
    create_pull_request \
      "issue-reference-pass" \
      "Closes #${ISSUE_NUMBER}" \
      "main" \
      "${BRANCH_PREFIX}/head"
    build_event_payload
    run_action 0 check_issue_reference=true
    ;;

  issue-reference-fail)
    create_issue "issue-reference-fail-unused"
    create_branch_with_commit "${BRANCH_PREFIX}/head" "issue reference fail"
    create_pull_request \
      "issue-reference-fail" \
      "This PR mentions #${ISSUE_NUMBER} without a closing keyword." \
      "main" \
      "${BRANCH_PREFIX}/head"
    build_event_payload
    run_action 1 check_issue_reference=true
    ;;

  assignee-pass)
    create_issue "assignee-pass"
    create_branch_with_commit "${BRANCH_PREFIX}/head" "assignee pass"
    create_pull_request \
      "assignee-pass" \
      "Closes #${ISSUE_NUMBER}" \
      "main" \
      "${BRANCH_PREFIX}/head"
    wait_for_closing_issue_link
    assign_issue_to_pr_author
    build_event_payload
    run_action 0 check_issue_linking=true require_assignee=true
    ;;

  assignee-fail)
    create_issue "assignee-fail"
    create_branch_with_commit "${BRANCH_PREFIX}/head" "assignee fail"
    create_pull_request \
      "assignee-fail" \
      "Closes #${ISSUE_NUMBER}" \
      "main" \
      "${BRANCH_PREFIX}/head"
    wait_for_closing_issue_link
    build_event_payload
    run_action 1 check_issue_linking=true require_assignee=true
    ;;

  sign-off-pass)
    create_branch_with_commit "${BRANCH_PREFIX}/head" \
      "sign-off pass

$(sign_off_trailer)"
    create_pull_request \
      "sign-off-pass" \
      "Integration test for sign-off pass." \
      "main" \
      "${BRANCH_PREFIX}/head"
    build_event_payload
    run_action 0 check_sign_off=true
    ;;

  sign-off-fail)
    create_branch_with_commit "${BRANCH_PREFIX}/head" "sign-off fail without trailer"
    create_pull_request \
      "sign-off-fail" \
      "Integration test for sign-off fail." \
      "main" \
      "${BRANCH_PREFIX}/head"
    build_event_payload
    run_action 1 check_sign_off=true
    ;;

  signature-fail)
    create_branch_with_commit "${BRANCH_PREFIX}/head" "unsigned commit"
    create_pull_request \
      "signature-fail" \
      "Integration test for unsigned commit." \
      "main" \
      "${BRANCH_PREFIX}/head"
    build_event_payload
    run_action 1 check_commit_signature=true
    ;;

  target-branch-pass)
    create_branch_with_commit "${BRANCH_PREFIX}/head" "target branch pass"
    create_pull_request \
      "target-branch-pass" \
      "Integration test for allowed target branch." \
      "main" \
      "${BRANCH_PREFIX}/head"
    build_event_payload
    run_action 0 target_branches=$'release\n'
    ;;

  target-branch-fail)
    restricted_base="${BRANCH_PREFIX}/restricted-base"
    feature_branch="${BRANCH_PREFIX}/feature"

    git fetch origin main
    git checkout -B "${restricted_base}" "origin/main"
    git push -u origin "${restricted_base}"
    track_branch "${restricted_base}"

    git checkout -B "${feature_branch}" "${restricted_base}"
    git commit --allow-empty -m "target branch fail"
    git push -u origin "${feature_branch}"
    track_branch "${feature_branch}"

    create_pull_request \
      "target-branch-fail" \
      "Integration test for disallowed target branch." \
      "${restricted_base}" \
      "${feature_branch}"
    build_event_payload
    run_action 1 target_branches=$'release\n'
    ;;

  *)
    fail "unknown case id: ${CASE_ID}"
    ;;
esac

log "case passed"
