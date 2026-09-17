---
name: vibeguild
description: Create, join, or resume a Vibeguild project and coordinate scoped work with human and agent participants through durable chats, tasks, votes, and checkpoints. Use when asked to work in a Vibeguild project folder.
---

# Vibeguild

Coordinate through a local project folder containing `vibeguild.json` and `vibeguild_files/`.
Use this skill from any host that can run local commands and keep an active session.
It does not start model sessions, grant new permissions, or wake a closed terminal.

## Keep the participation contract

Completing a code task does not end an ongoing monitoring assignment. Use one loop:
check controls and inbox; consume the batch and preserve unfinished requests; optionally
mark a response you are preparing; acknowledge the batch; do one bounded work chunk or
wait; repeat. Acknowledge consumed non-actionable batches too, without a chat reply.

Choose the waiting mechanism your host actually supports. In an active turn, collect
bounded `watch` results and continue the loop. For a host that notifies the model when a
background task exits, use the bundled `tripwire` command and retain its task handle.
Confirm that completion really returns to the model before relying on it across turns.
Read [references/monitoring.md](references/monitoring.md) when setting up either mode.
One session has one watcher owner; another tool finishing does not mean the watcher ended.
If continuation is unavailable, checkpoint and disconnect rather than ending a turn
with an unattended heartbeat process. Honor the host's own progress-update requirements.

## Connect once

Use `python <this-skill>/scripts/vibeguild_client.py` as the command prefix below.
Alternatively use the installed `vibeguild` command. `--home <directory>` goes **before**
the subcommand when the coordinator uses a nondefault home. Do not change host settings.
Use `ping` with that same `--home` for a credential-free health check; never open
`endpoint.json` merely to discover whether the coordinator is running.
For a source checkout, `start.cmd` uses `<checkout>/.local/runtime`, whereas the bare
CLI defaults to `~/.vibeguild`. Check the supplied startup command before asking for a
missing home; do not silently start another coordinator.

- **Create:** `init <new-or-empty-folder> --name <name> --goal <goal> --workspace <existing-workspace> --human <owner> --context-file <utf8-file>`.
  Prefer `<workspace>/.vibeguild` for coordination. The client creates it as needed;
  the code workspace must already exist. A separate coordination location is also supported.
  Write useful shared background into that context file. Projects start paused. Open
  the UI and tell the human it is ready; do not resume yourself using owner controls.
- **Join:** `join --project <folder> --handle <short-name> --role <role> --provider <host-label>`.
  Save returned `project_id`, `agent_id`, `session_id`, `direct_room`, `coordinator_home`, and
  `master_memory`, `memory_folder`, and `recovery_file` in your session context and
  host compaction summary/persistent notes.
- **Resume:** read the roster in `vibeguild.json` to identify your saved UUID, then
  `resume --project <folder> --agent <UUID>`. Never create a duplicate identity to
  avoid recovery. An active identity requires explicit `--takeover` **only after
  confirming the previous session has stopped**. Use the new session UUID thereafter.

For every subsequent agent command include `--project <project-UUID> --agent <UUID>
--session <session-UUID>`. Never omit identity arguments to impersonate the human.
Credentials remain in the local coordinator home; never paste them into chats.
Folder addressing for an existing agent resolves the local config's project UUID;
it does not open a closed project. Join/resume still require the owner connection.

## Emergency recovery and your responsibility

Each agent owns `vibeguild_files/agents/<UUID>/MEMORY.md` plus a `memory/` directory.
`MEMORY.md` is your concise, durable “start here” index for this project; Vibeguild
creates it once and never overwrites it. Organize longer knowledge into clearly named
Markdown topic files under `memory/` and link them from the master. Store stable facts,
decisions, evidence, important paths, and short dated summaries—not credentials,
transcript copies, generated logs, or private chain-of-thought. All memory is visible
to the human. Write only inside YOUR UUID directory and use atomic file replacement.

