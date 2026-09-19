---
name: axiom-for-herdr
description: Software engineering coordination through visible herdr panes, combining Sol XHIGH integration, Astra XHIGH planning and advice, Luna MAX Fast implementation, Sol MAX design, independent Sol review, and pane cleanup.
---

# Axiom for herdr

Apply this workflow to the task for which the user explicitly invoked Axiom for
herdr, including follow-up work on that task.

Main thinks. Sol designs. Luna executes. Sol reviews. The user can watch and
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

## Model policy

- Main: `gpt-5.6-sol` / `xhigh`
- Worker: `gpt-5.6-luna` / `max` / Fast
- Design: `gpt-5.6-sol` / `max`
- Reviewer: `gpt-5.6-sol` / `xhigh`
- Advisor: `gpt-6-astra` / `xhigh` for both difficult plan drafts and consultations

Main is selected at session startup, for example with
`codex -m gpt-5.6-sol -c 'model_reasoning_effort="xhigh"'` inside herdr.
The plugin cannot switch the active Main model and does not rewrite global defaults.
The helper adds `-c 'service_tier="fast"' -c features.fast_mode=true` only for workers.
Design, reviewer, and advisor receive no tier override and retain the existing Codex tier settings.
Fast is distinct from reasoning effort; verify actual routing from session evidence,
not just the requested launch arguments.

## Main's decisions

- Keep intent, architecture, design direction, ownership, integration, and final
  acceptance in Main. Small obvious edits can remain in Main.
- Ordinary bounded investigation, implementation, tests, and debugging go to
  `gpt-5.6-luna` / `max` / Fast, following the Luna economics policy above.
- Unsettled, material visual, interaction, or information-design work goes to
  `gpt-5.6-sol` / `max`. Finished design specifications can be implemented by Luna.
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

## Long-running monitoring

- Delegate repeated status checks for CI/CD, GitHub Actions, builds, tests, and similar long-running processes to a Luna worker through completion. Monitoring alone is a useful assignment; keep it with the existing Luna responsible for that process when available.
- Main does not repeatedly check the delegated process or the worker's progress. Continue useful independent work or use the existing run waiter for the report.
- The Luna worker reports completion, failure, inability to monitor, or a need for Main's judgment, with concise evidence. Do not send Main periodic unchanged-status reports.

## Astra planning and advice

Read [advisor.md](references/advisor.md) before a consultation. After enough orientation,
use `advisor` for a difficult plan draft, consequential design trade-off, failure that
does not converge, changed plan assumptions, unresolved technical review dispute,
or an explicit user request. A routine plan update or simple edit is not a trigger.
Main owns adoption, assignment, and final acceptance. Keep the Advisor separate from
the independent Sol Reviewer.

Write a self-contained task file with selected user/Main dialogue, current agreements
and constraints, the decision, and primary evidence. Label Main's hypotheses separately;
do not transfer internal reasoning or full execution transcripts. This helper does not
automatically export conversation history. Astra can inspect relevant files read-only
and request missing facts; broad investigation goes back to Main for delegation.

Use `spawn --role advisor` through the visible herdr path in [operations.md](references/operations.md).
Once needed, keep the same Advisor pane for Main's entire work session, including
later consultations. Send new evidence, changed assumptions, and Main's decisions
through `send`. Resolving one consultation does not end the Advisor's lifetime;
follow the pane lifecycle below and advisor.md for justified session replacement.
The helper does not enforce this lifecycle; Main owns it. If Astra XHIGH is
unavailable, disclose the failure and continue useful work in Main without silently
substituting a model or effort, duplicating the pane, or widening permissions.

## Child permissions

All delegated roles launch with `--sandbox workspace-write --ask-for-approval never`.
Also pin `-c default_permissions=":workspace"`, as validated with CLI 0.154.0 / shared
app-server 0.153.4. See operations.md for this compatibility choice and verify effective
child permissions on other versions; the two policy systems are not composed.
This is a fixed child setting, independent of Main's mode; do not inherit Main's
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

The Advisor has the same permissions, with a no-project-edit role instruction;
only the assigned report and required report-protocol metadata in the task directory
are writable by its advisory contract.

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

