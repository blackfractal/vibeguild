"""Loopback coordinator and same-origin browser UI, with long-poll notifications."""
from __future__ import annotations
import json
import os
import secrets
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .core import Project, Problem, FileLock, atomic, encoded
from .folder_picker import choose_folder, PickerError


class OwnerSessionRequired(Problem):
    def __init__(self):
        super().__init__("Your local browser session expired. Reconnect and try again.", 401)
        self.code = "owner_session_required"


def home():
    return Path(os.environ.get("VIBEGUILD_HOME", str(Path.home() / ".vibeguild"))).resolve()


class Coordinator:
    def __init__(self, location=None):
        self.home = Path(location or home())
        self.home.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.picker_lock = threading.Lock()
        self.projects = {}
        self.secret = secrets.token_urlsafe(32)
        self.web_token = secrets.token_urlsafe(32)
        self.run_lock = FileLock(self.home / "server.lock")
        try:
            self.recent = json.loads((self.home / "recent.json").read_text("utf-8"))
        except (OSError, ValueError):
            self.recent = []

    def add(self, project):
        project.set_recovery_home(self.home)
        self.projects[project.id] = project
        self.recent = [str(project.path)] + [p for p in self.recent if p != str(project.path)]
        atomic(self.home / "recent.json", self.recent[:20])
        return project

    def open(self, path):
        with self.lock:
            resolved = Path(path).resolve()
            for project in self.projects.values():
                if project.path == resolved:
                    return project
            return self.add(Project(resolved))

    def project(self, pid):
        if pid not in self.projects:
            raise Problem("Open the project first", 404)
        return self.projects[pid]

    def close(self):
        for p in self.projects.values():
            p.close()
        self.run_lock.close()


