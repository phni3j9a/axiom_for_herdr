"""Advisor protocol regressions with simulated herdr; no live panes are created."""

from contextlib import redirect_stdout
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_main_binding import FakeHerdr, helper, pane


class AdvisorTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.run = self.root / "run"
        (self.run / "tasks").mkdir(parents=True)
        helper.atomic_json(self.run / "run.json", {
            "id": "advisor-run", "cwd": str(self.root),
            "main_pane_id": "main-pane", "main_terminal_id": "main-terminal",
            "main_thread_id": "main-thread", "herdr": "/usr/local/bin/herdr",
            "socket_path": "/tmp/herdr.sock",
        })
        self.fake = FakeHerdr([pane()])
        for context in (
            patch.dict(helper.os.environ, {"CODEX_THREAD_ID": "main-thread"}, clear=True),
            patch.object(helper, "Herdr", return_value=self.fake),
        ):
            context.start()
            self.addCleanup(context.stop)

    def call(self, *argv):
        args = helper.parser().parse_args(list(argv))
        output = io.StringIO()
        with redirect_stdout(output):
            args.fn(args)
        return output.getvalue()

    def start_advisor(self):
        assignment = self.root / "consultation.md"
        assignment.write_text(
            'User: "Keep the old client compatible."\n'
            "Main hypothesis: introduce a versioned endpoint.\n"
            "Evidence: old clients reject new required fields.\n"
            "Draft a migration plan; request missing rollout facts.\n",
            encoding="utf-8",
        )
        self.call("spawn", "--run", str(self.run), "--role", "advisor",
                  "--label", "migration", "--task-file", str(assignment))
        return next((self.run / "tasks").iterdir()), assignment.read_text()

    def publish(self, task_dir, request_id, status, text):
        report = task_dir / f"{request_id}.report.md"
        report.write_text(text, encoding="utf-8")
        with patch.dict(helper.os.environ, {"AXIOM_HERDR_ROLE": "advisor"}):
            self.call("report", "--task", str(task_dir), "--request-id", request_id,
                      "--status", status, "--file", str(report))

    def test_advisor_packet_preserves_selected_evidence_and_role_boundary(self):
        task_dir, assignment = self.start_advisor()
        task = helper.read_json(task_dir / "task.json")
        packet = Path(task["request_file"]).read_text()
        self.assertIn(assignment, packet)
        self.assertIn("Do not edit project files", packet)
        self.assertIn("Do not create subagents or manage herdr panes", packet)
        self.assertIn("not the independent Reviewer", packet)
        self.assertIn("blocked report", packet)
        self.assertIn("required begin/report protocol metadata in the task directory", packet)
        self.assertIn(str(helper.SKILL / "references" / "advisor.md"), packet)
        self.assertNotIn("Review the candidate read-only", packet)
        self.assertEqual((task["model"], task["effort"]), ("gpt-6-astra", "xhigh"))

    def test_missing_evidence_followup_reuses_pane_and_rejects_stale_report(self):
        task_dir, _ = self.start_advisor()
        first = helper.read_json(task_dir / "task.json")
        self.publish(task_dir, first["request_id"], "blocked", "Need the client rollout window.")
        self.call("collect", "--task", str(task_dir))
        with self.assertRaisesRegex(helper.Failure, "complete report"):
            self.call("close", "--task", str(task_dir))

        followup = self.root / "followup.md"
        followup.write_text("New evidence: old clients remain for 14 days. Revise the plan.\n")
        self.call("send", "--task", str(task_dir), "--task-file", str(followup))
        second = helper.read_json(task_dir / "task.json")
        self.assertNotEqual(first["request_id"], second["request_id"])
        for key in ("name", "pane_id", "terminal_id", "model", "effort", "role"):
            self.assertEqual(first[key], second[key])
        self.assertIn(followup.read_text(), Path(second["request_file"]).read_text())
        self.assertIn("not the independent Reviewer", Path(second["request_file"]).read_text())
        self.assertEqual(sum(c[:2] == ("agent", "start") for c in self.fake.calls), 1)
        self.assertEqual(sum(c[:2] == ("pane", "split") for c in self.fake.calls), 1)
        self.assertEqual(sum(c[:2] == ("agent", "prompt") for c in self.fake.calls), 2)
        with self.assertRaisesRegex(helper.Failure, "no longer current"):
            self.publish(task_dir, first["request_id"], "complete", "Stale plan")
        with self.assertRaisesRegex(helper.Failure, "complete report"):
            self.call("close", "--task", str(task_dir))

        self.publish(task_dir, second["request_id"], "complete", "Version both endpoints for 14 days.")
        self.call("collect", "--task", str(task_dir))
        self.call("close", "--task", str(task_dir))
        self.assertEqual([c for c in self.fake.calls if c[:2] == ("pane", "close")],
                         [("pane", "close", first["pane_id"])])

    def test_advisor_cannot_initialize_or_manage_a_team(self):
        with patch.dict(helper.os.environ, {"AXIOM_HERDR_ROLE": "advisor"}):
            with self.assertRaisesRegex(helper.Failure, "cannot initialize"):
                self.call("init", "--cwd", str(self.root))
            with self.assertRaisesRegex(helper.Failure, "only Main manages panes"):
                self.call("status", "--run", str(self.run))
        self.assertEqual(self.fake.calls, [])

    def test_wrong_main_cannot_submit_advisor_followup(self):
        task_dir, _ = self.start_advisor()
        original = helper.read_json(task_dir / "task.json")
        followup = self.root / "followup.md"
        followup.write_text("Unrelated conversation's instruction")
        with patch.dict(helper.os.environ, {"CODEX_THREAD_ID": "other-thread"}):
            with self.assertRaisesRegex(helper.Failure, "caller thread"):
                self.call("send", "--task", str(task_dir), "--task-file", str(followup))
        self.assertEqual(original, helper.read_json(task_dir / "task.json"))
        self.assertEqual(sum(c[:2] == ("agent", "prompt") for c in self.fake.calls), 1)


if __name__ == "__main__":
    unittest.main()
