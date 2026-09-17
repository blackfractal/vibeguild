import concurrent.futures
import copy
import json
import tempfile
import unittest
from pathlib import Path

from vibeguild.core import Project, Problem, atomic, encoded


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "code").mkdir()
        self.p = Project.create(self.root / "project", "Test", "Build a parser", self.root / "code", general_context="Shared constraints: keep formats compatible.")
        self.now = 100000.
        self.p.clock = lambda: self.now
        self.a = self.p.command("register", {"handle": "builder"}, human=True)
        self.b = self.p.command("register", {"handle": "reviewer"}, human=True)
        self.p.command("control", {"paused": False}, human=True)

    def tearDown(self):
        self.p.close()
        self.temp.cleanup()

    def call(self, action, args, who=None, **kw):
        return self.p.command(action, args, credential=(who or self.a)["credential"], **kw)

    def drain(self, who=None, bootstrap=False):
        who = who or self.a
        all_messages = []
        while True:
            out = self.p.inbox(who["credential"], bootstrap=bootstrap)
            all_messages += out.get("messages", [])
            if out.get("batch_id"):
                self.call("ack", {"batch_id": out["batch_id"]}, who)
            if not out.get("more"):
                return out, all_messages
            bootstrap = False

    def test_incremental_reads_no_ack_feedback_or_replay(self):
        first, _ = self.drain(bootstrap=True)
        self.assertIn("Shared constraints", first["general_context"])
        seq = len(self.p.events)
        self.drain(self.b, bootstrap=True)
        self.assertFalse(self.p.has_updates(seq, self.a["agent_id"]))
        seq = len(self.p.events)
        empty = self.p.inbox(self.a["credential"])
        self.assertEqual([], empty["messages"])
        self.assertNotIn("batch_id", empty)
        self.assertEqual(seq, len(self.p.events))
        sent = self.call("send", {"body": "Ready for review"}, self.b)
        out = self.p.inbox(self.a["credential"])
        self.assertEqual([sent["event_id"]], [m["id"] for m in out["messages"]])
        retry = self.p.inbox(self.a["credential"])
        self.assertEqual(out["batch_id"], retry["pending_batch"])
        self.assertNotIn("messages", retry)
        self.call("ack", {"batch_id": out["batch_id"], "pending": [sent["event_id"]]})
        self.assertEqual([], self.p.inbox(self.a["credential"])["messages"])

    def test_resume_fences_and_recovers_checkpoint_pending_cursor(self):
        self.drain(bootstrap=True)
        self.call("checkpoint", {"body": "Parser changed; verify line 20", "pending": ["review-request"]})
        cursor = self.p.state["agents"][self.a["agent_id"]]["cursor"]
        with self.assertRaises(Problem):
            self.p.command("resume", {"agent_id": self.a["agent_id"]}, human=True)
        fresh = self.p.command("resume", {"agent_id": self.a["agent_id"], "takeover": True}, human=True)
        with self.assertRaises(Problem):
            self.call("send", {"body": "old session"})
        boot = self.p.inbox(fresh["credential"], bootstrap=True)
        self.assertEqual(["review-request"], boot["identity"]["pending"])
        self.assertIn("Parser", boot["identity"]["checkpoint"])
        self.assertEqual(cursor, self.p.state["agents"][self.a["agent_id"]]["cursor"])
        ledger = "".join(p.read_text("utf-8") for p in (self.p.files / "journal").glob("*.json"))
        self.assertNotIn(fresh["credential"], ledger)
        self.assertNotIn(self.a["credential"], ledger)

    def test_dormant_ui_profile_can_resume_immediately(self):
        profile = self.p.command("register", {"handle": "designer", "dormant": True}, human=True)
        self.p.command("resume", {"agent_id": profile["agent_id"]}, human=True)

    def test_agent_rename_keeps_uuid_session_history_and_direct_room(self):
        original_id = self.a["agent_id"]
        original_room = self.a["direct_room"]
        first = self.call("send", {"body": "Known as @builder when written"})

        renamed = self.p.command("agent_update", {"agent_id": original_id, "handle": "architect"}, human=True)

        self.assertEqual(original_id, renamed["agent_id"])
        self.assertEqual("architect", self.p.state["agents"][original_id]["handle"])
        self.assertEqual(original_room, self.p.state["agents"][original_id]["direct_room"])
        self.assertEqual("@architect", self.p.state["rooms"][original_room]["name"])
        self.assertEqual("architect", next(a["handle"] for a in self.p.state["config"]["agents"] if a["id"] == original_id))
        self.assertEqual("builder", next(m["sender_name"] for m in self.p.messages if m["id"] == first["event_id"]))
        self.call("send", {"body": "The existing session still works"})
        recovery = self.p.files / "agents" / original_id / "RECOVERY.md"
        self.assertTrue(recovery.is_file())
        self.assertIn("@architect", recovery.read_text("utf-8"))
        rename_event = self.p.events[renamed["seq"] - 1]
        self.assertEqual({"agent_id": original_id, "old_handle": "builder", "handle": "architect"}, rename_event["data"])

    def test_agent_rename_rejects_agent_actor_and_duplicate_handle(self):
        with self.assertRaises(Problem):
            self.call("agent_update", {"agent_id": self.a["agent_id"], "handle": "architect"})
        with self.assertRaises(Problem):
            self.p.command("agent_update", {"agent_id": self.a["agent_id"], "handle": "reviewer"}, human=True)

    def test_agent_rename_updates_roster_incrementally(self):
        self.drain(bootstrap=True)
        self.p.command("agent_update", {"agent_id": self.a["agent_id"], "handle": "architect"}, human=True)
        out = self.p.inbox(self.a["credential"])
        self.assertEqual("architect", next(a["handle"] for a in out["roster"] if a["id"] == self.a["agent_id"]))
        self.assertTrue(any(e["kind"] == "agent_update" for e in out["messages"]))

    def test_context_reset_and_changed_general_context(self):
        self.drain(bootstrap=True)
        self.p.command("settings", {"general_context": "New requirement: offline only"}, human=True)
        out, _ = self.drain()
        self.assertEqual("New requirement: offline only", out["general_context"])
        self.assertNotIn("general_context", self.p.inbox(self.a["credential"]))
        self.call("context_reset", {})
        out = self.p.inbox(self.a["credential"], bootstrap=True)
        self.assertEqual("New requirement: offline only", out["general_context"])

    def test_pause_human_can_interject_and_ack(self):
        self.p.command("control", {"paused": True}, human=True)
        with self.assertRaises(Problem):
            self.call("send", {"body": "Should not publish"})
        self.call("checkpoint", {"body": "Stopped at checkpoint"})
        self.call("presence", {"status": "paused"})
        self.p.command("send", {"room": self.a["direct_room"], "body": "Please change direction"}, human=True)
        out = self.p.inbox(self.a["credential"])
        self.assertTrue(out["control"]["effective_paused"])
        self.assertEqual([], out["messages"])
        self.p.command("control", {"paused": False}, human=True)
        _, events = self.drain()
        self.assertTrue(any(e["data"].get("body") == "Please change direction" for e in events))

    def test_vote_waits_for_human_and_abstention(self):
        v = self.call("vote", {"question": "Parser format?", "options": ["JSON", "YAML"], "minutes": 10})["vote_id"]
        self.call("ballot", {"vote_id": v, "option": 0})
        self.call("ballot", {"vote_id": v, "option": "abstain"}, self.b)
        self.assertEqual("open", self.p.state["votes"][v]["status"])
        self.p.command("ballot", {"vote_id": v, "option": 0}, human=True)
        self.assertEqual("everyone_voted", self.p.state["votes"][v]["close_reason"])

    def test_vote_deadline_and_frozen_electorate(self):
        v = self.call("vote", {"question": "Choice", "options": ["A", "B"], "minutes": 1})["vote_id"]
        third = self.p.command("register", {"handle": "late"}, human=True)
        with self.assertRaises(Problem):
            self.call("ballot", {"vote_id": v, "option": 0}, third)
        self.now += 60
        with self.assertRaises(Problem):
            self.call("ballot", {"vote_id": v, "option": 0})
        self.assertEqual("deadline", self.p.state["votes"][v]["close_reason"])

    def test_single_lead_and_authority(self):
        with self.assertRaises(Problem):
            self.call("lead", {"agent_id": self.a["agent_id"]})
        self.p.command("lead", {"agent_id": self.a["agent_id"]}, human=True)
        self.call("decision", {"body": "Keep JSON"})
        self.p.command("lead", {"agent_id": self.b["agent_id"]}, human=True)
        with self.assertRaises(Problem):
            self.call("decision", {"body": "Old lead"})

    def test_concurrent_idempotent_publication_and_restart(self):
        def send(_):
            return self.call("send", {"body": "one message"}, request_id="same-id")
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(send, range(20)))
        self.assertEqual(1, len({r["event_id"] for r in results}))
        self.assertEqual(1, len(self.p.messages))
        pid, path = self.p.id, self.p.path
        self.p.close()
        self.p = Project(path, clock=lambda: self.now)
        self.assertEqual(pid, self.p.id)
        self.assertEqual(results[0]["event_id"], send(None)["event_id"])
        self.assertIn("one message", (self.p.files / "agent_chat.txt").read_text("utf-8"))

    def test_config_projection_failure_cannot_undo_committed_setting(self):
        old_config = copy.deepcopy(self.p.state["config"])
        self.p.command("settings", {"general_context": "Newest context"}, human=True)
        path = self.p.path
        self.p.close()
        atomic(path / "vibeguild.json", old_config)
        self.p = Project(path, clock=lambda: self.now)
        self.assertEqual("Newest context", self.p.state["config"]["general_context"])

    def test_offline_config_edit_is_imported_paused(self):
        path = self.p.path
        config = copy.deepcopy(self.p.state["config"])
        self.p.close()
        config["general_context"] = "Offline amendment"
        atomic(path / "vibeguild.json", config)
        self.p = Project(path, clock=lambda: self.now)
        self.assertTrue(self.p.state["control"]["paused"])
        self.assertEqual("Offline amendment", self.p.state["config"]["general_context"])

    def test_hash_corruption_and_exclusive_coordinator(self):
        with self.assertRaises(Problem):
            Project(self.p.path)
        path = self.p.path
        self.p.close()
        event_path = sorted((self.p.files / "journal").glob("*.json"))[-1]
        obj = json.loads(event_path.read_text("utf-8"))
        obj["actor"] = "tampered"
        atomic(event_path, obj)
        with self.assertRaisesRegex(Problem, "integrity"):
            Project(path)

    def test_shared_edit_lock_revision_and_completion_evidence(self):
        self.p.command("settings", {"policy": {"coordination_mode": "shared"}}, human=True)
        first = self.call("task", {"title": "Implement"})["task_id"]
        second = self.call("task", {"title": "Test"})["task_id"]
        self.call("task_update", {"task_id": first, "revision": 1, "status": "working"})
        with self.assertRaises(Problem):
            self.call("task_update", {"task_id": second, "revision": 1, "status": "working"}, self.b)
        with self.assertRaises(Problem):
            self.call("task_update", {"task_id": first, "revision": 1, "status": "done", "result": "ok"})
        with self.assertRaises(Problem):
            self.call("task_update", {"task_id": first, "revision": 2, "status": "done"})
        self.call("task_update", {"task_id": first, "revision": 2, "status": "done", "result": "unit tests pass; test_parser.py"})
        self.call("task_update", {"task_id": second, "revision": 1, "status": "working"}, self.b)

    def test_worktree_mapping_required_for_editing(self):
        tid = self.call("task", {"title": "Edit"})["task_id"]
        with self.assertRaises(Problem):
            self.call("task_update", {"task_id": tid, "revision": 1, "status": "working"})
        (self.root / "worktree").mkdir()
        self.call("workspace", {"path": str(self.root / "worktree")})
        self.call("task_update", {"task_id": tid, "revision": 1, "status": "working"})
        with self.assertRaises(Problem):
            self.call("workspace", {"path": str(self.root / "worktree")}, self.b)

    def test_budget_estimate_and_reported_usage_separate(self):
        self.p.command("settings", {"policy": {"token_budget": 1}}, human=True)
        out = self.p.inbox(self.a["credential"], bootstrap=True)
        self.assertTrue(out["control"]["budget_paused"])
        with self.assertRaises(Problem):
            self.call("send", {"body": "Must pause"})
        self.call("usage", {"source": "host", "record_id": "one", "input": 123, "output": 45})
        self.call("usage", {"source": "host", "record_id": "one", "input": 123, "output": 45})
        self.assertEqual(1, len(self.p.state["usage"]))
        self.p.command("settings", {"policy": {"token_budget": None}}, human=True)
        self.call("send", {"body": "Human raised budget"})

    def test_scratch_range_and_multibyte_inbox_cap(self):
        self.drain(bootstrap=True)
        body = "解析結果🚀" * 5000
        msg = self.call("send", {"room": "agent_scratch", "body": body}, self.b)
        out = self.p.inbox(self.a["credential"], max_bytes=16000)
        self.assertLessEqual(len(encoded(out)), 16000)
        item = out["messages"][-1]["data"]
        self.assertEqual("preview", item["representation"])
        part = self.p.fetch(self.a["credential"], msg["event_id"], 100, 300)
        self.assertEqual(body[100:400], part["body"])
        self.assertTrue(self.p.fetch(self.a["credential"], msg["event_id"], 100, 300)["repeated_range"])

    def test_bootstrap_teaches_summary_detail_routing_and_agents_cannot_dump_in_chat(self):
        boot = self.p.inbox(self.a["credential"], bootstrap=True)
        self.assertIn("Coordination only", boot["room_guidance"]["agent_chat"])
        self.assertIn("Technical detail", boot["room_guidance"]["agent_scratch"])
        self.call("ack", {"batch_id": boot["batch_id"]})
        with self.assertRaisesRegex(Problem, "agent_scratch"):
            self.call("send", {"room": "agent_chat", "body": "x" * 2001})
        detailed = self.call("send", {"room": "agent_scratch", "body": "x" * 2001})
        self.assertTrue(detailed["event_id"])
        human = self.p.command("send", {"room": "agent_chat", "body": "y" * 2001}, human=True)
        self.assertTrue(human["event_id"])

    def test_twenty_agents_and_bounded_paging(self):
        for i in range(18):
            self.p.command("register", {"handle": "agent"+str(i)}, human=True)
        out, events = self.drain(bootstrap=True)
        self.assertEqual(20, len(self.p.state["agents"]))
        self.assertEqual(20, len([e for e in events if e["kind"] == "register"]))
        self.assertLessEqual(len(encoded(out)), 16000)

    def test_inactivity_does_not_stop_active_work_or_reset_on_own_report(self):
        self.call("presence", {"status": "working"})
        self.call("presence", {"status": "waiting"}, self.b)
        self.now += 3300
        self.assertTrue(self.p.inbox(self.a["credential"], bootstrap=True)["control"]["status_due"])
        before = self.p.state["agents"][self.a["agent_id"]]["last_incoming"]
        self.call("send", {"body": "Still working; parser validation remains"})
        self.assertEqual(before, self.p.state["agents"][self.a["agent_id"]]["last_incoming"])
        self.now += 3601
        self.p.tick()
        self.assertFalse(self.p.state["agents"][self.a["agent_id"]]["paused"])
        self.assertTrue(self.p.state["agents"][self.b["agent_id"]]["paused"])

    def test_watch_heartbeat_is_small_truthful_and_rate_limited(self):
        aid = self.a["agent_id"]
        path = self.p.files / "agents" / aid / "HEARTBEAT.json"
        initial = json.loads(path.read_text("utf-8"))
        before = len(self.p.events)
        self.now += 59
        self.p.touch_session(self.a["credential"])
        self.assertEqual(before, len(self.p.events))
        self.now += 1
        self.p.touch_session(self.a["credential"])
        heartbeat = json.loads(path.read_text("utf-8"))
        self.assertEqual(self.now, heartbeat["last_seen"])
        self.assertEqual(aid, heartbeat["agent_id"])
        self.assertEqual(60, heartbeat["heartbeat_interval_seconds"])
        self.assertIn("not proof", heartbeat["meaning"])
        self.assertNotIn(self.a["credential"], path.read_text("utf-8"))
        self.assertEqual(initial["agent_id"], heartbeat["agent_id"])

    def test_human_mention_reaches_agent_outside_room(self):
        self.drain(bootstrap=True)
        room = self.p.command("room", {"name": "Review", "members": [self.b["agent_id"]]}, human=True)["room_id"]
        msg = self.p.command("send", {"room": room, "body": "@builder please inspect this"}, human=True)
        _, events = self.drain()
        self.assertIn(msg["event_id"], [e["id"] for e in events])

    def test_human_unread_watermarks_are_durable_and_do_not_wake_agents(self):
        self.drain(bootstrap=True)
        self.drain(self.b, bootstrap=True)
        sent = self.call("send", {"room": "agent_chat", "body": "A new result"}, self.b)
        snap = self.p.snapshot()
        self.assertEqual(1, snap["unread"]["agent_chat"]["count"])
        before = len(self.p.events)
        marked = self.p.command("human_read", {"room": "agent_chat"}, human=True)
        self.assertEqual(sent["seq"], marked["through"])
        self.assertEqual(0, self.p.snapshot()["unread"]["agent_chat"]["count"])
        self.assertFalse(self.p.has_updates(before, self.a["agent_id"]))
        self.p.command("send", {"room": "agent_chat", "body": "My own note"}, human=True)
        self.assertEqual(0, self.p.snapshot()["unread"]["agent_chat"]["count"])
        with self.assertRaises(Problem):
            self.call("human_read", {"room": "agent_chat"})

    def test_agent_receipt_uses_existing_ack_cursor_without_receipt_events(self):
        self.drain(bootstrap=True)
        sent = self.p.command("send", {"room": self.a["direct_room"], "body": "Please inspect the parser"}, human=True)
        receipt = self.p.history(room=self.a["direct_room"])[-1]["receipts"]
        self.assertEqual([{"agent_id": self.a["agent_id"], "acknowledged": False}], receipt)
        out = self.p.inbox(self.a["credential"])
        delivered = next(e for e in out["messages"] if e["id"] == sent["event_id"])
        self.assertNotIn("recipients", delivered["data"])
        self.call("ack", {"batch_id": out["batch_id"], "pending": []})
        receipt = self.p.history(room=self.a["direct_room"])[-1]["receipts"]
        self.assertEqual([{"agent_id": self.a["agent_id"], "acknowledged": True}], receipt)
        self.assertFalse(any(e["kind"] == "receipt" for e in self.p.events))

    def test_preparing_response_is_explicit_short_lived_and_clears_on_send(self):
        incoming = self.p.command("send", {"room": self.a["direct_room"], "body": "Can you answer this?"}, human=True)
        before = len(self.p.events)
        self.call("presence", {"status": "working", "responding_to": incoming["event_id"]})
        agent = self.p.state["agents"][self.a["agent_id"]]
        self.assertEqual(incoming["event_id"], agent["responding_to"])
        self.assertEqual(self.a["direct_room"], agent["responding_room"])
        self.assertEqual(self.now + 120, agent["responding_expires_at"])
        self.assertTrue(self.p.has_updates(before))
        self.assertFalse(self.p.has_updates(before, self.b["agent_id"]))
        heartbeat = json.loads((self.p.files / "agents" / self.a["agent_id"] / "HEARTBEAT.json").read_text("utf-8"))
        self.assertEqual(incoming["event_id"], heartbeat["responding_to"])
        self.call("send", {"room": self.a["direct_room"], "body": "Here is the answer."})
        self.assertNotIn("responding_to", self.p.state["agents"][self.a["agent_id"]])

    def test_preparing_response_rejects_unrelated_messages_and_pauses(self):
        unrelated = self.p.command("send", {"room": self.b["direct_room"], "body": "For reviewer"}, human=True)
        with self.assertRaises(Problem):
            self.call("presence", {"status": "working", "responding_to": unrelated["event_id"]})
        incoming = self.p.command("send", {"room": self.a["direct_room"], "body": "For builder"}, human=True)
        self.p.command("control", {"paused": True}, human=True)
        with self.assertRaises(Problem):
            self.call("presence", {"status": "working", "responding_to": incoming["event_id"]})

    def test_preparing_response_after_bootstrap_ack_keeps_recipient_eligibility(self):
        incoming = self.p.command("send", {"room": self.a["direct_room"], "body": "Please review"}, human=True)
        batch = self.p.inbox(self.a["credential"], bootstrap=True)
        self.call("ack", {"batch_id": batch["batch_id"], "pending": [incoming["event_id"]]})
        self.call("presence", {"status": "working", "responding_to": incoming["event_id"]})
        self.assertEqual(incoming["event_id"], self.p.state["agents"][self.a["agent_id"]]["responding_to"])

    def test_explicit_disconnect_records_clean_signoff_and_resume_clears_it(self):
        self.call("presence", {"status": "disconnected", "reason": "Host session ending"})
        agent = self.p.state["agents"][self.a["agent_id"]]
        self.assertEqual(self.now, agent["signed_off_at"])
        self.assertEqual("Host session ending", agent["signoff_reason"])
        heartbeat = json.loads((self.p.files / "agents" / self.a["agent_id"] / "HEARTBEAT.json").read_text("utf-8"))
        self.assertEqual(self.now, heartbeat["signed_off_at"])
        resumed = self.p.command("resume", {"agent_id": self.a["agent_id"]}, human=True)
        agent = self.p.state["agents"][self.a["agent_id"]]
        self.assertNotIn("signed_off_at", agent)
        self.assertNotIn("signoff_reason", agent)
        self.assertEqual("ready", agent["status"])
        self.assertTrue(resumed["session_id"])

    def test_human_mentions_are_uuid_resolved_and_sound_setting_is_project_scoped(self):
        human = self.p.human_id()
        self.assertFalse(self.p.state["config"]["notifications"]["human_mention_sound"])
        self.p.command("settings", {"notifications": {"human_mention_sound": True}}, human=True)
        result = self.call("send", {"room": "agent_chat", "body": "@Jonathan I need your decision"})
        event = self.p.events[result["seq"] - 1]
        self.assertEqual([human], event["data"]["human_mentions"])
        self.assertTrue(self.p.state["config"]["notifications"]["human_mention_sound"])
        out = self.p.inbox(self.b["credential"], bootstrap=True)
        delivered = next(e for e in out["messages"] if e["id"] == result["event_id"])
        self.assertNotIn("human_mentions", delivered["data"])
        with self.assertRaises(Problem):
            self.p.command("settings", {"notifications": {"human_mention_sound": "yes"}}, human=True)

    def test_unrelated_pair_chat_and_notes_do_not_wake_other_agents(self):
        room = self.p.command("room", {"name": "Review", "members": [self.b["agent_id"]]}, human=True)["room_id"]
        seq = len(self.p.events)
        self.call("send", {"room": room, "body": "Focused discussion"}, self.b)
        self.call("note", {"body": "A working note"}, self.b)
        self.assertFalse(self.p.has_updates(seq, self.a["agent_id"]))
        self.assertTrue(self.p.has_updates(seq))
        self.p.command("send", {"room": room, "body": "@builder please join us"}, human=True)
        self.assertTrue(self.p.has_updates(seq, self.a["agent_id"]))


if __name__ == "__main__":
    unittest.main()
