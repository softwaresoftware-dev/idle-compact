---
name: idle-compact
description: Set up, inspect, or tune automatic compaction of idle Claude Code sessions — a background timer that types a real /compact into any session left untouched past a threshold (45 minutes by default). Use when the user says "compact my sessions when they go idle", "auto compact after N minutes", "/idle-compact", asks which sessions are idle or why one was or wasn't compacted, or wants to change the idle threshold, context floor, or exclusions.
---

# Idle Compaction

Claude Code's built-in auto-compact triggers on how **full** the context is.
This triggers on how **long** a session has sat untouched. A session past the
threshold gets a real `/compact` typed into it, so the user returns to a
session that has already tidied itself.

Everything runs through one stdlib-only script:

```bash
IC="${CLAUDE_PLUGIN_ROOT}/bin/claude-idle-compact"
```

## First: is it running?

It runs as a long-lived daemon (`watch`), registered through the **daemon
capability** so it restarts on failure and survives a plugin update.

```bash
"$IC" daemons          # prints name / command / args / cwd to register
```

Register that with an available daemon-capability tool: start it, then
install its autostart. **Stop the daemon before installing autostart** — the
installer runs `systemctl start` without stopping an already-running process,
and two instances would type into the same session at once.

Check it with the daemon capability's status tool, or:

```bash
systemctl --user status idle-compact.service
journalctl --user -u idle-compact.service -f
```

`ipc_reachable: false` is expected and not a fault: this daemon serves no IPC,
it just wakes on an interval.

**No daemon capability available?** `"$IC" install --interval 5` writes a
self-contained systemd timer instead. It works, but it hardcodes the path it
was installed from — after a plugin update that path is a stale version
directory, so prefer the daemon capability wherever it exists.

## Answering "what's idle / why wasn't this compacted?"

```bash
"$IC" status      # every live session, idle age, context size, eligible or why not
"$IC" inspect     # read-only: adds what the injector sees on each session's screen
```

`inspect` never types anything. Use it to explain a skip. The reasons that
confuse people most:

- **`unsent draft in the prompt box`** — the user left text typed but unsent.
  Injecting would append `/compact` to their draft and submit the mess, so it
  refuses. Tell them to clear or send the draft.
- **`no input box visible`** — that tab is scrolled up, or a dialog/permission
  prompt is open. Scrolling to the bottom fixes it.
- **`already compacted, nothing new since`** — idempotency. A session is only
  compacted again once there are fresh turns after the last compaction.
- **`context N < floor`** — too little context to be worth summarizing.

## Changing behaviour

```bash
"$IC" config                                    # show current settings
"$IC" config --set idle_minutes=90
"$IC" config --set min_context_tokens=50000
"$IC" config --set exclude_sessions=<session-id>,<session-id>
"$IC" config --set kinds=bg                     # desktop/background only
"$IC" config --set instructions="keep the deploy steps"
```

Config lives at `~/.config/claude-idle-compact/config.json`; every compaction
is logged to `~/.local/state/claude-idle-compact/log.jsonl`.

## Running it by hand

```bash
"$IC" run --dry-run     # what this pass would compact
"$IC" run               # do it now
"$IC" compact <id>      # one session (job id, session id, pid, or name)
```

## Rules

- **Never pass `--force` to compact the user's session on a hunch.** It skips
  the idle, size, and idempotency checks. It is for when the user explicitly
  asks to compact a specific session right now.
- **Don't compact the current session** — it is excluded automatically, and
  typing into it mid-turn would corrupt the turn in progress.
- If a session cannot be driven (unsupported terminal), say so plainly rather
  than suggesting the user compact it by hand without explaining why.