Before starting Main for this workflow, set Codex's
`background_terminal_max_timeout=3600000`; the recommended invocation is
`codex -c background_terminal_max_timeout=3600000`. This sets the technical
upper bound for a one-hour outer result wait, but it does not change the actual
`yield_time_ms`; pass both values when using that host capability. The helper's
singleton event wait does not depend on an internal one-hour timeout. The plugin
does not edit user settings or reconfigure a running Main after startup.

Use one `wait --until-event` process per run to watch all owned tasks. The helper
enforces this invariant with a run-level lock: a duplicate exits with
`reason: waiter_already_active` and identifies the existing waiter. Normal waits
have no helper timeout. An optional operational `--timeout` must be at least 3600
seconds; shorter values require the hidden test-only switch and are never a Main
polling mechanism. Local polling backs off from two to ten seconds without
invoking Main's model.

Keep the wait's two continuation handles distinct. A yielded command has an exec
`session_id`; resume that exact process with empty `write_stdin`. A yielded outer
wrapper has a `cell_id`; resume that exact wrapper cell. A wrapper yield with no
terminal helper JSON is only a transport yield: do not launch another helper,
call `status` or `read`, scan transcripts, or post unchanged progress commentary.
Only terminal helper JSON (`event`, `no_pending`, `safety_timeout`,
`waiter_already_active`, or an error) permits a state transition. See the concrete
state table in operations.md.

Use the longest event-driven result wait supported by the active host; with the
documented one-hour configuration, pass `yield_time_ms=3600000`. Reports,
attention, process exit, and user steering may return control earlier and must be
handled immediately. If the host cannot honor the requested result wait or
higher-priority rules prohibit it, follow the unsupported-host procedure in
operations.md. Preserve the existing helper and resume its handles instead of
converting the limitation into shorter helper waits. The invariant is one live
waiter until an event, not a particular number of elapsed milliseconds.

Unchanged notifications are suppressed across completed waits; new requests,
reports, or agent state changes can notify again. A suppressed notification is
still pending work, not acceptance or resolution. Handle each returned event
before waiting again, or explicitly retain its blocker while other workers
proceed. Do not restart waiting when no tasks are pending, or retry a helper error without
diagnosing it. After an explicit safety timeout, reassess once before starting a
new event wait.

## Pane lifecycle

When a report is ready, `collect` it and inspect the relevant artifact or diff.
`complete` describes a returned assignment, not product acceptance or permission
to end a role's lifetime. Main decides whether fixes, further work, or review are needed.

- Keep Workers responsible for a candidate throughout its entire review cycle,
  including idle periods between implementation, fixes, and re-review. Send
  accepted fixes to the original responsible Worker with Main's adjudication,
  current candidate, and verification requirements. If that session is lost,
  recover with a new Worker carrying the relevant previous report and current intent.
- Keep the same independent Reviewer through that review cycle. Once Main ends
  it, close the Reviewer and participating Workers whose work is resolved.
- For Worker or Design assignments without a pending review or follow-up, such as
  an accepted standalone investigation, close the participant after Main accepts its result.
- Once an Advisor is started, retain it throughout Main's work session and close
  it when Main wraps up the overall work and performs pane cleanup. A work session
  is the continuing work with the user, including follow-ups. An individual
  consultation ending, an intermediate reply, waiting for user input, or context
  compaction does not end it.

Retain task handles, ownership, reports, and Main's decisions across turns and
compaction so follow-ups use `send` on the intended sessions. An unchanged,
collected `complete` report from a settled agent is excluded from `wait`'s pending
count even while its pane stays open. `pending: 0` is not a signal to close retained
participants or restart the waiter. Retention alone requires no new prompts or
periodic progress checks.

When a participant's lifetime ends, use `close` with its current collected complete
report and the existing identity/activity checks. Keep unresolved or active work
visible; do not bypass those checks to finish cleanup. No additional user confirmation
is needed just to close an owned, completed participant at that point.

## Review continuity

Read [review.md](references/review.md) before independent review. Keep the responsible
Workers and the same Reviewer across accepted fixes and re-review. Main adjudicates
each review report, sends bounded fixes to the responsible Workers, then sends the
updated candidate and verification evidence to the same Reviewer. Apply the pane
lifecycle above when Main considers the entire review cycle complete. Main decides
when review has diminishing value.

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
