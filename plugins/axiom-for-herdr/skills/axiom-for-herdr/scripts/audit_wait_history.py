#!/usr/bin/env python3
"""Audit Axiom Main wait behavior in Codex rollout JSONL files."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re
import sys


HELPER_ACTION = re.compile(r"(?:^|[/\\])axiom_herdr\.py\s+(wait|status|read)\b")
RUN_ARGUMENT = re.compile(r"(?:^|\s)--run(?:=|\s+)([^\s'\"]+)")
TIMEOUT_ARGUMENT = re.compile(r"(?:^|\s)--timeout(?:=|\s+)([0-9]+(?:\.[0-9]+)?)")


def rollout_files(paths):
    found = set()
    for supplied in paths:
        path = Path(supplied).expanduser()
        candidates = path.rglob("rollout-*.jsonl") if path.is_dir() else (path,)
        for candidate in candidates:
            if candidate.is_file():
                found.add(candidate.resolve())
    return sorted(found)


def command_text(item):
    command = item.get("command")
    if isinstance(command, list):
        return " ".join(str(part) for part in command)
    return str(command or "")


def output_json(item):
    for key in ("stdout", "aggregated_output", "formatted_output"):
        value = item.get(key)
        if not isinstance(value, str) or not value.strip():
            continue
        try:
            parsed = json.loads(value)
        except ValueError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return {}


def outcome(value, item=None):
    if item and item.get("exit_code") not in (None, 0):
        return "error"
    reason = value.get("reason")
    if isinstance(reason, str):
        return reason
    if value.get("timeout") is True:
        return "safety_timeout"
    if value.get("events"):
        return "event"
    if value.get("pending") == 0:
        return "no_pending"
    return "unknown"


def duration_seconds(item):
    duration = item.get("duration") or {}
    if isinstance(duration, dict) and "secs" in duration:
        return float(duration.get("secs", 0)) + float(duration.get("nanos", 0)) / 1_000_000_000
    started, completed = item.get("started_at_ms"), item.get("completed_at_ms")
    if isinstance(started, (int, float)) and isinstance(completed, (int, float)):
        return max(0.0, (completed - started) / 1000)
    return 0.0


def maximum_concurrency(intervals):
    points = []
    for started, completed in intervals:
        if started is None or completed is None:
            continue
        points.extend(((started, 1), (completed, -1)))
    active = maximum = 0
    for _, change in sorted(points, key=lambda point: (point[0], point[1])):
        active += change
        maximum = max(maximum, active)
    return maximum


def blank_session(path, thread_id):
    return {
        "file": str(path),
        "thread_id": thread_id,
        "waits": 0,
        "reasons": Counter(),
        "timeout_arguments": Counter(),
        "status_calls": 0,
        "read_calls": 0,
        "wait_duration_seconds": 0.0,
        "intervals": defaultdict(list),
        "malformed_lines": 0,
    }


def audit_file(path):
    sessions = {}
    fallback_id = path.stem
    with path.open(encoding="utf-8", errors="replace") as source:
        for line in source:
            try:
                record = json.loads(line)
            except ValueError:
                session = sessions.setdefault(fallback_id, blank_session(path, fallback_id))
                session["malformed_lines"] += 1
                continue
            if record.get("type") != "event_msg":
                continue
            payload = record.get("payload") or {}
            if payload.get("type") != "item_completed":
                continue
            item = payload.get("item") or {}
            if item.get("type") != "CommandExecution":
                continue
            text = command_text(item)
            match = HELPER_ACTION.search(text)
            if not match:
                continue
            thread_id = str(payload.get("thread_id") or fallback_id)
            session = sessions.setdefault(thread_id, blank_session(path, thread_id))
            action = match.group(1)
            if action == "status":
                session["status_calls"] += 1
                continue
            if action == "read":
                session["read_calls"] += 1
                continue

            session["waits"] += 1
            value = output_json(item)
            session["reasons"][outcome(value, item)] += 1
            timeout = TIMEOUT_ARGUMENT.search(text)
            session["timeout_arguments"][timeout.group(1) if timeout else "until-event"] += 1
            session["wait_duration_seconds"] += duration_seconds(item)
            run = RUN_ARGUMENT.search(text)
            run_id = run.group(1) if run else "unknown"
            session["intervals"][run_id].append(
                (item.get("started_at_ms", payload.get("started_at_ms")),
                 item.get("completed_at_ms", payload.get("completed_at_ms")))
            )
    return sessions.values()


def serializable(session):
    intervals = session.pop("intervals")
    session["reasons"] = dict(sorted(session["reasons"].items()))
    session["timeout_arguments"] = dict(sorted(session["timeout_arguments"].items()))
    session["wait_duration_seconds"] = round(session["wait_duration_seconds"], 3)
    session["max_concurrent_waits"] = max(
        (maximum_concurrency(run_intervals) for run_intervals in intervals.values()),
        default=0,
    )
    return session


def audit(paths):
    sessions = []
    for path in rollout_files(paths):
        sessions.extend(serializable(session) for session in audit_file(path))
    sessions.sort(key=lambda session: (session["file"], session["thread_id"]))
    totals = {
        "files": len({session["file"] for session in sessions}),
        "sessions": len(sessions),
        "waits": sum(session["waits"] for session in sessions),
        "reasons": dict(sorted(sum((Counter(session["reasons"]) for session in sessions), Counter()).items())),
        "status_calls": sum(session["status_calls"] for session in sessions),
        "read_calls": sum(session["read_calls"] for session in sessions),
        "max_concurrent_waits": max(
            (session["max_concurrent_waits"] for session in sessions), default=0
        ),
    }
    return {"totals": totals, "sessions": sessions}


def parser():
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("paths", nargs="+", help="Rollout JSONL files or directories")
    return value


def main():
    args = parser().parse_args()
    result = audit(args.paths)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