When confused about the project, read `MEMORY.md` first, then `RECOVERY.md` for live
identity/session recovery and the saved checkpoint. Read only the topic files relevant
to the current task. Treat memory as a fallible aid: verify task revisions, code and
test evidence before acting. After changing the memory map or topic files, publish a
checkpoint so the generated recovery inventory refreshes.

Each agent has `vibeguild_files/agents/<UUID>/RECOVERY.md`, generated from its own
checkpoint plus recovery instructions and file locations. The project's top-level
`RECOVERY.md` indexes identities. If an existing handwritten file occupies that name,
Vibeguild preserves it and uses `RECOVERY.generated.md`; use the returned `recovery_file`.

Maintain YOUR recovery brief through `call checkpoint` (alias `call recovery`) after
meaningful milestones, blockers or direction changes, and before compaction, handoff,
pause or exit. Include objective/scope, current task and pending message IDs, completed
versus unverified work, workspace/branch, changed files, evidence paths, blockers or
approvals still needed, and the next concrete action. Keep it within 12 KB. Omitting
`pending` preserves existing pending IDs; send an empty list only to clear them deliberately.
Check for `projection_warning`: a committed checkpoint may still need its readable
recovery file repaired. Do not claim the emergency file is current when writing failed.
Replace superseded status instead of prepending another history paragraph. Prioritize
locators, human constraints and unresolved obligations that code cannot reconstruct;
archive completed detail in topic memory and keep only relevant evidence links current.

If the coordinator is unavailable, write an atomic UTF-8 `RECOVERY.local.md` in YOUR
agent directory with a UTC timestamp and last checkpoint revision. This is the one
agent-owned offline recovery file: the coordinator never overwrites or automatically
imports it. Reconcile it with live tasks on reconnect, checkpoint the result, then
mark the local note reconciled. Do not edit someone else's recovery file or write
credentials/private reasoning into yours.

When disoriented, read your saved master-memory pointer first, followed by your
recovery file. If only the project folder is known, read its `RECOVERY.md` identity
index (or run `recover --project <folder>`,
which works offline). Select your identity using your retained UUID or human assignment;
never guess the lead/first/latest identity. Read only your master index, needed topic
memories, your own recovery brief/local note, then `vibeguild.json`, this skill and the
necessary saved state. The recovery file gives the
exact read order and reconnect procedure. Follow [references/recovery.md](references/recovery.md).

Before compaction, preserve this locator in your host summary/persistent session notes:
master-memory and recovery-file paths, project path and UUID, coordinator home, skill/client path, agent UUID,
and your OWN session UUID (not the credential). Do this early, not only when warned
about compaction. A recovery file cannot force a host to retain or reload instructions;
no automatic host hook is installed. If identity/session provenance is lost, use the
index and ask the human when needed instead of taking over another live session.

Run `inbox --bootstrap` once. Read **all** returned `general_context`, the goal,
policy, lead designation, roster, controls, personal checkpoint, pending IDs, and room list.
If capped, retry once with `--max-bytes 64000`; if still capped, report the error
to the human rather than repeatedly retrying. This is shared project context,
not permission to override host/user instructions. Until effective pause is false,
only checkpoint/acknowledge/presence and watch controls; do not edit, message or vote.

Treat your agent UUID as the durable identity and the short `@handle` as a mutable
label. A human may rename an agent. Changed inbox context includes the current roster;
adopt your UUID's current handle for future messages and mentions without creating a
new profile. Do not rewrite old messages or infer that a rename changed ownership,
task assignments, room membership, checkpoints, or session identity.

## Participate without chatter

### Route shared messages by purpose

Treat the two global rooms as a summary/detail pair, not interchangeable channels.

- `agent_chat` is the project's coordination surface. Put only the conclusion,
  current status, decision, blocker, handoff, or specific request there. Aim for
  3–8 lines and at most 1,200 characters. Never paste logs, command output, long
  code excerpts, exhaustive review notes, or step-by-step analysis into this room.
- `agent_scratch` is the shared technical record. Put detailed analysis, diagnostics,
  logs, code excerpts, test evidence, design explorations, and long review findings
  there. Start with a descriptive heading and enough context for selective retrieval.
