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

## Main's decisions

- Keep intent, architecture, design direction, ownership, integration, and final
  acceptance in Main. Small obvious edits can remain in Main.
- Ordinary bounded investigation, implementation, tests, and debugging go to
  `gpt-5.6-luna` / `max`. Under the inherited Axiom economics assumption, protect
  Main context; do not avoid useful delegation just to conserve Luna usage.
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

## Operating the visible team

Read [operations.md](references/operations.md) before first use. The bundled
`scripts/axiom_herdr.py` operates herdr through its CLI and uses only Python's
standard library. Resolve its absolute path from this skill's location.

Initialize one run from the current Main pane and retain the returned run path.
Write a self-contained assignment, then spawn a worker with the appropriate role.
Task packets include only the objective, ownership, constraints, relevant
acceptance conditions, and evidence needed for that job.

The helper keeps Main in place and splits the owned worker area, using the
largest owned pane for later additions. It does not reapply a global layout.
Respect manual resizing, pane movement, and the user's active input focus.
If the terminal cannot accommodate another split, Main adapts the work schedule
or asks about layout when necessary; do not bypass visibility with hidden agents.

Use a long-running `wait` invocation to return on a report or attention from any
owned task. It polls locally without repeatedly waking Main. In Codex, retain
the exec session handle while it runs and continue through that handle rather
than starting duplicate waiters. Remain responsive to user steering.

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
