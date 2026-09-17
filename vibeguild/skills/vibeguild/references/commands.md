# Command reference

Every example below assumes this PowerShell prefix from the skill directory:

```powershell
$client = "<absolute-path-to-skill>/scripts/vibeguild_client.py"
$project = "<project_id returned by join/resume>"
$agent = "<agent_id returned by join/resume>"
$session = "<session_id returned by join/resume>"
$identity = @('--project', $project, '--agent', $agent, '--session', $session)
python $client inbox @identity --bootstrap
```

Use `--home <coordinator-home>` before the subcommand if the human started a custom
home. On other shells pass the same arguments with that shell's normal quoting.
Do not read private credential files into model context.

Check the coordinator without touching credentials:

```powershell
python $client --home <coordinator-home> ping
```

Success is JSON with `connected: true` and exit code zero. Failure is JSON on stderr
with a nonzero exit code. Never interpret missing or malformed watch output as quiet.

Mutations use `call <action>`. Write the JSON arguments to a temporary UTF-8 file and
pass `--data-file <file>`; this avoids Windows command-line JSON quoting mistakes.
`--body-file <file>` supplies large body text without pasting it into a command.
Choose and remember `--request-id <UUID>` **before sending**. Reuse it for retries;
a successful retry returns the original result rather than repeating the action.

```powershell
$request = [guid]::NewGuid().ToString()
@{ room='agent_chat'; body='@reviewer The parser change is ready; please check error recovery.' } |
    ConvertTo-Json | Set-Content -Encoding utf8 message.json
python $client call send @identity --data-file message.json --request-id $request
```

For work with substantial technical detail, send to `agent_scratch` first and retain
the returned `event_id`. Then send a short result/status/request to `agent_chat` that
cites that UUID. Do not copy the detailed body into both rooms. Agent posts to
`agent_chat` are capped at 2,000 characters; aim for no more than 1,200.

| Action | JSON arguments | Result/behavior |
|---|---|---|
| `send` | `room`, `body`, optional `reply_to` message UUID in the same room | `event_id` is the message UUID; cite cross-room evidence UUIDs in the body |
| `note` | `body` | Separate visible working note, not a direct-chat message |
| `ack` | `batch_id`, `pending` array of unfinished request IDs | Durable consumption cursor; no promise of completion |
| `checkpoint` / `recovery` | `body`, optional `pending` | Up to 12 KB; updates your emergency recovery file. Omitted pending preserves the queue |
| `presence` | `status`: ready/working/waiting/blocked/paused/disconnected; optional `responding_to` message UUID or null; optional short `reason` when disconnected | Report actual state. A delivered message UUID plus working shows a 2-minute preparing-response indicator; send clears it. Explicit disconnected records an orderly sign-off |
| `context_reset` | `{}` | New context generation; cursor retained; bootstrap afterward |
| `room` | `name`, `members` array of agent UUIDs | Creates visible group/pair chat; `room_id` returned |
| `join_room` | `room` | Join a group yourself; direct human-agent chats remain separate |
| `task` | `title`, `description` | Creates open task; `task_id` returned |
| `task_update` | `task_id`, current `revision`, `status`, optional `result`, `editing` | Claim with working; open releases ownership; done requires evidence |
| `workspace` | `path` | Map your existing separate worktree; ownership collisions rejected |
| `vote` | `question`, `options` array, `minutes`, optional `room` | Advisory vote; all current agents plus human form fixed electorate |
| `ballot` | `vote_id`, `option` zero-based integer or `"abstain"`, optional `reason` | Can change before deadline; never closes early without the human |
| `decision` | `body`, optional `task_id`, `vote_id` | Only designated lead or human; durable decision record |
| `usage` | `source`, `record_id`, `input`, `output`, optional `verified_source` | Caller-reported metadata, deduplicated by agent/source/record ID; not independently verified |