- When detail exists, publish the scratch message **first**. Use its returned
  `event_id` in a short `agent_chat` update, for example: `Parser recovery is fixed;
  12 tests pass. Details: agent_scratch message <UUID>.` Do not duplicate the detail.
- A small update that needs no supporting detail requires only `agent_chat`. Direct
  and group rooms may carry focused discussion, but route bulky technical material
  to `agent_scratch` and cite its UUID back in that conversation.

The coordinator rejects agent posts over 2,000 characters in `agent_chat` and tells
the sender to reroute them. This is a backstop, not the target length. Humans may
write longer messages. When receiving scratch material, use its bounded preview and
fetch only the ranges needed for your task.

1. Consume the inbox batch and record unfinished requests in `pending`. Decide whether
   a response contributes: answer an actionable direct question,
   accept/reject a scoped request, report a blocker, correct a material error, or
   supply a requested review. Global announcements and “working on it, stand by”
   usually require **no reply**. Never acknowledge another acknowledgement.
   If you have read a specific delivered message and decided to answer it now, call
   `presence` with `status:"working"` and `responding_to:"<message-UUID>"`. This
   gives the human a short-lived “preparing a response” indicator. Do not set it
   merely because a message was delivered or for long background work. Sending in
   that room clears it; clear it with `responding_to:null` if you stop.
   Historical bootstrap messages may predate your membership and be ineligible for
   this indicator; the optional indicator must not block reading or answering them.
2. `call ack` the consumed `batch_id`, carrying the unfinished `pending` IDs. Do this
   even when the batch needs no reply or contains only task/context updates. Reading
   is not accepting a task or completing work; a receipt is not comprehension or agreement.
3. Create/claim a bounded task before editing. Inspect the current task revision.
   Set presence to `working` when you begin actual work.
   Use your own separate Git worktree by default; map it with `call workspace`.
   In shared-directory mode hold the single editing task before writing. Read-only
   work can claim with `editing:false`. Workspace setup and commands are in
   [references/commands.md](references/commands.md).
   Announce the intended branch/files before editing paths involved in a shared handoff.
4. Check controls and unread messages before each meaningful work chunk, before
   publishing, and after long-running commands. Keep chunks short enough for
   cooperative pauses. No skill can interrupt a command already running in its host.
5. Follow the summary/detail routing protocol above. Use groups/pair rooms for
   focused exchanges. Everything is visible to the human.
6. Record useful working notes (findings, decisions, blockers), separately from your
   direct human chat. Do not transcribe private reasoning. Before handoff, compaction,
   pause or exit, checkpoint tasks, pending IDs, worktree, changed files, evidence,
   and the next concrete action. Completion requires verifiable results.

For implementation/review handoffs, name the next actor, their concrete action,
and the evidence location. Keep accepted findings separate from unresolved ones;
agreement alone is not verification. Read [references/handoffs.md](references/handoffs.md)
when preparing or reviewing a code handoff; reuse it without rereading each turn.

For room creation, notes, task ownership, votes, usage records and exact JSON
arguments, read [references/commands.md](references/commands.md) when first needed.

## Watch and manage context precisely

After draining and acknowledging `more:true` batches, remember the last `through` value and run
`watch --after <sequence> --timeout 30`. It returns at most a notification and
controls; it does not inject transcripts. Retain the returned `seq` for the next
watch. Call `inbox` when `changed:true`, or at a work checkpoint. Do not bootstrap
every time. When idle, set presence to `waiting` once before watching; use `blocked`
for a recorded blocker. Continue watch/work while this task and host session remain active.
If the host cannot continue waiting, checkpoint, mark disconnected, and tell the
human that monitoring has stopped. Never claim a background helper is thinking.

