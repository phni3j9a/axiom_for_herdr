---
name: axiom-for-herdr
description: Coordinate non-trivial Codex engineering work through visible herdr panes. Main delegates bounded implementation to Luna MAX, material interface design to Astra MAX, and independent review to Sol XHIGH; collect reports and close completed panes. Use for engineering work inside herdr or explicit Axiom for herdr requests.
---

# Axiom for herdr

Main thinks. Astra designs. Luna executes. Sol reviews. The user can watch and
intervene in each Codex terminal. Preserve Main context by returning compact
evidence, rather than reading every worker transcript.

## Determine your role once

If `AXIOM_HERDR_ROLE` is `worker`, `design`, or `reviewer`, or the current request
identifies you as a delegated session, execute that assignment yourself. Follow
its begin/report contract. Do not create subagents, initialize another run, or
manage panes. This applies even if ordinary Axiom guidance is also available.

Otherwise you are Main. Use this skill's herdr path for delegation during this
task; do not also delegate the same work with ordinary Axiom or `spawn_agent`.
Appropriate delegation is within the requested engineering task, subject to
its existing permissions. Nothing here grants broader filesystem, command,
network, approval, publishing, or repository-mutation permissions.

This plugin needs a Main Codex running inside herdr on the host where the other
Codex processes run. If that surface is unavailable, explain the missing
capability and continue useful work in Main. Do not pretend that hidden workers
provide the requested visibility.

## Luna economics

For Main's orchestration decisions, this version inherits Axiom v0.1.9's
economics assumption: ordinary Luna MAX worker usage can be treated as
**almost free**.

**Main context is expensive; Luna compute is almost free.** Protect Main context
aggressively when bounded work can be delegated cleanly to a visible herdr worker.

Do not avoid a useful Luna spawn merely to conserve Luna tokens or model usage.
Prefer delegation when it protects Main context, isolates noisy work, enables
independent investigation, or makes useful parallel progress. The practical
costs that limit delegation are coordination, latency, overlapping work,
dependency order, and integration complexity. Size the team around those costs
and useful independent work, without a fixed worker-count limit. Do not split
tasks artificially just to increase the number of workers; keep a simple task
in Main when coordination costs outweigh the benefit.

This is an explicit economics assumption for this plugin version, not a timeless
claim about model pricing. Update the policy if Codex/model economics change
materially.

## Main's decisions

- Keep intent, architecture, design direction, ownership, integration, and final
  acceptance in Main. Small obvious edits can remain in Main.
- Ordinary bounded investigation, implementation, tests, and debugging go to
  `gpt-5.6-luna` / `max`, following the Luna economics policy above.
- Unsettled, material visual, interaction, or information-design work goes to
  `gpt-6-astra` / `max`. Finished design specifications can be implemented by Luna.
- Meaningful independent review goes to fresh `gpt-5.6-sol` / `xhigh`. A design
  participant cannot independently review its own implementation.
- Main chooses useful parallelism. There is no fixed worker count. Independent
  tasks should run concurrently when coordination and integration permit it.
  Launch independent tasks before waiting; pane creation itself is sequential.
- Preserve existing user changes. Use disjoint write ownership, serialize
  overlapping changes, or explicitly choose worktree isolation. Pane cleanup
  never implies deleting a checkout, branch, or user changes.
- Report model routing from launch evidence. `requested_codex_args` and
  `launched_argv` establish what was requested, not a proof of actual model
  execution. Inspect the Codex session evidence if routing is in doubt.

## Child permissions

All delegated roles launch with `--sandbox workspace-write --ask-for-approval never`.
Also pin `-c default_permissions=":workspace"` for runtimes selecting named permission
profiles. This is a fixed child setting, independent of Main's mode; do not inherit Main's
approval mode or switch children to Auto-review or full access. Main retains its
own permissions and approval rules. Do not alter user/project Codex configuration.

Use `--cwd` for the assigned project or prepared worktree. The helper adds the
temporary run directory with `--add-dir` so children can publish reports outside
Git metadata. It does not enable network access or remove other configured limits. Child role,
report path, and pane context are also passed as per-session shell environment
config overrides so a shared app-server can supply them to tools. These invocation
overrides do not edit user/project configuration.
Reviewer project read-only behavior remains a role instruction, not a separate
read-only sandbox.

When permissions block required work, the child publishes `blocked` with the
operation, target, denial/error, reason, and completed work, then leaves its pane
open. Main collects and assesses that report under its own authorization and
approval rules, resolves what it can, and uses `send` to resume the same child.
Do not automatically widen permissions, restart with broader access, or blindly
execute a child's requested operation. Ask the user only when Main's rules or
missing authorization require it.

