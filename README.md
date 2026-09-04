# idle-compact

Compacts Claude Code sessions that have sat idle too long.

Claude Code's built-in auto-compact triggers on how **full** the context is.
This triggers on how **long** a session has been untouched. After 45 minutes
idle (configurable), a real `/compact` is typed into the session — so you come
back to a session that has already tidied itself instead of one that stalls on
a compaction the moment you type.

Works on **desktop-app sessions** as well as terminal ones.

## How it works

**Finding idle sessions is read-only.** Claude Code keeps a live registry at
`~/.claude/sessions/<pid>.json` — pid, session id, cwd, kind, status, and when
the status last changed. Idle age is the newest of `statusUpdatedAt`,
`updatedAt`, and the transcript's mtime; context size comes from the last
assistant record's `usage` block. No hooks, so sessions that were already
running when you installed this are covered too.

**Triggering compaction is a keystroke.** There is no API for it, so the only
honest way is to type it into the session's own TUI:

| Session kind | Backend | Addressed by |
|---|---|---|
| desktop app, `claude --bg` | `claude attach <id>` inside a private tmux server | job id — exact |
| running under tmux | `tmux send-keys` to its pane | `TMUX_PANE` — exact |
| yakuake tab | `org.kde.yakuake.runCommandInTerminal` | terminal id — **inferred**, so probed first |
| Konsole tab | `org.kde.konsole.Session.runCommand` | session path — exact |

Background sessions live in the Claude Code daemon, so the throwaway `claude
attach` client is torn down afterwards and the session carries on untouched —
including in the desktop app, which is looking at the same session.

## What it refuses to do

Typing into a live session is only safe if you know what is on screen, so
every backend reads the session's rendered screen first and **refuses** when:

- **there is an unsent draft in the prompt box** — appending `/compact` to
  someone's half-typed message and submitting it is worse than not compacting
- **the session is working**, or a dialog or permission prompt is open
- **no input box is visible at all** — a scrolled-up tab, or a TUI that hasn't
  finished drawing. "No box" is deliberately distinct from "empty box"

Yakuake is the one backend where the terminal has to be *inferred* from the
process (identity comes from a Konsole session path, typing goes to a yakuake
terminal id). Before typing anything that matters it sends a harmless unknown
slash command and confirms that line landed in the expected session's
transcript. A bad guess costs one `Unknown command:` line rather than
compacting the wrong session.

Enter is delivered as a carriage return in its own write. Text and terminator
sent together are read by the TUI as a paste — the newline goes *into* the
prompt box and nothing is submitted.

Afterwards it waits for a `compactMetadata` record in that session's
transcript, and fails fast when Claude Code declines (e.g. "Not enough
messages to compact") rather than sitting out the timeout.

**Idempotency:** a session is compacted again only once there are fresh turns
after the last compaction. A compacted session that nobody has touched is left
alone forever.

## Install

```
/softwaresoftware:install idle-compact
```

Then install the timer (checks every 5 minutes):

```bash
claude-idle-compact install --interval 5
```

## Usage

```bash
claude-idle-compact status      # live sessions: idle age, context, eligible or why not
claude-idle-compact inspect     # read-only: adds what the injector sees on screen
claude-idle-compact run         # one pass now
claude-idle-compact run --dry-run
claude-idle-compact compact <id>          # one session (job id, session id, pid, name)
claude-idle-compact compact <id> --force  # skip the idle/size/idempotency checks
claude-idle-compact config --set idle_minutes=90
claude-idle-compact uninstall   # remove the timer
```

```
$ claude-idle-compact status
idle threshold 45m · context floor 50,000 tokens · kinds bg,interactive
ID        KIND         STATUS   IDLE       CONTEXT  NAME                    WHY
●60df6a0c interactive  idle     3d          84,120  cb-st-terms-12-r1       idle past threshold
 0b1295f6 interactive  idle     3m               -  thatcher-97             idle 3m < 45m
 f87a7d77 interactive  busy     2s               -  thatcher-61             this session
```

## Settings

`~/.config/claude-idle-compact/config.json`

| Key | Default | |
|---|---|---|
| `idle_minutes` | `45` | how long untouched before compacting |
| `min_context_tokens` | `50000` | skip sessions with little to summarize |
| `kinds` | `["bg","interactive"]` | `bg` = desktop app / `claude --bg` |
| `max_per_pass` | `4` | spreads a first run over a pile of stale sessions |
| `exclude_sessions` | `[]` | session ids never touched |
| `exclude_cwds` | `[]` | cwd substrings never touched |
| `compact_timeout_seconds` | `420` | |
| `instructions` | `""` | optional focus passed to `/compact` |

Every attempt is logged to `~/.local/state/claude-idle-compact/log.jsonl`.

## Limits

- Linux. Terminal sessions need tmux, yakuake, or Konsole; background and
  desktop sessions only need tmux.
- Konsole (not yakuake) needs `EnableSecuritySensitiveDBusAPI=true` under
  `[General]` in `~/.config/konsolerc` to accept typed input.
- The current session is always excluded.
