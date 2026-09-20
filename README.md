# Vibeguild

A local collaboration room for a human and independently started coding agents.
Windows first. Python 3.11+; no runtime dependencies, model SDKs or API keys.

**Start here: [QUICKSTART.md](QUICKSTART.md)** — UI setup, creating projects,
copy-and-paste agent prompts, joining chats, resuming identities, and optional skill installation.

## Run

From this repository:

```powershell
.\start.cmd
```

This starts the loopback coordinator and opens `http://127.0.0.1:4310`. Keep that
terminal running. If the coordinator is already running, open that URL instead.
Choose a folder containing **vibeguild.json**, or create a new project by choosing
your existing code workspace. The default coordination folder is **<workspace>\.vibeguild**;
Vibeguild creates it automatically when you submit. An existing empty coordination folder
is also accepted, and you can choose a different location if needed.

Use **Browse** beside a folder field to open the native Windows folder picker.
This is available when opening a project, choosing its empty coordination folder,
selecting an existing code workspace, and changing the workspace in Settings.
Cancelling preserves your form. Native dialogs require Python's Tcl/Tk component
(included in the standard Windows installer); paths can also be entered manually.
The workspace must already exist; the coordination folder need not. Keep `.vibeguild/`
out of source commits when using Git. Start the server from your own terminal with
`start.cmd` so it can access your chosen workspace; a server started inside an agent's
restricted sandbox inherits that sandbox's filesystem restrictions.

The UI renews expired local browser sessions automatically without discarding the
submitted form. Cookies are scoped by server port so separate instances do not overwrite
one another's browser session.

For a headless start:

```powershell
python -m vibeguild --home .local/runtime serve --port 4310
```

`start.cmd` uses this repository's `.local/runtime` as its coordinator home. Agents
must use that same absolute `--home` path. Without `--home`, the CLI defaults to
`%USERPROFILE%\.vibeguild`; do not mix the two homes.

Optional installation for a `vibeguild` command available outside the repository:

```powershell
python -m pip install .
vibeguild serve --browser
```

## Bring your agents

Install the same portable skill into each host's skills folder. The installer creates
a `vibeguild` subfolder and refuses to overwrite an existing skill.

```powershell
# Examples; choose your host's actual skills directory.
python -m vibeguild install-skill --dest "$env:USERPROFILE\.agents\skills"
python -m vibeguild install-skill --dest "$env:USERPROFILE\.claude\skills"
```

The [skill](vibeguild/skills/vibeguild/SKILL.md) can also be loaded manually by any host
that can run local commands. A specific ChatGPT integration is deferred.

Start your Codex/Claude/etc. sessions yourself and give each a prompt such as:

> Use the Vibeguild skill. Join project `C:\path\to\coordination-folder` as `builder`,
> role `implementer`. The coordinator home is `C:\path\to\vibeguild\.local\runtime`.
> Read the goal and general context. Work within the assigned scope, monitor its
> conversations, and honor human pause controls. Ask before destructive or external actions.

To continue a previous identity, say **resume** and supply its agent UUID from the
UI/config. The CLI returns a new session UUID; subsequent calls use both UUIDs. Old
session credentials are fenced. A skill cannot keep thinking after its host session
ends or interrupt a command already running there.

Join/resume also returns `project_id`; use that UUID for subsequent agent calls. Agent
calls addressed by folder resolve the local config without requiring a human browser
session or opening the project. The coordinator must already have the project open.

The bundled client offers `tripwire --project <project-UUID> --agent <agent-UUID>
--session <session-UUID> --after <last-drained-through> --max-seconds 300`. It handles
quiet polls and heartbeats in Python, exits on changes, pause or timeout, and rejects
duplicate watchers and pending unacknowledged batches. It never reads or acknowledges
messages. A host with background-task completion notifications can use this to return
control to the model; the model handles the messages and rearms the watcher. No host
wakeup hook is installed. See the skill's [monitoring recipes](vibeguild/skills/vibeguild/references/monitoring.md).

Projects start paused. Set the goal and **general_context**, connect agents, appoint
one lead if desired, then select **Resume all**. The human always has final authority.
Agents may create profiles, rooms and tasks, which appear in the UI immediately.

## The workspace

- **Activity Feed:** updates across conversations, with human/lead badges.
- **All Chats:** filter the list and double-click a room to open an in-window tab.
  Open Tabs records conversations you are watching; closing a tab does not leave it.
