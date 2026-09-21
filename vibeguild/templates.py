"""Allowlisted built-in templates and version-checked, confined snapshots."""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
from pathlib import Path

BODY_LIMIT = 16 * 1024
SHIPPED_LIMIT = 3072
CATALOG_LIMIT = 16 * 1024
TEMPLATE_ROOT = Path(__file__).parent / "skills" / "vibeguild" / "references" / "templates"
CATALOG = (
    {"id": "conservative-engineer", "title": "Conservative engineer", "summary": "Make the smallest complete change while preserving existing behavior."},
    {"id": "creative-designer", "title": "Creative designer", "summary": "Explore distinct approaches and reduce the key design uncertainty."},
    {"id": "adversarial-reviewer", "title": "Adversarial reviewer", "summary": "Challenge design premises with concrete counterexamples and alternatives."},
    {"id": "defensive-reviewer", "title": "Defensive reviewer", "summary": "Trace compatibility and failure paths to find reproducible regressions."},
    {"id": "arbitrator", "title": "Arbitrator", "summary": "Weigh competing viewpoints, clarify evidence gaps and reach a reasoned outcome."},
)


def catalog():
    items = [dict(item) for item in CATALOG]
    if len(items) > 32 or len(json.dumps(items).encode("utf-8")) > CATALOG_LIMIT:
        raise ValueError("Template catalog exceeds its metadata limit")
    return items


def metadata(template_id):
    if not isinstance(template_id, str) or not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", template_id):
        raise ValueError("Invalid template id; use a canonical catalog slug")
    item = next((item for item in CATALOG if item["id"] == template_id), None)
    if item is None:
        raise ValueError("Unknown template: " + template_id)
    return dict(item)


def canonical_body(body):
    if not isinstance(body, str):
        raise ValueError("Template body must be UTF-8 text")
    raw = body.removeprefix("\ufeff").replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
    if not raw.strip() or len(raw) > BODY_LIMIT:
        raise ValueError("Template body must be nonempty and at most 16 KiB")
    return raw


def read_body(path):
    with Path(path).open("rb") as stream:
        raw = stream.read(BODY_LIMIT + 1)
    if len(raw) > BODY_LIMIT:
        raise ValueError("Template file exceeds 16 KiB")
    return canonical_body(raw.decode("utf-8"))


def selected(template_id):
    item = metadata(template_id)
    raw = read_body(TEMPLATE_ROOT / (template_id + ".md"))
    return {**item, "body": raw.decode("utf-8"), "sha256": hashlib.sha256(raw).hexdigest()}


def bind(template_id):
    if template_id is None:
        return None
    content = selected(template_id)
    return {"id": content["id"], "sha256": content["sha256"]}


def binding_fields(agent):
    ref = agent.get("template_ref")
    return {"template_ref": dict(ref)} if ref is not None else {}


def validate_binding(ref):
    if not isinstance(ref, dict):
        raise ValueError("This identity has no template binding")
    metadata(ref.get("id"))
    if not isinstance(ref.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", ref["sha256"]):
        raise ValueError("Invalid template digest")
    return ref


def verified_body(body, ref):
    validate_binding(ref)
    raw = canonical_body(body)
    if hashlib.sha256(raw).hexdigest() != ref["sha256"]:
        raise ValueError("Template digest mismatch; keep the bound version and ask the human")
    return raw


def snapshot_path(memory_folder):
    # The authenticated coordinator supplies this folder; no caller-selected output.
    memory = Path(memory_folder).absolute()
    root = memory.parent
    if memory.name != "memory" or root.resolve() != root:
        raise ValueError("Invalid agent memory root or redirected agent directory")
    target = memory / "template.md"
    if not target.resolve().is_relative_to(root):
        raise ValueError("Template snapshot escapes its agent directory")
    return target


def read_snapshot(memory_folder, ref):
    validate_binding(ref)
    path = snapshot_path(memory_folder)
    raw = read_body(path)
    return verified_body(raw.decode("utf-8"), ref).decode("utf-8")


def save_snapshot(memory_folder, ref, body):
    raw = verified_body(body, ref)
    path = snapshot_path(memory_folder)
    path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path(memory_folder)  # Recheck after directory creation.
    temporary = path.with_name(path.name + "." + secrets.token_hex(6) + ".pending")
    try:
        with temporary.open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        snapshot_path(memory_folder)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return str(path)


def profile_template(agent, memory_folder):
    ref = agent.get("template_ref")
    if ref is None:
        return {"template_ref": None, "state": "none"}
    result = {"template_ref": dict(ref)}
    try:
        result.update(metadata(ref["id"]))
        validate_binding(ref)
        try:
            body = read_snapshot(memory_folder, ref)
        except FileNotFoundError:
            # A dangling link is a broken snapshot, not an absent one.
            if (Path(memory_folder) / "template.md").is_symlink():
                raise ValueError("Template snapshot is a broken link")
            content = selected(ref["id"])
            body = verified_body(content["body"], ref).decode("utf-8")
            return {**result, "state": "assigned", "body": body}
        return {**result, "state": "saved", "body": body}
    except (OSError, ValueError, KeyError) as exc:
        return {**result, "state": "unavailable", "error": str(exc)}

