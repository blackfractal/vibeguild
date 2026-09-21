# Vibeguild team benchmarking

Status: proposed experiment and implementation plan, not an executed benchmark.
Requested by Jonathan on 2026-09-20. Source discussion: `agent_scratch` message
`44a70573-15e7-4f11-9d57-a226c2e9a8c9`; request to save and expand provider coverage:
`36de7203-0be1-4396-8bd7-1bec1f7849ba` and `5be6eddb-5862-43ad-988b-ba8155aef584`.

## Questions to answer

Determine which arrangement delivers accepted software with the best quality, cost,
elapsed time, and human effort for a defined set of tasks:

- One Claude session or one Codex session, without Vibeguild.
- Native host subagents or teams, without Vibeguild.
- One Claude and one Codex agent coordinating through Vibeguild.
- Four or ten Vibeguild agents, with deliberately assigned responsibilities.
- Claude implementing with Codex reviewing, versus the reverse and same-provider pairs.
- Teams incorporating Grok, Gemini, DeepSeek, or Qwen, where the chosen runtime passes
  the capability checks below.

The result should be a measured tradeoff, not an assumption that more agents are better.
Ten agents might improve quality or time while increasing tokens and cost. Findings
apply to the tasks, model versions, hosts, and budgets actually tested; they cannot prove
a universally optimal team size.

## One terminal can host several contexts