class Handler(BaseHTTPRequestHandler):
    server_version = "Vibeguild/0.1"

    def log_message(self, *_):
        pass

    @property
    def app(self):
        return self.server.app

    def respond(self, status, body, mime="application/json; charset=utf-8", cookie=False):
        raw = body if isinstance(body, bytes) else encoded(body)
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        if cookie:
            self.send_header("Set-Cookie", f"vibeguild_{self.server.server_address[1]}={self.app.web_token}; HttpOnly; SameSite=Strict; Path=/")
        self.end_headers()
        try:
            self.wfile.write(raw)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            pass

    def check(self):
        port = self.server.server_address[1]
        host = self.headers.get("Host", "")
        allowed = {f"127.0.0.1:{port}", f"localhost:{port}"}
        if host not in allowed:
            raise Problem("Invalid Host", 403)
        origin = self.headers.get("Origin")
        if origin and origin not in {"http://" + h for h in allowed}:
            raise Problem("Cross-origin access denied", 403)
        if self.headers.get("Sec-Fetch-Site") == "cross-site":
            raise Problem("Cross-site access denied", 403)
        bearer = self.headers.get("Authorization", "").removeprefix("Bearer ")
        cookies = dict(c.strip().split("=", 1) for c in self.headers.get("Cookie", "").split(";") if "=" in c)
        human = secrets.compare_digest(bearer, self.app.secret) or secrets.compare_digest(cookies.get(f"vibeguild_{port}", ""), self.app.web_token)
        return human, bearer

    def do_GET(self):
        try:
            human, credential = self.check()
            url = urlparse(self.path)
            query = {k: v[0] for k, v in parse_qs(url.query).items()}
            if url.path == "/api/session":
                if self.headers.get("X-Vibeguild-UI") != "1":
                    raise Problem("Use the local Vibeguild interface to reconnect", 403)
                return self.respond(200, {"ok": True}, cookie=True)
            if url.path == "/api/health":
                return self.respond(200, {"ok": True, "service": "vibeguild", "version": "0.1.0"})
            if not url.path.startswith("/api/"):
                allowed = {"/": ("index.html", "text/html; charset=utf-8"), "/app.js": ("app.js", "text/javascript; charset=utf-8"), "/style.css": ("style.css", "text/css; charset=utf-8")}
                if url.path not in allowed:
                    raise Problem("Not found", 404)
                name, mime = allowed[url.path]
                return self.respond(200, (Path(__file__).parent / "web" / name).read_bytes(), mime, cookie=url.path == "/")
            if not human:
                raise OwnerSessionRequired()
            if url.path == "/api/recent":
                return self.respond(200, {"paths": self.app.recent})
            p = self.app.project(query.get("project"))
            if url.path == "/api/state":
                return self.respond(200, p.snapshot())
            if url.path == "/api/history":
                return self.respond(200, {"messages": p.history(query.get("room"), int(query.get("before", 0)) or None, query.get("q", ""), query.get("agent_id"))})
            if url.path == "/api/message":
                with p.lock:
                    message = next((m for m in p.messages if m["id"] == query.get("id")), None)
                    if not message:
                        raise Problem("Message not found", 404)
                    start = max(0, int(query.get("start", 0)))
                    return self.respond(200, {"body": message["body"][start:start+12000], "start": start, "next": start+12000, "total": len(message["body"])})
            if url.path == "/api/changes":
                after = int(query.get("after", 0))
                deadline = time.monotonic() + 20
                with p.changed:
                    while not p.has_updates(after) and time.monotonic() < deadline:
                        p.changed.wait(min(1, deadline-time.monotonic()))
                        p.tick()
                return self.respond(200, {"seq": len(p.events)})
            raise Problem("Not found", 404)
        except Problem as exc:
            self.respond(exc.status, {"error": str(exc), "code": getattr(exc, "code", None)})
        except (ValueError, TypeError) as exc:
            self.respond(400, {"error": str(exc)})
        except Exception:
            self.respond(500, {"error": "Unexpected service error; retry safely with the same request ID"})

    def do_POST(self):
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 500000:
                raise Problem("Request is empty or too large", 413)
            # Consume a bounded body before replying, including rejected requests.
            # Closing a Windows socket with unread request bytes can reset it before
            # the browser receives the authentication/origin error response.
            raw = self.rfile.read(size)
            human, credential = self.check()
            if self.headers.get_content_type() != "application/json":
                raise Problem("Use application/json", 415)
            args = json.loads(raw)
            if not isinstance(args, dict):
                raise Problem("Request must be an object")
            path = urlparse(self.path).path
            if path in ("/api/open", "/api/create", "/api/browse", "/api/pick-folder") and not human:
                raise OwnerSessionRequired()
            if path == "/api/pick-folder":
                initial, title = args.get("path", ""), args.get("title", "Choose a folder")
                allow_new = args.get("allow_new", False)
                if not isinstance(initial, str) or len(initial) > 4096 or not isinstance(title, str) or len(title) > 200 or not isinstance(allow_new, bool):
                    raise Problem("Invalid folder picker arguments")
                if not self.app.picker_lock.acquire(blocking=False):
                    raise Problem("A folder picker is already open. Select a folder or cancel that dialog first.", 409)
                try:
                    selected = choose_folder(initial, title, allow_new=allow_new)
                    return self.respond(200, {"path": selected, "cancelled": selected is None})
                except PickerError as exc:
                    raise Problem(str(exc), 503) from exc
                finally:
                    self.app.picker_lock.release()
            if path == "/api/browse":
                base = Path(args.get("path") or Path.home()).expanduser().resolve()
                if not base.is_dir():
                    raise Problem("Folder does not exist")
                entries = []
                for f in base.iterdir():
                    if f.is_dir() and not f.name.startswith("."):
                        entries.append({"name": f.name, "path": str(f), "project": (f / "vibeguild.json").is_file()})
                return self.respond(200, {"path": str(base), "parent": str(base.parent), "folders": sorted(entries, key=lambda e: e["name"].casefold())[:300], "project": (base / "vibeguild.json").is_file()})
            if path == "/api/create":
                with self.app.lock:
                    project_path = args.get("path") or str(Path(args["workspace"]).expanduser() / ".vibeguild")
                    p = self.app.add(Project.create(project_path, args["name"], args["goal"], args["workspace"], args.get("human", "Human"), args.get("reference", ""), args.get("general_context", "")))
                return self.respond(200, {"project": p.id})
            if path == "/api/open":
                return self.respond(200, {"project": self.app.open(args["path"]).id})
            p = self.app.project(args.get("project"))
            if path == "/api/command":
                if not human and not credential:
                    raise OwnerSessionRequired()
                result = p.command(args["action"], args.get("args", {}), credential, human, args.get("request_id"))
                return self.respond(200, result)
            if path == "/api/inbox":
                return self.respond(200, p.inbox(credential, args.get("bootstrap", False), args.get("max_bytes")))
            if path == "/api/fetch":
                return self.respond(200, p.fetch(credential, args["message_id"], args.get("start", 0), args.get("length", 3000)))
            if path == "/api/inspect":
                return self.respond(200, p.inspect(credential, args["kind"], args.get("key"), args.get("start", 0), args.get("limit", 10), args.get("query", "")))
            if path == "/api/watch":
                actor = p.touch_session(credential)
                after = int(args.get("after", len(p.events)))
                timeout = min(45, max(0, float(args.get("timeout", 30))))
                deadline = time.monotonic() + timeout
                with p.changed:
                    def pending_batch():
                        batch = p.state["sessions"][p.state["agents"][actor]["session_id"]].get("batch")
                        return batch["id"] if batch and not batch.get("acknowledged") else None
                    while not p.has_updates(after, actor) and not pending_batch() and time.monotonic() < deadline:
                        p.changed.wait(min(1, max(.01, deadline-time.monotonic())))
                        p.tick()
                    a = p.state["agents"][actor]
                    p.resolve_actor(credential)
                    control = {**p.state["control"], "agent_paused": a["paused"], "budget_paused": a.get("budget_paused", False)}
                    result = {"changed": p.has_updates(after, actor), "seq": len(p.events), "control": control, "pending_batch": pending_batch()}
                return self.respond(200, result)
            raise Problem("Not found", 404)
        except Problem as exc:
            self.respond(exc.status, {"error": str(exc), "code": getattr(exc, "code", None)})
        except (ValueError, KeyError, TypeError, OSError) as exc:
            self.respond(400, {"error": str(exc)})
        except Exception:
            self.respond(500, {"error": "Unexpected service error; retry safely with the same request ID"})


def make_server(port=4310, location=None):
    app = Coordinator(location)
    try:
        server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    except Exception:
        app.close()
        raise
    server.daemon_threads = True
    server.app = app
    atomic(app.home / "endpoint.json", {"url": f"http://127.0.0.1:{server.server_address[1]}", "credential": app.secret})
    atomic(app.home / "endpoint-public.json", {"url": f"http://127.0.0.1:{server.server_address[1]}"})
    return server
