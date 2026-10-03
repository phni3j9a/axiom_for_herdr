"""Model routing through the public CLI with simulated herdr; no model calls."""

from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from test_main_binding import FakeHerdr, SCRIPT, helper, pane


class ModelConfigTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.run = self.root / "run"
        (self.run / "tasks").mkdir(parents=True)
        helper.atomic_json(self.run / "run.json", {
            "id": "routing-run", "cwd": str(self.root),
            "main_pane_id": "main-pane", "main_terminal_id": "main-terminal",
            "main_thread_id": "main-thread", "herdr": "/usr/local/bin/herdr",
        })
        self.assignment = self.root / "task.md"
        self.assignment.write_text("Perform the assigned work.\n")
        self.config = self.root / ".config" / "axiom-for-herdr" / "models.json"
        self.fake = FakeHerdr([pane()])
        for context in (
            patch.dict(helper.os.environ, {"HOME": str(self.root),
                                          "CODEX_THREAD_ID": "main-thread"}, clear=True),
            patch.object(helper, "Herdr", return_value=self.fake),
        ):
            context.start()
            self.addCleanup(context.stop)

    def write_config(self, data, path=None):
        path = path or self.config
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def call(self, *argv):
        args = helper.parser().parse_args(list(argv))
        output = io.StringIO()
        with redirect_stdout(output):
            args.fn(args)
        return output.getvalue()

    def spawn(self, role="worker", *overrides):
        self.call("spawn", "--run", str(self.run), "--role", role,
                  "--label", "routing", "--task-file", str(self.assignment), *overrides)
        start = next(call for call in reversed(self.fake.calls) if call[:2] == ("agent", "start"))
        argv = list(start[start.index("--") + 1:])
        task = next(helper.read_json(path / "task.json") for path in (self.run / "tasks").iterdir()
                    if helper.read_json(path / "task.json")["name"] == start[2])
        return argv, task

    def test_missing_default_file_shows_requested_defaults_without_herdr(self):
        result = json.loads(self.call("models"))
        self.assertEqual(result, {
            "config_path": str(self.config), "config_loaded": False,
            "roles": {
                "worker": {"model": "gpt-6-luna", "effort": "max", "service_tier": "fast"},
                "design": {"model": "gpt-6.1-sol", "effort": "max", "service_tier": None},
                "reviewer": {"model": "gpt-6.1-sol", "effort": "high", "service_tier": None},
                "advisor": {"model": "gpt-6-astra", "effort": "xhigh", "service_tier": None},
            },
        })
        self.assertEqual(self.fake.calls, [])
        self.assertFalse(self.config.exists())

    def test_partial_user_settings_reach_launch_and_record_without_changing_other_roles(self):
        self.write_config({"reviewer": {"model": "my-review-model", "effort": "medium",
                                        "service_tier": "fast"}})
        original = self.config.read_bytes()
        argv, task = self.spawn("reviewer")
        self.assertEqual(argv[argv.index("-m") + 1], "my-review-model")
        self.assertIn('model_reasoning_effort="medium"', argv)
        self.assertIn('service_tier="fast"', argv)
        self.assertIn("features.fast_mode=true", argv)
        self.assertEqual((task["model"], task["effort"], task["service_tier"]),
                         ("my-review-model", "medium", "fast"))
        self.assertEqual(task["model_config_path"], str(self.config))
        self.assertEqual(task["requested_codex_args"], argv)
        self.assertEqual(task["launched_argv"], argv)
        self.assertEqual(argv[argv.index("--sandbox") + 1], "workspace-write")
        self.assertEqual(argv[argv.index("--ask-for-approval") + 1], "never")
        worker_argv, worker = self.spawn()
        self.assertEqual((worker["model"], worker["effort"]), ("gpt-6-luna", "max"))
        self.assertIn('service_tier="fast"', worker_argv)
        self.assertEqual(self.config.read_bytes(), original)

    def test_cli_fields_override_config_and_omitted_fields_inherit(self):
        self.write_config({"design": {"model": "saved-design", "effort": "low"}})
        argv, task = self.spawn("design", "--model", "one-off-model", "--service-tier", "fast")
        self.assertEqual((task["model"], task["effort"], task["service_tier"]),
                         ("one-off-model", "low", "fast"))
        self.assertIn('model_reasoning_effort="low"', argv)
        argv, task = self.spawn("design", "--effort", "ultra")
        self.assertEqual((task["model"], task["effort"]), ("saved-design", "ultra"))
        self.assertFalse(any(a.startswith("service_tier=") for a in argv))

    def test_config_path_precedence_cli_environment_xdg_then_home(self):
        self.write_config({"worker": {"model": "home-model"}})
        xdg = self.root / "xdg"
        self.write_config({"worker": {"model": "xdg-model"}}, xdg / "axiom-for-herdr" / "models.json")
        environment = self.write_config({"worker": {"model": "env-model"}}, self.root / "env.json")
        explicit = self.write_config({"worker": {"model": "cli-model"}}, self.root / "cli.json")
        self.assertEqual(json.loads(self.call("models"))["roles"]["worker"]["model"], "home-model")
        with patch.dict(helper.os.environ, {"XDG_CONFIG_HOME": str(xdg)}):
            self.assertEqual(json.loads(self.call("models"))["roles"]["worker"]["model"], "xdg-model")
            with patch.dict(helper.os.environ, {"AXIOM_HERDR_MODEL_CONFIG": "~/env.json"}):
                self.assertEqual(json.loads(self.call("models"))["config_path"], str(environment))
                _, env_task = self.spawn()
                self.assertEqual(env_task["model"], "env-model")
                _, cli_task = self.spawn("worker", "--model-config", str(explicit))
                self.assertEqual(cli_task["model"], "cli-model")
                self.assertEqual(cli_task["model_config_path"], str(explicit))

    def test_null_tier_and_cli_inherit_remove_plugin_tier_override(self):
        self.write_config({"worker": {"service_tier": None}})
        argv, task = self.spawn()
        self.assertIsNone(task["service_tier"])
        self.assertFalse(any(a.startswith(("service_tier=", "features.fast_mode=")) for a in argv))
        self.config.unlink()
        argv, task = self.spawn("worker", "--service-tier", "inherit")
        self.assertIsNone(task["service_tier"])
        self.assertFalse(any(a.startswith(("service_tier=", "features.fast_mode=")) for a in argv))

    def test_other_tier_is_forwarded_without_enabling_fast_feature(self):
        argv, task = self.spawn("worker", "--service-tier", "default")
        self.assertEqual(task["service_tier"], "default")
        self.assertIn('service_tier="default"', argv)
        self.assertNotIn("features.fast_mode=true", argv)

    def test_bad_config_stops_before_task_or_pane_creation(self):
        for data in ([], {"main": {}}, {"workre": {}}, {"worker": []},
                     {"worker": {"modle": "typo"}}, {"worker": {"model": ""}},
                     {"worker": {"model": "two words"}}, {"worker": {"model": "--help"}},
                     {"worker": {"model": "bad\u0000name"}}, {"worker": {"effort": None}},
                     {"worker": {"effort": 7}}, {"worker": {"service_tier": False}}):
            with self.subTest(data=data):
                self.write_config(data)
                with self.assertRaises(helper.Failure):
                    self.spawn()
        self.config.write_text("{broken JSON", encoding="utf-8")
        with self.assertRaisesRegex(helper.Failure, "Cannot read model config"):
            self.spawn()
        self.assertEqual(list((self.run / "tasks").iterdir()), [])
        self.assertFalse(any(c[:2] == ("pane", "split") for c in self.fake.calls))

    def test_explicit_missing_config_is_an_error_instead_of_default_fallback(self):
        with self.assertRaisesRegex(helper.Failure, "Model config not found"):
            self.spawn("worker", "--model-config", str(self.root / "missing.json"))
        with patch.dict(helper.os.environ, {"AXIOM_HERDR_MODEL_CONFIG": str(self.root / "missing.json")}):
            with self.assertRaisesRegex(helper.Failure, "Model config not found"):
                self.call("models")
        self.assertEqual(list((self.run / "tasks").iterdir()), [])

    def test_bad_cli_setting_is_rejected_before_pane_creation(self):
        for flag, value in (("--model", ""), ("--effort", "two words"), ("--service-tier", "")):
            with self.subTest(flag=flag):
                with self.assertRaises(helper.Failure):
                    self.spawn("worker", flag, value)
        self.assertEqual(list((self.run / "tasks").iterdir()), [])
        self.assertFalse(any(c[:2] == ("pane", "split") for c in self.fake.calls))

    def test_config_changes_apply_to_new_spawns_but_not_send(self):
        _, original = self.spawn("advisor")
        task_path = self.run / "tasks" / original["id"]
        self.write_config({"advisor": {"model": "custom-advisor", "effort": "medium"}})
        self.call("send", "--task", str(task_path), "--task-file", str(self.assignment))
        current = helper.read_json(task_path / "task.json")
        self.assertEqual((current["model"], current["effort"]), ("gpt-6-astra", "xhigh"))
        _, new = self.spawn("advisor")
        self.assertEqual((new["model"], new["effort"]), ("custom-advisor", "medium"))
        self.assertEqual(sum(c[:2] == ("agent", "start") for c in self.fake.calls), 2)

    def test_models_cli_runs_without_herdr_and_reports_invalid_file_on_stderr(self):
        result = subprocess.run([sys.executable, str(SCRIPT), "models"],
                                capture_output=True, text=True, env={"HOME": str(self.root)})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["roles"]["reviewer"]["effort"], "high")
        self.write_config({"worker": {"model": 42}})
        result = subprocess.run([sys.executable, str(SCRIPT), "models"],
                                capture_output=True, text=True, env={"HOME": str(self.root)})
        self.assertEqual(result.returncode, 1)
        self.assertIn("worker.model", json.loads(result.stderr)["error"])
        self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
