#!/usr/bin/env python3
"""Visible Codex delegation through herdr. Python 3.10+, standard library only."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import uuid


MODELS = {
    "worker": ("gpt-5.6-luna", "max"),
    "design": ("gpt-6-astra", "max"),
    "reviewer": ("gpt-5.6-sol", "xhigh"),
}
HERE = Path(__file__).resolve()
SKILL = HERE.parent.parent


class Failure(Exception):
    pass


def emit(value):
    print(json.dumps(value, ensure_ascii=False, indent=2), flush=True)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def atomic_json(path, value):
    path = Path(path)
    fd, temporary = tempfile.mkstemp(prefix=".write-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(value, out, ensure_ascii=False, indent=2)
            out.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def command(argv, *, env=None, timeout=45):
    try:
        p = subprocess.run(argv, env=env, capture_output=True, text=True,
                           errors="replace", timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        raise Failure("Command timed out; input may have been delivered. Inspect before retrying.") from exc
    if p.returncode:
        raise Failure((p.stderr or p.stdout or f"Command exited {p.returncode}").strip()[-3000:])
    return p.stdout


class Herdr:
    def __init__(self, run=None, socket_path=None):
        self.binary = (run or {}).get("herdr") or os.environ.get("HERDR_BIN_PATH") or shutil.which("herdr")
        if not self.binary:
            raise Failure("herdr is not on PATH. Run on the machine hosting the herdr panes.")
        self.env = os.environ.copy()
        if run is not None:
            socket_path = run.get("socket_path")
        if run is not None or socket_path is not None:
            self.env.pop("HERDR_SOCKET_PATH", None)
            if socket_path:
                self.env["HERDR_SOCKET_PATH"] = socket_path

    def call(self, *args, raw=False):
        output = command([self.binary, *map(str, args)], env=self.env)
        if raw:
            return output
        try:
            envelope = json.loads(output)
        except ValueError as exc:
            raise Failure("Expected a JSON response from herdr; inspect CLI compatibility.") from exc
        if "error" in envelope:
            raise Failure(json.dumps(envelope["error"], ensure_ascii=False))
        if "result" not in envelope:
            raise Failure("herdr response has no result field.")
        return envelope["result"]

    def current(self):
        if not os.environ.get("HERDR_PANE_ID"):
            raise Failure("HERDR_PANE_ID is unavailable to this command. Register the verified "
                          "Main with init --main-pane and --main-terminal-id, then use its run.")
        return self.call("pane", "current", "--current")["pane"]

    def agents(self):
        return {a["name"]: a for a in self.call("agent", "list")["agents"] if a.get("name")}


def caller_thread_id():
    thread_id = os.environ.get("CODEX_THREAD_ID") or None
    session_id = os.environ.get("CODEX_SESSION_ID") or None
    if thread_id and session_id and thread_id != session_id:
        raise Failure("CODEX_THREAD_ID and CODEX_SESSION_ID are contradictory and identify different conversations.")
    return thread_id or session_id


def pane_session_id(pane):
    if not isinstance(pane, dict):
        return None
    identity = pane.get("agent_session")
    if isinstance(identity, dict):
        identity = identity.get("value") or identity.get("id")
    if identity:
        return str(identity)
    for key in ("agent_session_id", "session_id", "thread_id"):
        identity = pane.get(key)
        if identity:
            return str(identity)
    return None


def is_codex_pane(pane):
    return str(pane.get("agent") or "").lower() == "codex"


def check_pane_session(pane, expected_thread_id):
    observed = pane_session_id(pane)
    if observed and observed != expected_thread_id:
        raise Failure("The Main pane reports a different Codex session/conversation than this run.")


def get_pane(herdr, pane_id):
    return herdr.call("pane", "get", str(pane_id))["pane"]


def live_panes(herdr):
    return herdr.call("pane", "list")["panes"]


def resolve_bound_main(run, herdr, thread_id):
    expected_terminal_id = run.get("main_terminal_id")
    expected_pane_id = run.get("main_pane_id")
    if not expected_terminal_id or not expected_pane_id:
        raise Failure("The bound run is missing its Main pane or terminal identity.")

    panes = live_panes(herdr)
    if not isinstance(panes, list):
        raise Failure("herdr returned no usable live pane list for the bound Main terminal.")
    recorded = [pane for pane in panes
                if isinstance(pane, dict) and pane.get("pane_id") == expected_pane_id]
    if len(recorded) > 1:
        raise Failure("The recorded Main pane identity is ambiguous or has been reused.")
    matches = [pane for pane in panes
               if isinstance(pane, dict) and pane.get("terminal_id") == expected_terminal_id]
    if len(matches) > 1:
        raise Failure("The bound Main terminal identity is ambiguous; no pane was changed.")
    if not matches:
        if recorded and recorded[0].get("terminal_id") != expected_terminal_id:
            raise Failure("The recorded Main pane was reused by another terminal; no pane was changed.")
        raise Failure("The bound Main terminal is missing from the live pane list; no pane was changed.")
    pane = matches[0]
    # Moving/swapping a terminal can leave another terminal at the old pane ID.
    # A unique surviving terminal identity is authoritative, not its old position.
    if not pane.get("pane_id") or not is_codex_pane(pane):
        raise Failure("The bound Main terminal is not a live Codex pane; no pane was changed.")
    check_pane_session(pane, thread_id)
    return pane


def main_only(run, herdr):
    if os.environ.get("AXIOM_HERDR_ROLE") in MODELS:
        raise Failure("Delegated sessions may report results, but only Main manages panes.")
    if "main_thread_id" in run:
        expected_thread_id = run.get("main_thread_id")
        if not expected_thread_id:
            raise Failure("The bound run has no Main conversation identity.")
        thread_id = caller_thread_id()
        if not thread_id:
            raise Failure("This bound run requires CODEX_THREAD_ID or CODEX_SESSION_ID.")
        if thread_id != expected_thread_id:
            raise Failure("The caller thread does not match this run's Main thread. No pane was changed.")
        return resolve_bound_main(run, herdr, thread_id)
    pane = herdr.current()
    if (not isinstance(pane, dict) or not run.get("main_terminal_id")
            or pane.get("terminal_id") != run["main_terminal_id"]):
        raise Failure("This run belongs to another Main terminal. No pane was changed.")
    return pane


def load_run(path):
    path = Path(path).expanduser().resolve()
    return path, read_json(path / "run.json")


def load_task(path):
    path = Path(path).expanduser().resolve()
    task = read_json(path / "task.json")
    run_dir, run = load_run(task["run_dir"])
    return path, task, run_dir, run


def save_task(path, task):
    atomic_json(path / "task.json", task)


def tasks_in(run_dir):
    return [(p.parent, read_json(p)) for p in sorted((run_dir / "tasks").glob("*/task.json"))]


def live_agent(task, agents):
    agent = agents.get(task["name"])
    if not agent or agent["terminal_id"] != task.get("terminal_id") or (agent.get("agent") or "").lower() != "codex":
        raise Failure(f"{task['name']}: original Codex is unavailable. Inspect the recorded pane; it was not closed.")
    return agent


def ready(agent):
    return agent["agent_status"] in ("idle", "done") and not agent.get("launch_pending", False)


def result_path(path, task):
    return path / f"{task['request_id']}.result.json"


def result_for(path, task):
    file = result_path(path, task)
    if not file.exists():
        return None
    value = read_json(file)
    if value.get("task_id") != task["id"] or value.get("request_id") != task["request_id"]:
        raise Failure("Result identity does not match the current request.")
    return value


def collected_for(path):
    return read_json(path / "collected.json") if (path / "collected.json").exists() else None


def prepare_request(path, task, source):
    assignment = Path(source).expanduser().resolve().read_text(encoding="utf-8")
    if not assignment.strip():
        raise Failure("The task file is empty.")
    request_id = uuid.uuid4().hex[:12]
    task.update(request_id=request_id, submitted=False, submission_uncertain=False)
    base = [sys.executable, str(HERE)]
    begin = shlex.join(base + ["begin", "--task", str(path), "--request-id", request_id])
    report = shlex.join(base + ["report", "--task", str(path), "--request-id", request_id,
                                "--status", "complete", "--file", str(path / f"{request_id}.report.md")])
    role_note = (
        "Review the candidate read-only. Do not edit project files, commit, format, or auto-fix. "
        "You may write your report in the assigned task directory. Read "
        f"{SKILL / 'references' / 'review.md'} before reviewing."
        if task["role"] == "reviewer" else
        "Work only within the assigned ownership. Preserve existing user changes."
    )
    packet = f"""# Axiom for herdr assignment

