# Headless, mostly stateless agent sessions

Status: proposal, not implemented. Drafted by @rev on 2026-09-20 from a terminal
discussion with Jonathan. Revised the same day after @imp's review (relayed by Jonathan);
the accepted corrections are folded in below and listed under "Review record".

## Problem

Vibeguild agents are currently hosted as long-lived interactive Claude Code or Codex
sessions that idle inside a watch loop for hours. On a 16 GB laptop this fails in two ways:

- Claude Code kills background tasks when the machine is low on memory and the session has
  been idle for about 30 minutes. The Vibeguild watcher is idle by design, so it is the
  first casualty. The reaper has an off switch but Jonathan wants it kept on.
- Codex prompts for approval on nearly every step. The Vibeguild client talks to the
  coordinator over HTTP on 127.0.0.1, and the Codex workspace-write sandbox denies network
  by default, so every client call is an approval request.

Measured on 2026-09-20: two idle Claude sessions held 0.65 GB together, one Codex session
0.29 GB, while the machine sat at 83% used with a commit charge of 28.9 GB. The agents are
a small slice of the pressure, but they are the slice that never goes away.

## Goal

Run each agent as a short-lived headless process that starts when there is something to do
and exits when the room goes quiet. Idle cost becomes one small driver process per machine.
Peak cost becomes one model host process per active agent. Nothing waits inside a model host
for longer than a few minutes, so the reaper has nothing to kill.

Non-goals: changing the room protocol, the template system, or how Jonathan commits.
Roles remain behavioral defaults expressed in templates, never enforced permissions. A
future allowlist must be possible without restructuring.

Two limits to be honest about. Exiting a process releases its memory; starting a fresh
conversation limits accumulated context; resuming a large transcript brings much of that
memory back for the life of the run, which is why host sessions roll at task boundaries and
on a size threshold. And this plan reduces the agents' share of memory; it does not find or
fix the cause of the system-wide pressure on the laptop, which was mostly other software.

## Terms

The models are already stateless. Every call resends the full transcript, and the provider
keeps nothing between calls except a time-limited prompt cache. What an interactive session
holds is the transcript file on disk, the process's in-memory copy of it plus all tool
results, and the ability to wait. "Headless" below means no terminal attached. "Stateless"
means deliberately discarding the transcript at a task boundary so the process never grows.
Neither changes how the models behave; resuming a transcript from a new process is the same
API call the interactive session would have made.

- **Batch**: what `inbox` returns today. Unread events since the agent's cursor (room
  messages, task changes, changed shared context) plus current controls. Not a re-read of
  rooms or coordinator files.
- **Run**: one host process launched by the driver for one agent. It handles one or more
  batches and exits.
- **Host session**: the Claude Code or Codex transcript that a run resumes or creates.
  Distinct from the Vibeguild session UUID, which the driver holds for the agent's whole life.
- **Driver**: a small Python process that waits on the coordinator and launches runs.

## Architecture

### Driver

New module `vibeguild/driver.py` exposed as `vibeguild drive --project <folder> --agent <UUID>`.
One driver per agent, or one driver hosting several agents sequentially. It:

1. Resumes the Vibeguild identity once (`resume`, or `--takeover` after confirming the old
   session stopped) and holds the session credential in the coordinator home.
2. Waits with `/api/watch` in a loop. Each watch call is a heartbeat, so the UI keeps
   showing the agent as present with `waiting` status.
3. On `changed:true`, or on a pause being cleared, launches one run for the agent with the
   configured host command and passes: coordinator home, project folder, agent UUID,
   Vibeguild session UUID, the host session to resume (if any), and a lifetime budget.
4. Streams the run's JSON events to a log file under `.local/runs/<agent>/<timestamp>.jsonl`.
5. On run exit, reads the run outcome (see below). `continue_work` schedules another run
   immediately, without waiting for a new event. `wait_for_input` returns to watching.
   `completed` rolls the host session and returns to watching. `paused` returns to watching
   controls only. A run that ends without a recognizable outcome is treated as a crash.
6. Honors global, agent, and budget pause by not launching runs. Sets presence `paused`.
7. On shutdown sets presence `disconnected` with a reason and terminates any child run.

The driver uses the agent's own identity for watch and presence. It never sends messages,
votes, or edits. It is a host, not a participant.

Process ownership, fixed before the prototype:

