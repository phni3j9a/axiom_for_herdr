# Claude Code as Main

Read this when Main is a Claude Code session rather than Codex. Everything else in
SKILL.md and operations.md applies unchanged unless this file replaces it. Only Main
changes: Workers, Design, Reviewers, and Advisors are still visible Codex sessions
launched by the same helper with the same models, permissions, and report protocol.

## Prerequisites and identity

- Start Claude Code inside a herdr pane. Its Bash tool then inherits `HERDR_PANE_ID`
  and `HERDR_SOCKET_PATH`, and `doctor` shows `calling_pane.agent: "claude"`.
- Claude Code has no `CODEX_THREAD_ID`. `init` therefore binds the run to the calling
  herdr terminal (`main_terminal_id`) instead of a conversation ID. Every later Main
  operation must run from that same pane; a moved pane keeps its terminal identity.
- Do not use the explicit `--main-pane` / `--main-terminal-id` registration. It requires
  a Codex conversation ID and a Codex Main pane, and fails for Claude Code by design.
- If `HERDR_PANE_ID` is missing, Claude Code is not running inside herdr. Explain that
  the visible team is unavailable and continue useful work in Main; do not guess a pane.

## Model and delegation

- Main's model is whatever the Claude Code session runs. The Sol XHIGH Main launch
  instruction and `background_terminal_max_timeout` setting are Codex-only.
- Delegate through the herdr helper, not through Claude Code's Agent tool or other
  hidden subagents. Do not duplicate the same work in both paths.
- Children use the same configurable model routing (`models.json`, `--model-config`,
  and per-spawn overrides) and fixed Codex permission settings. Claude Code's own permission mode
  and approval rules apply only to Main's actions.

## Waiting for events

The exec `session_id`, wrapper `cell_id`, empty `write_stdin`, and `yield_time_ms`
handles in operations.md are Codex host mechanics. In Claude Code the singleton waiter
is one background Bash command:

- Start `python3 "$helper" wait --run "$run_dir" --until-event` once with
  `run_in_background: true` and the longest supported background timeout
  (`7200000` ms at the time of writing). Retain the returned background task ID.
- Claude Code re-invokes Main when that command exits. Read its terminal helper JSON
  from the task output and act on `reason` exactly as in the operations.md table.
- While it runs, do not read its output file repeatedly, call `status` or `read`,
  sleep, or start another waiter. Continue independent work, or end the turn and let
  the completion notification resume Main.
- If the background command is stopped without terminal helper JSON (for example at
  its timeout), that is not an event. Run `status` once, recover any ready report, and
  start one new waiter only if work is still pending and the old process has exited.

## Startup prompt delivery

`spawn` reports `submitted: true` once herdr accepts the prompt. On Codex CLI 0.159.3
a freshly started Codex was observed to drop that first prompt and sit at an empty
input, which the waiter reports as `idle_without_report`. Follow the normal recovery:
`read` the pane, and if the assignment never arrived, `send` the same task file to the
same session. Do not spawn a duplicate pane.
