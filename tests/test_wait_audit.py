"""Session-history audit regressions."""

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SCRIPT = (Path(__file__).resolve().parents[1] / "plugins" / "axiom-for-herdr" /
          "skills" / "axiom-for-herdr" / "scripts" / "audit_wait_history.py")
SPEC = importlib.util.spec_from_file_location("audit_wait_history", SCRIPT)
audit_helper = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit_helper)


def completion(command, stdout, started, completed, thread="main-thread"):
    return {
        "type": "event_msg",
        "payload": {
            "type": "item_completed",
            "thread_id": thread,
            "item": {
                "type": "CommandExecution",
                "command": ["/bin/zsh", "-lc", command],
                "stdout": json.dumps(stdout),
                "started_at_ms": started,
                "completed_at_ms": completed,
                "duration": {"secs": (completed - started) // 1000,
                             "nanos": ((completed - started) % 1000) * 1_000_000},
            },
        },
    }


class WaitAuditTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.rollout = self.root / "rollout-test.jsonl"

    def write(self, records):
        self.rollout.write_text(
            "".join(json.dumps(record) + "\n" for record in records),
            encoding="utf-8",
        )

    def test_audit_counts_wait_reasons_arguments_and_overlap(self):
        helper = "/cache/axiom_herdr.py"
        self.write([
            completion(f"python3 {helper} wait --run /tmp/run --timeout 55",
                       {"events": [], "pending": 1, "timeout": True}, 0, 5000),
            completion(f"python3 {helper} wait --run /tmp/run --until-event",
                       {"reason": "event", "events": [{"event": "report_ready"}],
                        "pending": 1}, 1000, 4000),
            completion(f"python3 {helper} status --run /tmp/run", {}, 6000, 6100),
            completion(f"python3 {helper} read --task /tmp/task", {}, 6200, 6300),
        ])

        result = audit_helper.audit([self.root])

        self.assertEqual(result["totals"], {
            "files": 1,
            "sessions": 1,
            "waits": 2,
            "reasons": {"event": 1, "safety_timeout": 1},
            "status_calls": 1,
            "read_calls": 1,
            "max_concurrent_waits": 2,
        })
        session = result["sessions"][0]
        self.assertEqual(session["timeout_arguments"], {"55": 1, "until-event": 1})
        self.assertEqual(session["wait_duration_seconds"], 8.0)
        self.assertEqual(session["max_concurrent_waits"], 2)

    def test_unrelated_commands_and_non_completion_items_are_ignored(self):
        self.write([
            completion("python3 another.py wait --run /tmp/run", {}, 0, 1),
            {"type": "response_item", "payload": {"type": "custom_tool_call"}},
        ])
        self.assertEqual(audit_helper.audit([self.rollout]), {
            "totals": {
                "files": 0,
                "sessions": 0,
                "waits": 0,
                "reasons": {},
                "status_calls": 0,
                "read_calls": 0,
                "max_concurrent_waits": 0,
            },
            "sessions": [],
        })

    def test_failed_wait_is_classified_as_error(self):
        record = completion(
            "python3 /cache/axiom_herdr.py wait --run /tmp/run --until-event",
            {}, 0, 100,
        )
        record["payload"]["item"]["exit_code"] = 1
        self.write([record])
        result = audit_helper.audit([self.rollout])
        self.assertEqual(result["totals"]["reasons"], {"error": 1})


if __name__ == "__main__":
    unittest.main()