- One driver per agent, enforced with a lock file in the coordinator home keyed by agent
  UUID. A second driver for the same agent exits with an error.
- One active run per agent. The driver stops watching while a run is alive and hands the
  watch to the run; it resumes watching only after the run's process has exited. Watch is
  never held by two owners.
- On lifetime timeout or driver shutdown the driver terminates the run's whole process
  tree, not just the top process, so MCP servers, subagents, and stray shells cannot
  outlive it and recreate the memory problem.
- A machine-wide concurrency limit (proposed default 1, configurable) bounds how many runs
  are alive at once across all drivers, so peak memory is one host process per slot.
  Drivers queue behind the limit rather than launching.

### Run

Inside a run the agent executes the loop the skill already describes, with one change at the
end: instead of watching indefinitely it watches within a grace window.

1. Bootstrap if the host session is fresh: read master memory and recovery brief, then
   `inbox --bootstrap`. Otherwise `inbox`.
2. Consume the batch, act, ack, checkpoint. Exactly as today.
3. Watch in 30-second calls for up to the grace window (proposed default 3 minutes,
   configurable). A new batch inside the window is handled by the same run, so a live
   exchange stays fast and keeps the prompt cache warm.
4. When the window passes with no change, or the lifetime budget (proposed default 20
   minutes) is reached, write a final checkpoint, report an outcome, and exit.

The outcome is one of:

- `continue_work`: the agent has runnable work left on its claimed task and stopped only
  because the budget ran out. The driver relaunches at once.
- `wait_for_input`: nothing to do until someone else acts (review posted, question asked,
  handoff made). The driver watches.
- `completed`: the current task is closed and the transcript can be discarded.
- `paused`: a pause flag was seen; the agent checkpointed and stopped.

Without `continue_work`, unfinished work would stall after the budget with no new event to
wake it. The grace window is why this is "mostly" stateless. A chatty exchange lives in one
process. A quiet room costs nothing.

### Host session policy

Per task, not per batch and not forever:

- Resume the same host session while the agent's current task is open.
- Roll to a fresh host session when the task reaches `done` or `dropped`, or when the
  transcript exceeds a size threshold, or when the agent's exit record asks for it.
- Before a roll the agent must have written a checkpoint. The driver refuses to roll on a
  run that exited without one and instead resumes the old session once more.

A roll is a host-side event only. The Vibeguild session UUID does not change. The next run
performs the existing "same live session" recovery: `call context_reset`, then
`inbox --bootstrap`.

### Run outcome and clean-exit proof

The driver learns two things from the host's structured output stream, not from files the
agent writes:

- The host session identifier, captured at run start. Claude Code emits it in the first
  `system`/`init` event of `--output-format stream-json`; Codex emits `thread.started` in
  `codex exec --json`. The driver records it against this run before the model does any work.
- A final result event tied to this run: Claude's terminal `result` event, Codex's
  completion or failure event. Its presence is the proof of a clean exit. A checkpoint alone
  is not proof, because a run can checkpoint, start another operation, and then crash.

The outcome word itself is carried in the run's last assistant message under an agreed
marker line (proposed `VG_RUN_OUTCOME: <word>`), read by the driver from the final result
event. The checkpoint payload gains one optional field, `run_outcome`, mirroring it for the
human-readable recovery brief; the driver does not rely on it.

If a run exits without a final result event, or with an unrecognized outcome, the driver
treats it as a crash, logs it, keeps the same host session, and applies a backoff (proposed
1, 2, 5 minutes, then stop and set presence `blocked` with a reason).

### Durable retries

The coordinator deduplicates mutations on `actor:request_id` (core.py:392). A retry of an
uncertain mutation must therefore reuse its original request ID; a fresh ID would make the
duplicate real. The skill already says so. What is missing for crash recovery is
persistence: before sending any mutation, the run appends the operation and its request ID
to a small journal in its agent directory (proposed `memory/../pending_ops.jsonl`, exact
location to fix in the skill). On the next run the agent replays that journal first: resend
each entry with the same ID, which either lands once or returns the cached result, then
clear the entry. Room posts, acks, task updates, and checkpoints are covered this way.

File edits and external commands are not idempotent through the coordinator and need their
own reconciliation: the agent inspects the worktree and the task record before repeating
them, as the skill already requires for handoffs.

### Launch policy

Each agent gets one small launch policy, stored in the driver's config (proposed
`.local/runtime/drivers/<agent>.json`), separate from the template:

```json
{
  "host": "claude",
  "command": ["claude", "-p", "--output-format", "stream-json", "--verbose"],
  "permissions": {"mode": "permissive"},
  "mcp": "none",
  "grace_seconds": 180,
  "lifetime_seconds": 1200
}
```

Headless and permission level are separate choices. Headless only means no terminal; it
does not require bypassing anything. The `permissions` object decides what the run may do,
and its host mappings are not equivalent, so each is named explicitly:

| Mode | Claude | Codex |
| --- | --- | --- |
| `permissive` (default now) | to decide: `--permission-mode bypassPermissions`, or the documented headless automatic-review option if it fits (verify) | `-a never -s workspace-write` plus `-c 'sandbox_workspace_write.network_access=true'` so the client reaches 127.0.0.1; never `--dangerously-bypass-approvals-and-sandbox` |
| `allowlist` (future) | `--allowedTools` / `--disallowedTools` | sandbox and approval flags, per role |

Codex's `never` suppresses prompts but leaves the sandbox in force, so the network setting
is what fixes the current approval storm, and it is passed on the command line rather than
by editing the user's config. Claude's `bypassPermissions` removes all checks, which is a
larger grant than the Codex row; Jonathan has accepted that for now, but it is recorded as a
choice, not a consequence of going headless.

The allowlist seam is the same object with `allow` and `deny` lists filled in. Templates
never learn about permissions. Asking a reviewer to fix a quick procedure stays a room
message.

`mcp: "none"` means the run starts without the user's MCP servers, which a Vibeguild agent
does not need and which dominate startup time. Exact flags to verify: Claude
`--strict-mcp-config` with an empty `--mcp-config`; Codex a profile with no `mcp_servers`.

### Host commands, verified 2026-09-20

| Host | Version | Fresh | Resume | Notes |
| --- | --- | --- | --- | --- |
| Claude Code | 2.1.278 | `claude -p "<prompt>"` | `claude -p --resume <id> "<prompt>"` | Print-mode sessions are hidden from the picker but resumable by ID |
| Codex | 0.155.1 | `codex exec "<prompt>"` | `codex exec resume <SESSION_ID> [PROMPT]` (command support verified by @imp; a real resume cycle still to test) | `--full-auto` no longer listed; use `-a never -s workspace-write` or `--approve-for-me` |

Trivial headless turn including process start, MCP connection, model round trip and exit:
Claude 7.4 s, Codex 6.1 s. Startup is a few seconds of that. Negligible against a review
that runs the test suite; noticeable in a one-line exchange, which the grace window absorbs.

## Changes by component

### Skill (`vibeguild/skills/vibeguild`)

- `SKILL.md`: add a "hosted mode" paragraph to the participation contract. When the run
  receives a lifetime budget it watches within the grace window and exits with a checkpoint
  instead of watching indefinitely. Exit is an honest session ending in this mode because
  the driver, not the model, owns the wait.
- `references/monitoring.md`: new section "Driver-hosted runs" beside foreground and
  host-notified background wait.
- `references/recovery.md`: note that a host-session roll is a same-live-session context
  reset, not a new Vibeguild session.
- Templates: unchanged.

### Coordinator (`vibeguild/core.py`, `server.py`, `cli.py`)

- Accept and store the optional `run_outcome` checkpoint field. No validation beyond type.
- Inactivity pause needs an explicit policy change. Watch calls refresh `last_seen` only;
  `watch_started` is set at register, resume, and pause-clear (core.py:561, 566), so a
  driver watching all day would still be paused after `agent_inactivity_minutes`
  (core.py:377). The pause exists to stop resident sessions idling at cost; a hosted agent
  idles for free. Proposed: a `hosted` flag on the agent, set by the driver at resume, that
  exempts it from the inactivity pause only. Human pause, global pause, and budget pause
  are unchanged and still honored by the driver. Covered by a test.
- Optional: a `hosted_by` marker in presence so the UI can label the agent as driver-hosted
  and show the last run time. Cosmetic, later.

### CLI

- `vibeguild drive` subcommand wrapping `driver.py`.
- `start.cmd` unchanged. The driver is started separately, one per agent, and can be
  stopped with Ctrl+C.

## What is lost, stated plainly

- Interactive permission prompts. Control moves from prompt to policy. Accepted; the
  policy is permissive for now.
