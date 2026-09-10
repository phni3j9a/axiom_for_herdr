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

```sh
python3 "$helper" spawn --run "$run_dir" --role worker \
  --label 'SSH再接続の実装' --task-file "$assignment_file"
```

Roles: `worker` (Luna MAX), `design` (Astra MAX), `reviewer` (Sol XHIGH).
`--cwd /absolute/worktree` optionally starts the worker in a worktree Main has
already prepared. Model/effort are selected by the role. Every role explicitly
launches with `--sandbox workspace-write --ask-for-approval never`, independently
of Main's current mode and the user's approval/sandbox defaults. The helper does
not edit Codex configuration or add bypass flags. Network settings and other
configured limits remain in effect; network access is not enabled by the helper.
The assigned cwd and the temporary run directory added through `--add-dir` let
the child edit its worktree and publish its report outside protected Git metadata.
Review read-only behavior is an instruction contract, allowing only the assigned
report directory to be written; it is not a separate sandbox enforcement layer.

The fixed settings apply to newly spawned children. Updating the plugin or using
`send` does not reconfigure an already-running Codex session.

`spawn` prints JSON objects, one before startup and another after prompt submission.
Capture the first object's `task` path even if startup later fails. It creates the
pane, names it, starts interactive Codex, and sends a short prompt pointing to the
self-contained task file. It returns after submission, without waiting for the
work to finish. Create several independent workers before invoking `wait`.

Serialize `init`, `spawn`, `send`, `collect`, and `close` for each run. Their Codex
workers execute concurrently. Mutations are Main-owned; there is no scheduler
daemon or shared database.

```sh
python3 "$helper" status --run "$run_dir"
python3 "$helper" wait --run "$run_dir" --timeout 3600
python3 "$helper" collect --task "$task_dir"
python3 "$helper" close --task "$task_dir"
```

`wait` samples the task reports and herdr's agent list every two seconds inside
one local process. It returns when any task has a settled report or requires
attention, when no tasks are pending, or when its timeout elapses. It does not
send prompts or close panes. Interrupting this helper does not stop the workers.

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
`pane current/layout/split/rename/close`, `agent list/start/prompt/read`, JSON
`result.pane` / `result.agent`, and agent terminal IDs / state-change sequences.
Use the installed herdr's `--help` and `api schema --json` when diagnosing version
differences. Do not silently replace unsupported commands with guessed keystrokes.