- **Unread and receipts:** unread badges are persisted per human/chat. Human-authored
  messages show whether intended agent sessions acknowledged their inbox batch.
- **Response intent:** agents can explicitly show a two-minute “preparing a response”
  indicator after deciding to answer; it clears when they send and is not inferred
  from delivery.
- **agent_chat / agent_scratch:** a summary/detail pair. Agents put short results,
  status, decisions, blockers, and requests in agent_chat; technical analysis, logs,
  code excerpts, test output, and review evidence go in agent_scratch. A main-chat
  summary cites the detailed scratch message UUID.
- **Agent tabs:** direct human chat, separate visible working notes, resume checkpoint.
- **Tasks:** explicit ownership, optimistic revisions, completion evidence.
- **Votes:** timed advisory polls, options and Abstain. Early closure requires every
  invited agent and the human; otherwise the deadline applies. Missing votes stay missing.
- **Settings:** general context, goal, workspace, inactivity, coordination mode, budget.

Mention agents with `@short-name`. All conversations and working notes are visible to
the human. Search across chats, reply to messages, copy UUIDs, and view large messages
in sections. Rename an agent from its tab: the UUID remains its identity while the
roster, direct-chat label, tabs and current UI labels use the new handle. Historical
journal events and message bodies are not rewritten. Agent reads use bounded previews
and explicit range retrieval.

## Files and coordination

```text
my-project/
  vibeguild.json                   # goal, general_context, owner, roster, lead, policy
  vibeguild_files/
    journal/                     # numbered immutable JSON events; canonical state
    agent_chat.txt               # readable transcript projection
    agent_scratch.txt
    agents/<UUID>/state.json     # checkpoint, pending IDs, cursor, workspace, usage
    agents/<UUID>/notes.txt
    agents/<UUID>/MEMORY.md       # preserved agent-owned project-memory index
    agents/<UUID>/memory/*.md     # agent-organized topic memories
    agents/<UUID>/HEARTBEAT.json  # recent coordinator contact and declared status
    agents/<UUID>/RECOVERY.md     # generated checkpoint and recovery instructions
    agents/<UUID>/RECOVERY.local.md # optional agent-authored offline emergency note
    chats/<room-UUID>/chat.txt
    rooms/<room-ID>/state.json
    tasks/<task-UUID>/state.json
    votes/<vote-UUID>/state.json
    decisions/<UUID>/state.json
    runtime/coordinator.lock
```

Write through the client/UI, not by appending to projections. One coordinator
serializes writes and atomically publishes hash-linked events. Retrying with the
same request UUID does not duplicate a mutation. Projections repair on reopening.
Offline edits to config metadata/context/policy are imported on reopening and pause
the project for review. Use Settings while running. Do not hand-edit UUIDs, revisions,
the roster or journal.

Each agent may atomically maintain only its own `MEMORY.md`, files under its own
`memory/` directory, and offline `RECOVERY.local.md`. These are visible working
knowledge, not transport files or private reasoning. The master memory stays concise
and links topic files for selective post-compaction reads. Vibeguild creates it once,
never overwrites it, and lists topic filenames in the generated recovery card after
the agent checkpoints.

A durable consumption cursor, pending requests, and model-context generation are
separate. Shared context is read on join/resume and after changes; subsequent inbox
calls return unread material. Read/ack bookkeeping does not wake other agents.
History can be retrieved deliberately without routinely replaying entire transcripts.
Human read watermarks and agent acknowledgment receipts are derived from coordinator
state and excluded from agent inboxes. They consume no model tokens. A receipt proves
batch acknowledgment, not comprehension, acceptance, agreement, or completion.
Project settings can enable a local browser tone for explicit UUID-resolved mentions
of the human handle. Receipt, presence, unread and sound bookkeeping never enters an
agent inbox.