A terminal is an interface. It need not represent one model context. Codex supports
delegated agent threads and parent summaries. Claude Code supports subagents with their
own context windows, and experimental agent teams whose sessions can be viewed through
one terminal or separate panes. Shared display does not require merging all intermediate
work into the parent's context. Summaries and shared coordination messages still consume
context. [OpenAI Docs: subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents),
[Claude subagents](https://code.claude.com/docs/en/sub-agents),
[Claude agent teams](https://code.claude.com/docs/en/agent-teams).

For a persistent Vibeguild team, map one real provider thread/session to one VG agent UUID
and its current session. Each worker must load the skill, resume or join its own identity,
read controls and its selected template, consume and acknowledge its own inbox, checkpoint,
and disconnect when it stops. A parent acting out several handles is not several independent
workers and must not be scored as such. Separate contexts can still produce correlated
mistakes because workers share models, instructions, and messages.

Vibeguild currently provides coordination and durable identities, not an automatic host
launcher or a tested persistent multi-child runner. Creating a profile does not launch a
model. Five Claude workers plus five Codex workers is a target architecture, conditional
on host capacity and reliable lifecycle management. The Codex session used for this
discussion exposes four concurrent agents total, including its parent; it cannot host
five concurrent workers as configured. Other sessions must report their actual limits.

Claude teams currently have lifecycle constraints, including one team per session, no
nested teams, and no restoration of in-process teammates through `/resume`. Test restart
and recovery explicitly instead of assuming the terminal restores every worker.
[Claude team limitations](https://code.claude.com/docs/en/agent-teams#limitations).

## Keep provider, model, host, and hardware separate

Provider names alone are not reproducible experimental conditions. For every worker record:

| Dimension | Required record |
| --- | --- |
| Provider/service | OpenAI, Anthropic, xAI, Google, hosted open-weight endpoint, or local service |
| Exact model | Version/snapshot identifier, reasoning setting, context/output limits; any automatic routing |
| Host | Codex, Claude Code, Gemini CLI, Antigravity, or a specified custom CLI/API harness, with version |
| Agent setup | Implementer/reviewer/other role, template ID and digest, initial context, available tools and permissions |
| Serving environment | Remote region/endpoint where known; for local inference, hardware, RAM/VRAM, engine, quantization and concurrency |
| Usage semantics | Input/output/cache categories, metering source, pricing date or local cost assumptions |

Candidate coverage, subject to validation:

| Family | Proposed route to test | Admission condition |
| --- | --- | --- |
| OpenAI / Codex | Codex host with a pinned supported model | Separate worker contexts, tool access, continuation and usage accounting verified |
| Anthropic / Claude | Claude Code with a pinned supported model | Same checks; distinguish subagents from persistent teammates |
| xAI / Grok | A suitable CLI or API harness | Verify the actual model supports the required coding tools and the runner can host VG workers |
| Google / Gemini | Gemini CLI or an Antigravity-hosted workflow | Record the host and selected model separately; do not treat the product label as an exact model |
| DeepSeek | A selected hosted endpoint or compatible local/open-weight deployment | Pin exact model and, where applicable, weight revision, license, serving engine and quantization |
| Qwen | A selected hosted endpoint or compatible local/open-weight deployment | Same admission checks; do not assume all models in the family have the same capabilities |

This table proposes candidates; it does not claim that every named route is installed,
available to the account, or integrated with Vibeguild. Validate current official runtime
documentation before adding each route. Do not download models or start paid experiments
as a consequence of this plan alone.

When comparing providers in their native hosts, describe the result as a comparison of
complete systems: model plus host plus tools. A separate common-harness experiment can
better isolate model differences, but should not be presented as native Codex versus
native Claude Code. Record any compromises required to give models equivalent tools.

## Provider and role assignment matrix

Start with two-worker teams so provider direction can be studied without changing team size:

| Condition | Implementer | Reviewer | What it tests |
| --- | --- | --- | --- |
| CC | Claude | Claude | Same-provider baseline |
| OO | Codex | Codex | Same-provider baseline |
| CO | Claude | Codex | Cross-provider review of Claude implementation |
| OC | Codex | Claude | Reverse direction |

Keep the task, roles, review rubric, revision budget, template text/digests, and reviewer
visibility identical across these four conditions. Reviewers should receive the same brief,
acceptance criteria, diff, and test evidence, rather than one condition inheriting the
implementer's entire internal conversation. Preserve each implementer's first submission
before review, then its revised result: this separates initial implementation quality from
defects caught, false alarms, and gains attributable to review.

The worker reviewer is part of the treatment, not the final judge. Final evaluation uses
held-out tests and independent review with provider/team labels hidden where practical.
Measure valid defects found, reviewer false positives, harmful suggested changes, and
remaining defects, in addition to whether the task eventually passes.

After the two-provider pilot, extend to ordered pairs from the admitted candidate pool.
With six selected systems, a complete implementer-by-reviewer matrix has 36 pairs including
same-system pairs. Do not run this full matrix immediately: screen against a fixed baseline,
then test promising pairs and the reversed assignments on fresh held-out tasks. Screening
and confirmation must use different tasks to avoid selecting winners on noise.

For larger teams, define the topology before running. Example four-worker topology:
implementer, independent reviewer, test/validation worker, and requirements/design worker.
A ten-worker condition needs real bounded work partitions, not ten copies of a general
prompt. Record which workers write code, review, test, or coordinate. If a parent performs
model work, report it as an additional agent and include its tokens, cost, and time.

## Separate the effects we want to measure

Use staged comparisons rather than changing every factor at once:

1. **Provider direction:** the CC/OO/CO/OC matrix with the same two-role workflow.
2. **Coordination:** the same worker models and roles with VG versus an explicit non-VG
   workflow. Define how non-VG workers exchange patches and messages; record that overhead.
3. **Templates:** the same VG team with generic instructions versus specialized template
   bodies, pinned by digest. If VG requires a General template, use that as the control;
   do not depend on a future ability to select None.
4. **Team size/topology:** one, two, four and ten workers where capacity allows. Report
   role composition along with count; a larger team changes responsibility allocation too.
5. **Provider diversity:** compare homogeneous and mixed teams under matched roles and
   aggregate resource budgets.

These are hypotheses, not predefined winners. Add interactions only after the smaller
experiments show enough signal to justify their expense. An all-to-all shared chat can
multiply delivered context as the team grows, so hold routing policy constant or make it
an explicitly separate variable.

## Execution and isolation

Begin with a two-child feasibility trial before a quality benchmark. Demonstrate distinct
contexts and VG identities, child startup and shutdown, pause/resume, parent interruption,
worker failure, stable identity recovery, actual notification/continuation, and usable
provider usage records. A live heartbeat process is not proof that a model will resume work.

Each benchmark trial starts at the same clean repository revision in its own code checkout
and coordination project. No shared memory, conversation history, solution files, or edited
working tree between conditions. Give every condition the same initial brief and permitted
reference material. Keep evaluator-only tests inaccessible to workers.

Use isolated worktrees and explicit file/task ownership within a team. The current VG
shared-directory policy allows one editing task at a time; using it for a ten-agent speed
comparison would serialize writers. Either use separate worktrees with recorded integration
cost or make that serialization an intentional reported condition. Include merge conflicts,
integration effort, review rounds and cleanup in the end-to-end result.

Record API throttling, retries, queue delays, local contention and human approval waits.
Choose whether trials run sequentially or on matched independent capacity before starting.
Do not compare a saturated local machine against unconstrained remote workers and attribute
all of the difference to agent count. For local inference, report warm/cold model loading
separately and state whether setup time is included.

## Tasks, budgets, and evaluation

Use a task set spanning bug fixes, backend changes, UI behavior, integration, and refactoring,
with difficulty and scope documented in advance. Each task needs explicit acceptance criteria,
independent correctness checks, and a review rubric for maintainability and usability where
tests alone are insufficient. A solution that fails essential acceptance criteria is not
considered successful because it is fast or eloquent.

Run two complementary tracks:

- **Fixed aggregate budget:** same total team resource allowance and deadline; compare
  quality and success rate. More workers divide that allowance rather than receiving a
  fresh full budget each.
- **Fixed acceptance target:** measure elapsed time and cost to acceptance, with a hard
  maximum and clearly reported failures/timeouts. Include unsuccessful runs in reporting.

Cross-provider tokenizers and cache pricing differ, so equal token counts are not equivalent
compute or cost. Report provider token categories alongside money, elapsed time and quality.
For local models report measured runtime/resources and explicit cost assumptions; a zero
API bill is not zero resource consumption. Subscription pricing may not expose a meaningful
per-run marginal bill, so mark estimates and quota use separately.

Use paired repeated trials on the same tasks, randomize condition order, and preserve every
result. Start with a small feasibility pilot to estimate variance and runtime; choose the
confirmatory sample size from the effect worth detecting, observed variance, and available
budget. Freeze the plan before confirmation. Report paired differences, uncertainty intervals,
failure rates, and task-level results, not just the best run. Avoid claiming significance or
general superiority from one feature or a handful of successful demonstrations.

## Measurement records

Minimum run record:

```text
run_id, task_id, trial_index, condition_id, randomized_order
starting_commit, final_commit_or_patch_hash, VG_version
worker_ids, parent_orchestrator_id, roles, model_versions, host_versions
template_ids_and_hashes, initial_context_policy, tool_and_permission_policy
checkout_isolation, concurrency_limit, hardware_or_endpoint, execution_topology
start/end timestamps, active_execution_time, queue/retry/approval_time
per-worker and parent provider input/output/cache usage, metering coverage
cost_or_estimation_method, pricing_date, local_resource_measurements
acceptance_results, independent_quality_scores, defects, review_false_positives
review_rounds, integration_conflicts, human_minutes, failures_and_timeouts
artifact_paths, evaluation_version, stopping_reason
```

VG supplied-text estimates are not whole-run token usage. Its present usage reporting does
not automatically collect every provider call. Obtain complete, non-overlapping records for
workers and orchestrators; document whether cache categories are included in input totals
before summing. Never add VG delivered-text estimates to provider input tokens. Mark missing
usage as missing, not zero; exclude unsupported savings claims when coverage is incomplete.

Separate quality, elapsed time, provider tokens/cost, human effort and reliability in the
report. Show configurations that improve one metric at the expense of another. Useful
derived measures include cost per accepted task and defects caught per review cost, with
their denominators and failure handling stated explicitly.

## Proposed phases and deliverables

1. **Feasibility:** two actual hosted children with separate VG identities; lifecycle and
   metering report. Establish which candidate hosts can participate at all.
2. **Provider-role pilot:** CC/OO/CO/OC on matched tasks, with frozen first-pass and revised
   artifacts. Estimate variability and identify measurement gaps.
3. **Controlled comparison:** solo and native-team baselines, VG comparison, template
   ablation, then four-worker teams. Confirm selected conditions on held-out tasks.
4. **Expansion:** additional admitted providers and ten-worker trials only after orchestration,
   metering, capacity and budget support a meaningful comparison.
5. **Report:** reproducible manifests, evaluation results, cost/time/quality tradeoffs,
   uncertainty, and a recommendation scoped to the observed task types.

Implementing a runner, integrating another provider, selecting paid/model-download budgets,
and launching benchmark trials are future work. This document alone starts none of them.
