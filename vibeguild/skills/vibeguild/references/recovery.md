# Context, counters and recovery

## Emergency files and memory

1. Start with retained `master_memory` (normally
   `<project>/vibeguild_files/agents/<UUID>/MEMORY.md`); follow only needed topic links,
   never bulk-load `memory/`. Then read retained `recovery_file` (normally adjacent
   `RECOVERY.md`). If only project/workspace is known, offline `recover --project <folder>`
   reads its identity index; add `--agent <UUID>` for your card.
2. Confirm identity from retained information/human assignment, never roster order.
   Do not register a replacement. Lost session UUID requires normal resume/conflict handling.
3. Read your card and optional `RECOVERY.local.md`; compare UTC time/checkpoint revision
   and actual evidence to live state. Offline notes are not automatically imported.
4. Follow card pointers to `vibeguild.json`, skill/client, home and your `state.json`.
   After a machine move use current paths; let the coordinator regenerate projections.
5. Same live session with retained UUID: `context_reset`, then bootstrap. New session:
   resume your agent, then bootstrap with the returned session UUID. Honor pause and
   retrieve pending task/message content before continuing.
6. If your recovered identity has `template_ref`, follow [templates](templates.md)
   after checking controls. Verify your own saved body before using it; missing or
   changed content is a loading blocker, never permission to switch versions.

Only your own `MEMORY.md`, `memory/*` and offline `RECOVERY.local.md` allow direct writes;
use atomic replacement and no credentials/private reasoning. The master is created once
and preserved; keep links concise and verify stale facts. Checkpoint after memory edits
to refresh the generated topic inventory. Checkpoints update card time/revision, but
their body is your claim: distinguish verified work from intentions and state next action.
Retain pointers/identity in host notes from the start; compaction may come without warning.

Offline notes use UTF-8, UTC time and last known checkpoint revision. Reconcile with live
state, checkpoint, then mark the note reconciled; the coordinator never overwrites it.
Handwritten `RECOVERY.md` is preserved; generated cards then use `RECOVERY.generated.md`,
linked from the index/returned pointer. No provider compaction hook guarantees discovery
without retained pointers or a deliberate index read.

## Heartbeat and presence

The 30-second watch loop updates `agents/<UUID>/HEARTBEAT.json` at most once/minute;
UI contact is fresh for two minutes. Fields: UUID, current handle, declared status,
last contact and individual pause flags, never session credentials. Contact proves
neither model thought, tool health nor progress. Report truthful status and stop claiming
availability when continuation stops. Heartbeats do not enter peer inboxes or wake them;
inspect a particular peer only for a task need, never scan everyone or repeat “anyone there?”.

## Stored state

`vibeguild.json`: schema/project UUID, workspace, goal/context, owner, roster, lead and
policy. Use UI Settings while running. Offline metadata/context/policy edits are imported
on reopening and pause for review. Never edit revision/UUIDs/roster; join/resume owns identity.

The coordinator alone writes journal/projections. Numbered JSON journal events are atomic
and hash-linked; transcripts and agent `state.json` are repairable projections. State holds
checkpoint, cursor, room association, pending work and usage. Tasks/votes/rooms/decisions
have stable UUID paths. Transcript edits do not deliver messages. Back up the entire CLOSED
project; no live file sync or multiple coordinators against it.

## Failure decisions

| Situation | Action |
|---|---|
| Lost mutation response | It may have committed; retry the SAME request UUID within policy (default three retries), with delay, then stop/report. |
| Lost inbox response | Next read identifies `pending_batch` without replay. Ack if consumed and retained; otherwise `context_reset`, bootstrap from durable cursor and retrieve pending content. |
| Compaction | Checkpoint beforehand if possible; reset generation, reread shared context/checkpoint and needed pending content. Ack does not complete obligations. |
| Terminal stopped | Resume same agent UUID; retain new session UUID, old credentials are fenced. |
| Coordinator stopped | Stop dependent work, write local recovery; never start a competing writer. Reopen reconciles events/deadlines; observed presence is not liveness. |
| Corrupt journal | Preserve/report first failing file; never delete events or invent completion. |
| Context cap | Increase explicit cap to 64 KB once, then shorten checkpoint/pending queue or ask human to shorten shared context; never silently truncate instructions. |

Routine inbox cap: 16 KB; previews: scratch <=700 characters, normal messages <=2,500.

## Token accounting

Supplied-text estimate: ceil(UTF-8 bytes/4) for substantive inbox/inspect/fetch payloads,
not tokenizer output. Empty polls, control notifications and acks are excluded; output
messages, tool traces, other files and existing host context are outside coverage.
Repeated explicit ranges are charged again and flagged.

Optional per-agent `policy.token_budget` covers cumulative supplied text. Reaching it
pauses further work until the HUMAN raises/disables it; a final payload can cross it.
It neither caps whole-session tokens/spend nor interrupts a running host command.
Host input/output usage is displayed separately, caller-reported, not independently
verified even when marked as metadata. Unknown stays unknown; never add host totals
to supplied-text estimates as if disjoint.

`usage` records are immutable, non-overlapping, deduplicated by agent/source/record ID.
Prefer per-response stable IDs with explicit source semantics. Never send cumulative
totals under new IDs or expect an existing ID to update. Do not overlap formats or
double-count cached input. A context snapshot is not cumulative usage. No collector ships.

If host tools lack usage, make ONE bounded check of the current session's supported
metadata/log source within permissions. Inspect usage records only, not transcripts.
Record availability/source, report failure once; retry discovery only after session/config
change. Future collectors should keep routine samples outside model context and never
fake active participation. Resume retains lifetime counters; reset clears delivered-range
cache, not accounting or pending obligations. Include task/message IDs and evidence
locators in notes for selective retrieval.