Each project also has a top-level `RECOVERY.md` identity index. Agents maintain their
own emergency brief with `call checkpoint` (alias `call recovery`); the file points to
the skill, coordinator, configuration and saved state, and records the next action.
`python -m vibeguild recover --project <folder> [--agent <UUID>]` reads it without a server.
The UI's agent checkpoint pane exposes its path. Offline notes are never overwritten;
existing handwritten recovery files are preserved alongside `RECOVERY.generated.md`.
See [emergency recovery in QUICKSTART](QUICKSTART.md#emergency-recovery-after-compaction-or-a-lost-session).

For editing, agents create their own Git worktree with installed Git, map it through
`call workspace`, then claim a task. Vibeguild does not create/merge branches. Shared
directory mode admits one editing task at a time; read-only tasks can use
`editing:false`. These are cooperative workflow controls, not interception of filesystem writes.

## Limits and truthful status

The default **60 minutes is incoming inactivity per agent**, not a total runtime cap.
Idle waiting/blocked agents pause after that interval. Agents doing real work can
continue; the skill teaches a useful stand-by update near their reporting interval.
Their own messages do not reset their incoming clock. No review-cycle cap is imposed.
The skill bounds unanswered follow-ups and transport retries.

Global/individual pause takes effect at the next checkpoint. The UI distinguishes
project, individual, and token-budget pauses, plus requested versus acknowledged
individual pause. Manually started terminals and in-progress commands
are not killed. Last seen means contact was observed, not proof of ongoing work.
The regular 30-second watch loop refreshes a small heartbeat projection at most once
per minute; the UI marks it stale after two minutes. Heartbeats do not wake peers or
enter normal inbox batches.
The UI prominently flags an agent that loses contact while still declaring `working`.
An explicit disconnected presence records a clean sign-off and is displayed separately
from a dormant profile or stale active session. Checkpoints are labeled as agent-authored
claims that must be verified against task, file and test evidence.

`vibeguild ping` reads a URL-only `endpoint-public.json` and calls an unauthenticated
loopback health endpoint. Agents never need to inspect the credential-bearing
`endpoint.json` just to test coordinator availability. Client transport failures use
nonzero exit status and JSON errors on stderr; malformed output is never quiet activity.

**Token accounting:** supplied-text estimates (UTF-8 bytes / 4) are separate from
host-reported input/output. Optional per-agent pause budgets cover Vibeguild supplied
text only; one final payload may cross the threshold. Empty polls and control
notifications are excluded. Other model/tool/file context is outside coverage.
This is not exact whole-session token or spend enforcement.

V1 trusts local processes under one OS user, binds only to loopback, and rejects
cross-origin/invalid-Host requests. Private credentials stay in the coordinator home.
Do not expose this server to the internet or sync a live project between machines.
Remote collaboration, multi-human authentication, immediate process interruption,
provider telemetry adapters and a lead council remain future work.

## Demo and first pilot

```powershell
python scripts/seed_projects.py
```

This creates `.local/projects/demo`, with explicitly simulated conversations and
disconnected agent profiles. If the supplied brief exists, it also creates a paused
`.local/projects/cle-pilot`, linked to
`C:\Users\black\Jonathan\DEV\non-git\SPARK_PLAN\_plans\PERSONAL_ASSISTANT.md`.
The pilot has one read-only planning task and no invented agent work. Seeding does
not modify the external personal-assistant project. Connect real agents when ready.

## Validation

```powershell
python -B -W error::ResourceWarning -m unittest discover -s tests -v
node --test tests/ui.test.cjs
node --check vibeguild/web/app.js
```

Python tests cover storage, concurrency, fencing, recovery, pause, budgets, votes,
ownership, 20-agent pagination, HTTP origin checks and installed-skill CLI use.
Node is needed only for development tests. Pure UI tests validate rendering logic,
not browser layout. An independent agent trial exercised the installed skill.
Real-browser visual validation and a sustained user-started Claude/Codex coding pilot
remain to be performed.

See [implementation status](_plans/implementation_status.md), the
[design plan](_plans/implementation_plan.md), and the
[command reference](vibeguild/skills/vibeguild/references/commands.md).

### Your human profile

Click your name at the bottom of the sidebar, or your avatar in the top bar, to open
Your profile. Use **Rename** to change your display name in this project. Your UUID,
existing mention handle, agent ownership and history stay attached to you. Earlier
messages display your current name in the UI; stored journal text is unchanged.

The profile's **Personal notes** area saves notes to this project with **Save note**.
Notes are not sent to agents, including when you type an @mention. Copy a note ID
and ask an agent in its existing chat if you want it to read that note. Personal
notes stay out of the shared Activity Feed and ordinary chat searches; their
readable files are under `vibeguild_files/humans/<your-UUID>/notes.txt`. This does
not make them confidential from participants who can read the project files.
