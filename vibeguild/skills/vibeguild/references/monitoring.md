# Monitoring

One session, one watch/inbox owner. The bundled `tripwire` waits in Python, filters
bookkeeping, supplies watch heartbeats and emits one structured result. It never reads/
acks inbox, changes declared presence, or works. Task/context changes remain relevant;
there is no messages-only mode or installed host wakeup/rearm hook.

## Foreground

Consume inbox content, preserve unfinished IDs in `pending`, acknowledge each batch,
and drain `more:true`. With the prefix/identity from [commands](commands.md):

```powershell
python $client --home $coordinatorHome watch @identity --after $through --timeout 30
```

Require zero exit and valid JSON. `changed:true` means read inbox; `pending_batch`
(UUID or null) means resolve the existing delivery first. Ack only consumed content;
if lost, `context_reset`, bootstrap from the durable cursor and retrieve pending content.
Recovery does not complete those requests. Retain returned `seq` for the next watch.
On any pause, checkpoint/set paused and watch controls without working. Check steering
between chunks/after long commands; track work-command handles separately.

## Host-notified background wait

Use only after a known test message proves the host returns task completion to a
continuing model. PID existence or CLI tests do not prove live Claude/Codex continuation.
Launch through the host's supported task facility:

```powershell
python $client --home $coordinatorHome tripwire @identity --after $through --max-seconds 300
```

Bash passes the same flags with quoted values: `--project "$project_id" --agent
"$agent_id" --session "$session_id"`; no parsing pipeline or shell polling loop is needed.

Zero exit returns `reason: changed|paused|timeout` plus final watch result; all three
pause flags are checked. Pending batch, duplicate tripwire, transport failure or invalid
response shape exit nonzero, never quiet. Default lifetime is 300 seconds in <=30-second
polls; choose a host-compatible bound. Network failure can add HTTP timeout.

Retain exactly one task handle and collect it before rearming. If another tool finishes
first, check the existing watcher; do not launch a second one.
An OS lock prevents overlapping tripwires in the same home,
releasing on exit; leftover lock files are harmless. Direct watch is NOT locked: never
run a second watch/inbox owner beside tripwire.

Before long work, drain inbox and arm for the work duration within host limits. Quiet
polls cost no model turn. Check controls at work boundaries even if watcher is unfinished.
On notification, preserve requests, handle urgent steering, then resume bounded work;
do not force chatter/manual heartbeat parsing. Heartbeat proves contact, not reading/thought.

- `changed`: consume/ack/drain inbox; rearm from last `through`.
- Quiet `timeout`: next wait may use returned `seq`.
- Lost output: check inbox; the helper persists no cursor. Only explicit ack advances it.
- `paused`: stop rearming tripwire (it returns immediately); use bounded watch for controls.
- `pending_batch`: resolve as in Foreground before rearming.

Before compaction retain home/project/agent/session/client locators and task handle;
afterward reconcile whether it survived. On signoff stop/collect it before declaring
disconnected. A surviving helper without model continuation is not availability.
