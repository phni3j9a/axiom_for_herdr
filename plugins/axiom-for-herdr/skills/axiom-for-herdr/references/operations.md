# Operating the helper

Resolve `scripts/axiom_herdr.py` relative to this skill. In shell examples below,
`helper`, `run_dir`, and `task_dir` stand for absolute paths captured from output;
they are not fixed locations. Do not interpolate user text into shell commands.
Write the exact assignment into a file and use `--task-file`.

## Main operations

```sh
python3 "$helper" doctor
python3 "$helper" init --cwd "$project_dir"
```

`init` creates a private temporary run directory and binds it to the calling
Main's herdr terminal and server endpoint. Record its returned `run` path.
It can also handle a project without Git; Main still checks any repository
instructions and existing Git changes when applicable. Reuse the same run
through compaction instead of creating a second set of workers.

### Main registration with a shared app-server

If commands lack `HERDR_PANE_ID`, register the verified association explicitly:

```sh
python3 "$helper" init --cwd "$project_dir" \
  --main-pane "$verified_pane_id" \
  --main-terminal-id "$verified_terminal_id" \
  --socket "$herdr_socket_path"
python3 "$helper" doctor --run "$run_dir"
```

Use the calling conversation's `CODEX_THREAD_ID` (`CODEX_SESSION_ID` is a fallback),
not a copied ID from another conversation. Both explicit pane and terminal IDs are
required. The helper validates that the specified live pane is the expected Codex
terminal and checks any advertised session identity. It records the caller's thread
ID and selected socket in the private run directory. No global registry is needed.

The initial pairing is an explicit association established by Main/user; the presence
of two IDs alone does not prove that a pane displays this conversation. Get candidate
IDs from `herdr pane list`. Prefer an exact advertised `agent_session` identity match.
When absent, inspect the candidate terminal to establish that it contains this
conversation, or use an explicit user-provided association. Do not infer the pairing
from focus, cwd, or the number of agents. If uncertain, obtain the missing identity.
`herdr status server` shows the socket; `--socket` affects only this command/run.

Once bound, every Main operation checks the caller's conversation ID and finds the
recorded terminal in the live pane list. A moved Main follows its original terminal;
a missing/reused terminal or a different conversation is rejected. An unrelated
focused pane or inherited `HERDR_PANE_ID` cannot retarget a registered run. Old runs
without a thread binding keep their original current-pane ownership check.
Spawn refreshes Main after task preparation and agent listing, just before deriving
the layout/split target. The separate lookup and split calls are not atomic against
a simultaneous move; herdr has no terminal-ID/CAS precondition for this split.

```sh
python3 "$helper" spawn --run "$run_dir" --role worker \
  --label 'SSH再接続の実装' --task-file "$assignment_file"
```