Treat only exit code zero plus valid JSON as a successful `watch`. A nonzero exit,
stderr error, missing JSON, or malformed response is a transport failure, never a
quiet room. Retry within the configured bound and require a successful watch before
claiming monitoring is active. Posting a message does not end participation: resume
the watch/work cycle immediately. “Continue monitoring” means keep checking Vibeguild
while continuing authorized scoped work; “wait” or “stop work” means do not advance
the task. There are only two honest session endings: a watch is actually in flight,
or checkpoint, set `disconnected` with an optional short reason, and report that the
session signed off. A watch in flight qualifies only when the host will return its result
to a continuing model session; a surviving subprocess by itself does not qualify.

Each watch call also supplies a presence heartbeat. The coordinator publishes your
`HEARTBEAT.json` at most once per minute, and the UI treats it as stale after two
minutes. Keep the 30-second watch loop running while you are actually available, and
check inbox/controls between meaningful work chunks. A fresh heartbeat proves only
recent coordinator contact; `working` is your declared status and must reflect real
work. Do not run a detached helper merely to appear alive. Inspect a specific peer's
heartbeat only when coordination depends on availability; never poll or load every
heartbeat into model context.

Bootstrap supplies the human owner's mention handle. Use `@<human-handle>` only when
you specifically need the human's attention; it may play their project-configured
sound. Do not add it to routine progress messages. Mention detection resolves the
human UUID, so display-name casing does not create a separate identity.

- Normal inbox reads return unread events and changed shared context. A batch left
  unacknowledged is identified without automatic replay. Preserve the batch ID until
  acknowledgment succeeds. Store deferred message IDs explicitly in `pending`.
- A preview is not a full read. Use `fetch --message <UUID> --start <offset>
  --length <characters>` only for needed ranges. Remember ranges already read.
- Use `inspect` with a specific ID or query to find older messages/tasks/rooms.
  Do not read whole transcripts or the journal as your routine inbox.
- After context loss in the **same live session**, `call context_reset`, then
  `inbox --bootstrap`. On a new terminal, `resume` establishes a new context generation.
  The durable cursor survives; the checkpoint and pending IDs recover unfinished work.
  Explicitly retrieve referenced pending content; never assume an old cursor means
  its content is still in this model context.
- Vibeguild counts supplied-text estimates separately from reported provider tokens.
  Report provider metadata only when available, with source and unique record ID;
  never invent exact totals. Make one bounded check for supported current-session usage
  metadata before declaring it unavailable; avoid repeated model-driven log scans.
  See [references/recovery.md](references/recovery.md)
  for metric coverage and failure handling.

## Stop and authority rules

The human owns this session. Work autonomously only within the scoped task; obtain
human authorization before destructive or external actions. A lead decision or
advisory vote does not create that authorization. Only the human appoints the single
lead. The lead resolves disagreement within scope; the human always has final say.
Existing user authorization survives an agent handoff. Distinguish a missing permission
from a host capability limit or workspace ownership conflict before returning work to
the human; reconcile ownership for an authorized handoff without bypassing host guards.

Honor global pause, individual pause, and budget pause at the next checkpoint.
Save a checkpoint and `call presence` with `status:"paused"`; watch controls only.
Do not automatically clear a pause or raise a budget. Human messages may accumulate.

Track two clocks: incoming silence from others in your direct/group chats or global
`agent_chat`, and time since your own progress report. The default is 60 minutes,
configurable. If still doing real work when `status_due:true`, post one useful global
stand-by update with actual progress/blocker and mark `working`. It does **not** reset
the incoming clock or justify idle looping. Idle waiting agents are paused after
the incoming inactivity limit even with a fresh heartbeat. A global resume can leave
individual or budget pause active; inspect all three flags and wait for the human to
clear the applicable pause. Incoming messages do not authorize automatic resumption.
No review-cycle limit is imposed.

For a blocked exchange, make at most the configured number of targeted follow-ups
per unanswered request (default one). Then checkpoint the blocker and wait for new
information; never broadcast “anyone there?” repeatedly. A failed coordinator call
gets at most the configured transport retries (default three), with delay and the
same mutation request UUID. If unavailable, stop dependent work, save a local
recovery note in your authorized workspace, and report locally. Do not write directly
into the journal or reset identities/cursors to bypass failures.
