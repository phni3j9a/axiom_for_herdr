"""Wait regressions with simulated herdr state and time; no agents are launched."""

import argparse
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = (Path(__file__).resolve().parents[1] / "plugins" / "axiom-for-herdr" /
          "skills" / "axiom-for-herdr" / "scripts" / "axiom_herdr.py")
SPEC = importlib.util.spec_from_file_location("axiom_herdr", SCRIPT)
helper = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(helper)


class WaitTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.run = Path(self.temporary.name)
        (self.run / "tasks").mkdir()
        helper.atomic_json(self.run / "run.json", {"main_terminal_id": "main"})
        self.agents = {}
        self.clock = 0
        self.samples = 0
        self.sleeps = []
        self.on_sleep = None
        self.closed_panes = []

        class FakeHerdr:
            def current(inner):
                return {"terminal_id": "main"}

            def agents(inner):
                self.samples += 1
                return self.agents

            def call(inner, *args):
                self.closed_panes.append(args)

        for mocked in (
            patch.object(helper, "Herdr", return_value=FakeHerdr()),
            patch.object(helper.time, "monotonic", side_effect=lambda: self.clock),
            patch.object(helper.time, "time", side_effect=lambda: 100 + self.clock),
            patch.object(helper.time, "sleep", side_effect=self.sleep),
            patch.dict(helper.os.environ, {"AXIOM_HERDR_ROLE": "main"}),
        ):
            mocked.start()
            self.addCleanup(mocked.stop)

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.clock += seconds
        if self.on_sleep:
            callback, self.on_sleep = self.on_sleep, None
            callback()

    def task(self, name="one", state="running"):
        path = self.run / "tasks" / name
        path.mkdir()
        helper.save_task(path, dict(id=name, name=name, run_dir=str(self.run),
                                   request_id="request-1", terminal_id=name,
                                   pane_id=name, submitted_at=0, role="worker", label=name))
        if state is not None:
            self.agents[name] = dict(name=name, terminal_id=name, pane_id=name,
                                     agent="codex", agent_status=state,
                                     state_change_seq=1, launch_pending=False)
        return path

    def report(self, path, status="complete", text="Report"):
        task = helper.read_json(path / "task.json")
        helper.atomic_json(helper.result_path(path, task), dict(
            task_id=task["id"], request_id=task["request_id"], status=status,
            report=text, published_at=helper.time.time()))

    def invoke(self, function, **kwargs):
        output = io.StringIO()
        with redirect_stdout(output):
            function(argparse.Namespace(**kwargs))
        # One JSON value also ensures the local polling loop emits no chatter.
        return json.loads(output.getvalue())

    def wait(self, timeout=4):
        return self.invoke(helper.wait, run=str(self.run), timeout=timeout,
                           until_event=False, test_short_wait=True)

    def assert_wait(self, result, reason, *, events, pending, timeout=False):
        self.assertEqual(result["reason"], reason)
        self.assertEqual(result["events"], events)
        self.assertEqual(result["pending"], pending)
        self.assertIsInstance(result["wait_id"], str)
        self.assertGreater(len(result["wait_id"]), 0)
        self.assertGreaterEqual(result["elapsed_seconds"], 0)
        self.assertEqual(result.get("timeout", False), timeout)

    def test_unchanged_attention_survives_wait_restart_without_repeating(self):
        for state, event in (("blocked", "blocked"), ("unknown", "unknown"),
                             (None, "agent_unavailable"), ("idle", "idle_without_report")):
            with self.subTest(state=state):
                path = self.task(str(event), state)
                first = self.wait()
                self.assertEqual([item["event"] for item in first["events"]], [event])
                samples, started = self.samples, self.clock
                repeated = self.wait()
                self.assertEqual(repeated["events"], [])
                self.assertTrue(repeated["timeout"])
                self.assertGreaterEqual(self.clock - started, 4)
                self.assertGreater(self.samples - samples, 1)
                self.assertTrue(path.exists())
        self.assertEqual(repeated["pending"], 4)
        self.assertEqual(self.closed_panes, [])

    def test_collection_of_blocked_report_is_not_new_activity(self):
        path = self.task(state="done")
        self.report(path, "blocked")
        self.assertEqual(self.wait()["events"][0]["event"], "report_ready")
        self.invoke(helper.collect, task=str(path))
        self.assert_wait(self.wait(), "safety_timeout", events=[], pending=1, timeout=True)
        self.report(path, "blocked", "A different question")
        self.assertEqual(len(self.wait()["events"]), 1)

    def test_new_request_notifies_even_with_identical_agent_state(self):
        path = self.task(state="blocked")
        self.wait()
        task = helper.read_json(path / "task.json")
        task["request_id"] = "request-2"
        helper.save_task(path, task)
        self.assertEqual(len(self.wait()["events"]), 1)

    def test_agent_activity_notifies_again(self):
        self.task(state="blocked")
        self.wait()
        self.agents["one"]["state_change_seq"] += 1
        self.assertEqual(len(self.wait()["events"]), 1)
        self.agents["one"]["agent_status"] = "unknown"
        self.assertEqual(self.wait()["events"][0]["event"], "unknown")

    def test_cleared_condition_can_recur(self):
        self.task(state="blocked")
        self.wait()
        self.agents["one"]["agent_status"] = "running"
        self.assertTrue(self.wait()["timeout"])
        self.agents["one"]["agent_status"] = "blocked"
        self.assertEqual(self.wait()["events"][0]["event"], "blocked")

    def test_other_worker_completion_interrupts_wait_with_known_blocker(self):
        self.task("blocked", "blocked")
        other = self.task("other")
        self.wait()

        def finish_other():
            self.report(other)
            self.agents["other"].update(agent_status="done", state_change_seq=2)

        self.on_sleep = finish_other
        result = self.wait(timeout=3600)
        self.assertEqual([event["task"] for event in result["events"]], [str(other)])
        self.assertEqual(result["pending"], 2)
        self.assertEqual(self.clock, 2)

    def test_suppressed_report_remains_recoverable_and_cannot_close_uncollected(self):
        path = self.task(state="done")
        self.report(path)
        self.wait()
        self.assertTrue(self.wait()["timeout"])
        row = self.invoke(helper.status, run=str(self.run), all=False)["tasks"][0]
        self.assertEqual((row["state"], row["report_status"]), ("done", "complete"))
        with self.assertRaises(helper.Failure):
            helper.close(argparse.Namespace(task=str(path)))
        report = self.invoke(helper.collect, task=str(path))
        self.assertEqual(report["result"]["report"], "Report")
        self.assert_wait(self.wait(), "no_pending", events=[], pending=0)
        self.assertEqual(self.closed_panes, [])
        self.invoke(helper.close, task=str(path))
        self.assertEqual(self.closed_panes, [("pane", "close", "one")])
        self.assert_wait(self.wait(), "no_pending", events=[], pending=0)

    def test_running_worker_backs_off_quietly_until_timeout(self):
        self.task()
        self.assert_wait(self.wait(timeout=20), "safety_timeout",
                         events=[], pending=1, timeout=True)
        self.assertEqual(self.clock, 20)
        self.assertEqual(self.sleeps, [2, 4, 8, 6])
        self.assertGreater(self.samples, 1)

    def test_empty_run_returns_without_sleep(self):
        self.assert_wait(self.wait(), "no_pending", events=[], pending=0)
        self.assertEqual(self.clock, 0)

    def test_second_waiter_returns_active_waiter_without_polling(self):
        self.task()
        lock, identity = helper.acquire_waiter(self.run)
        self.addCleanup(lock.close)
        samples = self.samples

        result = self.wait()

        self.assertEqual(result["reason"], "waiter_already_active")
        self.assertEqual(result["wait_id"], identity["wait_id"])
        self.assertEqual(result["active_waiter"], identity)
        self.assertIsNone(result["pending"])
        self.assertEqual(result["events"], [])
        self.assertEqual(self.samples, samples)
        self.assertEqual(self.sleeps, [])

    def test_short_operational_timeout_is_rejected(self):
        self.task()
        with self.assertRaisesRegex(helper.Failure, "at least 3600 seconds"):
            helper.wait(argparse.Namespace(run=str(self.run), timeout=55,
                                           until_event=False, test_short_wait=False))
        self.assertEqual(self.samples, 0)

    def test_wait_parser_defaults_to_no_internal_timeout(self):
        options = helper.parser().parse_args(["wait", "--run", str(self.run)])
        self.assertIsNone(options.timeout)
        self.assertFalse(options.until_event)
        self.assertFalse(options.test_short_wait)


if __name__ == "__main__":
    unittest.main()
