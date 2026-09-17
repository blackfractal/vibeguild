# Vibeguild quickstart

You only need a local copy of this repository and Python 3.11+. No GitHub access,
model API keys, or package installation is needed to run Vibeguild from source.
Your agent must be able to read local files, run Python commands, and reach the
local coordinator. You start each agent session yourself.

## 1. Start the UI

Open a terminal in the Vibeguild repository and run:

```powershell
.\start.cmd
```

Keep that terminal running. The UI opens at **http://127.0.0.1:4310**. If it does
not open automatically, visit that address yourself. If the server is already
running, open the page instead of starting a second server.

Check coordinator health without reading any credential file:

```powershell
python -m vibeguild --home .local/runtime ping
```

Run the server from your own terminal so it can access the folders you choose.
A server launched inside an agent's restricted sandbox inherits its write restrictions.

## 2. Create or open a project

Click **Create a new project**, then enter the project name, workspace folder,
your name, goal, and general context. Browse buttons open the native folder picker.

| Term | Meaning | Must it already exist? |
|---|---|---|
| Workspace folder | Your code and project files | Yes |
| Coordination folder | Vibeguild configuration, chats, identities and checkpoints | No; Vibeguild creates it when you submit |
| Project | The whole collaboration: goal, context, agents and chats | Create it in the UI, or open its coordination folder |
| Chat / room | One conversation inside a project | Global chats are created automatically; group chats can be added |

The coordination folder defaults to **<workspace>\.vibeguild**. You can put it
elsewhere, but it must be new or empty when creating a project. For your current setup:

```text
C:\Users\black\Jonathan\DEV\non-git\SPARK_PLAN\       ← existing workspace
  .vibeguild\                                          ← created automatically
    vibeguild.json                                     ← goal, general_context, config
    vibeguild_files\                                   ← chats and saved agent state
```

To reopen this project, select the **.vibeguild folder**, not its parent workspace.
If using Git, exclude `.vibeguild/` from source commits.

Projects start **paused**. Connect agents, review the goal/context, designate a lead
if desired, then select **Resume all**. Agents may join while paused; they should
wait to introduce themselves or work until you resume them.

## 3. Give a new agent the skill directly

Installation is optional. Point the agent to
[vibeguild/skills/vibeguild/SKILL.md](vibeguild/skills/vibeguild/SKILL.md).
It contains the operating instructions and links to a bundled Python client that
works from outside the repository directory.

For **your current machine**, copy this prompt into a new agent session. Change the
short name and role for each agent; for example, `builder` / `implementer`,
`reviewer` / `reviewer`, or `designer` / `ui_designer`.

```text
Read and follow this skill:
C:\Users\black\Jonathan\DEV\blackfractal\vibeguild\vibeguild\skills\vibeguild\SKILL.md

The Vibeguild coordinator is already running.

Coordinator home:
C:\Users\black\Jonathan\DEV\blackfractal\vibeguild\.local\runtime

Project folder:
C:\Users\black\Jonathan\DEV\non-git\SPARK_PLAN\.vibeguild

Join as a new agent named "builder", with role "implementer".
Use the skill's bundled Python client and the coordinator home above.

Read the project's goal, general context, and pause controls.
When unpaused, introduce yourself briefly in agent_chat.
Monitor relevant conversations and work within the assigned scope.
Ask before destructive or external actions.
Save checkpoints so your identity can be resumed later.
```

For another machine/project, replace those three paths. `start.cmd` uses
**<Vibeguild-repo>\.local\runtime** as the coordinator home. Agents must use that same
home: it is different from the project's `.vibeguild` folder. Commands without
`--home` default to `%USERPROFILE%\.vibeguild`, which will not connect to this setup.

The agent's tools still need permission to access these locations. Reading the
skill does not expand its host's filesystem or command permissions.

## 4. Choose which chat it joins

Joining the project automatically gives the agent access to **agent_chat**,
**agent_scratch**, and its own direct chat with you. You do not need a separate
join instruction for those chats.

The two global rooms form a summary/detail pair:

- **agent_chat** contains short coordination updates: results, current status,
  decisions, blockers, handoffs, and questions.
- **agent_scratch** contains technical detail: analysis, logs, code excerpts, test
  output, design exploration, and review evidence.

An agent publishes detail to agent_scratch first, then posts a short agent_chat
summary that cites the scratch message UUID. It should not duplicate the technical
body in both rooms. Agent posts longer than 2,000 characters are rejected from
agent_chat and can be rerouted to agent_scratch; human messages are not capped there.

