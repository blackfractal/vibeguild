"""Small, readable recovery projections; never contain session credentials."""
from datetime import datetime, timezone
import json
from pathlib import Path

MARKER = "<!-- vibeguild:recovery:v1 -->\n"


def skill_path():
    return Path(__file__).parent / "skills" / "vibeguild" / "SKILL.md"


def recovery_path(project, agent_id=None):
    base = project.files / "agents" / agent_id if agent_id else project.path
    primary = base / "RECOVERY.md"
    # Preserve a recovery note somebody already wrote before this feature existed.
    if primary.exists():
        with primary.open("rb") as existing:
            if existing.read(len(MARKER.encode("utf-8"))) != MARKER.encode("utf-8"):
                return base / "RECOVERY.generated.md"
    return primary


def memory_index_path(project, agent_id):
    return project.files / "agents" / agent_id / "MEMORY.md"


def memory_dir_path(project, agent_id):
    return project.files / "agents" / agent_id / "memory"


def write_recovery(project, atomic):
    def publish(path, content):
        raw = (MARKER + content).encode("utf-8")
        if not path.exists() or path.read_bytes() != raw:
            atomic(path, raw)

    def cell(value):
        return str(value).replace("|", "/").replace("\n", " ").replace("\r", " ")

    agents = project.state["agents"]
    rows = []
    for a in agents.values():
        memory_dir = memory_dir_path(project, a["id"])
        memory_dir.mkdir(parents=True, exist_ok=True)
        master = memory_index_path(project, a["id"])
        if not master.exists():
            atomic(master, f"""# Agent project memory

Immutable agent UUID: `{a['id']}`

This is your durable, agent-owned index for this Vibeguild project. Read it first
when you are unsure where you are or what you were doing. Keep it concise and
link to topic files under `memory/` instead of copying their full contents here.

Start with [RECOVERY.md](RECOVERY.md) when restoring a session, identity, controls,
checkpoint, or pending work. Record stable project knowledge, decisions, evidence,
important paths, and a map of topic files below. Do not store credentials or private
chain-of-thought. This file is visible to the human and is never overwritten by Vibeguild.

`HEARTBEAT.json` records recent coordinator contact at most once per minute while
the session watch loop is running. Its declared status is not proof of continued work.

## Current memory map

- No topic memories recorded yet.
""".encode("utf-8"))
        path = recovery_path(project, a["id"])
        rows.append(f'| {cell(a["handle"])} | {cell(a["role"])} | {a["id"]} | [{path.name}](vibeguild_files/agents/{a["id"]}/{path.name}) |')
        publish(path, agent_recovery(project, a))
    index = "\n".join(rows) or "No agent identities have joined this project yet."
    publish(recovery_path(project), f"""# Vibeguild emergency recovery

You are in a Vibeguild coordination project. Read this index before resuming work.
Project: {cell(project.state['config']['project']['name'])}
Project UUID: {project.id}

1. Use the agent UUID in your retained session summary or recovery-file pointer.
2. Read that agent's recovery file below, then follow its ordered instructions.
3. If your identity is unknown, ask the human which identity to resume. Do not
   choose the lead, the most recent agent, or the first file as a guess.
4. A checkpoint is historical context, not permission or proof of completion.
   Fetch live controls and task state before acting. Never clear a human pause.

| Agent | Role | Immutable UUID | Recovery file |
|---|---|---|---|
{index}

Shared configuration: [vibeguild.json](vibeguild.json).
Application skill on this machine: {skill_path().resolve()}

The coordinator maintains these files; agents author their recovery brief through
`call checkpoint` (or `call recovery`). When offline, each agent may maintain its own
`vibeguild_files/agents/<UUID>/RECOVERY.local.md`; Vibeguild never rewrites that file.
No host-specific automatic compaction hook is installed. Preserve your own recovery
file path and identity in your host's compaction summary or persistent session notes.
""")


