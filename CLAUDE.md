# open-files-in-cmux

## Overview
The `open-in-cmux` skill: when Claude Code writes a `PLAN<n>.md` / `RESULT<n>.md` that has a
same-numbered `PROMPT<n>.md`, a PostToolUse (Write) hook opens it in a cmux markdown viewer.
Source: `.claude/skills/open-in-cmux/` (`SKILL.md`, `open_in_cmux.py`, `test_open_in_cmux.py`),
exposed globally through the symlink `~/.claude-personal/skills/open-in-cmux`. The hook entry is
in `~/.claude-personal/settings.json`. Spec: `03_plans/PLAN2.md`.

## How to run
- Test: `python3 .claude/skills/open-in-cmux/test_open_in_cmux.py` (uses a fake `cmux`).
- Work in this repo is driven by `/prompt [@02_prompts/PROMPT<n>.md]`.

## Conventions
- **`.claude/skills/open-in-cmux/` is the live global copy.** Through the symlink and the hook,
  every edit takes effect in all projects at once, so run the tests before leaving it changed.
- `open_in_cmux.py` must always exit 0 and print nothing on stdout: a hook failure must never
  block Claude.
- Behavior changes start as a new PLAN in `03_plans/` (don't rewrite Confirmed / Implemented PLANs).
  Then keep `SKILL.md`, the script, the tests and `README.md` in sync.
- Results: `04_results/RESULT<n>.md`, numbered after the prompt they answer.
- Scripts: Python 3.9+, standard library only.
- The Bash sandbox can't reach the cmux socket (`Operation not permitted`) and can't write to
  `.claude/skills/` or `~/.claude-personal/skills/` (edit skill files with Edit/Write; symlinks are
  the user's job). Don't work around either; report it.
- Commits: Conventional Commits (`docs:`, `feat:`, `chore:` …).