Roles: `worker` (Luna MAX), `design` (Astra MAX), `reviewer` (Sol XHIGH).
`--cwd /absolute/worktree` optionally starts the worker in a worktree Main has
already prepared. Model/effort are selected by the role. Every role explicitly
launches with `--sandbox workspace-write --ask-for-approval never`, independently
of Main's current mode and the user's approval/sandbox defaults. The launch also
pins `-c default_permissions=":workspace"` because the tested CLI 0.154.0 / shared
app-server 0.153.4 pair used broad permissions with the legacy flags alone. In that
pair, both selectors together produced workspace-write / never and an outside-write
denial. This is measured compatibility for that pair, not a cross-version guarantee.
[Codex's permission docs](https://learn.chatgpt.com/docs/permissions) say profiles and
legacy sandbox settings do not compose; ordinarily the legacy selector wins. Do not
copy the dual selectors into user config or infer that both policies are merged.
Verify effective child permissions when upgrading Codex. The helper does
not edit Codex configuration or add bypass flags. Network settings and other
configured limits remain in effect; network access is not enabled by the helper.
The assigned cwd and the temporary run directory added through `--add-dir` let
the child edit its worktree and publish its report outside protected Git metadata.
Review read-only behavior is an instruction contract, allowing only the assigned
report directory to be written; it is not a separate sandbox enforcement layer.

The child role (`AXIOM_HERDR_ROLE`), report directory (`AXIOM_HERDR_TASK`), and
available herdr pane/socket/binary context are supplied both to the pane shell and
through per-session `-c shell_environment_policy.set.KEY=...` overrides. The latter
survive shared app-server command execution without modifying user/project config
or replacing unrelated environment-policy keys. Never put one child's context into
the shared daemon's global environment. Explicit environment values still respect
configured include filters; if a custom allowlist excludes the context keys, report
that conflict instead of broadening filters or claiming the context was delivered.

The fixed settings apply to newly spawned children. Updating the plugin or using
`send` does not reconfigure an already-running Codex session.

`spawn` prints JSON objects, one before startup and another after prompt submission.
Capture the first object's `task` path even if startup later fails. It creates the
pane, names it, starts interactive Codex, and sends a short prompt pointing to the
self-contained task file. It returns after submission, without waiting for the
work to finish. Create several independent workers before invoking `wait`.

Serialize `init`, `spawn`, `send`, `collect`, and `close` for each run, and keep at
most one active `wait` process for that run. Their Codex workers execute
concurrently. Mutations are Main-owned; there is no scheduler daemon or shared
database.

```sh
python3 "$helper" status --run "$run_dir"
python3 "$helper" wait --run "$run_dir" --timeout 3600
python3 "$helper" collect --task "$task_dir"
python3 "$helper" close --task "$task_dir"
```

`wait` samples the task reports and herdr's agent list every two seconds inside
one local process, without calling Main's model. It prints only when returning:
a new report/attention notification, no pending tasks, or timeout. Interrupting
this helper does not stop the workers.

### Waiting without repeatedly waking Main

1. Start `wait --timeout 3600` once after launching independent work. If the exec
   tool yields a running session ID, retain that ID through compaction. Initial
   process launch may yield sooner; use the fixed continuation wait below.
2. When Main has no useful independent work, wait on that same session for
   **300 seconds (five minutes)**. With `write_stdin`, use empty `chars` and
   **`yield_time_ms=300000` on every result-wait call**. Do not omit the value,
   shorten it to 60000, or choose an interval based on expected completion,
   progress commentary, or the "longest allowed" wording. If an outer execution
   wrapper also yields, use `yield_time_ms=300000` on its continuation handle as
   well; do not launch another helper.
3. If the tool returns with no new output and the session is still running,
   continue the same session with `yield_time_ms=300000`. A host that rejects or
   clamps this value needs the unsupported-host handling below. Do not insert
   `status`, `read`, transcript scans,
   short sleeps, or another waiter. Progress commentary follows the session's
   communication rules and does not require extra state reads.
4. On events, collect reports or investigate the specific affected task. Resolve
   what is actionable and retain any deferred blocker in Main's context before
   waiting for other work. On `pending: 0`, continue integration or finish; do not
   restart the waiter. On helper timeout, reassess once and start another helper
   only if work is still expected; retain the five-minute result-wait value.
   Diagnose helper errors before retrying them.

The helper's `--timeout` is in seconds; the exec tool's result-wait interval is a
separate setting, often in milliseconds. A one-hour helper does not force Codex
to wait one hour in a single tool call. The five-minute value is the result-wait
timeout, not a delay applied to completed work: reports, attention, process exit,
and user steering can return earlier and must be handled promptly. Do not pad
those returns with sleeps. The helper's internal polling remains two seconds.

**Unsupported host:** if the tool cannot accept/honor 300000 ms, an outer wrapper
forces shorter wakeups, or higher-priority rules require shorter waits, record
and report that specific limitation once. Do not reinterpret this policy as
one-minute polling, repeatedly try shorter waits, change host configuration, or
claim that five-minute Main wakeups are enforced. Preserve the active helper and
worker handles. Use an already available, permitted event-driven continuation
if it can meet the policy; otherwise continue useful independent work or surface
the waiting limitation when no such work remains. This skill cannot override
host limits or higher-priority instructions and does not install a push mechanism.

### Repeated notifications

`wait-notices.json` in the run directory remembers the last notified request,
report, and relevant agent state for each task. Identical notifications are
suppressed across `wait` invocations, including unchanged `blocked`, `unknown`,
unavailable agents, and idle agents without reports. New request IDs, published
reports, or agent state changes notify again. Collection alone does not create
a new notification. A cleared condition removes its remembered notification.

Suppressed tasks still count as pending. Their reports and panes remain available
through `status`, `collect`, and `read`; notification is not collection, acceptance,
or permission to close. After context loss or an interrupted/lost tool response,
inspect `status` once and recover outstanding reports before resuming the waiter.
Do not delete the notification record or keep restarting the helper to force
repeated alerts. No prompts, approvals, or pane closures happen in `wait`.

`collect` prints the current request's report and records a receipt. `close`
requires a complete collected report, the original Codex terminal, a settled
agent, and unchanged report/activity since collection. Main must read the
result before issuing `close`. The helper does not judge correctness or review
findings. Each owned completed pane is closed by Main through this operation;
there is no unattended auto-close watcher.

Reports remain in the run directory after panes close. `status --all` includes
closed tasks. Important conclusions belong in Main's summary or the project's
normal documentation. The temporary directory is not a durable archive and may
be removed by OS cleanup. This plugin does not delete the reports automatically.

## Follow-up and review

```sh
python3 "$helper" send --task "$task_dir" --task-file "$followup_file"
```

`send` keeps the same Codex session, creates a fresh request ID, and submits a
new packet. It requires a settled agent so completion of unrelated active work
cannot satisfy the new request. Re-review packets include the same finding IDs,
Main's ACCEPT/REJECT/DEFER decisions, the new candidate, and relevant verification.

Keep the Reviewer open until Main ends the review cycle. There is no special
review-round counter or automatic verdict. `close` has the same mechanism for
each role, so Main must apply the Reviewer lifecycle policy.

## Worker result protocol

The generated task packet supplies exact commands and paths:

```sh
python3 "$helper" begin --task "$task_dir" --request-id "$request_id"
python3 "$helper" report --task "$task_dir" --request-id "$request_id" \
  --status complete --file "$report_file"
```

`begin` invalidates the previous report. Call it before acting on direct user
follow-ups as well as at the start of the assignment. `report` atomically publishes
the file's contents with the task and current request IDs. Use `--status blocked`
when Main needs to answer a question or resolve a blocker. An old request ID is
rejected after Main sends a new assignment. Include direct user steering and its
effects in the report, even when that steering arrived outside Main's conversation.

## Attention and recovery

```sh
python3 "$helper" read --task "$task_dir" --lines 120
```

- **Startup failed:** use the printed task handle. If the assigned Codex eventually
  becomes ready, `send` can give that same session a fresh task packet. If no Codex
  started, inspect the recorded pane and resolve startup there. Do not blindly
  rerun `spawn`, which would create another pane.
- **Prompt delivery timed out:** `submission_uncertain` stays true. Read the terminal
  first. If the work is already running, wait and collect. Send a fresh request
  only after determining what the agent received and whether more instructions
  are actually needed.
- **Permission denied:** the child publishes `blocked` with the exact operation,
  target path or network destination, denial/error, reason, and completed work.
  `collect` the report and retain the pane. Main assesses the request under its
  own permissions and approval rules, resolves it if authorized, and uses `send`
  to continue the same session. Do not automatically expand the child's access,
  restart with bypass flags, or blindly execute its request. If report publication
  itself fails, inspect the pane to recover the blocker.
- **Approval or question UI:** leave the pane visible and let the user or Main
  respond within existing authorization. `never` disables runtime approval
  requests; it does not guarantee that sign-in or every other UI is noninteractive.
  The helper does not approve dialogs.
- **Idle without report:** inspect the pane and ask the same agent to follow its
  return contract, using the appropriate current request or a deliberate follow-up.
- **Pane moved:** the live agent name is resolved to its current pane and checked
  against the recorded terminal ID. Manual layouts are not globally reset.
- **Pane closed manually / server restarted:** do not assume a reused pane ID is
  the same terminal. Report files remain readable locally; Main can use them to
  recover context for a replacement. No automatic restart or pane-ID substitution.
- **Activity after collection:** inspect the new input/result, collect the up-to-date
  report when settled, then decide whether to close. A direct user instruction
  racing the final close is not atomically synchronized by herdr; the begin/report
  contract and close checks reduce that window but do not eliminate it.

The first release targets the CLI surface documented by herdr in September 2026:
`pane current/get/list/layout/split/rename/close`, `agent list/start/prompt/read`, JSON
`result.pane` / `result.panes` / `result.agent`, and agent terminal IDs / state-change sequences.
Use the installed herdr's `--help` and `api schema --json` when diagnosing version
differences. Do not silently replace unsupported commands with guessed keystrokes.
