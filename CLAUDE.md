# CLAUDE.md — idle-compact

Compacts Claude Code sessions idle past a threshold by typing a real
`/compact` into them. One stdlib-only Python script; no MCP server, no
long-lived daemon (a systemd user timer runs `run` on an interval).

## Layout

- `bin/claude-idle-compact` — everything. Pure helpers at the top are
  unit-tested; session discovery, eligibility, backends, and the compaction
  driver below.
- `skills/idle-compact/SKILL.md` — how Claude answers "what's idle", "why
  wasn't this compacted", and setup/tuning requests.
- `tests/` — pytest over the pure helpers, with screen fixtures captured
  verbatim from real sessions.

## Invariants

- **Never type into a session without first reading its screen.**
  `read_prompt_box` returns `None` (no input box on screen) as a state
  *distinct* from `""` (empty box). Only `""` may be typed into. Conflating
  them means typing blind into a scrolled tab or an open dialog.
- **The prompt box is found by its border rules, not by scanning for `❯`.**
  Rendered replies contain `>` in tables and quotes, and every session's
  scrollback holds old prompt echoes. `is_rule` tolerates a tab title in the
  top rule but rejects any line containing box-drawing corners or verticals —
  that rejection is what keeps a table drawn inside a reply from reading as an
  input box. There is a test for each of these.
- **Enter must arrive as a lone carriage return, in its own write.** Text and
  its terminator sent together are read by Claude Code's TUI as a *paste*: the
  newline is inserted into the prompt box and the text stacks up unsent, which
  looks exactly like nothing happened. `ENTER = "\r"` — an empty string
  delivers no keystroke at all. The tmux backends get this split for free from
  `send-keys`; the D-Bus backends must keep their two calls. Tested in
  `TestEnterDelivery`; it cost an hour to find the first time.
- **Yakuake is the only backend whose target is inferred**, so it must keep
  the probe: an unknown slash command, confirmed in the *expected session's*
  transcript, before `/compact` is sent. Konsole, tmux, and attach address the
  session exactly (session path / `TMUX_PANE` / job id) and need no probe.
- **Idempotency is `turns_since_compact == 0`**, not a state file. A session
  compacted with nothing new since is never recompacted, and that survives
  losing local state.
- `await_compaction` must keep watching for refusals as well as success.
  Claude Code declines a pointless compaction with an ordinary
  `system`/`local_command` record ("Not enough messages to compact"), not an
  error — watching only for `compactMetadata` sits out the whole timeout.
- Discovery is read-only and must stay that way: the registry under
  `~/.claude/sessions/` belongs to Claude Code. `procStart` is compared
  against `/proc/<pid>/stat` field 22 to guard against pid reuse.

## Scheduling

Shipped path is the **daemon capability**: `watch` is a plain loop holding no
state between passes, so it is an ordinary restartable daemon. `daemons`
prints the registration; the consumer (a skill, or the operator) hands it to
daemon-manager.

`install` writes a standalone systemd timer and stays as the fallback for a
checkout with no daemon capability. It resolves `__file__` at install time,
which pins a version directory — fine from a git checkout, stale after a
marketplace plugin update. That asymmetry is the whole reason the daemon
capability is preferred, and it is why `install`'s help says so.

Two instances must never run at once: nothing guards a session from being
typed into twice. daemon-manager's autostart installer runs `systemctl start`
without stopping a running process, so anything registering this daemon must
stop it first.

## Testing

`make test` for unit tests. For an end-to-end rehearsal that touches nothing
real, make a throwaway background session and drive it:

```
claude --bg "Reply with exactly the word: ALPHA"     # prints a job id
bin/claude-idle-compact inspect <job-id> --attach
bin/claude-idle-compact -v compact <job-id> --force
claude stop <job-id> && claude rm <job-id>
```

A session with only a couple of turns will be declined with "not enough
messages to compact" — that is the fail-fast path working, not a bug. Give it
a few real turns first to exercise the success path.

`bin/claude-idle-compact inspect` is read-only across every live session and
is the fastest way to check the screen parser against reality after changing
it — the parser bugs that mattered were all found that way, not in unit tests.
