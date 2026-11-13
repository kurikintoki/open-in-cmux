# open-files-in-cmux

A global Claude Code skill, `open-in-cmux`: when `/prompt` writes a `PLAN<n>.md` or `RESULT<n>.md`,
the file opens by itself in a cmux markdown viewer, in a split to the right of
the Claude session, with live reload and without taking focus.

## How it works

A PostToolUse hook on the Write tool runs `open_in_cmux.py`. It opens the written file only if:

- its name is `PLAN<n>.md` / `RESULT<n>.md` (no number = 1),
- a `PROMPT<n>.md` with the same number exists (in the project's `02_prompts/`, else next to the
  output),
- the session runs inside cmux.

Otherwise it does nothing. It never blocks Claude: it always exits 0.

## Install

1. Link the skill:

   ```
   ln -s "$PWD/.claude/skills/open-in-cmux" ~/.claude-personal/skills/open-in-cmux
   ```

2. Add this to `hooks.PostToolUse` in `~/.claude-personal/settings.json`:

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

3. Start a new Claude Code session inside cmux.

Link first, then add the hook: without the script, the hook reports an error after every Write.
To turn it off, remove the hook entry.

## Open a file by hand

```
python3 ~/.claude-personal/skills/open-in-cmux/open_in_cmux.py <path>...
```

## Test

```
python3 .claude/skills/open-in-cmux/test_open_in_cmux.py
```
