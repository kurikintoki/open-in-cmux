# open-files-in-cmux

A global Claude Code skill, `open-in-cmux`: when `/prompt` writes a `PLAN<n>.md` or `RESULT<n>.md`,
the file opens by itself in a cmux markdown viewer, in a split to the right, with live reload and
without taking focus.

## How it works

`open_in_cmux.py` opens a file only if:

- its name is `PLAN<n>.md` / `RESULT<n>.md` (no number = 1),
- a `PROMPT<n>.md` with the same number exists (in the project's `02_prompts/`, else next to the
  output).

There are two ways to trigger it. Use one, not both: with both active, each file opens twice.

| Way | Use it when | How it starts |
|---|---|---|
| **Watcher** (`--watch`) | A managed policy sets `allowManagedHooksOnly`, so user hooks don't load | You start it in a cmux terminal, once per project |
| **Hook** (PostToolUse on Write) | User hooks work | Always on, once registered in `settings.json` |

To see whether your hooks are active, open `/hooks` in Claude Code. Where they are disabled, the
hook entry does nothing and reports no error.

## Install

Link the skill:

```
ln -s "$PWD/.claude/skills/open-in-cmux" ~/.claude-personal/skills/open-in-cmux
```

## Watcher

At the project root, in a separate cmux terminal (a split or a tab):

```
python3 ~/.claude-personal/skills/open-in-cmux/open_in_cmux.py --watch
```

It checks `03_plans/` and `04_results/` (or the directory itself if neither exists) once a second
and opens each matching file that appears after it started. Files that were already there, and
edits to existing files, are ignored. Stop it with Ctrl-C.

- Files that Claude did not write (made by hand, or brought in by `git pull`) open too if they match.
- Two watchers on one project open each file twice.
- Options: `[dir]` (project root), `--interval <seconds>`, `--surface <id|ref>` (the surface to
  split from; default: the focused one).
- Outside cmux it prints why and exits 1.

It can't be started from Claude's Bash tool: the sandbox blocks the cmux socket.

## Hook

Add this to `hooks.PostToolUse` in `~/.claude-personal/settings.json`, then start a new Claude Code
session inside cmux:

```json
{
  "matcher": "Write",
  "hooks": [
    {
      "type": "command",
      "command": "python3 \"$CLAUDE_CONFIG_DIR/skills/open-in-cmux/open_in_cmux.py\"",
      "timeout": 10
    }
  ]
}
```

Link the skill first: without the script, the hook reports an error after every Write. The hook
never blocks Claude: it always exits 0, and does nothing outside cmux. To turn it off, remove the
entry.

## Open a file by hand

```
python3 ~/.claude-personal/skills/open-in-cmux/open_in_cmux.py <path>...
```

## Test

```
python3 .claude/skills/open-in-cmux/test_open_in_cmux.py
```