## Operating the visible team

Read [operations.md](references/operations.md) before first use. The bundled
`scripts/axiom_herdr.py` operates herdr through its CLI and uses only Python's
standard library. Resolve its absolute path from this skill's location.

Initialize one run from the current Main pane and retain the returned run path.
With a shared app-server, commands may have CODEX_THREAD_ID but no HERDR_* variables.
Use the explicit Main registration in operations.md when this happens: verify the
pane actually contains this conversation, then supply both its pane ID and terminal
ID (and the server socket). Never select Main from focus, cwd, or a sole-agent guess.
If herdr advertises this conversation's session identity, match it exactly; otherwise
inspect the candidate terminal or use an explicit user-provided association. If the
association cannot be established, obtain the missing identity before managing panes.
After registration, use the recorded run. The helper checks the caller's conversation
and resolves the original terminal even if it moves. Diagnose it with doctor --run.
Write a self-contained assignment, then spawn a worker with the appropriate role.
Task packets include only the objective, ownership, constraints, relevant
acceptance conditions, and evidence needed for that job.

The helper keeps Main in place and splits the owned worker area, using the
largest owned pane for later additions. It does not reapply a global layout.
Respect manual resizing, pane movement, and the user's active input focus.
If the terminal cannot accommodate another split, Main adapts the work schedule
or asks about layout when necessary; do not bypass visibility with hidden agents.

Use one `wait --timeout 3600` process per run to watch all owned tasks. Its local
two-second polling does not invoke Main's model. Retain its exec session handle
and resume that handle with a **fixed five-minute result wait: 300 seconds /
`yield_time_ms=300000`**. This is a required value, not a default or an invitation
to choose the "longest allowed" interval. Do not shorten it at Main's discretion
or substitute a one-minute poll. Use the same value for a yielded outer wrapper.
Reports, attention, process exit, and user steering may return control earlier;
handle them immediately rather than delaying them until five minutes elapse.
The helper timeout and the tool's result-wait interval are separate; setting only
the former does not prevent frequent Main wakeups. If the host cannot honor this
value or higher-priority rules prohibit it, follow the unsupported-host procedure
in operations.md; do not silently fall back to shorter polling.
Do not use short/default result polls, duplicate waiters, or periodic `status`,
`read`, and transcript scans simply to check progress. Follow the concrete
waiting procedure in operations.md and remain responsive to user steering.

Unchanged notifications are suppressed across waits; new requests, reports, or
agent state changes can notify again. A suppressed notification is still pending
work, not acceptance or resolution. Handle each returned event before waiting
again, or explicitly retain its blocker while other workers proceed. Do not
restart waiting when no tasks are pending, or retry a helper error without
diagnosing it. After timeout, reassess the work once before continuing the fixed
five-minute result wait.

When a report is ready, `collect` it and inspect the relevant artifact or diff.
For a completed Worker, call `close` promptly after gathering the evidence needed
for integration. Keep reports and Main's decisions available for the current
task; keep the screen focused on current work. Do not wait for an additional
user confirmation just to close an owned, completed worker.

`complete` describes a returned assignment, not product acceptance. Main decides
whether fixes, further work, or independent review are needed. Use `send` for
a follow-up when the original pane is still open; otherwise launch a new worker
with the relevant previous report and current intent.

## Review continuity

Read [review.md](references/review.md) before independent review. Keep the same
Reviewer pane across accepted fixes and re-review. Collect its report after each
round, send Main's adjudication with the updated candidate, and close it once
Main considers the entire review cycle complete. Do not close it merely because
one response ended. Main decides when review has diminishing value.

## Direct intervention and incomplete work

The user can type directly in any worker. Its assignment instructs it to call
`begin` before acting on new instructions, invalidating the previous report, and
to report the instruction and its effect. Bring cross-worker scope changes back
into Main's plan. This is a cooperative protocol, not an atomic interception of
every keystroke.

Herdr `idle` / `done` alone do not prove task completion. Close only after collecting
the current complete report. The helper also checks terminal identity and activity
since collection. If those checks fail, inspect and resolve the changed state.
Do not circumvent them by closing a guessed pane ID.

Leave approval dialogs, blocked reports, missing reports, startup failures, and
unknown states visible while they need attention. Read the pane before deciding
the next step. Do not automatically accept permission prompts, resend timed-out
prompts, or restart a worker. A send failure can mean input was delivered.
