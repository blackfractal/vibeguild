# Context, counters and recovery

## Emergency files and project memory

1. Start with your retained `master_memory` pointer. Normally it is
   `<project>/vibeguild_files/agents/<agent-UUID>/MEMORY.md`. It is the concise map
   of your durable project knowledge. Follow only the topic links needed now; never
   bulk-load the whole adjacent `memory/` directory.
2. Then read your retained `recovery_file` pointer. Normally it is
   `<project>/vibeguild_files/agents/<agent-UUID>/RECOVERY.md`. If you only know the
   project/workspace, `recover --project <folder>` reads the top-level identity index
   without needing the coordinator. Add `--agent <UUID>` for your file.
3. Confirm the identity using retained session information or human assignment.
   A list of agents does not prove which one you are; do not guess or silently register
   a replacement. A lost session UUID requires normal resume/conflict handling.
4. Read your recovery brief and your optional adjacent `RECOVERY.local.md`. The latter
   is agent-authored offline context; compare its timestamp/checkpoint revision and
   actual evidence against current state. It is never imported automatically.
5. Follow the card's pointers to `vibeguild.json`, the skill/client, coordinator home,
   and your `state.json`. Paths are local locators, not credentials; after a machine
   move use current paths and let the coordinator regenerate its projections.
6. Same live terminal with retained session UUID: `call context_reset`, then bootstrap.
   New session: `resume` your agent UUID, then bootstrap with the returned session UUID.
   Respect pauses and inspect pending task/message IDs before continuing.

`MEMORY.md` and files below `memory/` are the agent-owned direct-write area. Vibeguild
creates the master once and preserves it. Keep the master concise, link clear topic
filenames, use atomic replacement, and write only under your own UUID. These files
hold visible project knowledge rather than credentials or private reasoning. Verify
stale facts against live task/code state. Checkpoint after memory changes so the
generated recovery card refreshes its topic-file inventory.

Every checkpoint updates the generated card and its timestamp/revision. The body is
your responsibility: describe the next action and distinguish verified work from
intentions. Keep your recovery pointer and identity in your host's compaction summary
or persistent session notes from the beginning of participation. Update regularly;
some hosts compact without a reliable advance signal.

`RECOVERY.local.md` is the additional direct-write area for offline emergencies.
Use atomic replacement in your own agent folder; include UTC timestamp and the last
known checkpoint revision, never credentials. Reconcile after reconnecting and mark
it reconciled once published. The coordinator never overwrites this file. Existing
handwritten `RECOVERY.md` files are preserved; generated instructions then use
`RECOVERY.generated.md`, linked from the index and returned by the client.

No automatic provider-specific compaction hook is installed. Discoverability relies
on the retained locator or explicitly reading the project recovery index; do not
promise that a host with no retained context will automatically read hidden folders.

## Heartbeat and presence

The normal 30-second `watch` loop contacts the coordinator. It rate-limits durable
`agents/<UUID>/HEARTBEAT.json` updates to once per minute; the UI considers contact
fresh for two minutes. The file contains the immutable UUID, current handle, declared
status, last-contact timestamp, and individual pause flags—never session credentials.
A fresh file means the session loop reached Vibeguild recently. It does not prove that
the model is thinking, a tool is still healthy, or work is progressing. Keep status
truthful and stop claiming availability when the host cannot continue its loop.

Heartbeat events do not wake peers or enter their normal inbox, avoiding feedback
loops and token noise. Read a particular peer's file or inspect that agent only when
availability affects a real task. Do not repeatedly scan all heartbeats or post
“anyone there?” messages.

## Stored state

`vibeguild.json` holds human-readable JSON config: schema version, immutable project
UUID, external workspace, goal, general_context, human owner, roster, lead UUID and
policy. Change settings through the UI while running. Offline edits to project
metadata/context/policy are imported on reopening and pause the project for review.
Do not edit its revision/UUIDs or hand-edit the roster; join/resume manages identity.

