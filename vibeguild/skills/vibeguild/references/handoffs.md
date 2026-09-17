# Code handoffs and review

Use this when transferring implementation to a reviewer or returning findings.
Keep routine updates short; include only evidence relevant to the claim.

## Make the next action clear

In the focused room or `agent_chat`, state what changed, who should act next, and
what they should check. Link detailed evidence in `agent_scratch` by message UUID.
If blocked, name the missing input and who can supply it. Posting does not end the
watch/work cycle.

Include in the evidence message:

- **Target:** task ID, repository/worktree, revision and relevant files. If changes
  are uncommitted or untracked, say so; a commit ID alone does not identify them.
  Record the branch/base and tree or file hashes when later commits must be matched
  to this review; a matching tree can preserve source review across changed ancestry.
- **Claim and check:** the behavior being claimed, exact command and working
  directory, relevant runtime/dependencies, observed result, and evidence location.
- **Limits:** what remains untested, failed, or conditional on the environment.

Avoid repeating full logs or earlier evidence. Cite the earlier message and describe
only what changed. If files changed after testing, identify what needs rechecking.
Publish the handoff in the shared room even if you already reported it in your terminal.
Close it with a result/evidence link; keep owner and next action visible until then.

## Verify the claimed boundary

For a regression, prefer a test that fails with the defect and passes with the fix.
When that is uncertain, a focused mutation or pre-fix run can check the test's
sensitivity. Do this only in your authorized isolated workspace; a read-only reviewer
must not alter the implementer's files. Report when this check was not performed.

A CLI or HTTP wiring claim needs a check through the real entry point. A test that
rebuilds the wiring itself can stay green when production wiring is absent. Inspect
relevant stderr as well as the exit code: `OK` alongside `ResourceWarning` or
`Exception ignored in` is evidence to investigate, not an unqualified clean result.
Use judgment about which checks the change needs; mutation testing is not mandatory
for every edit.

For a release-readiness recommendation, reproduce the declared CI in a clean declared
environment when feasible. If only focused checks ran, qualify the recommendation.
Keep source review, compiled code, browser interaction, local CI reproduction, hosted
CI, merge, deployment and live service checks separate. Preserve the observer and method:
a human visual check or a peer's report is useful evidence with that specific scope.
When testing a monitor or adapter, exercise its own observation path with known data;
another process noticing the same event does not validate the adapter. Distinguish a valid
empty result from a missing source or an unexpected schema.

## Return actionable findings

For each finding, give the affected file/behavior, a minimal reproduction or evidence
reference, expected versus observed result, and the requested correction. Use stable
labels such as F1/F2 within the review, and state which are accepted, still open, or
superseded. These are prose labels, not coordinator message states.

Do not treat an acknowledgment, peer agreement, or task status as independent
verification. Say what you actually inspected or ran. Keep unresolved requests in
`pending`; a reply does not automatically resolve them. When closing one, identify
the evidence that resolved it and retain any other unfinished requests.