- Typing into the agent's terminal. All human input goes through rooms, which is already
  the working practice.
- Live scrolling view of tool calls. Replaced by per-run JSON logs and the Vibeguild UI.
- Working knowledge on a host-session roll. Mitigated by rolling only at task boundaries
  and by the existing checkpoint discipline. Negative findings and withdrawn points must be
  written into the checkpoint or topic memory or they are gone.
- Prompt cache across quiet gaps. Not actually lost: both providers key the cache on the
  request prefix within the account, not on a process. Gaps longer than the cache TTL are
  cold in an interactive session too. The grace window keeps rapid exchanges warm.

## Risks and open questions

- Duplicate actions if a run dies between sending and acking. Covered by the durable retry
  journal above: same request ID on retry, persisted before the send. Remaining exposure is
  file edits and external commands, which need worktree and task inspection.
- Tools that need a human answer mid-turn (plan approval, clarifying questions) cannot be
  satisfied headless. The agent must post the question to the room and exit.
- Windows process management: killing a stuck run cleanly, and whether `claude -p` exits
  promptly after its final message when subagents are still running.
- A real `codex exec resume` cycle needs testing (command support is confirmed).
- Exact flags to start each host without MCP servers need verification.
- Whether Claude's documented headless automatic-review option is a workable `permissive`
  mapping instead of `bypassPermissions`.
- Whether print mode uses the same cache TTL as interactive. Behavior is correct either way.

## Phases

1. **Prototype: one Claude reviewer, one driver, one active run.** `driver.py` with the
   ownership rules above, structured-output capture of session ID and final result, the
   four run outcomes, durable retry journal, grace window, per-task resume, crash backoff.
   The skill changes the run depends on (hosted-mode paragraph, outcome marker, retry
   journal) ship in this phase, not later. Run @rev through it for a day. Tests in this
   phase: forced crash mid-mutation, each pause flag, and `continue_work` after a budget
   timeout, alongside the memory run. Success: no watcher kills, presence stays fresh, every
   batch acked exactly once, unfinished work resumes without a new event, idle agent below
   50 MB.
2. **Codex host.** Same driver, Codex launch policy, sandbox network flag, real resume
   cycle. Run @imp through it. Success: zero approval prompts during a normal implement
   cycle.
3. **Coordinator touches.** `hosted` flag and inactivity exemption with a test,
   `run_outcome` checkpoint field, optional `hosted_by` presence marker.
4. **Skill polish.** Monitoring and recovery reference sections, reinstall into both host
   skill folders.
5. **Launch-policy allowlist.** Only when Jonathan asks. Fill in the `allow`/`deny` mapping
   for one role and confirm nothing else moves.

## Acceptance

- A driver-hosted agent survives eight hours on the laptop with Chrome open and the reaper
  enabled, with no missed batches.
- Idle machine memory attributable to Vibeguild agents is the drivers only.
- A review handoff completes end to end through a driver-hosted reviewer with the same
  evidence quality as today: hashes, reproduced tests, labeled findings.
- Rolling a host session at task close loses no pending IDs and no checkpoint content.
- A run killed between a send and its ack produces exactly one message after recovery.
- A run that hits its budget with an open task is relaunched without any new room event.
- Existing tests pass unchanged; new tests cover the `hosted` exemption, the checkpoint
  field, and the retry journal replay.

## Review record

@imp reviewed the first draft on 2026-09-20 (relayed by Jonathan). Accepted and folded in:

1. Explicit run outcomes, with `continue_work` scheduling a relaunch. The draft would have
   stalled unfinished work after the budget.
2. Inactivity pause: the draft assumed watch calls refresh `watch_started`; they refresh
   `last_seen`. Verified against core.py. Replaced with the `hosted` exemption.
3. Retries reuse the original request ID and persist the operation before sending. The
   draft's "fresh request IDs" would have defeated the coordinator's deduplication.
4. Clean exit is proven by the host's final result event and the session ID is captured
   from the host's structured output, not from the checkpoint.
5. Process ownership: one driver, one run, watch handoff, process-tree cleanup,
   machine-wide concurrency limit.
6. Headless and permission level are separate choices with non-equivalent host mappings;
   the Codex network flag was already in the draft, the framing was not.

Also from that review: the plan reduces idle agent memory but does not fix the machine's
system-wide pressure; resuming a large transcript brings memory back for the run's life.
Both are now stated under Goal.
