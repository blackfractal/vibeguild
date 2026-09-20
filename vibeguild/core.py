"""Single-writer project store. Published JSON events are the commit boundary.

The state and readable transcripts are projections, never competing write paths.
Only the coordinator owns Project instances. CLI clients use the HTTP API.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import re
import secrets
import threading
import time
import uuid
from pathlib import Path
from .templates import bind, binding_fields
from .recovery import memory_dir_path, memory_index_path, recovery_path, skill_path, write_recovery

PALETTE = ["#61d8bb", "#a69aff", "#f2b86b", "#77b9fc", "#ee8fa8", "#bdd977", "#dd9fec", "#69d4e3", "#ef9d71", "#a8b3ce", "#f3d375", "#80cbaa", "#b6a0df", "#ddac97", "#97c8d9", "#cec98c", "#e3a7c4", "#86b5a3", "#acaee8", "#dac2a2"]
DEFAULT_POLICY = {"agent_inactivity_minutes": 60, "working_status_interval_minutes": 60,
                  "working_status_lead_minutes": 5, "max_unanswered_followups_per_request": 1,
                  "max_transport_retries": 3, "token_budget": None, "inbox_max_bytes": 16000,
                  "coordination_mode": "worktrees"}
DEFAULT_NOTIFICATIONS = {"human_mention_sound": False}
COLLECTIONS = ("agents", "rooms", "tasks", "votes", "sessions", "decisions", "usage", "reads")
ROOM_GUIDANCE = {
    "agent_chat": "Coordination only: concise status, conclusions, decisions, blockers, and requests. Put technical detail in agent_scratch and cite its message UUID.",
    "agent_scratch": "Technical detail: analysis, logs, code excerpts, test output, and review evidence. Publish here first, then summarize and cite this message UUID in agent_chat.",
}


class Problem(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def uid():
    return str(uuid.uuid4())


def encoded(value):
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def atomic(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + secrets.token_hex(6) + ".pending")
    try:
        with temporary.open("xb") as out:
            out.write(value if isinstance(value, bytes) else encoded(value))
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def text(value, label="text", limit=100000):
    if not isinstance(value, str) or not value.strip() or len(value.encode("utf-8")) > limit:
        raise Problem(f"{label} must be nonempty text, at most {limit} UTF-8 bytes")
    return value.strip()


def handle_from_name(value):
    handle = re.sub(r"[^a-z0-9_-]+", "-", str(value).strip().lower()).strip("-_")[:24]
    return handle if re.fullmatch(r"[a-z][a-z0-9_-]{0,23}", handle or "") else "human"


def number(value, label, low=0, high=10000000):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or not low <= value <= high:
        raise Problem(f"{label} must be a number between {low} and {high}")
    return value


def validate_config(config):
    if not isinstance(config, dict):
        raise Problem("vibeguild.json must contain a JSON object")
    if config.get("schema_version") != 1:
        raise Problem("Unsupported vibeguild.json schema_version; expected 1")
    p = config.get("project", {})
    text(p.get("name"), "project name", 120)
    text(p.get("goal"), "project goal", 20000)
    text(p.get("workspace"), "external code workspace", 4096)
    if not isinstance(config.get("general_context", ""), str) or len(config.get("general_context", "").encode("utf-8")) > 12000:
        raise Problem("general_context must be text, at most 12000 UTF-8 bytes")
    try:
        uuid.UUID(p.get("id", ""))
    except (ValueError, TypeError, AttributeError):
        raise Problem("project.id must be a UUID")
    if not config.get("humans") or len(config["humans"]) != 1:
        raise Problem("Version 1 requires exactly one human owner")
    for human in config["humans"]:
        handle = human.get("handle", handle_from_name(human.get("name", "human")))
        if not re.fullmatch(r"[a-z][a-z0-9_-]{0,23}", handle):
            raise Problem("Human mention handles use lowercase letters, digits, underscores or hyphens")
    notifications = config.get("notifications", DEFAULT_NOTIFICATIONS)
    if not isinstance(notifications, dict) or set(notifications) - set(DEFAULT_NOTIFICATIONS):
        raise Problem("Unknown notification setting")
    if not isinstance(notifications.get("human_mention_sound", False), bool):
        raise Problem("human_mention_sound must be true or false")
    policy = config.get("policy", {})
    for key in ("agent_inactivity_minutes", "working_status_interval_minutes"):
        number(policy.get(key), key, 1, 10080)
    number(policy.get("working_status_lead_minutes"), "status lead", 0, 10080)
    number(policy.get("inbox_max_bytes"), "inbox_max_bytes", 2048, 64000)
    for key in ("max_unanswered_followups_per_request", "max_transport_retries"):
        value = number(policy.get(key), key, 0, 10)
        if not isinstance(value, int):
            raise Problem(key + " must be an integer")
    if policy.get("token_budget") is not None:
        number(policy["token_budget"], "token budget", 1)
    if policy.get("coordination_mode") not in ("worktrees", "shared"):
        raise Problem("coordination_mode must be worktrees or shared")
    return config


class FileLock:
    """Lifetime OS lock; a leftover lock file cannot impersonate a live owner."""
    def __init__(self, path, conflict="This project already has a coordinator"):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.file = open(path, "a+b")
        try:
            self.file.seek(0)
            if not self.file.read(1):
                self.file.write(b"0")
                self.file.flush()
            self.file.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.file.close()
            raise Problem(conflict, 409)

    def close(self):
        if not self.file.closed:
            self.file.close()


class Project:
    def __init__(self, path, clock=time.time):
        self.path = Path(path).resolve()
        self.files = self.path / "vibeguild_files"
        self.clock = clock
        self.lock = threading.RLock()
        self.changed = threading.Condition(self.lock)
        self.events, self.messages, self.requests = [], [], {}
        self.state = {k: {} for k in COLLECTIONS}
        self.file_lock = None
        self.recovery_home = None
        try:
            config = json.loads((self.path / "vibeguild.json").read_text("utf-8"))
            validate_config(config)
            if not self.files.is_dir():
                raise Problem("Missing vibeguild_files directory")
            self.file_lock = FileLock(self.files / "runtime" / "coordinator.lock")
            last = ""
            for file in sorted((self.files / "journal").glob("*.json")):
                event = json.loads(file.read_text("utf-8"))
                checksum = event.pop("checksum")
                if digest(event) != checksum or event["previous"] != last or event["seq"] != len(self.events) + 1:
                    raise Problem(f"Journal integrity failure: {file.name}; preserve files and restore a backup")
                event["checksum"] = checksum
                self._apply(event)
                last = checksum
            if not self.events:
                initial = {k: {} for k in COLLECTIONS}
                initial["config"] = config
                initial["control"] = {"paused": True, "reason": "Project ready. Start when the goal is authorized.", "revision": 1}
                initial["reads"][config["humans"][0]["id"]] = {"participant_id": config["humans"][0]["id"], "rooms": {}}
                for room in ("agent_chat", "agent_scratch"):
                    initial["rooms"][room] = {"id": room, "name": room, "kind": "global" if room == "agent_chat" else "scratch", "members": [], "created_at": clock()}
                self._commit("project_created", config["humans"][0]["id"], {"name": config["project"]["name"]}, initial)
            elif config["project"]["id"] != self.state["config"]["project"]["id"]:
                raise Problem("Config project UUID does not match its journal")
            elif config != self.state["config"] and config.get("revision", 0) >= self.state["config"].get("revision", 0):
                # Only policy/project metadata are externally configurable; immutable IDs/roster are protected.
                known = self.state["config"]
                safe = copy.deepcopy(known)
                safe["policy"] = config["policy"]
                safe["notifications"] = config.get("notifications", safe.get("notifications", copy.deepcopy(DEFAULT_NOTIFICATIONS)))
                safe["general_context"] = config.get("general_context", "")
                for key in ("name", "goal", "workspace", "reference"):
                    if key in config["project"]:
                        safe["project"][key] = config["project"][key]
                if safe != known:
                    s = copy.deepcopy(self.state)
                    s["config"] = safe
                    s["control"] = {"paused": True, "reason": "Configuration changed; review and resume", "revision": s["control"]["revision"] + 1}
                    self._commit("settings_updated", known["humans"][0]["id"], {}, s)
            human_id = self.human_id()
            if human_id not in self.state["reads"]:
                # First upgrade from a journal created before human read tracking.
                # Existing messages were already visible in the old UI, so establish
                # a baseline rather than presenting all history as newly unread.
                s = copy.deepcopy(self.state)
                s["reads"][human_id] = {"participant_id": human_id, "rooms": {
                    rid: max((m["seq"] for m in self.messages if m.get("room") == rid), default=0)
                    for rid in s["rooms"]}}
                self._commit("human_read_baseline", human_id, {"room_count": len(s["rooms"])}, s)
            self._project_config()
            self.rebuild_transcripts()
            self._project_entities(self.state)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            self.close()
            raise Problem(f"Cannot open project: {exc}") from exc
        except Exception:
            self.close()
            raise

    @classmethod
    def create(cls, path, name, goal, workspace, human="Jonathan", reference="", general_context=""):
        root = Path(path).expanduser().resolve()
        if (root / "vibeguild.json").exists():
            raise Problem("This folder already contains a Vibeguild project", 409)
        if root.exists() and any(root.iterdir()):
            raise Problem("The coordination folder contains files. Choose an empty folder or a new .vibeguild subfolder inside your workspace.")
        work = Path(workspace).expanduser().resolve()
        if work == root or not work.is_dir():
            raise Problem("Choose an existing code/workspace folder. Keep coordination in its own subfolder, such as <workspace>/.vibeguild.")
        human_name = text(human, "human name", 80)
        config = {"schema_version": 1, "project": {"id": uid(), "name": name, "goal": goal, "workspace": str(work), "reference": reference},
                  "humans": [{"id": uid(), "name": human_name, "handle": handle_from_name(human_name)}], "general_context": general_context,
                  "agents": [], "lead_agent_id": None, "policy": copy.deepcopy(DEFAULT_POLICY), "notifications": copy.deepcopy(DEFAULT_NOTIFICATIONS)}
        validate_config(config)
        (root / "vibeguild_files" / "journal").mkdir(parents=True)
        atomic(root / "vibeguild.json", config)
        return cls(root)

    def close(self):
        if self.file_lock:
            self.file_lock.close()

    @property
    def id(self):
        return self.state["config"]["project"]["id"]

    def _apply(self, event):
        for key, value in event["changes"].items():
            if key in COLLECTIONS:
                self.state[key].update(value)
            else:
                self.state[key] = value
        self.events.append(event)
        if event["kind"] in ("message", "note"):
            self.messages.append({**event["data"], "id": event["id"], "seq": event["seq"], "at": event["at"], "actor": event["actor"], "kind": event["kind"]})
        if event.get("request_key"):
            self.requests[event["request_key"]] = event["result"]

    def _commit(self, kind, actor, data, state, request_key=None, result=None):
        if state.get("config") != self.state.get("config"):
            state["config"]["revision"] = self.state.get("config", {}).get("revision", 0) + 1
        changes = {}
        for key, value in state.items():
            old = self.state.get(key)
            if value != old:
                changes[key] = {k: v for k, v in value.items() if v != (old or {}).get(k)} if key in COLLECTIONS else value
        private_result = copy.deepcopy(result or {})
        public_result = {k: v for k, v in private_result.items() if k != "credential"}
        event = {"id": uid(), "seq": len(self.events) + 1, "at": self.clock(), "kind": kind, "actor": actor,
                 "data": data, "changes": changes, "previous": self.events[-1]["checksum"] if self.events else "",
                 "request_key": request_key, "result": public_result or {"ok": True}}
        event["result"].update({"event_id": event["id"], "seq": event["seq"]})
        event["checksum"] = digest(event)
        atomic(self.files / "journal" / f'{event["seq"]:012d}_{event["id"]}.json', event)
        self._apply(event)
        # A projection failure cannot undo a committed message. Repair on restart/rebuild.
        projection_warning = None
        try:
            if "config" in changes:
                self._project_config()
            if kind in ("message", "note"):
                self._append_transcript(event)
            self._project_entities(changes)
        except OSError as exc:
            projection_warning = f"Event committed, but a readable projection could not be refreshed: {exc}. Preserve an offline recovery note if needed."
        with self.changed:
            self.changed.notify_all()
        return {**copy.deepcopy(event["result"]), **({"credential": private_result["credential"]} if "credential" in private_result else {}), **({"projection_warning": projection_warning} if projection_warning else {})}

    def _project_config(self):
        atomic(self.path / "vibeguild.json", self.state["config"])

    def _project_entities(self, changes):
        for kind in ("agents", "rooms", "tasks", "votes", "decisions", "reads"):
            for key, value in changes.get(kind, {}).items():
                public = {k: v for k, v in value.items() if k != "session_id"}
                atomic(self.files / kind / key / "state.json", public)
                if kind == "agents":
                    atomic(self.files / "agents" / key / "HEARTBEAT.json", self._heartbeat(value))
        if any(k in changes for k in ("config", "agents", "rooms", "tasks")):
            write_recovery(self, atomic)

    def _heartbeat(self, agent):
        last_seen = agent.get("last_seen", 0)
        return {"schema_version": 1, "agent_id": agent["id"], "handle": agent["handle"],
                "status": agent.get("status", "disconnected"), "last_seen": last_seen,
                "heartbeat_interval_seconds": 60, "fresh_for_seconds": 120,
                "paused": bool(agent.get("paused")), "budget_paused": bool(agent.get("budget_paused")),
                "signed_off_at": agent.get("signed_off_at"), "signoff_reason": agent.get("signoff_reason"),
                "responding_to": agent.get("responding_to"), "responding_room": agent.get("responding_room"),
                "responding_expires_at": agent.get("responding_expires_at"),
                "meaning": "Recent coordinator contact; status is agent-declared and is not proof that work continues."}

    def set_recovery_home(self, location):
        with self.lock:
            self.recovery_home = Path(location).resolve()
            write_recovery(self, atomic)

    def _transcript_path(self, data, kind):
        if kind == "note":
            if "human_id" in data:
                return self.files / "humans" / data["human_id"] / "notes.txt"
            return self.files / "agents" / data["agent_id"] / "notes.txt"
        room = data["room"]
        if room in ("agent_chat", "agent_scratch"):
            return self.files / (room + ".txt")
        return self.files / "chats" / room / "chat.txt"

    def _append_transcript(self, event):
        d = event["data"]
        path = self._transcript_path(d, event["kind"])
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="\n") as out:
            out.write(f'\n[{event["seq"]} | {event["id"]} | {event["at"]:.3f}] {d["sender_name"]}\n{d["body"]}\n')

    def rebuild_transcripts(self):
        paths = {self.files / "agent_chat.txt", self.files / "agent_scratch.txt"}
        paths.update(self._transcript_path(m, m["kind"]) for m in self.messages)
        for path in paths:
            atomic(path, b"VIBEGUILD / readable projection; publish through the client.\n")
        for event in self.events:
            if event["kind"] in ("message", "note"):
                self._append_transcript(event)

    def human_id(self):
        return self.state["config"]["humans"][0]["id"]

    def _actor(self, credential):
        hashed = hashlib.sha256(credential.encode()).hexdigest()
        for session in self.state["sessions"].values():
            if secrets.compare_digest(session["token_hash"], hashed):
                agent = self.state["agents"][session["agent_id"]]
                if agent["session_id"] != session["id"]:
                    raise Problem("Session replaced; resume explicitly before writing", 409)
                return agent["id"], session["id"]
        raise Problem("Invalid agent credential", 401)

    def resolve_actor(self, credential=None, human=False):
        return (self.human_id(), None) if human else self._actor(credential or "")

    def tick(self):
        with self.lock:
            s = copy.deepcopy(self.state)
            now = self.clock()
            changed = []
            for vote in s["votes"].values():
                if vote["status"] == "open" and now >= vote["closes_at"]:
                    vote.update(status="closed", closed_at=now, close_reason="deadline")
                    changed.append(vote["id"])
            if changed:
                self._commit("votes_closed", "system", {"votes": changed}, s)
            for a in list(self.state["agents"].values()):
                if not a["paused"] and a["status"] in ("waiting", "blocked") and not any(t["owner"] == a["id"] and t["status"] == "working" for t in self.state["tasks"].values()):
                    if now-max(a["last_incoming"], a["watch_started"]) >= self.state["config"]["policy"]["agent_inactivity_minutes"]*60:
                        update = copy.deepcopy(self.state)
                        update["agents"][a["id"]].update(paused=True, pause_reason="Incoming inactivity limit reached")
                        self._commit("inactivity_pause", "system", {"agent_id": a["id"]}, update)

    def command(self, action, args, credential=None, human=False, request_id=None):
        with self.lock:
            if action == "recovery":
                action = "checkpoint"
            if not isinstance(args, dict):
                raise Problem("Command arguments must be a JSON object")
            if request_id is not None:
                text(request_id, "request ID", 200)
            self.tick()
            actor, session_id = self.resolve_actor(credential, human)
            key = f"{actor}:{request_id}" if request_id else None
            if key in self.requests:
                result = copy.deepcopy(self.requests[key])
                if result.get("recovery_file"):
                    try:
                        write_recovery(self, atomic)
                    except OSError as exc:
                        result["projection_warning"] = f"Recovery file could not be refreshed: {exc}"
                return result
            s = copy.deepcopy(self.state)
            now = self.clock()
            agent = s["agents"].get(actor)
            permitted_paused = {"ack", "checkpoint", "presence", "context_reset", "usage"}
            if agent and action not in permitted_paused:
                if s["control"]["paused"] or agent.get("paused") or agent.get("budget_paused"):
                    raise Problem("Paused: checkpoint/acknowledge and watch for resume", 409)
            if action in {"settings", "lead", "control", "agent_update", "human_update", "human_read"} and not human:
                raise Problem("This operation requires the human owner", 403)
            result, data, kind = {}, {}, action
            if action == "register":
                handle = text(args.get("handle"), "short name", 24).lower()
                if not re.fullmatch(r"[a-z][a-z0-9_-]{0,23}", handle):
                    raise Problem("Short names use lowercase letters, digits, underscores or hyphens")
                if any(a["handle"] == handle for a in s["agents"].values()):
                    raise Problem("Short name exists; use resume with its UUID", 409)
                try:
                    template_ref = bind(args.get("template"))
                except (ValueError, OSError) as exc:
                    raise Problem(str(exc)) from exc
                aid = uid()
                a = {"id": aid, "handle": handle, "role": text(args.get("role", "contributor"), "role", 100),
                     "provider": text(args.get("provider", "other"), "provider", 80), "owner_id": self.human_id(),
                     "color": PALETTE[len(s["agents"]) % len(PALETTE)], "created_at": now, "paused": False,
                     "budget_paused": False, "status": "ready", "last_seen": now, "last_report": now,
                     "last_incoming": now, "watch_started": now, "checkpoint": "", "workspace": s["config"]["project"]["workspace"],
                     "session_id": None, "pending": [], "token_estimate": 0}
                if template_ref is not None:
                    a["template_ref"] = template_ref
                s["agents"][aid] = a
                rid = uid()
                s["rooms"][rid] = {"id": rid, "name": "@" + handle, "kind": "direct", "members": [aid], "created_at": now}
                a["direct_room"] = rid
                result = self._new_session(s, a, now)
                if args.get("dormant"):
                    a["status"] = "disconnected"
                data = {"agent_id": aid, "name": handle, **binding_fields(a)}
                self._sync_roster(s)
            elif action == "human_update":
                owner = s["config"]["humans"][0]
                if args.get("human_id") != owner["id"]:
                    raise Problem("Unknown human owner", 404)
                name = text(args.get("name"), "human name", 80)
                old_name = owner["name"]
                if name == old_name:
                    return {"ok": True, "human_id": owner["id"], "name": name,
                            "handle": owner.get("handle", handle_from_name(old_name)), "unchanged": True}
                # Old projects may derive the mention handle from the display name.
                # Freeze that existing address before changing the label.
                owner.setdefault("handle", handle_from_name(old_name))
                owner["name"] = name
                data = {"human_id": owner["id"], "old_name": old_name, "name": name}
                result = {"human_id": owner["id"], "name": name, "handle": owner["handle"]}
            elif action == "agent_update":
                a = s["agents"].get(args.get("agent_id"))
                if not a:
                    raise Problem("Unknown agent", 404)
                handle = text(args.get("handle"), "short name", 24).lower()
                if not re.fullmatch(r"[a-z][a-z0-9_-]{0,23}", handle):
                    raise Problem("Short names use lowercase letters, digits, underscores or hyphens")
                if any(other["id"] != a["id"] and other["handle"] == handle for other in s["agents"].values()):
                    raise Problem("Short name already belongs to another agent", 409)
                old_handle = a["handle"]
                if handle == old_handle:
                    return {"ok": True, "agent_id": a["id"], "handle": handle, "unchanged": True}
                a["handle"] = handle
                s["rooms"][a["direct_room"]]["name"] = "@" + handle
                self._sync_roster(s)
                data = {"agent_id": a["id"], "old_handle": old_handle, "handle": handle}
                result = {"agent_id": a["id"], "handle": handle}
            elif action == "resume":
                if not human:
                    raise Problem("Resume needs the local owner connection", 403)
                a = s["agents"].get(args.get("agent_id"))
                if not a:
                    raise Problem("Unknown agent", 404)
                if a["session_id"] and now - a["last_seen"] < 120 and a["status"] != "disconnected" and not args.get("takeover"):
                    raise Problem("Session may still be active. Use explicit takeover only after stopping the old session.", 409)
                result = self._new_session(s, a, now)
                data = {"agent_id": a["id"]}
            elif action == "room":
                members = list(dict.fromkeys(args.get("members", [])))
                if agent and actor not in members:
                    members.append(actor)
                if any(m not in s["agents"] for m in members):
                    raise Problem("Unknown room member")
                rid = uid()
                s["rooms"][rid] = {"id": rid, "name": text(args.get("name"), "chat name", 80), "kind": "group", "members": members, "created_at": now}
                result = {"room_id": rid}
                data = s["rooms"][rid]
            elif action == "note" and human:
                # Personal notes never belong to a chat or resolve mentions.
                # The authenticated owner, not command input, supplies authorship.
                data = {"body": text(args.get("body"), "note", 250000), "human_id": actor,
                        "recipients": [], "mentions": [], "human_mentions": [],
                        "sender_name": s["config"]["humans"][0]["name"], "human": True}
                kind = "note"
            elif action in ("send", "note"):
                body = text(args.get("body"), "message", 250000)
                rid = args.get("room", "agent_chat")
                if rid not in s["rooms"]:
                    raise Problem("Unknown chat", 404)
                if agent and action == "send" and rid == "agent_chat" and len(body) > 2000:
                    raise Problem(f"agent_chat is limited to 2000 characters for agent summaries; received {len(body)}. Publish technical detail in agent_scratch, then send a concise agent_chat summary citing the scratch message UUID.")
                if agent and s["rooms"][rid]["kind"] not in ("global", "scratch") and actor not in s["rooms"][rid]["members"]:
                    raise Problem("Join the room before posting", 403)
                if args.get("reply_to") is not None and not any(m["id"] == args["reply_to"] and m.get("room") == rid and m["kind"] == "message" for m in self.messages):
                    raise Problem("Reply must reference an existing message in this chat")
                mentions = [a["id"] for a in s["agents"].values() if re.search(r"(?<!\w)@" + re.escape(a["handle"]) + r"(?![\w-])", body)]
                human_mentions = [h["id"] for h in s["config"]["humans"] if re.search(
                    r"(?<!\w)@" + re.escape(h.get("handle", handle_from_name(h["name"]))) + r"(?![\w-])", body, re.IGNORECASE)]
                recipients = [] if action == "note" else [a["id"] for a in s["agents"].values() if a["id"] != actor and
                              (s["rooms"][rid]["kind"] in ("global", "scratch") or a["id"] in mentions or
                               (s["rooms"][rid]["kind"] in ("direct", "group") and a["id"] in s["rooms"][rid]["members"]))]
                data = {"body": body, "room": rid, "mentions": mentions, "human_mentions": human_mentions, "reply_to": args.get("reply_to"),
                        "recipients": recipients, "sender_name": agent["handle"] if agent else s["config"]["humans"][0]["name"], "human": human}
                if action == "note":
                    if not agent:
                        raise Problem("Working notes belong to an agent; use its direct chat to interject")
                    data["agent_id"] = actor
                    kind = "note"
                else:
                    kind = "message"
                    for aid in recipients:
                        if rid == "agent_chat" or aid in mentions or s["rooms"][rid]["kind"] in ("direct", "group"):
                            s["agents"][aid]["last_incoming"] = now
                    if agent:
                        agent["last_report"] = now
                        if agent.get("responding_room") == rid:
                            for key_name in ("responding_to", "responding_room", "responding_since", "responding_expires_at"):
                                agent.pop(key_name, None)
            elif action == "human_read":
                rid = args.get("room")
                if rid not in s["rooms"]:
                    raise Problem("Unknown chat", 404)
                latest = max((m["seq"] for m in self.messages if m.get("room") == rid), default=0)
                record = s["reads"].setdefault(actor, {"participant_id": actor, "rooms": {}})
                previous = record["rooms"].get(rid, 0)
                if latest <= previous:
                    return {"ok": True, "room": rid, "through": previous, "unchanged": True}
                record["rooms"][rid] = latest
                data = {"room": rid, "through": latest}
                result = {"room": rid, "through": latest}
            elif action == "join_room":
                room = s["rooms"].get(args.get("room"))
                if not room or not agent or room["kind"] == "direct":
                    raise Problem("Select an existing group room using an agent session")
                if actor not in room["members"]:
                    room["members"].append(actor)
                data = {"room": room["id"], "agent_id": actor}
            elif action == "control":
                target = args.get("agent_id")
                paused = bool(args.get("paused"))
                if target:
                    if target not in s["agents"]:
                        raise Problem("Unknown agent", 404)
                    a = s["agents"][target]
                    a["paused"] = paused
                    a["pause_revision"] = a.get("pause_revision", 0) + 1
                    if not paused:
                        a["watch_started"] = now
                else:
                    s["control"] = {"paused": paused, "reason": args.get("reason", "Paused by human" if paused else "Running"), "revision": s["control"]["revision"] + 1}
                    if not paused:
                        for a in s["agents"].values():
                            a["watch_started"] = now
                data = {"agent_id": target, "paused": paused}
            elif action == "lead":
                aid = args.get("agent_id")
                if aid is not None and aid not in s["agents"]:
                    raise Problem("Unknown lead agent", 404)
                s["config"]["lead_agent_id"] = aid
                s["config"]["governance_revision"] = s["config"].get("governance_revision", 0) + 1
                data = {"agent_id": aid}
            elif action == "settings":
                if "general_context" in args:
                    s["config"]["general_context"] = args["general_context"]
                for k in ("name", "goal", "workspace"):
                    if k in args:
                        s["config"]["project"][k] = args[k]
                for k, v in args.get("policy", {}).items():
                    if k not in DEFAULT_POLICY:
                        raise Problem("Unknown policy: " + k)
                    s["config"]["policy"][k] = v
                if "notifications" in args:
                    notifications = args["notifications"]
                    if not isinstance(notifications, dict):
                        raise Problem("notifications must be an object")
                    current = s["config"].setdefault("notifications", copy.deepcopy(DEFAULT_NOTIFICATIONS))
                    for k, v in notifications.items():
                        if k not in DEFAULT_NOTIFICATIONS:
                            raise Problem("Unknown notification setting: " + k)
                        current[k] = v
                validate_config(s["config"])
                budget = s["config"]["policy"]["token_budget"]
                for a in s["agents"].values():
                    a["budget_paused"] = budget is not None and a["token_estimate"] >= budget
            elif action in ("checkpoint", "presence", "context_reset", "ack"):
                if not agent:
                    raise Problem("Use an agent session for this command")
                session = s["sessions"][session_id]
                if "pending" in args and (not isinstance(args["pending"], list) or len(args["pending"]) > 100 or any(not isinstance(v, str) or len(v) > 200 for v in args["pending"])):
                    raise Problem("pending must be at most 100 short request IDs")
                if action == "checkpoint":
                    agent["checkpoint"] = text(args.get("body"), "checkpoint", 12000)
                    agent["pending"] = args.get("pending", agent["pending"])
                    agent["checkpoint_at"] = now
                    agent["checkpoint_revision"] = agent.get("checkpoint_revision", 0) + 1
                elif action == "presence":
                    status = args.get("status", agent.get("status", "waiting"))
                    if status not in ("working", "waiting", "blocked", "paused", "disconnected", "ready"):
                        raise Problem("Invalid agent status")
                    agent["status"] = status
                    if status == "disconnected":
                        reason = args.get("reason", "")
                        if not isinstance(reason, str) or len(reason.encode("utf-8")) > 240:
                            raise Problem("Sign-off reason must be text, at most 240 UTF-8 bytes")
                        agent["signed_off_at"] = now
                        agent["signoff_reason"] = reason.strip()
                    else:
                        agent.pop("signed_off_at", None)
                        agent.pop("signoff_reason", None)
                    if "responding_to" in args:
                        message_id = args.get("responding_to")
                        if message_id is None:
                            for key_name in ("responding_to", "responding_room", "responding_since", "responding_expires_at"):
                                agent.pop(key_name, None)
                        else:
                            if s["control"]["paused"] or agent.get("paused") or agent.get("budget_paused"):
                                raise Problem("Cannot prepare a response while paused", 409)
                            message = next((m for m in self.messages if m["id"] == message_id and m["kind"] == "message"), None)
                            if not message or actor not in self._message_recipients(message):
                                raise Problem("Responding indicator must reference a message delivered to this agent")
                            if status != "working":
                                raise Problem("Set status working while preparing a response")
                            agent.update(responding_to=message_id, responding_room=message["room"], responding_since=now,
                                         responding_expires_at=now + 120)
                    elif status in ("waiting", "blocked", "paused", "disconnected", "ready"):
                        for key_name in ("responding_to", "responding_room", "responding_since", "responding_expires_at"):
                            agent.pop(key_name, None)
                    if status == "paused":
                        agent["pause_ack_revision"] = s["control"]["revision"]
                        agent["pause_ack_agent_revision"] = agent.get("pause_revision", 0)
                elif action == "context_reset":
                    session["generation"] = uid()
                    session["delivered"] = []
                    session.pop("known_revision", None)
                    session["batch"] = None
                else:
                    batch_id = args.get("batch_id")
                    batch = session.get("batch")
                    if not batch or batch["id"] != batch_id:
                        raise Problem("Unknown/stale batch; fetch inbox before acknowledging", 409)
                    if batch.get("acknowledged"):
                        return {"ok": True, "cursor": agent.get("cursor", 0)}
                    agent["cursor"] = batch["through"]
                    session["batch"]["acknowledged"] = True
                    agent["pending"] = args.get("pending", agent["pending"])
                agent["last_seen"] = now
                result = {"ok": True, "generation": session["generation"], "cursor": agent.get("cursor", 0)}
                if action == "checkpoint":
                    result["recovery_file"] = str(recovery_path(self, actor))
            elif action == "task":
                tid = uid()
                title = text(args.get("title"), "task title", 180)
                description = args.get("description", "")
                if not isinstance(description, str) or len(description.encode("utf-8")) > 12000:
                    raise Problem("Task description must be text, at most 12000 UTF-8 bytes")
                s["tasks"][tid] = {"id": tid, "title": title, "description": description, "owner": None,
                                   "status": "open", "revision": 1, "result": "", "created_at": now}
                result, data = {"task_id": tid}, {"task_id": tid, "title": title}
            elif action == "task_update":
                task = s["tasks"].get(args.get("task_id"))
                if not task:
                    raise Problem("Unknown task", 404)
                if args.get("revision") != task["revision"]:
                    raise Problem("Task changed; reload its revision before acting", 409)
                status = args.get("status")
                if status not in ("working", "blocked", "review", "done", "open"):
                    raise Problem("Invalid task status")
                if task["owner"] not in (None, actor) and not human:
                    raise Problem("Task belongs to another agent", 409)
                if status == "working" and agent and any(t["owner"] == actor and t["status"] == "working" and t["id"] != task["id"] for t in s["tasks"].values()):
                    raise Problem("Finish or checkpoint the current task before claiming another", 409)
                if status == "working" and agent and args.get("editing", True):
                    if s["config"]["policy"]["coordination_mode"] == "worktrees" and (not agent.get("workspace_assigned") or Path(agent["workspace"]) == Path(s["config"]["project"]["workspace"])):
                        raise Problem("Assign a separate worktree with call workspace before claiming an editing task; use editing:false for read-only work")
                    if s["config"]["policy"]["coordination_mode"] == "shared" and any(t["owner"] != actor and t["status"] == "working" and t.get("editing", True) for t in s["tasks"].values()):
                        raise Problem("Shared workspace is held by another editing task", 409)
                if status == "done":
                    text(args.get("result"), "completion evidence", 12000)
                task.update(status=status, owner=None if status == "open" else actor if agent else task["owner"], revision=task["revision"] + 1, result=args.get("result", task["result"]))
                if status == "working":
                    task["editing"] = bool(args.get("editing", True))
                data = {"task_id": task["id"], "status": status, "title": task["title"], "result": task["result"]}
                result = {"revision": task["revision"]}
            elif action == "workspace":
                target = s["agents"].get(args.get("agent_id", actor))
                if not target or (not human and target["id"] != actor):
                    raise Problem("Choose your own agent workspace", 403)
                path = Path(text(args.get("path"), "workspace path", 4096)).resolve()
                if not path.is_dir() or path == self.path:
                    raise Problem("Workspace must be an existing external folder")
                if s["config"]["policy"]["coordination_mode"] == "worktrees" and any(a["id"] != target["id"] and a.get("workspace_assigned") and a["workspace"] == str(path) for a in s["agents"].values()):
                    raise Problem("Another agent owns this worktree path", 409)
                target.update(workspace=str(path), workspace_assigned=True)
                data = {"agent_id": target["id"], "workspace": str(path)}
            elif action == "decision":
                if not human and s["config"].get("lead_agent_id") != actor:
                    raise Problem("Only the designated lead or human can issue a decision", 403)
                did = uid()
                decision = {"id": did, "body": text(args.get("body"), "decision", 12000), "actor": actor, "at": now,
                            "governance_revision": s["config"].get("governance_revision", 0), "task_id": args.get("task_id"), "vote_id": args.get("vote_id")}
                s["decisions"][did] = decision
                data, result = decision, {"decision_id": did}
            elif action == "vote":
                options = args.get("options", [])
                if not isinstance(options, list) or not 2 <= len(options) <= 10 or any(not isinstance(o, str) for o in options):
                    raise Problem("A vote needs 2–10 distinct options")
                options = [text(o, "option", 180) for o in options]
                if len(set(options)) != len(options):
                    raise Problem("Vote options must be distinct")
                duration = number(args.get("minutes"), "vote minutes", 1/60, 10080)
                vid = uid()
                electorate = list(s["agents"]) + [self.human_id()]
                room = args.get("room", "agent_chat")
                if room not in s["rooms"]:
                    raise Problem("Unknown vote room")
                vote = {"id": vid, "question": text(args.get("question"), "question", 2000), "options": options,
                        "electorate": electorate, "ballots": {}, "opens_at": now, "closes_at": now + duration * 60,
                        "status": "open", "creator": actor, "room": room, "advisory": True}
                s["votes"][vid] = vote
                data, result = {"vote_id": vid, "question": vote["question"], "room": room}, {"vote_id": vid}
            elif action == "ballot":
                vote = s["votes"].get(args.get("vote_id"))
                if not vote or vote["status"] != "open" or now >= vote["closes_at"]:
                    raise Problem("Vote is closed or does not exist", 409)
                if actor not in vote["electorate"]:
                    raise Problem("You are not in this vote's frozen electorate", 403)
                option = args.get("option")
                if option != "abstain" and (isinstance(option, bool) or not isinstance(option, int) or not 0 <= option < len(vote["options"])):
                    raise Problem("Choose an option index or abstain")
                vote["ballots"][actor] = {"option": option, "at": now, "reason": str(args.get("reason", ""))[:2000]}
                if all(voter in vote["ballots"] for voter in vote["electorate"]):
                    vote.update(status="closed", closed_at=now, close_reason="everyone_voted")
                data = {"vote_id": vote["id"], "closed": vote["status"] == "closed"}
            elif action == "usage":
                if not agent:
                    raise Problem("Usage belongs to an agent session")
                source = text(args.get("source"), "usage source", 200)
                rid = text(args.get("record_id"), "provider record ID", 200)
                ukey = f"{actor}:{source}:{rid}"
                if ukey in s["usage"]:
                    return {"ok": True, "duplicate": True}
                entry = {"agent_id": actor, "source": source, "record_id": rid, "at": now,
                         "input": number(args.get("input", 0), "input tokens"), "output": number(args.get("output", 0), "output tokens"),
                         "kind": "self_reported" if not args.get("verified_source") else "reported_metadata"}
                s["usage"][ukey] = entry
                data = {"agent_id": actor}
            else:
                raise Problem("Unknown command: " + action, 404)
            if agent:
                agent["last_seen"] = now
            return self._commit(kind, actor, data, s, key, result)

    def _new_session(self, s, agent, now):
        token = secrets.token_urlsafe(32)
        sid = uid()
        old = s["sessions"].get(agent.get("session_id"), {})
        s["sessions"][sid] = {"id": sid, "agent_id": agent["id"], "token_hash": hashlib.sha256(token.encode()).hexdigest(),
                              "generation": uid(), "delivered": [], "batch": None}
        agent.update(session_id=sid, last_seen=now, watch_started=now, status="ready")
        agent.pop("signed_off_at", None)
        agent.pop("signoff_reason", None)
        return {"agent_id": agent["id"], "session_id": sid, "credential": token, "direct_room": agent["direct_room"],
                "recovery_file": str(recovery_path(self, agent["id"])), "master_memory": str(memory_index_path(self, agent["id"])),
                "memory_folder": str(memory_dir_path(self, agent["id"])), "heartbeat_file": str(self.files / "agents" / agent["id"] / "HEARTBEAT.json"),
                "skill_file": str(skill_path().resolve()), **binding_fields(agent)}

    def _sync_roster(self, state):
        state["config"]["agents"] = [{**{k: a[k] for k in ("id", "handle", "color", "owner_id", "role", "provider")}, **binding_fields(a)} for a in state["agents"].values()]

    def snapshot(self):
        with self.lock:
            self.tick()
            s = copy.deepcopy(self.state)
            s.pop("sessions")
            for a in s["agents"].values():
                a["recovery_file"] = str(recovery_path(self, a["id"]))
                a["master_memory"] = str(memory_index_path(self, a["id"]))
                a["memory_folder"] = str(memory_dir_path(self, a["id"]))
                a["heartbeat_file"] = str(self.files / "agents" / a["id"] / "HEARTBEAT.json")
            s["path"] = str(self.path)
            s["seq"] = len(self.events)
            s["now"] = self.clock()
            read_rooms = s["reads"].get(self.human_id(), {}).get("rooms", {})
            s["unread"] = {rid: {"count": len(rows), "latest_seq": max((m["seq"] for m in rows), default=read_rooms.get(rid, 0))}
                           for rid in s["rooms"]
                             for rows in [[m for m in self.messages if m.get("room") == rid and m["actor"] != self.human_id() and m["seq"] > read_rooms.get(rid, 0)]]}
            s["activity"] = [self.public_event(e) for e in self.events if e["kind"] not in ("ack", "inbox", "history_read", "human_read", "human_read_baseline", "presence", "checkpoint", "context_reset", "usage")
                             and not (e["kind"] == "note" and "human_id" in e["data"])][-150:]
            return s

    def has_updates(self, after, actor=None):
        """Bookkeeping must not wake agents into an empty-read/ack feedback loop."""
        ignored = {"ack", "inbox", "history_read", "human_read", "human_read_baseline", "checkpoint", "context_reset", "usage"}
        if actor is not None:
            ignored.add("presence")
        for e in self.events[max(0, after):]:
            if e["kind"] in ignored or actor is not None and e["actor"] == actor:
                continue
            if actor is not None:
                if e["kind"] == "note":
                    continue
                if e["kind"] == "message":
                    room = self.state["rooms"][e["data"]["room"]]
                    if room["kind"] not in ("global", "scratch") and actor not in room["members"] and actor not in e["data"].get("mentions", []):
                        continue
                if e["kind"] == "control" and e["data"].get("agent_id") not in (None, actor):
                    continue
            return True
        return False

    def public_event(self, e):
        d = copy.deepcopy(e["data"])
        d.pop("recipients", None)
        if "body" in d:
            d["truncated"] = len(d["body"]) > 1200
            d["body"] = d["body"][:1200]
        return {"id": e["id"], "seq": e["seq"], "at": e["at"], "kind": e["kind"], "actor": e["actor"], "data": d}

    def history(self, room=None, before=None, query="", agent_id=None, human_id=None):
        with self.lock:
            if human_id and (human_id != self.human_id() or agent_id or room):
                raise Problem("Choose the human owner's notes without a room or agent filter")
            rows = [m for m in self.messages if (not room or m.get("room") == room)
                    and (m.get("human_id") == human_id and m["kind"] == "note" if human_id else
                         m.get("agent_id") == agent_id if agent_id else m["kind"] == "message")
                    and (not before or m["seq"] < before) and (not query or query.casefold() in m["body"].casefold())]
            result = []
            for m in rows[-50:]:
                item = {**m, "body": m["body"][:16000], "has_more_body": len(m["body"]) > 16000}
                if m["actor"] == self.human_id():
                    item["receipts"] = [{"agent_id": aid, "acknowledged": self.state["agents"].get(aid, {}).get("cursor", 0) >= m["seq"]}
                                        for aid in self._message_recipients(m) if aid in self.state["agents"]]
                result.append(item)
            return result

    def _message_recipients(self, message):
        if "recipients" in message:
            return message["recipients"]
        room = self.state["rooms"].get(message.get("room"), {})
        return [a["id"] for a in self.state["agents"].values() if a["id"] != message["actor"] and a.get("created_at", 0) <= message["at"] and
                (room.get("kind") in ("global", "scratch") or a["id"] in message.get("mentions", []) or
                 (room.get("kind") in ("direct", "group") and a["id"] in room.get("members", [])))]

    def inbox(self, credential, bootstrap=False, max_bytes=None):
        with self.lock:
            self.tick()
            actor, sid = self.resolve_actor(credential)
            a = self.state["agents"][actor]
            session = self.state["sessions"][sid]
            policy = self.state["config"]["policy"]
            now = self.clock()
            paused = self.state["control"]["paused"] or a["paused"] or a.get("budget_paused")
            control = {**self.state["control"], "agent_paused": a["paused"], "budget_paused": a.get("budget_paused", False),
                       "effective_paused": paused, "idle_seconds_left": max(0, policy["agent_inactivity_minutes"]*60 - (now - max(a["last_incoming"], a["watch_started"]))),
                       "status_due": a["status"] == "working" and now-a["last_report"] >= max(0, (policy["working_status_interval_minutes"]-policy["working_status_lead_minutes"])*60)}
            if paused and not bootstrap:
                return {"control": control, "messages": [], "instruction": "Checkpoint, acknowledge paused, then watch controls. Do not work or vote."}
            pending_batch = session.get("batch")
            if pending_batch and not pending_batch.get("acknowledged") and not bootstrap:
                return {"control": control, "pending_batch": pending_batch["id"], "instruction": "Previous batch not acknowledged. Ack with pending IDs, or explicitly history-fetch missing content. No automatic replay."}
            limit = min(int(max_bytes or policy["inbox_max_bytes"]), 64000)
            if limit < 2048:
                raise Problem("Inbox limit must be at least 2048 bytes")
            room_ids = [r["id"] for r in self.state["rooms"].values() if r["kind"] in ("global", "scratch") or actor in r["members"]]
            out = {"control": control, "generation": session["generation"], "messages": [], "more": False}
            revision = digest(self.state["config"])
            room_revision = digest(self.state["rooms"])
            if bootstrap or session.get("known_revision") != revision:
                out["project"] = self.state["config"]["project"]
                out["general_context"] = self.state["config"].get("general_context", "")
                out["policy"] = policy
                out["lead_agent_id"] = self.state["config"].get("lead_agent_id")
                out["roster"] = copy.deepcopy(self.state["config"].get("agents", []))
                out["humans"] = [{**h, "handle": h.get("handle", handle_from_name(h["name"]))} for h in self.state["config"]["humans"]]
            if bootstrap or session.get("known_rooms") != room_revision:
                out["rooms"] = [{k: r[k] for k in ("id", "name", "kind", "members")} for r in self.state["rooms"].values() if r["id"] in room_ids]
                out["room_count"] = len(room_ids)
            if bootstrap:
                out["identity"] = {k: a[k] for k in ("id", "handle", "role", "workspace", "checkpoint", "pending", "direct_room")}
                out["identity"].update(binding_fields(a))
                out["tasks"] = [t for t in self.state["tasks"].values() if t["owner"] == actor]
                out["open_votes"] = [v for v in self.state["votes"].values() if v["status"] == "open" and actor in v["electorate"] and actor not in v["ballots"]]
                out["room_guidance"] = copy.deepcopy(ROOM_GUIDANCE)
            # Never silently omit required shared context. Request an explicit larger
            # bootstrap if it will not fit; messages remain independently paginated.
            if len(encoded(out)) + 700 > limit:
                raise Problem("Bootstrap/context exceeds this inbox cap. Retry with --max-bytes 64000; shorten completed-task checkpoints/context if still too large.", 413)
            through = a.get("cursor", 0)
            for e in self.events[through:]:
                relevant = (e["kind"] == "message" and e["actor"] != actor and (e["data"].get("room") in room_ids or actor in e["data"].get("mentions", []))) or e["kind"] in ("vote", "ballot", "votes_closed", "decision", "task", "task_update", "lead", "room", "register", "agent_update", "human_update")
                if relevant:
                    item = self.public_event(e)
                    item.get("data", {}).pop("human_mentions", None)
                    if e["kind"] == "message":
                        body = e["data"]["body"]
                        maximum = 700 if e["data"]["room"] == "agent_scratch" else 2500
                        item["data"]["body"] = body[:maximum]
                        item["data"]["representation"] = "preview" if len(body) > maximum else "full"
                        item["data"]["total_chars"] = len(body)
                    if e["kind"] in ("vote", "ballot"):
                        v = self.state["votes"][e["data"]["vote_id"]]
                        item["data"]["vote"] = {k: v[k] for k in ("id", "question", "options", "closes_at", "status")}
                    if len(encoded(out)) + len(encoded(item)) + 700 > limit:
                        if not out["messages"] and "project" not in out:
                            raise Problem("Next event exceeds this cap. Retry with --max-bytes 64000 or use targeted inspect/fetch.", 413)
                        out["more"] = True
                        break
                    out["messages"].append(item)
                through = e["seq"]
            if not bootstrap and "project" not in out and "rooms" not in out and not out["messages"] and not out["more"]:
                return {"control": control, "messages": [], "through": through, "more": False}
            batch_id = uid()
            out.update(batch_id=batch_id, through=through)
            size = len(encoded(out))
            out["payload"] = {"bytes": size, "estimated_tokens": math.ceil(size/4), "method": "UTF-8 bytes / 4; not provider usage"}
            s = copy.deepcopy(self.state)
            sess = s["sessions"][sid]
            sess["known_revision"] = revision
            sess["known_rooms"] = room_revision
            sess["batch"] = {"id": batch_id, "through": through, "acknowledged": False}
            aa = s["agents"][actor]
            aa["last_seen"] = now
            aa["token_estimate"] += out["payload"]["estimated_tokens"]
            aa["budget_paused"] = policy["token_budget"] is not None and aa["token_estimate"] >= policy["token_budget"]
            out["control"]["budget_paused"] = aa["budget_paused"]
            out["control"]["effective_paused"] = bool(paused or aa["budget_paused"])
            self._commit("inbox", actor, {"bytes": size}, s)
            return out

    def fetch(self, credential, message_id, start=0, length=3000):
        with self.lock:
            actor, sid = self.resolve_actor(credential)
            msg = next((m for m in self.messages if m["id"] == message_id), None)
            if not msg:
                raise Problem("Message not found", 404)
            start = int(number(start, "start", 0, len(msg["body"])))
            length = int(number(length, "length", 1, 12000))
            a = self.state["agents"][actor]
            if a.get("budget_paused") or a["paused"] or self.state["control"]["paused"]:
                raise Problem("Paused; history retrieval is deferred", 409)
            body = msg["body"][start:start+length]
            s = copy.deepcopy(self.state)
            s["agents"][actor]["token_estimate"] += math.ceil(len(body.encode("utf-8"))/4)
            budget = s["config"]["policy"]["token_budget"]
            s["agents"][actor]["budget_paused"] = budget is not None and s["agents"][actor]["token_estimate"] >= budget
            key = f"{message_id}:{start}:{len(body)}"
            delivered = s["sessions"][sid]["delivered"]
            repeated = key in delivered
            if not repeated:
                delivered.append(key)
            self._commit("history_read", actor, {"message_id": message_id, "start": start, "length": len(body), "repeated": repeated}, s)
            return {"id": message_id, "body": body, "start": start, "next": start+len(body), "total": len(msg["body"]), "repeated_range": repeated}

    def inspect(self, credential, kind, key=None, start=0, limit=10, query=""):
        """Explicit targeted state/history retrieval, separate from incremental delivery."""
        with self.lock:
            actor, sid = self.resolve_actor(credential)
            a = self.state["agents"][actor]
            if a.get("budget_paused") or a["paused"] or self.state["control"]["paused"]:
                raise Problem("Paused; inspect is deferred", 409)
            if kind not in ("agents", "rooms", "tasks", "votes", "decisions", "messages"):
                raise Problem("Inspect agents, rooms, tasks, votes, decisions or messages")
            start = int(number(start, "start", 0))
            limit = int(number(limit, "limit", 1, 20))
            source = self.messages if kind == "messages" else list(self.state[kind].values())
            rows = [copy.deepcopy(v) for v in source if (not key or v["id"] == key)
                    and not (kind == "messages" and "human_id" in v and (not key or query))
                    and (not query or query.casefold() in json.dumps(v).casefold())]
            result = {"kind": kind, "total": len(rows), "start": start, "items": rows[start:start+limit]}
            for row in result["items"]:
                row.pop("session_id", None)
                if kind == "messages":
                    row["total_chars"] = len(row["body"])
                    row["body"] = row["body"][:700]
            if len(encoded(result)) > 64000:
                raise Problem("Result too large; reduce --limit", 413)
            s = copy.deepcopy(self.state)
            aa = s["agents"][actor]
            aa["token_estimate"] += math.ceil(len(encoded(result))/4)
            budget = s["config"]["policy"]["token_budget"]
            aa["budget_paused"] = budget is not None and aa["token_estimate"] >= budget
            self._commit("history_read", actor, {"kind": kind, "key": key, "count": len(result["items"])}, s)
            return result

    def template_identity(self, credential):
        """Authenticated own binding only; no peer-selected path or template body."""
        with self.lock:
            self.tick()
            actor, _ = self.resolve_actor(credential)
            agent = self.state["agents"][actor]
            return {"agent_id": actor, "template_ref": agent.get("template_ref"),
                    "memory_folder": str(memory_dir_path(self, actor)),
                    "paused": bool(self.state["control"]["paused"] or agent.get("paused") or agent.get("budget_paused"))}

    def touch_session(self, credential):
        with self.lock:
            actor, _ = self.resolve_actor(credential)
            now = self.clock()
            if now-self.state["agents"][actor]["last_seen"] >= 60:
                s = copy.deepcopy(self.state)
                s["agents"][actor]["last_seen"] = now
                self._commit("presence", actor, {"contact": "watch"}, s)
            return actor