Role: {task['role']}. Task: {task['id']}. Request: {request_id}.
You are a delegated Codex session, not Main. Perform this assignment yourself.
Do not create subagents or manage herdr panes, including through another Axiom skill.
{role_note}

## Assignment from Main

{assignment}

## Permissions

Delegated sessions use workspace-write with approval_policy=never, independently
of Main's mode. Work within the configured writable paths and network policy.
Do not change permission settings, request escalation, or restart with broader
access. If permissions block required work, publish --status blocked with the
exact operation, target path or network destination, denial/error, why it is
needed, and work already completed. Main will assess it under Main's own
permissions and approval rules, then send a follow-up. Leave the pane open.

## Return contract

Run this before starting work, and again before acting on any direct user follow-up:
```sh
{begin}
```
This invalidates the previous report so Main does not close your pane during new work.
Write a concise report to {path / f'{request_id}.report.md'} with your conclusion,
changed files/evidence, verification actually performed, unresolved issues, and any
direct user instructions plus their effects (state none if there were none).
Then publish it with:
```sh
{report}
```
Use --status blocked instead of complete when Main must answer a question or resolve
a blocker. A complete report means this assignment returned, not that Main accepted it.
If a direct user follow-up changes the work, invalidate and republish the report before
finishing that turn. Main owns cross-worker scope and review adjudication.
Leave the pane open. Reply briefly after publishing; Main manages its lifecycle.
"""
    request = path / f"{request_id}.task.md"
    request.write_text(packet, encoding="utf-8")
    task["request_file"] = str(request)
    save_task(path, task)


def submit(path, task, herdr):
    agent = live_agent(task, herdr.agents())
    if not ready(agent):
        raise Failure("Agent is not ready for a new request. Inspect it; no prompt was sent.")
    task["submission_uncertain"] = True
    task["submitted_at"] = time.time()
    save_task(path, task)
    herdr.call("agent", "prompt", task["name"],
               f"Read {task['request_file']} and complete that assignment, including its return contract.")
    task.update(submitted=True, submission_uncertain=False)
    save_task(path, task)


def init(args):
    if os.environ.get("AXIOM_HERDR_ROLE") in MODELS:
        raise Failure("A delegated session cannot initialize an orchestration run.")
    main_pane_id = getattr(args, "main_pane", None)
    main_terminal_id = getattr(args, "main_terminal_id", None)
    if bool(main_pane_id) != bool(main_terminal_id):
        raise Failure("--main-pane and --main-terminal-id must be provided together.")
    thread_id = caller_thread_id()
    socket_path = getattr(args, "socket", None)
    herdr = Herdr() if socket_path is None else Herdr(socket_path=socket_path)
    if main_pane_id and main_terminal_id:
        if not thread_id:
            raise Failure("Explicit Main pairing requires CODEX_THREAD_ID or CODEX_SESSION_ID.")
        pane = get_pane(herdr, main_pane_id)
        if pane.get("pane_id") != main_pane_id:
            raise Failure("herdr returned a different pane than --main-pane.")
        if pane.get("terminal_id") != main_terminal_id:
            raise Failure("--main-terminal-id does not match the specified live pane.")
        if not is_codex_pane(pane):
            raise Failure("The specified Main pane does not contain a Codex agent.")
        check_pane_session(pane, thread_id)
    else:
        pane = herdr.current()
        if thread_id:
            check_pane_session(pane, thread_id)
    cwd = Path(getattr(args, "cwd", None) or os.getcwd()).expanduser().resolve()
    if not cwd.is_dir():
        raise Failure("Main cwd must be an existing directory.")
    # Keep transport files outside Git metadata, which Codex can protect read-only.
    run_dir = Path(tempfile.mkdtemp(prefix="axiom-herdr-")).resolve()
    (run_dir / "tasks").mkdir()
    run = dict(id=uuid.uuid4().hex[:12], cwd=str(cwd), main_pane_id=pane["pane_id"],
               main_terminal_id=pane["terminal_id"], herdr=str(herdr.binary),
               socket_path=herdr.env.get("HERDR_SOCKET_PATH"))
    if thread_id:
        run["main_thread_id"] = thread_id
    atomic_json(run_dir / "run.json", run)
    emit({"run": str(run_dir), "main_pane": pane["pane_id"]})


def spawn(args):
    run_dir, run = load_run(args.run)
    herdr = Herdr(run)
    # Authorize the caller before doing any local task preparation. The bound
    # Main is resolved again after the agent listing, because that work can
    # observe a terminal move or swap.
    main_only(run, herdr)
    cwd = Path(getattr(args, "cwd", None) or run["cwd"]).expanduser().resolve()
    if not cwd.is_dir():
        raise Failure("Worker cwd must be an existing directory.")
    # Read before creating any terminal.
    Path(args.task_file).expanduser().resolve().read_text(encoding="utf-8")
    path = run_dir / "tasks" / uuid.uuid4().hex[:10]
    path.mkdir(mode=0o700)
    model, effort = MODELS[args.role]
    task = dict(id=path.name, run_dir=str(run_dir), name=f"ah-{run['id']}-{path.name}",
                role=args.role, label=args.label, cwd=str(cwd), model=model, effort=effort)
    prepare_request(path, task, args.task_file)
    # Output the handle before any pane mutation so partial failures remain inspectable.
    emit({"task": str(path), "name": task["name"], "request_id": task["request_id"]})
    agents = herdr.agents()
    main_pane = main_only(run, herdr)
    layout = herdr.call("pane", "layout", "--pane", main_pane["pane_id"])["layout"]
    owned = set()
    for _, previous in tasks_in(run_dir):
        if previous.get("closed"):
            continue
        agent = agents.get(previous["name"])
        if agent and agent["terminal_id"] == previous.get("terminal_id"):
            owned.add(agent["pane_id"])
    # Split the largest existing owned pane in this tab. Never rebalance existing ratios.
    candidates = [p for p in layout["panes"] if p["pane_id"] in owned]
    if candidates:
        target = max(candidates, key=lambda p: p["rect"]["width"] * p["rect"]["height"])
        rect = target["rect"]
        direction = "right" if rect["width"] > rect["height"] * 4 else "down"
        target_id, ratio = target["pane_id"], "0.5"
    else:
        target_id, direction, ratio = main_pane["pane_id"], "right", "0.42"
    pane = herdr.call("pane", "split", target_id, "--direction", direction,
                      "--ratio", ratio, "--cwd", cwd, "--no-focus",
                      "--env", f"AXIOM_HERDR_ROLE={args.role}",
                      "--env", f"AXIOM_HERDR_TASK={path}")["pane"]
    task.update(pane_id=pane["pane_id"], terminal_id=pane["terminal_id"])
    save_task(path, task)
    herdr.call("pane", "rename", pane["pane_id"], f"{args.role} · {args.label}")
    argv = ["-C", str(cwd), "-m", model, "-c", f'model_reasoning_effort="{effort}"',
            "-c", 'default_permissions=":workspace"']
    context = [
        ("AXIOM_HERDR_ROLE", args.role),
        ("AXIOM_HERDR_TASK", path),
        ("HERDR_PANE_ID", pane["pane_id"]),
    ]
    if herdr.env.get("HERDR_SOCKET_PATH"):
        context.append(("HERDR_SOCKET_PATH", herdr.env["HERDR_SOCKET_PATH"]))
    if herdr.binary:
        context.append(("HERDR_BIN_PATH", herdr.binary))
    for key, value in context:
        argv.extend(["-c", f"shell_environment_policy.set.{key}={json.dumps(str(value), ensure_ascii=False)}"])
    argv.extend(["--sandbox", "workspace-write", "--ask-for-approval", "never",
                 "--add-dir", str(run_dir), "--no-alt-screen"])
    task["requested_codex_args"] = argv
    save_task(path, task)
    started = herdr.call("agent", "start", task["name"], "--kind", "codex",
                         "--pane", pane["pane_id"], "--timeout", "30000", "--", *argv)
    task["launched_argv"] = started.get("argv")
    save_task(path, task)
    submit(path, task, herdr)
    emit({"task": str(path), "pane_id": pane["pane_id"], "submitted": True})


def send(args):
    path, task, _, run = load_task(args.task)
    herdr = Herdr(run)
    main_only(run, herdr)
    if task.get("closed"):
        raise Failure("This task's pane has already been closed.")
    agent = live_agent(task, herdr.agents())
    if not ready(agent):
        raise Failure("Wait for an idle agent before sending a new request.")
    prepare_request(path, task, args.task_file)
    submit(path, task, herdr)
    emit({"task": str(path), "request_id": task["request_id"], "submitted": True})


def publish(args):
    path, task, _, _ = load_task(args.task)
    if task.get("closed") or args.request_id != task["request_id"]:
        raise Failure("The request is no longer current. Do not publish an old result.")
    beginning = args.action == "begin"
    text = "" if beginning else Path(args.file).expanduser().resolve().read_text(encoding="utf-8")
    if not beginning and not text.strip():
        raise Failure("The report file is empty.")
    result = dict(task_id=task["id"], request_id=args.request_id,
                  status="working" if beginning else args.status, report=text,
                  published_at=time.time())
    atomic_json(result_path(path, task), result)
    emit({"result": str(result_path(path, task)), "status": result["status"]})


def status(args):
    run_dir, run = load_run(args.run)
    herdr = Herdr(run)
    main_only(run, herdr)
    agents = herdr.agents()
    rows = []
    for path, task in tasks_in(run_dir):
        if task.get("closed") and not args.all:
            continue
        agent = agents.get(task["name"])
        if agent and agent["terminal_id"] != task.get("terminal_id"):
            agent = None
        result = result_for(path, task)
        rows.append(dict(task=str(path), role=task["role"], label=task["label"],
                         pane_id=agent["pane_id"] if agent else task.get("pane_id"),
                         state="closed" if task.get("closed") else (agent or {}).get("agent_status", "unavailable"),
                         report_status=(result or {}).get("status"),
                         submission_uncertain=task.get("submission_uncertain", False)))
    emit({"run": str(run_dir), "tasks": rows})


def wait(args):
    run_dir, run = load_run(args.run)
    herdr = Herdr(run)
    main_only(run, herdr)
    notice_path = run_dir / "wait-notices.json"
    previous = read_json(notice_path) if notice_path.exists() else {}
    deadline = time.monotonic() + args.timeout
    while True:
        agents = herdr.agents()
        events, pending = [], 0
        current = {}
        for path, task in tasks_in(run_dir):
            if task.get("closed"):
                continue
            result, collected = result_for(path, task), collected_for(path)
            agent = agents.get(task["name"])
            if agent and agent["terminal_id"] != task.get("terminal_id"):
                agent = None
            unchanged = result and collected and digest(result) == collected["digest"]
            if (unchanged and collected.get("ready") and result["status"] == "complete"
                    and agent and ready(agent)
                    and agent["state_change_seq"] == collected.get("state_change_seq")):
                continue
            pending += 1
            event = None
            if agent is None:
                event = "agent_unavailable"
            elif agent["agent_status"] in ("blocked", "unknown"):
                event = agent["agent_status"]
            elif ready(agent) and result and result["status"] in ("complete", "blocked"):
                event = "report_ready" if not unchanged else "activity_since_collection"
            elif ready(agent) and time.time() - task.get("submitted_at", 0) > 8:
                event = "idle_without_report"
            if event:
                # Collection alone is not new activity. Ignore the display event's
                # report_ready -> activity_since_collection rename in that case.
                kind = "report" if event in ("report_ready", "activity_since_collection") else event
                fingerprint = digest(dict(
                    request_id=task["request_id"], event=kind, result=result,
                    agent={key: (agent or {}).get(key) for key in
                           ("terminal_id", "agent_status", "state_change_seq", "launch_pending")},
                ))
                current[str(path)] = fingerprint
                if previous.get(str(path)) != fingerprint:
                    events.append({"task": str(path), "event": event,
                                   "pane_id": (agent or {}).get("pane_id", task.get("pane_id"))})
        # Persist across wait invocations. Resolved/closed tasks disappear from the
        # snapshot, so a later recurrence can notify again. This is not a receipt:
        # status/collect still expose outstanding work, and close keeps its checks.
        if current != previous:
            atomic_json(notice_path, current)
            previous = current
        if events or not pending:
            emit({"events": events, "pending": pending})
            return
        if time.monotonic() >= deadline:
            emit({"events": [], "pending": pending, "timeout": True})
            return
        # Poll locally; Main does not spend turns polling each terminal.
        time.sleep(min(2, max(0, deadline - time.monotonic())))


def collect(args):
    path, task, _, run = load_task(args.task)
    herdr = Herdr(run)
    main_only(run, herdr)
    result = result_for(path, task)
    if not result or result["status"] == "working":
        raise Failure("There is no finished report for this request yet.")
    agent = herdr.agents().get(task["name"])
    if agent and agent["terminal_id"] != task.get("terminal_id"):
        agent = None
    receipt = dict(request_id=task["request_id"], digest=digest(result),
                   state_change_seq=(agent or {}).get("state_change_seq"),
                   terminal_id=task.get("terminal_id"),
                   ready=bool(agent and ready(agent)), collected_at=time.time())
    atomic_json(path / "collected.json", receipt)
    emit({"task": str(path), "result": result, "receipt": receipt})


def close(args):
    path, task, _, run = load_task(args.task)
    herdr = Herdr(run)
    main_only(run, herdr)
    if task.get("closed"):
        emit({"closed": True, "already_closed": True})
        return
    result, receipt = result_for(path, task), collected_for(path)
    if not result or result["status"] != "complete" or not receipt or not receipt["ready"]:
        raise Failure("Collect a complete report from an idle agent before closing its pane.")
    if receipt["request_id"] != task["request_id"] or receipt["digest"] != digest(result):
        raise Failure("The report changed after collection. Collect and review the current report.")
    agent = live_agent(task, herdr.agents())
    if not ready(agent) or agent["state_change_seq"] != receipt["state_change_seq"]:
        raise Failure("Agent activity changed after collection. Inspect it before closing.")
    if agent["terminal_id"] == run["main_terminal_id"]:
        raise Failure("Refusing to close the Main terminal.")
    # Recheck the report after reading live state, narrowing the direct-intervention race.
    if digest(result_for(path, task)) != receipt["digest"]:
        raise Failure("Report changed during close; no pane was closed.")
    herdr.call("pane", "close", agent["pane_id"])
    task["closed"] = True
    save_task(path, task)
    emit({"closed": True, "task": str(path), "report": str(result_path(path, task))})


def read(args):
    _, task, _, run = load_task(args.task)
    herdr = Herdr(run)
    main_only(run, herdr)
    agent = live_agent(task, herdr.agents())
    print(herdr.call("agent", "read", agent["pane_id"], "--source", "recent-unwrapped",
                     "--lines", args.lines, raw=True), end="")


def doctor(args):
    run_path = getattr(args, "run", None)
    if run_path:
        _, run = load_run(run_path)
        herdr = Herdr(run)
        calling_pane = main_only(run, herdr)
    else:
        herdr = Herdr()
        if not os.environ.get("HERDR_PANE_ID"):
            raise Failure("No bound run was supplied and HERDR_PANE_ID is unavailable; "
                          "use init --main-pane and --main-terminal-id from the Main UI.")
        calling_pane = herdr.current()
    codex = shutil.which("codex")
    if not codex:
        raise Failure("codex is not on PATH on this machine.")
    emit({"herdr": command([herdr.binary, "--version"]).strip(),
          "codex": command([codex, "--version"]).strip(),
          "calling_pane": calling_pane,
          "note": "Read-only environment check; no agents were started."})


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="action", required=True)
    q = sub.add_parser("doctor", help="Inspect versions and the current herdr pane")
    q.add_argument("--run", help="Use and validate an existing orchestration run")
    q.set_defaults(fn=doctor)
    q = sub.add_parser("init", help="Create a run owned by the current Main pane")
    q.add_argument("--cwd")
    q.add_argument("--main-pane", help="Explicitly pair Main with this live herdr pane")
    q.add_argument("--main-terminal-id", help="Explicitly pair Main with this terminal identity")
    q.add_argument("--socket", help="Use this herdr socket for this run")
    q.set_defaults(fn=init)
    q = sub.add_parser("spawn", help="Start a visible Codex and send one task")
    q.add_argument("--run", required=True)
    q.add_argument("--role", choices=MODELS, default="worker")
    q.add_argument("--label", required=True)
    q.add_argument("--task-file", required=True)
    q.add_argument("--cwd")
    q.set_defaults(fn=spawn)
    q = sub.add_parser("send", help="Send a follow-up to the same idle Codex session")
    q.add_argument("--task", required=True)
    q.add_argument("--task-file", required=True)
    q.set_defaults(fn=send)
    for name in ("begin", "report"):
        q = sub.add_parser(name, help="Worker-only result publication protocol")
        q.add_argument("--task", required=True)
        q.add_argument("--request-id", required=True)
        if name == "report":
            q.add_argument("--status", choices=("complete", "blocked"), required=True)
            q.add_argument("--file", required=True)
        q.set_defaults(fn=publish)
    q = sub.add_parser("status", help="List owned active tasks")
    q.add_argument("--run", required=True)
    q.add_argument("--all", action="store_true")
    q.set_defaults(fn=status)
    q = sub.add_parser("wait", help="Wait for a report or attention from any owned task")
    q.add_argument("--run", required=True)
    q.add_argument("--timeout", type=float, default=3600)
    q.set_defaults(fn=wait)
    for name, fn in (("collect", collect), ("close", close), ("read", read)):
        q = sub.add_parser(name)
        q.add_argument("--task", required=True)
        if name == "read":
            q.add_argument("--lines", type=int, default=120)
        q.set_defaults(fn=fn)
    return p


if __name__ == "__main__":
    try:
        options = parser().parse_args()
        options.fn(options)
    except (Failure, OSError, ValueError, KeyError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)
