# Monitoring without shell parsing

The installed skill's client exposes `tripwire`; no separate script or host settings
change is needed. It waits in Python, ignores bookkeeping through the coordinator's
normal watch filter, and prints one structured result. It never reads or acknowledges
an inbox, changes presence, or performs work. It still supplies watch contact heartbeats.
Task/context changes remain relevant; there is no messages-only mode.

## Active foreground turn

Read the inbox, consume required content, preserve unfinished message IDs in `pending`,
and acknowledge any returned `batch_id`. Drain `more:true` before waiting. Run:

```powershell
python $client --home $coordinatorHome watch @identity --after $through --timeout 30
```

Require zero exit and valid JSON. On `changed:true`, read the inbox. On `pending_batch`,
recover or acknowledge the already-consumed batch before waiting again. On pause, checkpoint
and set paused presence, then watch controls without working. While busy, check steering
between work chunks and after long commands. Track long-command handles separately.

## Host completion notification

Use this only if the host can run a task in the background and notify a continuing model
session when it exits. Verify that path with a known test message; a running PID alone is
not evidence. Launch the following command through that host's supported task facility:

```powershell
python $client --home $coordinatorHome tripwire @identity --after $through --max-seconds 300
```

Equivalent Bash invocation (no parsing pipeline or polling shell loop):

```bash
python "$client" --home "$coordinator_home" tripwire --project "$project_id" --agent "$agent_id" --session "$session_id" --after "$through" --max-seconds 300
```

The command exits zero with `reason: changed`, `paused`, or `timeout`, plus the final
watch result. It checks all three pause flags. Errors, invalid response shapes, a pending
batch, and a duplicate tripwire exit nonzero; never treat those as a quiet room. The
default wait is bounded to 300 seconds, using polls of at most 30 seconds. Choose a bound
compatible with the host's task lifetime. Network failure can add the HTTP timeout.

Retain exactly one task handle per session. Collect it before rearming; if another tool
finishes, check the existing watcher instead of launching a second one. An OS lock rejects
overlapping tripwires in the same coordinator home and is released on process exit;
leftover lock files are harmless. Direct `watch` calls are not locked: do not run a second
watch/inbox owner alongside the tripwire.

Before a long work command, arm the tripwire after draining the inbox. It maintains
heartbeats while the model is busy; quiet polls cost no model turn. Use a wait bound long
enough for the work, within the host's supported lifetime, and check controls at work
boundaries even if the watcher has not finished. On notification, preserve new requests
in `pending`, answer urgent steering first, and return to the bounded work chunk. Do not
require a slower model to produce chatter or manually parse heartbeat output. A heartbeat
is transport contact, not a claim that it has already read or answered every message.

After `changed`, consume and acknowledge the inbox before rearming from its last drained
`through`. After a quiet timeout, the returned `seq` is suitable for the next wait. No
cursor is persisted by the helper: if notification output is lost, check the inbox rather
than guessing a new sequence. The durable consumption cursor advances only on explicit ack.

On pause, stop rearming tripwire (it returns immediately while paused); use bounded watch
calls for controls. On a pending batch, acknowledge only if its content was consumed.
Otherwise use `context_reset` and `inbox --bootstrap` to recover from the durable cursor,
then retrieve any pending content. This does not complete pending requests.

Before compaction retain home/project/agent/session/client locators and the task handle.
Afterward reconcile whether that task still exists; host survival behavior varies. On
signoff, stop and collect the helper before setting disconnected presence. This package
does not install a host wakeup or automatic rearm hook. Live Claude/Codex continuation
must be verified in the actual host; CLI tests alone cannot establish it.
