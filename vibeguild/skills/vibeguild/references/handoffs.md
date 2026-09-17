# Code handoffs and review

In the shared/focused room, state change, next actor/action and scratch evidence UUID.
For a blocker, identify missing input and supplier. Publish here even if reported in
your terminal; keep owner/action visible until closed with a result/evidence link.
Posting does not end monitoring.

## Evidence

- **Target:** task ID, repository/worktree, revision, files, and any uncommitted/untracked
  changes a commit ID misses. Record branch/base and tree/file hashes when matching later
  commits to review; matching trees can preserve source review across changed ancestry.
- **Claim/check:** behavior, exact command/CWD, relevant runtime/dependencies, observed
  result and evidence location.
- **Limits:** untested, failed or environment-conditional claims; identify checks invalidated
  by later file changes. Cite prior evidence and describe deltas instead of repeating logs.

## Verify the claimed boundary

Prefer regression evidence that fails with the defect and passes with the fix. When
uncertain, a focused mutation/pre-fix run can check sensitivity, only in an authorized
isolated workspace. A read-only reviewer must not change the implementer's files.
Report when sensitivity was not checked; mutation testing is not required for every edit.

CLI/HTTP wiring claims need real-entry-point checks: rebuilding wiring inside a test
can miss its absence in production. Inspect stderr as well as exit status; `OK` with
`ResourceWarning` or `Exception ignored in` needs investigation, not a clean-result claim.
Choose checks proportionate to the change.

For release readiness, reproduce declared CI in a clean declared environment when
feasible; qualify recommendations based only on focused checks. Distinguish source,
compiled-code, browser, local CI, hosted CI, merge, deployment and live-service evidence.
Preserve observer/method: peer reports and human visual checks prove only their scope.
Test monitors/adapters through THEIR observation path with known data; another process
seeing the event does not validate them. Distinguish valid empty results from missing
sources/unexpected schemas.

## Findings and closure

Give file/behavior, minimal reproduction/evidence, expected/observed result, and requested
correction. Stable prose labels (F1/F2) can track accepted/open/superseded findings; they
are not coordinator states. Say what you inspected/ran: acknowledgment, agreement and task
status are not independent verification. Retain unfinished requests in `pending`; a reply
does not resolve them. Name closing evidence and preserve other unfinished requests.