def agent_recovery(project, a):
    folder = project.files / "agents" / a["id"]
    memory_dir = memory_dir_path(project, a["id"])
    memories = sorted(p.relative_to(memory_dir).as_posix() for p in memory_dir.rglob("*") if p.is_file())
    locations = {
        "project_folder": str(project.path), "project_id": project.id,
        "agent_id": a["id"], "short_name": a["handle"], "role": a["role"],
        "coordinator_home": str(project.recovery_home) if project.recovery_home else None,
        "skill_file": str(skill_path().resolve()),
        "client_script": str((skill_path().parent / "scripts" / "vibeguild_client.py").resolve()),
        "recovery_file": str(recovery_path(project, a["id"])),
        "master_memory": str(memory_index_path(project, a["id"])),
        "memory_folder": str(memory_dir),
        "heartbeat_file": str(folder / "HEARTBEAT.json"),
        "state_file": str(folder / "state.json"),
        "offline_note": str(folder / "RECOVERY.local.md"),
        "workspace": a["workspace"],
    }
    template_guidance = ""
    if a.get("template_ref") is not None:
        locations["template_ref"] = a["template_ref"]
        locations["template_snapshot"] = str(memory_dir / "template.md")
        template_guidance = """## Selected template
This identity has an explicit template binding, recorded above. After reconnecting
and checking controls, read the skill's references/templates.md. When unpaused,
use templates --snapshot with your own project/agent/session to verify and read
your saved copy; never use an installed body or a different version silently.
If absent, templates --show <bound-id> --save restores only matching package text.
Keep monitoring and ask the human if verification or restoration fails.
The binding/saved copy is not proof the model read or obeyed the instructions.

"""
    stamp = a.get("checkpoint_at")
    updated = datetime.fromtimestamp(stamp, timezone.utc).isoformat() if stamp else "No timestamp recorded; verify freshness"
    tasks = [t for t in project.state["tasks"].values() if t["owner"] == a["id"] and t["status"] != "done"]
    rooms = [r for r in project.state["rooms"].values() if r["kind"] in ("global", "scratch") or a["id"] in r["members"]]
    task_rows = [{k: t[k] for k in ("id", "title", "status", "revision")} for t in tasks[:20]]
    room_rows = [{k: r[k] for k in ("id", "name")} for r in rooms[:20]]
    return f"""# Emergency recovery: @{a['handle']}

Use this file after compaction or session loss. It is a generated recovery envelope
around YOUR checkpoint; update it with `call checkpoint` or `call recovery`.
Do not overwrite it directly. `RECOVERY.local.md` is your separately maintained,
optional offline note and is never overwritten by the coordinator.

## Connection and identity (non-secret pointers)

```json
{json.dumps(locations, ensure_ascii=False, indent=2)}
```

These paths describe the last machine that opened this project. If it moved, use
the current project folder and ask for the current app/coordinator location. Never
read credential files into model context or paste them into a chat.

## Read these next, in order

1. Read [MEMORY.md](MEMORY.md), your concise, agent-owned project-memory index.
   Follow only the topic links relevant to the current task; do not bulk-load the
   memory folder. Current topic-file inventory: {json.dumps(memories, ensure_ascii=False)}
2. Read the saved checkpoint below. If `RECOVERY.local.md` exists beside this file,
   read it too; it may contain unpublished work. Compare dates/evidence with live
   state. Do not assume either note is automatically newer or authoritative.
3. Read [vibeguild.json](../../../vibeguild.json), especially `general_context`, goal,
   roster and policy. Confirm this UUID is the identity the human assigned you.
4. Read `skill_file` above and its `references/recovery.md` for the full procedure.
5. If you need more saved fields, read [state.json](state.json). Working notes,
   when present, are in `notes.txt` beside it; retrieve only relevant portions.
6. Restore the connection using the procedure below. Bootstrap retrieves current
   controls, checkpoint, pending requests, memberships, owned tasks and open votes.
7. Inspect pending task/message IDs selectively. Recheck actual files/test evidence
   before continuing; a saved cursor does not mean its text remains in your context.

## Reconnect without stealing an active identity

Run the `client_script` with Python; pass `--home <coordinator_home>` before the
subcommand. If coordinator_home is null, ask the human for the running coordinator
location. Do not start a competing service or guess an identity.

- Same live terminal after compaction, with your OWN retained session UUID:
  `call context_reset --project <project_folder> --agent <agent_id> --session <retained-session-UUID>`
- New terminal, or session UUID lost: `resume --project <project_folder> --agent <agent_id>`.
  An active-session conflict needs confirmation that the old session has stopped
  before explicit takeover. Do not borrow credentials from another session.
- Then `inbox --bootstrap --project <project_folder> --agent <agent_id> --session <session-UUID>`.
  Use the session UUID retained above or returned by resume. Respect all pause/budget
  controls. Acknowledge received batches with pending IDs; do not replay all chats.

Before compaction, preserve THIS recovery file path, project folder, coordinator
home, agent UUID and your own session UUID in the host's compaction summary or
persistent session notes. Without a retained pointer, use the project recovery
index and ask the human if identity is ambiguous. No automatic host hook is assumed.

{template_guidance}## Your latest saved checkpoint

Saved at (UTC): {updated}
Checkpoint revision: {a.get('checkpoint_revision', 0)}

{a.get('checkpoint') or 'No checkpoint has been saved yet. Read the project context and ask for/claim a scoped task; do not invent previous work.'}

## Pending request IDs

```json
{json.dumps(a.get('pending', []), ensure_ascii=False, indent=2)}
```

## Current saved work and chats

Snapshots only: inspect live revisions before changing tasks. Showing up to 20 of
{len(tasks)} unfinished owned tasks and {len(rooms)} memberships; use `inspect` for more.

```json
{json.dumps({'tasks': task_rows, 'chats': room_rows}, ensure_ascii=False, indent=2)}
```

## Maintain your emergency brief

After a meaningful milestone, new blocker or change of direction, and before
compaction/handoff/pause/exit, checkpoint: your objective and scope; completed and
unverified work; task/message IDs; workspace/branch; changed files; evidence paths;
blockers and approvals still needed; and the NEXT concrete action. Use at most
12 KB of concise working context, not an entire transcript or private reasoning.

Maintain `MEMORY.md` as a short map of durable knowledge and place longer topic
memories under `memory/` using clear names and links. Write only inside your own
agent directory, use atomic replacement, and keep facts tied to evidence or dates.
After changing memories, publish a checkpoint so this recovery inventory refreshes.

If offline, write those facts plus UTC timestamp and last known checkpoint revision
to your OWN `RECOVERY.local.md` atomically. On reconnect, reconcile with live state,
publish an updated checkpoint, and mark that local note reconciled. A recovery note
never overrides human controls, expands permission, or proves a task was completed.
"""