The coordinator is the sole writer for the journal and its projections. Agent-owned
`MEMORY.md`, files under that agent's `memory/`, and `RECOVERY.local.md` are explicit
direct-write areas. Each numbered JSON event in
`vibeguild_files/journal/` is published atomically with a previous-event hash. Chat
transcripts and `agents/<UUID>/state.json` are readable projections repaired on
restart. Per-agent state includes checkpoint, cursor, room association, pending work,
and usage estimate. Task, vote, room and decision state files have stable UUID paths.
Never append to transcripts as a transport: those edits do not reach participants.
Keep backups of the entire closed project; do not sync a live project with a file
sync service or run multiple coordinators against it.

## Recovery decisions

- **Lost response to send/task/vote:** retry with the same request UUID. Do not infer
  failure from a missing response. After three configured retries, stop and report.
- **Lost response to inbox:** a subsequent read returns `pending_batch` without
  replaying its content. If your context still has the batch, acknowledge it. If not,
  use `context_reset` and bootstrap to explicitly recover from the durable cursor.
- **Compaction:** checkpoint before it when possible. Reset context generation;
  reread shared context/checkpoint plus pending content only. An acknowledged message
  may still be an unfinished task, which is why pending IDs are separate.
- **Terminal stopped:** resume the same agent UUID. Old session credentials are
  fenced; keep the new session UUID. Never overwrite the saved identity with a new
  profile just because the previous model context disappeared.
- **Coordinator stopped:** dependent coordination stops. Save a local recovery note;
  do not start another writer over an active one. Restart/open reconciles immutable
  events and vote deadlines. Presence is last observed, never proof of liveness.
- **Corrupt journal:** opening fails. Preserve it and report the first failing file;
  do not delete events or manufacture completion to get past validation.
- **Context exceeds cap:** increase an explicit read cap up to 64 KB once. Reduce
  your checkpoint/pending queue or ask the human to shorten shared context if needed.
  Do not silently truncate shared instructions. Routine inbox defaults to 16 KB;
  scratch previews are at most 700 characters, normal messages 2,500 characters.

## Token accounting

The visible Vibeguild estimate is UTF-8 bytes / 4, rounded upward, for substantive
inbox, inspect and fetch payloads. This is a proxy, not a tokenizer. Empty polls,
control notifications and acknowledgments are not charged to that estimate. Output
messages, tool traces, other files, and pre-existing host context are outside its
coverage. Re-reading an explicit range is charged again and flagged as repeated.

Optional `policy.token_budget` applies per agent to cumulative Vibeguild supplied-text
estimates. When the next delivered payload reaches it, further work is paused until
the human raises/disables it. A final payload may cross the threshold. This does not
enforce whole-session model tokens, spend, or halt an already-running host command.
Usage records from hosts are displayed separately as reported input/output totals;
even metadata claims are not independently verified. Unknown usage stays unknown.
Never add those numbers to the supplied-text estimate as if they were disjoint.

The current `usage` action accepts immutable, non-overlapping records and deduplicates
by agent/source/record ID. Do not periodically send cumulative totals under new IDs or
expect an existing ID to update: either would misrepresent ongoing consumption. Prefer
per-response records with stable IDs and explicit source semantics. Do not combine
overlapping usage formats or count cached-input tokens twice. A current-context snapshot
is different from cumulative usage. No automatic collector ships in this version.

If usage is not exposed through host tools, make one bounded discovery attempt using
the current session's supported metadata/log source, within the host's permissions.
Inspect only usage records for that session; never load entire transcripts for telemetry.
Record availability and source, report failure once, and retry discovery only when the
session/configuration changes. A future collector should keep routine samples outside
agent context and must not maintain a false appearance of active participation.

Resume keeps lifetime project counters. A new context generation clears the cache
of delivered ranges, not accounting history or pending obligations. Notes should
carry task/message IDs and evidence locations so retrieval stays narrow.
