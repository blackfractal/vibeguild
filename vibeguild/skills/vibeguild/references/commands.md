# Command reference

PowerShell setup; other shells pass the same arguments with native quoting:

```powershell
$client = "<absolute-skill-path>/scripts/vibeguild_client.py"
$coordinatorHome = "<coordinator-home>"
$project = "<project_id>"
$agent = "<agent_id>"
$session = "<session_id>"
$identity = @('--project', $project, '--agent', $agent, '--session', $session)
python $client --home $coordinatorHome ping
python $client --home $coordinatorHome inbox @identity --bootstrap
```

Use the server's home before every subcommand; never load credential files. `ping`
succeeds with exit zero and JSON `connected:true`; failure is nonzero with JSON stderr.

## Mutations

Mutations use `call <action>`.

Write UTF-8 JSON to `--data-file` (BOM accepted). `--body-file` replaces its `body`,
allowing long text without shell escaping. Select and retain `--request-id <UUID>` BEFORE
sending; retries reuse it and return the original result without repeating the mutation.

```powershell
$request = [guid]::NewGuid().ToString()
@{room='agent_scratch'} | ConvertTo-Json | Set-Content -Encoding utf8 message.json
python $client --home $coordinatorHome call send @identity --data-file message.json --body-file details.md --request-id $request
```

Retain scratch's returned `event_id`, then cite it in a short `agent_chat` summary.
Agent chat limit: 2,000 characters; target <=1,200. Technical bodies: <=250 KB UTF-8
per message; split/label larger artifacts. No binaries or credential-bearing logs.

| Action | JSON fields / behavior |
|---|---|
| `send` | `room`, `body`, optional same-room `reply_to`; returns message UUID as `event_id`. Cite cross-room UUIDs in body. |
| `note` | `body`; agent working note or owner personal note, with no automatic delivery. |
| `ack` | `batch_id`, `pending` array of unfinished request IDs; advances consumption, not completion. |
| `checkpoint` / `recovery` | `body` <=12 KB, optional `pending`; omission preserves queue. |
| `presence` | `status`: ready/working/waiting/blocked/paused/disconnected; optional `responding_to` UUID/null, short disconnected `reason`. |
| `context_reset` | `{}`; new context generation, cursor retained; bootstrap next. |
| `room` | `name`, `members` array of agent UUIDs; returns `room_id`. |
| `join_room` | `room`; join a group yourself; direct chats remain separate. |
| `task` | `title`, `description`; returns `task_id`. |
| `task_update` | `task_id`, current `revision`, `status`, optional `result`, `editing`; working claims, open releases, done requires evidence. |
| `workspace` | `path` to existing separate worktree; rejects ownership collisions. |
| `vote` | `question`, `options` array, `minutes`, optional `room`; advisory vote, fixed electorate: current agents plus human. |
| `ballot` | `vote_id`, zero-based `option` or `"abstain"`, optional `reason`; changeable before deadline. |
| `decision` | `body`, optional `task_id`, `vote_id`; designated lead/human only. |
| `usage` | `source`, `record_id`, `input`, `output`, optional `verified_source`; read [Token accounting](recovery.md#token-accounting) first. |

`control`, `settings`, `lead`, `human_read`, `human_update` and `agent_update` (rename) are human-only.
Do not evade agent restrictions through the owner connection. V1 trusts local processes
under one OS user; workflow controls are not a hostile-process sandbox.

Human read watermarks, ack-derived receipts and response-intent bookkeeping stay out of
agent inboxes; no extra receipt action/message is needed. UUID/session survives rename;
use the current handle without rewriting historical messages/journal.

`responding_to` explicitly signals a response you decided to write now. It requires a
delivered message and unpaused `working` status; expires after two minutes unless renewed.
It is not inferred from ack. Send in that room clears it; use null if abandoned.

## Targeted reads

```powershell
python $client --home $coordinatorHome inspect tasks @identity --key <UUID> --limit 1
python $client --home $coordinatorHome inspect rooms @identity --start 0 --limit 10
python $client --home $coordinatorHome inspect messages @identity --query "parser" --limit 5
python $client --home $coordinatorHome fetch @identity --message <UUID> --start 0 --length 3000
```

`inspect`: agents/rooms/tasks/votes/decisions/messages; `start` is a row offset.
Messages are previews; `fetch` offsets/lengths are characters, not bytes/tokens.
For `watch`/`tripwire`, read [monitoring](monitoring.md) before waiting.

Offline `recover --project <folder> [--agent <UUID>]` reads the identity index/your
recovery file without credentials/server. Accepts coordination folder or workspace
containing `.vibeguild`; it neither resumes nor authorizes work.

## Workspaces

Inspect repository instructions, `git status --short` and `git ls-files` for relevant
paths first. A new worktree omits untracked/uncommitted changes. If required code would
be missing, report paths and resolve the source revision or human-selected shared mode;
never silently commit others' work or review an incomplete copy.

```powershell
git -C "<source>" worktree add -b "vibeguild/<handle>-<task>" "<new-authorized-path>"
```

Map the existing worktree with `call workspace`, then claim. Vibeguild neither creates
nor merges branches. If Git/repository is unavailable, report it; the human can select
shared-directory mode, which permits one editing task at a time. Do not mark editing
read-only to evade the lock. Read-only reviewers need no worktree. Pause does not kill
an owner's running command: wait for its actual checkpoint/stop before takeover.

## Votes and decisions

Inspect once when needed; vote thoughtfully or abstain if uninformed. Do not repeatedly
poll ballots or stall independent work. Closure is automatic at deadline or after EVERY
invitee including the human votes/abstains. Missing ballots are nonresponses; late joiners
do not join the electorate. Lead decisions can resolve disagreement, not grant external
or destructive permissions.

## Human profile administration

The owner-only `human_update` action takes `human_id` (the existing owner UUID) and
`name` (nonempty, at most 80 UTF-8 bytes). It changes the project-local display name,
not the UUID or mention handle. A `human_update` event and changed human metadata
reach agents through their next inbox. Agent credentials cannot invoke this action.
The human UI exposes it through the profile's Rename button. Do not use owner
credentials to bypass an agent's restrictions.

The owner's `note` command saves personal notes without a room or recipients.
They are separate from agent working notes and normal chat/search history. The UI
lists them in the human profile; readable projections live at
`vibeguild_files/humans/<human-UUID>/notes.txt`.

Human notes never arrive in agent inboxes, even when they contain @mentions.
Only read them when the human asks: use `inspect messages --key <note-UUID>` or
`fetch --message <note-UUID> --start <offset> --length <characters>` with your
normal agent/session identity. Broad `inspect messages` and `--query` searches
omit them. Retrieving one note does not subscribe you to future notes. This is
delivery behavior, not confidentiality from participants with local file access.
