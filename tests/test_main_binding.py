"""Main conversation/pane binding regressions with simulated herdr state."""

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
SPEC = importlib.util.spec_from_file_location("axiom_herdr_binding", SCRIPT)
helper = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(helper)


class FakeHerdr:
    def __init__(self, panes=None, agents=None, socket_path="/tmp/herdr.sock"):
        self.panes = list(panes or [])
        self.agent_rows = dict(agents or {})
        self.calls = []
        self.binary = "/usr/local/bin/herdr"
        self.env = {"HERDR_SOCKET_PATH": socket_path} if socket_path else {}
        self.current_pane = self.panes[0] if self.panes else None
        self.child_number = 0

    def current(self):
        self.calls.append(("pane", "current", "--current"))
        if self.current_pane is None:
            raise helper.Failure("current pane should not be used")
        return self.current_pane

    def agents(self):
        self.calls.append(("agent", "list"))
        return self.agent_rows

    def call(self, *args, raw=False):
        self.calls.append(args)
        if args[:2] == ("pane", "get"):
            pane_id = args[2]
            for pane in self.panes:
                if pane.get("pane_id") == pane_id:
                    return {"pane": pane}
            raise helper.Failure("pane not found")
        if args[:2] == ("pane", "list"):
            return {"panes": self.panes}
        if args[:2] == ("pane", "layout"):
            return {"layout": {"panes": [], "splits": []}}
        if args[:2] == ("pane", "split"):
            self.child_number += 1
            pane = {
                "pane_id": f"child-pane-{self.child_number}",
                "terminal_id": f"child-terminal-{self.child_number}",
            }
            self.panes.append(pane)
            return {"pane": pane}
        if args[:2] == ("pane", "rename"):
            return {}
        if args[:2] == ("agent", "start"):
            name = args[2]
            pane_id = args[args.index("--pane") + 1]
            terminal_id = next(p["terminal_id"] for p in self.panes if p["pane_id"] == pane_id)
            self.agent_rows[name] = {
                "name": name,
                "agent": "codex",
                "pane_id": pane_id,
                "terminal_id": terminal_id,
                "agent_status": "idle",
                "launch_pending": False,
                "state_change_seq": 1,
            }
            argv = list(args[args.index("--") + 1:])
            return {"argv": argv}
        if args[:2] == ("agent", "prompt"):
            return {}
        if args[:2] == ("agent", "read") and raw:
            return "pane output\n"
        if args[:2] == ("pane", "close"):
            return {}
        raise AssertionError(f"unexpected herdr call: {args}")


class MovingMainFakeHerdr(FakeHerdr):
    """Replace pane snapshots when agents() first observes a Main move."""

    def __init__(self, initial_panes, moved_panes, agents=None):
        super().__init__(initial_panes, agents)
        self.moved_panes = [dict(value) for value in moved_panes]
        self.has_moved = False

    def agents(self):
        self.calls.append(("agent", "list"))
        if not self.has_moved:
            # Replace the list and its pane dictionaries instead of mutating an
            # object returned by the initial pane lookup.
            self.panes = [dict(value) for value in self.moved_panes]
            self.current_pane = self.panes[0] if self.panes else None
            self.has_moved = True
        return self.agent_rows


def pane(pane_id="main-pane", terminal_id="main-terminal", session_id="main-thread",
         agent="codex"):
    value = {
        "pane_id": pane_id,
        "terminal_id": terminal_id,
        "agent": agent,
    }
    if session_id is not None:
        value["agent_session"] = {"agent": "codex", "kind": "id",
                                   "source": "herdr:codex", "value": session_id}
    return value


class MainBindingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        role_patch = patch.dict(helper.os.environ, {"AXIOM_HERDR_ROLE": "main"})
        role_patch.start()
        self.addCleanup(role_patch.stop)

    def bound_run(self, **updates):
        run = {
            "id": "run-1",
            "cwd": str(self.root),
            "main_pane_id": "old-main-pane",
            "main_terminal_id": "main-terminal",
            "main_thread_id": "main-thread",
            "herdr": "/usr/local/bin/herdr",
            "socket_path": "/tmp/herdr.sock",
        }
        run.update(updates)
        return run

    def test_bound_matching_thread_works_without_herdr_environment(self):
        fake = FakeHerdr([pane("moved-main-pane")])
        with patch.dict(helper.os.environ, {"CODEX_THREAD_ID": "main-thread"}, clear=True):
            result = helper.main_only(self.bound_run(), fake)
        self.assertEqual(result["pane_id"], "moved-main-pane")
        self.assertIn(("pane", "list"), fake.calls)
        self.assertNotIn(("pane", "current", "--current"), fake.calls)

    def test_bound_run_falls_back_to_codex_session_id(self):
        fake = FakeHerdr([pane("moved-main-pane")])
        with patch.dict(helper.os.environ, {"CODEX_SESSION_ID": "main-thread"}, clear=True):
            self.assertEqual(helper.main_only(self.bound_run(), fake)["pane_id"], "moved-main-pane")

    def test_main_swap_follows_terminal_when_old_position_is_occupied(self):
        fake = FakeHerdr([
            pane("old-main-pane", terminal_id="other-terminal", session_id="other-thread"),
            pane("moved-main-pane"),
        ])
        with patch.dict(helper.os.environ, {"CODEX_THREAD_ID": "main-thread"}, clear=True):
            self.assertEqual(helper.main_only(self.bound_run(), fake)["pane_id"], "moved-main-pane")

    def test_bound_run_rejects_wrong_missing_and_conflicting_thread(self):
        cases = (
            ({"CODEX_THREAD_ID": "other-thread"}, "caller thread"),
            ({}, "requires CODEX_THREAD_ID"),
            ({"CODEX_THREAD_ID": "main-thread", "CODEX_SESSION_ID": "other-thread"},
             "different conversations"),
        )
        for environment, message in cases:
            with self.subTest(environment=environment):
                fake = FakeHerdr([pane("moved-main-pane")])
                with patch.dict(helper.os.environ, environment, clear=True):
                    with self.assertRaisesRegex(helper.Failure, message):
                        helper.main_only(self.bound_run(), fake)
                self.assertNotIn(("pane", "list"), fake.calls)

    def test_bound_run_rejects_missing_reused_ambiguous_or_different_thread_main(self):
        cases = (
            ([], "missing"),
            ([pane("old-main-pane", terminal_id="new-terminal")], "reused"),
            ([pane("new-1"), pane("new-2")], "ambiguous"),
            ([pane("new-main-pane", session_id="other-thread")], "different Codex session"),
        )
        for panes, message in cases:
            with self.subTest(message=message):
                fake = FakeHerdr(panes)
                with patch.dict(helper.os.environ, {"CODEX_THREAD_ID": "main-thread"}, clear=True):
                    with self.assertRaisesRegex(helper.Failure, message):
                        helper.main_only(self.bound_run(), fake)

    def test_focus_and_inherited_pane_id_cannot_retarget_bound_run(self):
        fake = FakeHerdr([pane("moved-main-pane")])
        fake.current_pane = pane("unrelated-pane", terminal_id="unrelated-terminal")
        with patch.dict(helper.os.environ, {
            "CODEX_THREAD_ID": "main-thread",
            "HERDR_PANE_ID": "unrelated-pane",
        }, clear=True):
            result = helper.main_only(self.bound_run(), fake)
        self.assertEqual(result["pane_id"], "moved-main-pane")
        self.assertNotIn(("pane", "current", "--current"), fake.calls)

    def test_explicit_init_validates_pane_terminal_codex_and_thread(self):
        fake = FakeHerdr([pane("main-pane", terminal_id="main-terminal")], socket_path="/tmp/custom.sock")
        run_dir = self.root / "new-run"
        run_dir.mkdir()
        with patch.dict(helper.os.environ, {"CODEX_THREAD_ID": "main-thread"}, clear=True), \
                patch.object(helper, "Herdr", return_value=fake), \
                patch.object(helper.tempfile, "mkdtemp", return_value=str(run_dir)):
            output = io.StringIO()
            with redirect_stdout(output):
                helper.init(argparse.Namespace(
                    cwd=str(self.root), main_pane="main-pane",
                    main_terminal_id="main-terminal", socket="/tmp/custom.sock"))
        run = helper.read_json(run_dir / "run.json")
        self.assertEqual(run["main_thread_id"], "main-thread")
        self.assertEqual(run["socket_path"], "/tmp/custom.sock")
        self.assertIn(("pane", "get", "main-pane"), fake.calls)
        self.assertNotIn(("pane", "current", "--current"), fake.calls)

    def test_explicit_init_requires_both_ids_thread_and_codex(self):
        fake = FakeHerdr([pane("main-pane", terminal_id="main-terminal")])
        common = dict(cwd=str(self.root), main_pane=None, main_terminal_id=None, socket=None)
        with patch.object(helper, "Herdr", return_value=fake):
            with self.assertRaisesRegex(helper.Failure, "provided together"):
                helper.init(argparse.Namespace(**{**common, "main_pane": "main-pane"}))
        with patch.dict(helper.os.environ, {}, clear=True), patch.object(helper, "Herdr", return_value=fake):
            with self.assertRaisesRegex(helper.Failure, "requires CODEX_THREAD_ID"):
                helper.init(argparse.Namespace(**{**common, "main_pane": "main-pane",
                                                   "main_terminal_id": "main-terminal"}))
        non_codex = FakeHerdr([pane("main-pane", terminal_id="main-terminal", agent="claude")])
        with patch.dict(helper.os.environ, {"CODEX_THREAD_ID": "main-thread"}, clear=True), \
                patch.object(helper, "Herdr", return_value=non_codex):
            with self.assertRaisesRegex(helper.Failure, "does not contain a Codex"):
                helper.init(argparse.Namespace(**{**common, "main_pane": "main-pane",
                                                   "main_terminal_id": "main-terminal"}))

    def test_environment_init_keeps_old_path_and_binds_thread_when_available(self):
        fake = FakeHerdr([pane("current-pane", terminal_id="current-terminal")])
        run_dir = self.root / "env-run"
        run_dir.mkdir()
        with patch.dict(helper.os.environ, {
            "HERDR_PANE_ID": "current-pane",
            "CODEX_THREAD_ID": "main-thread",
        }, clear=True), patch.object(helper, "Herdr", return_value=fake), \
                patch.object(helper.tempfile, "mkdtemp", return_value=str(run_dir)):
            with redirect_stdout(io.StringIO()):
                helper.init(argparse.Namespace(cwd=str(self.root), socket=None))
        run = helper.read_json(self.root / "env-run" / "run.json")
        self.assertEqual(run["main_thread_id"], "main-thread")
        self.assertIn(("pane", "current", "--current"), fake.calls)

    def test_spawn_passes_scoped_metadata_and_fixed_permissions_for_every_role(self):
        task_file = self.root / "assignment.md"
        task_file.write_text("do the bounded work\n", encoding="utf-8")
        expected_models = {
            "worker": ("gpt-5.6-luna", "max"),
            "design": ("gpt-5.6-sol", "max"),
            "reviewer": ("gpt-5.6-sol", "xhigh"),
        }
        for role, (model, effort) in expected_models.items():
            with self.subTest(role=role):
                run_dir = self.root / f"run-{role}"
                (run_dir / "tasks").mkdir(parents=True)
                helper.atomic_json(run_dir / "run.json", self.bound_run(cwd=str(self.root)))
                fake = FakeHerdr([pane("main-pane")])
                with patch.dict(helper.os.environ, {"CODEX_THREAD_ID": "main-thread"}, clear=True), \
                        patch.object(helper, "Herdr", return_value=fake):
                    output = io.StringIO()
                    with redirect_stdout(output):
                        helper.spawn(argparse.Namespace(
                            run=str(run_dir), role=role, label="label",
                            task_file=str(task_file), cwd=str(self.root)))
                start = next(call for call in fake.calls if call[:2] == ("agent", "start"))
                argv = list(start[start.index("--") + 1:])
                self.assertEqual(argv[argv.index("-m") + 1], model)
                self.assertIn(f'model_reasoning_effort="{effort}"', argv)
                tier_args = [value for value in argv if value.startswith("service_tier=")]
                fast_args = [value for value in argv if value.startswith("features.fast_mode=")]
                self.assertEqual(tier_args, ['service_tier="fast"'] if role == "worker" else [])
                self.assertEqual(fast_args, ["features.fast_mode=true"] if role == "worker" else [])
                config = {}
                for index, value in enumerate(argv[:-1]):
                    if value == "-c" and argv[index + 1].startswith("shell_environment_policy.set."):
                        key, raw = argv[index + 1].split("=", 1)
                        config[key.rsplit(".", 1)[-1]] = json.loads(raw)
                self.assertEqual(config["AXIOM_HERDR_ROLE"], role)
                self.assertTrue(config["AXIOM_HERDR_TASK"].endswith("/tasks/" + next(
                    path.name for path in (run_dir / "tasks").iterdir())))
                self.assertEqual(config["HERDR_PANE_ID"], "child-pane-1")
                self.assertEqual(config["HERDR_SOCKET_PATH"], "/tmp/herdr.sock")
                self.assertEqual(config["HERDR_BIN_PATH"], "/usr/local/bin/herdr")
                self.assertEqual(set(config), {
                    "AXIOM_HERDR_ROLE", "AXIOM_HERDR_TASK", "HERDR_PANE_ID",
                    "HERDR_SOCKET_PATH", "HERDR_BIN_PATH",
                })
                self.assertEqual(argv[argv.index("--sandbox") + 1], "workspace-write")
                self.assertIn('default_permissions=":workspace"', argv)
                self.assertEqual(argv[argv.index("--ask-for-approval") + 1], "never")
                split = next(call for call in fake.calls if call[:2] == ("pane", "split"))
                self.assertIn("--env", split)
                self.assertIn(f"AXIOM_HERDR_ROLE={role}", split)
                self.assertTrue(any(str(value).startswith("AXIOM_HERDR_TASK=") for value in split))

    def test_spawn_rechecks_main_after_agent_listing_when_main_moves(self):
        task_file = self.root / "assignment.md"
        task_file.write_text("do the bounded work\n", encoding="utf-8")
        run_dir = self.root / "spawn-run"
        (run_dir / "tasks").mkdir(parents=True)
        helper.atomic_json(run_dir / "run.json", self.bound_run(cwd=str(self.root)))
        fake = MovingMainFakeHerdr(
            initial_panes=[pane("old-main-pane")],
            moved_panes=[
                pane("old-main-pane", terminal_id="other-terminal", session_id="other-thread"),
                pane("new-main-pane"),
            ],
        )
        with patch.dict(helper.os.environ, {"CODEX_THREAD_ID": "main-thread"}, clear=True), \
                patch.object(helper, "Herdr", return_value=fake):
            with redirect_stdout(io.StringIO()):
                helper.spawn(argparse.Namespace(
                    run=str(run_dir), role="worker", label="label",
                    task_file=str(task_file), cwd=str(self.root)))
        split = next(call for call in fake.calls if call[:2] == ("pane", "split"))
        self.assertEqual(split[2], "new-main-pane")
        self.assertNotEqual(split[2], "old-main-pane")

    def test_spawn_rejects_disappeared_main_after_agent_listing_without_split(self):
        task_file = self.root / "assignment.md"
        task_file.write_text("do the bounded work\n", encoding="utf-8")
        run_dir = self.root / "spawn-run"
        (run_dir / "tasks").mkdir(parents=True)
        helper.atomic_json(run_dir / "run.json", self.bound_run(cwd=str(self.root)))
        fake = MovingMainFakeHerdr(
            initial_panes=[pane("old-main-pane")],
            moved_panes=[pane("old-main-pane", terminal_id="other-terminal", session_id="other-thread")],
        )
        output = io.StringIO()
        with patch.dict(helper.os.environ, {"CODEX_THREAD_ID": "main-thread"}, clear=True), \
                patch.object(helper, "Herdr", return_value=fake):
            with self.assertRaisesRegex(helper.Failure, "reused"):
                with redirect_stdout(output):
                    helper.spawn(argparse.Namespace(
                        run=str(run_dir), role="worker", label="label",
                        task_file=str(task_file), cwd=str(self.root)))
        self.assertTrue(any(call[:2] == ("agent", "list") for call in fake.calls))
        self.assertFalse(any(call[:2] == ("pane", "split") for call in fake.calls))
        self.assertIn('"task":', output.getvalue())

    def test_status_and_read_require_bound_main_ownership(self):
        run_dir = self.root / "status-run"
        (run_dir / "tasks" / "one").mkdir(parents=True)
        run = self.bound_run()
        helper.atomic_json(run_dir / "run.json", run)
        helper.save_task(run_dir / "tasks" / "one", {
            "id": "one", "run_dir": str(run_dir), "name": "worker-one",
            "request_id": "request-1", "terminal_id": "worker-terminal",
            "pane_id": "worker-pane", "role": "worker", "label": "worker",
        })
        fake = FakeHerdr([pane("moved-main-pane")], {
            "worker-one": {
                "name": "worker-one", "agent": "codex", "pane_id": "worker-pane",
                "terminal_id": "worker-terminal", "agent_status": "idle",
                "launch_pending": False, "state_change_seq": 1,
            }
        })
        with patch.dict(helper.os.environ, {"CODEX_THREAD_ID": "main-thread"}, clear=True), \
                patch.object(helper, "Herdr", return_value=fake):
            output = io.StringIO()
            with redirect_stdout(output):
                helper.status(argparse.Namespace(run=str(run_dir), all=False))
                helper.read(argparse.Namespace(task=str(run_dir / "tasks" / "one"), lines=10))
        self.assertNotIn(("pane", "current", "--current"), fake.calls)
        self.assertGreaterEqual(fake.calls.count(("pane", "list")), 2)

    def test_doctor_without_run_describes_missing_binding_without_claiming_ui_is_outside_herdr(self):
        fake = FakeHerdr()
        with patch.dict(helper.os.environ, {}, clear=True), patch.object(helper, "Herdr", return_value=fake):
            with self.assertRaisesRegex(helper.Failure, "No bound run.*HERDR_PANE_ID"):
                helper.doctor(argparse.Namespace(run=None))

    def test_doctor_validates_an_existing_bound_run_without_herdr_environment(self):
        run_dir = self.root / "doctor-run"
        run_dir.mkdir()
        helper.atomic_json(run_dir / "run.json", self.bound_run())
        fake = FakeHerdr([pane("moved-main-pane")])
        with patch.dict(helper.os.environ, {"CODEX_THREAD_ID": "main-thread"}, clear=True), \
                patch.object(helper, "Herdr", return_value=fake), \
                patch.object(helper.shutil, "which", return_value="/usr/bin/codex"), \
                patch.object(helper, "command", return_value="version\n"):
            output = io.StringIO()
            with redirect_stdout(output):
                helper.doctor(argparse.Namespace(run=str(run_dir)))
        report = json.loads(output.getvalue())
        self.assertEqual(report["calling_pane"]["pane_id"], "moved-main-pane")
        self.assertNotIn(("pane", "current", "--current"), fake.calls)


if __name__ == "__main__":
    unittest.main()
