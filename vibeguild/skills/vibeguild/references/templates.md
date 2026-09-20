# Optional agent templates

Templates supplement this skill with one working style for one agent UUID. They do
not change the host system prompt, permissions, pause controls or human authority.
The free-text role remains independent. Missing or null `template_ref` means no
template: use the base skill without loading template resources. Never infer a
selection from a role, handle, task, or the existence of these files.

Use the same client and coordinator `--home` as the rest of the session. The
installed Python launcher and `vibeguild` command share the implementation.

## Select explicitly before joining

`templates` lists only IDs, titles and summaries from the running coordinator. The
catalog contains conservative-engineer, creative-designer, adversarial-reviewer and
defensive-reviewer. Map a natural-language request such as "adversarial reviewer"
through the catalog title to its canonical ID; clarify if the match is ambiguous.
Select only the requested canonical slug. A request for a
general reviewer *role* can use `--role reviewer` without a template. An explicit
request for an unavailable general-reviewer *template* needs clarification; do not
silently substitute another template or join untemplated.

```powershell
python $client --home <home> templates
python $client --home <home> join --project <folder> --handle <name> --role <role> --provider <host> --template conservative-engineer
```

The coordinator binds `{id, sha256}` at registration. Retain the returned
`template_ref` alongside the identity. The human can instead choose an optional
template in **Add agent**, then have you resume that UUID. Existing identities
cannot switch templates; there is no stacking, custom path, or override mechanism.

## Load your bound version, after controls

Read the normal bootstrap and all effective pause controls first. While paused,
defer loading/saving templates and task work; use the base pause/checkpoint loop.
Once unpaused, use the authenticated helper with your exact identity:

```powershell
python $client --home <home> templates --snapshot --project <project-UUID> --agent <your-UUID> --session <your-session-UUID>
```

This checks the saved `memory/template.md` under your own agent directory against
your binding, then returns its body. Read that verified body into context. A saved
copy with the bound digest remains valid even if a newer package has changed the
built-in. Resume and context recovery use this same verification path; a digest in
memory alone is not evidence that a body is still correct.

If the error is specifically a missing snapshot, fetch and save the selected body:

```powershell
python $client --home <home> templates --show <your-bound-id> --save --project <project-UUID> --agent <your-UUID> --session <your-session-UUID>
```

The helper obtains authenticated binding and memory location, checks the selected
coordinator body against the bound digest, and atomically saves UTF-8 text with LF
line endings and no BOM. It returns the verified body for you to read. It never
accepts an output path. Do not copy files yourself or load the installed markdown
as a substitute: the coordinator package is authoritative for the selected version.
After reading the verified body, link `memory/template.md` from your `MEMORY.md`
and checkpoint the binding and loading result. Preserve that locator through host
compaction; do this before template-specific task work.

A digest mismatch, corrupt/unreadable copy, path-confinement failure, or save error
must be reported and checkpointed as a template-loading blocker. Do not overwrite a
corrupt copy, silently accept the newest package, drop the binding, or claim the
template was loaded. Ask the human to resolve the bound version while continuing
only the base coordination needed to recover. A matching saved copy needs no repair.

## Explicit inspection

`templates --show <slug>` is a credential-free explicit read of the current built-in
body. It does not bind an identity, save a snapshot or authorize template task work.
Use metadata for selection; do not read all bodies as routine session context.
Packaged markdown copies are human documentation, not an alternate loading source.

The human's profile **Template** pane shows the exact bound instructions when
available: **Verified saved copy**, **Assigned; saved copy not available**, or
**Bound instructions unavailable**. The latter shows no replacement body. These
states describe files and binding verification, never proof that a model loaded or
obeyed the instructions. Peers receive binding metadata only through normal inboxes.
