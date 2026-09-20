import hashlib
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

from vibeguild.core import Project, Problem
from vibeguild.server import make_server
from vibeguild import templates as t

ROOT = Path(__file__).resolve().parents[1]


class TemplateUnitTests(unittest.TestCase):
    def test_catalog_is_metadata_only_and_bodies_are_bounded(self):
        with patch.object(t, "read_body", side_effect=AssertionError("unexpected body read")):
            self.assertEqual(4, len(t.catalog()))
        for item in t.catalog():
            content = t.selected(item["id"])
            raw = t.canonical_body(content["body"])
            self.assertLessEqual(len(raw), t.SHIPPED_LIMIT)
            self.assertEqual(content["sha256"], hashlib.sha256(raw).hexdigest())
        for invalid in ("../secret", "/tmp/a", "general-reviewer", "", 7):
            with self.assertRaises(ValueError):
                t.selected(invalid)
        with patch.object(t, "CATALOG", t.CATALOG * 9):
            with self.assertRaises(ValueError):
                t.catalog()

    def test_snapshot_verification_is_atomic_and_survives_package_drift(self):
        with tempfile.TemporaryDirectory() as folder:
            memory = Path(folder) / "agent" / "memory"
            content = t.selected("defensive-reviewer")
            ref = {"id": content["id"], "sha256": content["sha256"]}
            path = Path(t.save_snapshot(memory, ref, "\ufeff" + content["body"].replace("\n", "\r\n")))
            self.assertEqual(content["body"], t.read_snapshot(memory, ref))
            with self.assertRaises(ValueError):
                t.save_snapshot(memory, ref, "Different body")
            self.assertEqual(content["body"], path.read_text("utf-8"))
            with patch.object(t, "selected", side_effect=AssertionError("must use snapshot")):
                self.assertEqual("saved", t.profile_template({"template_ref": ref}, memory)["state"])
            path.write_text("Corrupt", encoding="utf-8")
            self.assertEqual("unavailable", t.profile_template({"template_ref": ref}, memory)["state"])
            path.unlink()
            self.assertEqual("assigned", t.profile_template({"template_ref": ref}, memory)["state"])
            with patch.object(t, "selected", return_value={**content, "body": "Package changed"}):
                self.assertEqual("unavailable", t.profile_template({"template_ref": ref}, memory)["state"])
            self.assertFalse(path.exists(), "viewing must not repair/create snapshots")

    def test_snapshot_rejects_junction_or_symlink_escape(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            agent = root / "agent"
            outside = root / "outside"
            agent.mkdir()
            outside.mkdir()
            memory = agent / "memory"
            if os.name == "nt":
                result = subprocess.run(["cmd", "/c", "mklink", "/J", str(memory), str(outside)], capture_output=True)
                self.assertEqual(0, result.returncode, result.stderr)
            else:
                memory.symlink_to(outside, target_is_directory=True)
            try:
                with self.assertRaises(ValueError):
                    t.snapshot_path(memory)
                self.assertEqual([], list(outside.iterdir()))
            finally:
                # Remove only the verified link itself, never its target recursively.
                if os.name == "nt":
                    memory.rmdir()
                else:
                    memory.unlink()

    def test_oversized_or_invalid_body_fails_before_saving(self):
        with self.assertRaises(ValueError):
            t.canonical_body("x" * (t.BODY_LIMIT + 1))
        with self.assertRaises(ValueError):
            t.canonical_body(" ")
        self.assertEqual(b"a\nb\nc\n", t.canonical_body("\ufeffa\r\nb\rc\n"))

    def test_read_and_write_failures_never_substitute_or_leave_partial_snapshots(self):
        with tempfile.TemporaryDirectory() as folder:
            memory = Path(folder) / "agent" / "memory"
            content = t.selected("conservative-engineer")
            ref = {"id": content["id"], "sha256": content["sha256"]}
            path = Path(t.save_snapshot(memory, ref, content["body"]))
            with patch.object(t.os, "replace", side_effect=PermissionError("denied")):
                with self.assertRaises(PermissionError):
                    t.save_snapshot(memory, ref, content["body"])
            self.assertEqual(content["body"], path.read_text("utf-8"))
            self.assertEqual([path], list(memory.iterdir()), "failed atomic save cleans its temporary file")
            with patch.object(t, "read_body", side_effect=PermissionError("unreadable")), patch.object(t, "selected", side_effect=AssertionError("no fallback")):
                result = t.profile_template({"template_ref": ref}, memory)
            self.assertEqual("unavailable", result["state"])
            self.assertNotIn("body", result)
            path.write_bytes(b"x" * (t.BODY_LIMIT + 1))
            self.assertEqual("unavailable", t.profile_template({"template_ref": ref}, memory)["state"])
            self.assertEqual(t.BODY_LIMIT + 1, path.stat().st_size)


class TemplateHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.server = make_server(0, self.root / "runtime")
        self.url = "http://127.0.0.1:" + str(self.server.server_address[1])
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        (self.root / "code").mkdir()
        self.p = Project.create(self.root / "project", "Templates", "Test contracts", self.root / "code")
        self.server.app.add(self.p)

    def tearDown(self):
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()
        self.server.app.close()
        self.temp.cleanup()

    def http(self, route, data=None, credential=None, owner=False, extra=None):
        headers = dict(extra or {})
        if owner or credential:
            headers["Authorization"] = "Bearer " + (self.server.app.secret if owner else credential)
        if data is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(self.url + route, data=None if data is None else json.dumps(data).encode(), headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=4) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            with error:
                return error.code, json.load(error)

    def command(self, action, args, request_id=None):
        status, result = self.http("/api/command", {"project": self.p.id, "action": action, "args": args, "request_id": request_id}, owner=True)
        self.assertEqual(200, status, result)
        return result

    def cli(self, *args, success=True, launcher=None):
        command = [sys.executable, "-B"] + ([str(launcher)] if launcher else ["-m", "vibeguild"])
        result = subprocess.run(command + ["--home", str(self.root / "runtime"), *args], cwd=ROOT, text=True, encoding="utf-8", capture_output=True)
        if success:
            self.assertEqual(0, result.returncode, result.stderr)
            return json.loads(result.stdout)
        self.assertNotEqual(0, result.returncode)
        return json.loads(result.stderr)

    def test_public_catalog_owner_inspection_and_peer_isolation(self):
        status, listing = self.http("/api/templates")
        self.assertEqual(200, status)
        self.assertTrue(all("body" not in entry for entry in listing["templates"]))
        self.assertEqual(403, self.http("/api/templates", extra={"Origin": "https://other.example"})[0])
        self.assertEqual(403, self.http("/api/templates", extra={"Host": "other.example"})[0])
        self.assertEqual(403, self.http("/api/templates", extra={"Sec-Fetch-Site": "cross-site"})[0])
        self.assertEqual(400, self.http("/api/templates?id=..%2Fsecret")[0])
        a = self.command("register", {"handle": "selected", "template": "conservative-engineer"})
        b = self.command("register", {"handle": "legacy", "role": "conservative-engineer"})
        self.assertNotIn("template_ref", b)
        self.command("control", {"paused": False})
        status, inbox = self.http("/api/inbox", {"project": self.p.id, "bootstrap": True}, credential=b["credential"])
        self.assertEqual(200, status)
        self.assertEqual(a["template_ref"], inbox["roster"][0]["template_ref"])
        content = t.selected("conservative-engineer")
        self.assertNotIn(json.dumps(content["body"]), json.dumps(inbox))
        self.assertNotIn(json.dumps(content["body"]), json.dumps(self.p.events))
        route = "/api/agent-template?project=" + self.p.id + "&agent=" + a["agent_id"]
        self.assertEqual(401, self.http(route, credential=b["credential"])[0])
        status, profile = self.http(route, owner=True)
        self.assertEqual(200, status)
        self.assertEqual("assigned", profile["state"])
        self.assertEqual(content["body"], profile["body"])
        status, own = self.http("/api/template-identity", {"project": self.p.id, "agent": a["agent_id"]}, credential=b["credential"])
        self.assertEqual(200, status)
        self.assertEqual(b["agent_id"], own["agent_id"], "request cannot select a peer")
        self.assertIsNone(own["template_ref"])

    def test_binding_retry_rename_resume_and_reload(self):
        with self.assertRaises(Problem):
            self.p.command("register", {"handle": "bad", "template": "../bad"}, human=True)
        self.assertEqual({}, self.p.state["agents"])
        args = {"handle": "chosen", "template": "creative-designer"}
        first = self.command("register", args, "same-registration")
        again = self.command("register", args, "same-registration")
        self.assertEqual(first["agent_id"], again["agent_id"])
        self.assertEqual(1, len(self.p.state["agents"]))
        legacy = self.command("register", {"handle": "legacy", "template": None})
        self.command("agent_update", {"agent_id": first["agent_id"], "handle": "renamed"})
        self.p.close()
        self.p = Project(self.root / "project")
        self.server.app.add(self.p)
        resumed = self.command("resume", {"agent_id": first["agent_id"], "takeover": True})
        self.assertEqual(first["template_ref"], resumed["template_ref"])
        recovery = Path(resumed["recovery_file"]).read_text("utf-8")
        self.assertIn(first["template_ref"]["sha256"], recovery)
        self.assertIn("templates --snapshot", recovery)
        self.assertNotIn(t.selected("creative-designer")["body"], recovery)
        with patch("vibeguild.templates.selected", side_effect=AssertionError("legacy must not load a body")):
            ordinary = self.command("resume", {"agent_id": legacy["agent_id"], "takeover": True})
        self.assertNotIn("template_ref", ordinary)
        self.assertNotIn("Selected template", Path(ordinary["recovery_file"]).read_text("utf-8"))

    def test_actual_cli_and_installed_launcher_snapshot_roundtrip(self):
        installed = self.cli("install-skill", "--dest", str(self.root / "skills"))
        launcher = Path(installed["installed"]) / "scripts" / "vibeguild_client.py"
        self.assertEqual(4, len(self.cli("templates", launcher=launcher)["templates"]))
        a = self.cli("join", "--project", str(self.p.path), "--handle", "cli", "--template", "defensive-reviewer", launcher=launcher)
        identity = ["--project", self.p.id, "--agent", a["agent_id"], "--session", a["session_id"]]
        self.assertIn("Paused", self.cli("templates", "--show", "defensive-reviewer", "--save", *identity, success=False)["error"])
        self.command("control", {"paused": False})
        self.assertIn("bound", self.cli("templates", "--show", "creative-designer", "--save", *identity, success=False)["error"])
        saved = self.cli("templates", "--show", "defensive-reviewer", "--save", *identity, launcher=launcher)
        snapshot = self.cli("templates", "--snapshot", *identity)
        self.assertEqual(saved["body"], snapshot["body"])
        self.assertEqual(Path(a["memory_folder"]) / "template.md", Path(saved["snapshot"]))
        status, profile = self.http("/api/agent-template?project=" + self.p.id + "&agent=" + a["agent_id"], owner=True)
        self.assertEqual("saved", profile["state"])
        with patch("vibeguild.server.selected", return_value={"id": "defensive-reviewer", "sha256": "0"*64, "body": "Changed"}):
            self.assertEqual(saved["body"], self.cli("templates", "--snapshot", *identity)["body"])
            Path(saved["snapshot"]).unlink()
            error = self.cli("templates", "--show", "defensive-reviewer", "--save", *identity, success=False)
            self.assertIn("differs", error["error"])
            self.assertFalse(Path(saved["snapshot"]).exists())
        for item in t.catalog():
            self.assertTrue((Path(installed["installed"]) / "references" / "templates" / (item["id"] + ".md")).is_file())