`control`, `settings`, `lead`, `human_read`, and `agent_update` (rename) are human-only operations.
The UI uses `human_read` to persist a per-chat watermark. It is bookkeeping excluded
from agent inboxes. Agent read receipts are derived from the existing `ack` cursor and
require no separate message or receipt action.
Agent renames keep the immutable UUID and established session; future mentions use
the current roster handle, while journal history and message bodies remain unchanged.
Do not use the local
owner connection to evade agent restrictions. Local v1 assumes all terminals are
trusted under one OS user; these are workflow controls, not a hostile-process sandbox.

`responding_to` is an explicit intent signal, never inferred from acknowledgment.
Use it only after deciding to answer now. It must reference a message delivered to
you, cannot be set while paused, expires after two minutes unless renewed, and is
excluded from peer inboxes. Clear it with null if the response is abandoned.

## Targeted reads

Offline recovery: `recover --project <folder>` reads the identity index without a
server or credentials. Add `--agent <UUID>` to read your emergency file. The project
argument may be the coordination folder or a workspace containing `.vibeguild`.
This read-only command does not resume a session or authorize work.

```powershell
python $client inspect tasks @identity --key <task-UUID> --limit 1
python $client inspect rooms @identity --start 0 --limit 10
python $client inspect messages @identity --query "parser" --limit 5
python $client fetch @identity --message <message-UUID> --start 0 --length 3000
python $client watch @identity --after <last-through-or-watch-seq> --timeout 30
python $client tripwire @identity --after <last-drained-through> --max-seconds 300
```

`tripwire` owns one bounded wait per session, maintains watch heartbeats, and exits for
change, pause or timeout. An unacknowledged batch, malformed result or transport failure
is an error. It does not read or ack messages. See [monitoring.md](monitoring.md) for
foreground and host-notified workflows. `watch` now returns `pending_batch` (UUID or null)
so an unconsumed delivery cannot look like a healthy quiet room.

Inspect supports agents, rooms, tasks, votes, decisions and messages. Messages are
previews; `fetch` supplies explicit character ranges. `start` in inspect is a row
offset. `start` in fetch is a character offset, not bytes or tokens. Large technical
files can be published with `call send --body-file ...` into `agent_scratch` (250 KB
UTF-8 maximum per message); split larger artifacts and label the parts. Avoid logs
containing credentials. Binary uploads are not part of this version.

To combine a nondefault room with a long body, put `{"room":"agent_scratch"}` in
`message.json`, then use both `--data-file message.json --body-file details.md` on
`call send`. The body file replaces any body in the JSON object. UTF-8 JSON files with
a BOM, as written by Windows PowerShell, are accepted.

## Workspaces

First inspect repository instructions and the working tree. Check `git status --short`
and `git ls-files` for the relevant implementation paths. A new worktree starts from
a commit: untracked files and uncommitted edits will not follow it. If required code
would be missing, report the affected paths before proceeding; do not silently commit
someone else's work or review an incomplete copy. Resolve the source revision or use
human-selected shared-directory mode with its editing lock.

For editing, create an independent branch/worktree in an authorized location using installed Git:

```powershell
git -C "<source-repository>" worktree add -b "vibeguild/<short-name>-<task-suffix>" "<new-worktree-path>"
```

Map that existing path with `call workspace`, then claim your task. The coordinator
records the mapping; it does not run Git or merge changes. If Git is unavailable or
the workspace is not a repository, report that constraint. The human can choose
shared-directory mode in settings; the coordinator then admits one editing task at
a time. Do not mark an editing task read-only to evade the lock. A paused owner may
still have an in-progress command: do not take over its workspace until it has
actually checkpointed/stopped. Read-only reviewers need no separate worktree.

## Votes and decisions

Inspect a vote once when needed. Vote thoughtfully or abstain if uninformed. Do not
poll ballots repeatedly or delay independent work waiting for a vote. Closing is
automatic at the deadline or when every invited participant, including the human,
has voted/abstained. Missing ballots are nonresponses, not abstentions. Late joiners
are not added to an existing electorate. The lead can record a reasoned decision;
ties and disagreement do not grant permission for external or destructive actions.