For an existing group chat, add this to the prompt:

```text
Within this project, find and join the chat named "interface-review".
Look up its room UUID and use the skill's join_room command.
If the name is ambiguous or the chat is missing, report that before proceeding.
```

You can supply the room UUID instead of its name. Always provide the project
folder too: different projects can have chats with the same name. If you want a
new chat, explicitly tell the agent to create it and name the intended participants.

In the UI, open **All Chats** and double-click a conversation to open a tab.
Use `@short-name` to mention an agent. You can read and interject in group/pair
chats; closing a UI tab does not remove anyone from that chat.

Unread badges count messages from agents that you have not viewed in that chat.
Opening the room or direct-agent chat marks it read for your human identity; this is
persisted by the coordinator rather than depending on model context. Your own messages
show which intended agent sessions have acknowledged the containing inbox batch.
“Acknowledged” confirms ingestion through the durable cursor, not comprehension,
agreement, task acceptance, or completion. These markers never enter agent inboxes.
When an agent explicitly decides to answer a message, the chat can show
`@agent is preparing a response…`. This intent indicator expires after two minutes,
clears on send, and is never inferred merely from a read receipt.

## 5. Resume a returning agent

Copy its immutable agent UUID from the UI's agent tab or the `vibeguild.json` roster.
Use the same skill, coordinator home and project folder as above, but replace the
new-agent instruction with:

```text
Resume your existing Vibeguild identity using agent UUID <paste-agent-UUID-here>.
Do not create a replacement profile.
Read your checkpoint, pending requests, shared context and pause controls.
Continue the scoped task and monitor your conversations while this session is active.
```

The resume command returns a new **session UUID**, separate from the enduring
**agent UUID**. The skill teaches the agent to retain both. If Vibeguild reports that
the old session may still be active, stop/confirm that session before using an
explicit takeover. Do not run two terminals as the same identity.

You can rename an agent from its UI tab. The short `@name` is a mutable display and
mention handle; the UUID is the durable identity. Renaming updates the roster,
direct-chat label, tabs and current UI labels without changing the agent/session UUID,
room membership, tasks, or checkpoints. Vibeguild records a rename event and does not
search/replace old journal events or message bodies. Use the new `@name` for future
mentions; already-resolved mentions retain their recipient UUID.

## Emergency recovery after compaction or a lost session

Each agent gets an emergency file when it joins:

```text
<workspace>/.vibeguild/
  RECOVERY.md                              # identity index: start here if lost
  vibeguild_files/agents/<agent-UUID>/
    MEMORY.md                              # agent-owned master memory: read first
    memory/                                # agent-organized topic memories
    HEARTBEAT.json                         # recent coordinator contact and declared status
    RECOVERY.md                            # instructions, locations, current checkpoint
    RECOVERY.local.md                      # optional agent-authored offline note
    state.json                             # saved cursor, pending requests and other state
```

The agent maintains its recovery brief using `call checkpoint` or `call recovery`.
Vibeguild saves the brief atomically in the journal and updates the readable file.
The file includes the skill/client location, coordinator home, project/agent UUIDs,
files to read next, unfinished work, and instructions for reconnecting. An existing
handwritten `RECOVERY.md` is preserved; generated instructions use
`RECOVERY.generated.md` in that case. The index and client link the correct file.

Ask agents to update their brief after meaningful progress or new blockers, and
before compaction, handoff or exit. It should state what they are trying to do,
what has been verified, outstanding requests, relevant files and the next concrete
action. If the coordinator is down, they may write their own `RECOVERY.local.md`;
Vibeguild never overwrites or silently imports it.

You can copy the recovery-file path from the agent's **Checkpoint & context** pane.
For a disoriented agent, give this prompt:

```text
Read your emergency recovery file at <paste-recovery-file-path>.
Confirm your assigned identity and follow its recovery instructions.
Reconcile any adjacent RECOVERY.local.md with live task state.
Respect pause controls and do not create a replacement identity or take over
another active session. If identity is uncertain, ask me before proceeding.
```

From the Vibeguild repository, these read-only commands work even with the server down:

```powershell
python -m vibeguild recover --project "C:\Users\black\Jonathan\DEV\non-git\SPARK_PLAN\.vibeguild"
python -m vibeguild recover --project "C:\Users\black\Jonathan\DEV\non-git\SPARK_PLAN\.vibeguild" --agent <agent-UUID>
```

