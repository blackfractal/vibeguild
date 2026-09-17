# Implementation status — 2026-09-17

The user authorized building after the design discussion. The application and portable
skill are implemented. The older design documents include future specifications;
this file and README describe the actual v0.1 boundary.

Subsequent user clarification: coordination defaults to a dedicated `.vibeguild`
subfolder inside the existing code workspace, created automatically. A separately
located coordination folder remains an option. This supersedes the original default
of placing coordination outside the workspace.

## Delivered

- Python loopback service, provider-neutral CLI, Windows launcher; no runtime dependencies.
- **vibeguild.json** with **general_context**, owner, UUID identities, lead and policy.
- Atomic immutable events, integrity verification, exclusive-writer lock, idempotent
  mutations, repaired readable transcripts and per-agent/task/room/vote state files.
- Worktree mappings, sequential shared editing task fallback, optimistic task revisions.
- Bounded incremental inbox, acknowledgment/pending work, context generations, targeted
  state/search/range reads, per-session credentials and resume fencing.
- Dark chat UI: global/scratch/group/direct conversations, agent notes/checkpoints,
  human messages/mentions, colors/lead badges, combined feed, All Chats, double-click
  tabs, Open Tabs, tasks, search/replies, large text views and settings.
- Timed advisory votes with abstentions, frozen electorate, human-inclusive early
  close, deadline reconciliation, public ballots and durable lead/human decisions.
- Cooperative global/individual pause, acknowledgments, incoming-inactivity pause for
  idle agents, working-status reminders and last-seen reporting.
- Supplied-text estimates, separate reported provider usage, configurable estimate budgets.
- Generic skill supporting create/join/resume, active-session watching, selective
  responses, context hygiene, scoped autonomy, checkpoint/recovery and bounded retries.
- Per-agent emergency recovery files maintained through checkpoints, a project identity
  index, offline recovery reader, preserved agent-authored offline notes, UI recovery
  links, and explicit compaction-summary locators. No automatic host hook is claimed.
- Labelled demo and paused Clé pilot linked to the user's supplied brief.

## Validation boundary

Tests exercise concurrent duplicate publication/restart, fencing, context reset,
offline config edits versus stale projections, corruption, exclusive writer lock,
votes/deadlines, pause/interjection, worktree/shared task exclusion, budgets, ranges,
mentions, 20-agent paging, HTTP origin checks and installed skill use from another CWD.

An independent agent used the installed skill in `.local/skill-trial`: joined, read
general context, created a parser-validation proposal, published findings, checkpointed
and disconnected without editing code. This is a skill workflow trial, not a claim
that independent Claude and Codex terminals completed a coding project.

Pure JavaScript tests cover escaping, human identity, retrieval links, draft preservation,
workspace controls and human-pending votes. The browser-control tool reported no available
browsers/apps. Real-browser visual validation and the sustained coding pilot remain
acceptance work for the next interactive run.

## Design choices and limits

The runtime uses Python's standard library and plain HTML/CSS/JavaScript. Durable files
are canonical, with a single write/notification service. No SQLite or frontend build
chain is required. The shared editing lock is task-based and conservative.

Agents create/merge Git worktrees with their existing tools. Vibeguild maps distinct
workspace claims; a mapped folder is not proof that Git created it. It cannot stop
an agent from writing outside its agreed workspace.

Normal inboxes cap at 16 KB; explicit reads allow up to 64 KB. Oversized required
bootstrap context fails clearly rather than silently dropping instructions. Large
messages use previews and character-range reads. The full journal currently loads
into memory; archive compaction/indexing is future work. Twenty agents is a tested
functional target, not a multi-day throughput benchmark. Binary uploads are deferred.

Provider usage is reported, not independently verified. Budgets cover supplied-text
estimates only. Pause is cooperative, with no immediate termination claims.

## How the two-agent notes affected this build

| Observation | Concrete response |
|---|---|
| Stale handoffs can look new after restart | Event IDs, durable cursor, context generations and pending IDs |
| Reading differs from owning work | Acknowledgment, task claim and completion are separate |
| Concurrent publication must be safe | One writer, atomic events, exclusive lock, request idempotency |
| False success survives ordinary tests | Evidence on done; concurrency, stale-config, deadline and fencing tests |
| Helper liveness does not prove model liveness | Last-seen/status labels; no synthetic thinking heartbeat |
| Loopback alone did not protect mutations | Host/origin checks, same-origin cookie, owner/agent credentials, JSON requests |
| Dumps and repeated handoffs waste context | Delta inbox, scratch previews, targeted ranges, explicit estimate coverage |
| Human interjections must remain authoritative | Human controls, visible messages, appointed lead, advisory votes |
| Timeout is not verified process termination | Next-checkpoint pause only; no kill claims |
| Stale `working` can hide an abandoned in-flight task | Amber top-bar/roster alert for lost contact while working |
| Clean exit and killed terminal looked identical | Explicit disconnected presence records and displays a clean sign-off |
| Checkpoint prose can be mistaken for verified truth | Checkpoint pane labels it agent-authored and points to task/file/test evidence |
| Health checks tempted agents to inspect a credential file | URL-only endpoint, public loopback health route, and `vibeguild ping` |
| Broken watch output was mistaken for a quiet room | Skill requires zero exit plus valid JSON and defines two honest session endings |

Sources: [Codex notes](../_knowledge/codex_notes.md) and
[original Claude notes](../_knowledge/claude_notes.md), plus the
[Clé field notes](../_knowledge/cle_project_claude_notes.md).

## September field-note updates

The September 14–17 `_notes` review added a bounded Python `tripwire` wait, OS singleton
locking per project/agent/session/home, explicit pending-batch metadata on watch, agent-safe
folder resolution, UTF-8 BOM JSON input, and actual-length chat-cap diagnostics. The source
skill now starts with the participation loop, documents host completion requirements and
busy-work monitoring, and preserves current-state recovery and evidence scope in handoffs.
Automated coverage includes the freshly installed launcher, a killed lock owner, malformed
responses, pending work, pauses and Unicode. These checks do not certify live host wakeup
or continuation after compaction; those still need an actual host acceptance run.

Further field-note proposals remain separate work: a public session locator/identity
adapter, automatic rearming through tested host hooks, WebSocket notifications, bounded
pending-batch replay/digests, a compact generated current-state brief, and UI-only usage
collection with explicit record/delta/snapshot semantics. Current usage deduplication is
retained; changing duplicates to upserts without specifying those semantics is insufficient.
Inactivity/global/individual/budget pause controls remain authoritative; contact heartbeats
do not automatically clear them. No runtime service or installed skill is updated by merely
editing this repository.

## Deferred

Remote transport/multiple human accounts, remote authentication, immediate process
control, session launching, exact provider telemetry, specific ChatGPT integration,
lead councils, binary attachments and archival policy.
Potential field-note follow-ups include explicit message `needs_reply` metadata,
Git/worktree readiness diagnostics, and checkpoint-selected memory references. These
need interaction and state semantics beyond the reliability/UI changes above.
Native folder selection is implemented for open-project, project creation and workspace
settings, using an isolated Tk dialog process. Selection/cancellation, access checks
and single-dialog admission are covered by tests; native visual interaction requires
the user's desktop. Typed paths remain available.
