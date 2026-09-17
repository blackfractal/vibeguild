import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from vibeguild.core import Problem, uid
from vibeguild.monitor import tripwire


class TripwireTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.identity = [uid(), uid(), uid()]

    def run_wait(self, request, **kwargs):
        return tripwire(request, {}, *self.identity, "test-credential", self.root, after=10, **kwargs)

    def result(self, **kwargs):
        return {"changed": False, "seq": 10, "pending_batch": None,
                "control": {"paused": False, "agent_paused": False, "budget_paused": False}, **kwargs}

    def test_quiet_bookkeeping_advances_only_notification_cursor(self):
        request = Mock(side_effect=[self.result(seq=11), self.result(changed=True, seq=12)])
        self.assertEqual("changed", self.run_wait(request)["reason"])
        self.assertEqual([10, 11], [call.args[2]["after"] for call in request.call_args_list])
        self.assertEqual(["/api/watch", "/api/watch"], [call.args[1] for call in request.call_args_list])
        self.assertEqual(0, request.call_args_list[0].args[2]["timeout"])
        self.assertLessEqual(request.call_args_list[1].args[2]["timeout"], 30)

    def test_each_pause_stops_without_clearing_it(self):
        for flag in ("paused", "agent_paused", "budget_paused"):
            with self.subTest(flag=flag):
                result = self.result()
                result["control"][flag] = True
                request = Mock(return_value=result)
                self.assertEqual("paused", self.run_wait(request)["reason"])
                request.assert_called_once()

    def test_pending_batch_is_error_and_does_not_ack(self):
        request = Mock(return_value=self.result(pending_batch="unread-batch"))
        with self.assertRaisesRegex(Problem, "unread-batch"):
            self.run_wait(request)
        request.assert_called_once()

    def test_malformed_or_failed_observation_never_looks_quiet_and_releases_lock(self):
        old_server = self.result()
        del old_server["pending_batch"]
        for invalid in (None, [], {}, self.result(changed="false"), self.result(seq=True),
                        self.result(seq=9), self.result(control={}), self.result(pending_batch=42), old_server):
            with self.subTest(invalid=invalid), self.assertRaisesRegex(Problem, "Malformed"):
                self.run_wait(Mock(return_value=invalid))
        with self.assertRaisesRegex(Problem, "offline"):
            self.run_wait(Mock(side_effect=Problem("offline")))
        self.assertEqual("changed", self.run_wait(Mock(return_value=self.result(changed=True)))["reason"])

    def test_wait_is_bounded_and_invalid_bounds_fail_before_contact(self):
        self.assertEqual("timeout", self.run_wait(Mock(return_value=self.result()), max_seconds=.001)["reason"])
        for limit in (0, -1, float("nan"), float("inf")):
            request = Mock()
            with self.subTest(limit=limit), self.assertRaises(Problem):
                self.run_wait(request, max_seconds=limit)
            request.assert_not_called()

    def test_live_owner_blocks_duplicate_and_termination_releases_os_lock(self):
        lock_path = self.root / "tripwires" / ("_".join(self.identity) + ".lock")
        code = "from vibeguild.core import FileLock; import sys; lock=FileLock(sys.argv[1]); print('ready', flush=True); sys.stdin.read()"
        with subprocess.Popen([sys.executable, "-c", code, str(lock_path)], stdin=subprocess.PIPE,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as owner:
            try:
                self.assertEqual("ready", owner.stdout.readline().strip())
                request = Mock()
                with self.assertRaisesRegex(Problem, "already owns"):
                    self.run_wait(request)
                request.assert_not_called()
            finally:
                owner.terminate()
                owner.communicate(timeout=5)
        self.assertTrue(lock_path.exists())
        self.assertEqual("changed", self.run_wait(Mock(return_value=self.result(changed=True)))["reason"])


if __name__ == "__main__":
    unittest.main()