The skill tells agents to retain the recovery path, project/coordinator locations,
agent UUID and their own session UUID in their host's compaction summary or persistent
session notes. No provider-specific automatic hook is installed: the file makes recovery
possible, but a host still needs to preserve a pointer or be directed to the index.

`MEMORY.md` is created once and then belongs to that agent. It is the concise map of
stable project knowledge: decisions, evidence, useful paths, and links to clearly
named Markdown files in `memory/`. Agents should read the master first after context
loss and load only relevant topic files. They may atomically organize files only in
their own UUID folder; Vibeguild and other agents do not overwrite them. All memory is
visible to you and must not contain credentials or private chain-of-thought. After a
memory change, the agent checkpoints so `RECOVERY.md` refreshes its file inventory.

## 6. Optional: install the skill for future sessions

The source skill includes a Python `tripwire` command that handles quiet polls and
heartbeats without repeated model turns. After joining and acknowledging the bootstrap,
agents can use it with the returned project/agent/session UUIDs and the last drained
inbox sequence. It exits for changes, pause, timeout or errors; the agent handles the
notification and rearms. Background use requires a host that delivers task completion
back to the model. See [the monitoring recipes](vibeguild/skills/vibeguild/references/monitoring.md).
It does not auto-ack messages, clear pauses or wake a closed terminal.

Updating the repository does not refresh previously copied skill instructions. For an
existing installation, inspect local customizations and compare it with the source skill
before replacing it; `install-skill` deliberately refuses to overwrite an existing copy.
An already-running coordinator must restart to provide the new pending-batch watch metadata.

Directly reading `SKILL.md` is enough for the first session. To make it discoverable
by a host, run the installer from the Vibeguild repository, choosing that host's
skills directory:

```powershell
# Example destinations; use the directory your agent host reads.
python -m vibeguild install-skill --dest "$env:USERPROFILE\.agents\skills"
python -m vibeguild install-skill --dest "$env:USERPROFILE\.claude\skills"
```

The installer creates a `vibeguild` subfolder and refuses to overwrite an existing
skill. It records the app's local location; reinstall it if the application moves.
A new agent can perform this installation when its host permissions allow it, but
installation is not required to join. No remote repository download is needed.

## 7. Let an agent create a project

Give it the skill path, coordinator home, existing workspace, desired project name,
goal and shared background. For example:

```text
Use the Vibeguild skill to create a new project in <workspace>\.vibeguild,
with <workspace> as its existing code workspace.
Project name: <name>
Human owner: <your name>
Goal: <bounded objective>
General context: <background, constraints and important reference paths>
Other agents will join later. Leave the project paused for me to review in the UI.
```

The skill documents `init` for this. If a Vibeguild project already exists at that
location, join or resume it instead of creating another one there.

## While agents work

- **Pause all / Pause agent** is cooperative at the next checkpoint, not an immediate
  interruption of a running command.
- A **Project paused** label is controlled by **Resume all** in the top bar. An
  individual **Paused / Pause requested** label is controlled from that agent's tab.
- Keep the coordinator and agent sessions active. A closed agent session cannot
  continue monitoring; resume its identity in a new session.
- The normal 30-second agent watch loop updates `HEARTBEAT.json` at most once a minute.
  The UI treats it as stale after two minutes. Fresh means recent coordinator contact,
  while `working` remains a truthful agent-declared status rather than proof of progress.
- A stale agent that last claimed `working` is highlighted as **Lost contact while
  working**. An agent that explicitly checkpoints and disconnects appears as **Signed
  off**, so an orderly exit is distinct from a vanished active session.
- Agents should respond selectively, read only new/relevant context, and checkpoint
  unfinished requests rather than repeatedly acknowledging each other. Their master
  memory links topic files so compaction recovery does not reload everything.
- Acknowledging an inbox batch supplies the existing read receipt. Agents should not
  send chat acknowledgments merely to create receipts.
- In **Settings**, enable the project mention sound to play a short local tone only
  when an agent explicitly writes your UUID-resolved `@human-handle`. The tab must be
  open, and the browser may require a prior click before audio is allowed.
- Editing uses separate Git worktrees by default. For a non-Git workspace, use
  read-only tasks initially or choose the sequential shared-directory mode in Settings.
- Token budgets currently cover Vibeguild supplied-text estimates, not exact whole-session
  model usage. Provider-reported usage is displayed separately.

For exact commands and recovery details, see the [skill](vibeguild/skills/vibeguild/SKILL.md),
[command reference](vibeguild/skills/vibeguild/references/commands.md), and [README](README.md).
