#!/usr/bin/env python3
"""Open a PLAN<n>.md / RESULT<n>.md in a cmux markdown viewer. Spec: 03_plans/PLAN2.md.

usage: open_in_cmux.py              hook mode: reads a Claude Code PostToolUse (Write) JSON on stdin
       open_in_cmux.py <path>...    CLI mode: open these files (no PLAN/RESULT check)

Hook mode opens the written file only if it is PLAN<n>.md / RESULT<n>.md and a PROMPT<n>.md with
the same number exists. Outside cmux, nothing happens.

Always exits 0 and prints nothing on stdout, so it can never block Claude. A failure is one line
on stderr.
"""
import json
import os
import re
import shutil
import subprocess
import sys

OUTPUT_RE = re.compile(r"^(PLAN|RESULT)(\d*)\.md$")
PROMPT_RE = re.compile(r"^PROMPT(\d*)\.md$")
OUTPUT_DIRS = ("03_plans", "04_results")
TIMEOUT = 5  # seconds to wait for cmux


def warn(message):
    print(f"open_in_cmux.py: {message}", file=sys.stderr)


def number(digits):
    # An unnumbered name (PROMPT.md, PLAN.md, RESULT.md) counts as 1, as in /prompt's output_name.py.
    return int(digits) if digits else 1


def is_prompt_output(path):
    """True if path is PLAN<n>.md / RESULT<n>.md and a PROMPT<n>.md with the same number exists."""
    out_dir, base = os.path.split(path)
    m = OUTPUT_RE.match(base)
    if not m:
        return False
    root = os.path.dirname(out_dir) if os.path.basename(out_dir) in OUTPUT_DIRS else out_dir
    prompt_dir = os.path.join(root, "02_prompts")
    if not os.path.isdir(prompt_dir):
        prompt_dir = out_dir
    try:
        names = os.listdir(prompt_dir)
    except OSError:
        return False
    n = number(m.group(2))
    return any(p and number(p.group(1)) == n for p in map(PROMPT_RE.match, names))


def find_cmux():
    found = shutil.which("cmux")
    if found:
        return found
    bundled = os.environ.get("CMUX_BUNDLED_CLI_PATH")
    if bundled and os.path.isfile(bundled) and os.access(bundled, os.X_OK):
        return bundled
    return None


def open_file(path):
    """Open one file in a split to the right of Claude's pane. No-op outside cmux."""
    workspace = os.environ.get("CMUX_WORKSPACE_ID")
    if not workspace:
        return
    cmux = find_cmux()
    if not cmux:
        return
    if not os.path.isfile(path):
        warn(f"not a file: {path}")
        return
    cmd = [cmux, "markdown", "open", path, "--workspace", workspace]
    surface = os.environ.get("CMUX_SURFACE_ID")
    if surface:
        cmd += ["--surface", surface]
    cmd += ["--focus", "false"]
    try:
        r = subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                           stderr=subprocess.PIPE, text=True, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        warn(f"cmux did not answer within {TIMEOUT}s")
        return
    if r.returncode != 0:
        lines = (r.stderr or "").strip().splitlines()
        warn(f"cmux exited {r.returncode}: {lines[-1] if lines else 'no message'}")


def hook_path():
    """The file a PostToolUse (Write) hook reports, as an absolute path, or None."""
    data = json.load(sys.stdin)
    path = (data.get("tool_input") or {}).get("file_path")
    if not isinstance(path, str) or not path:
        return None
    return os.path.normpath(os.path.join(data.get("cwd") or os.getcwd(), path))


def main():
    try:
        if len(sys.argv) > 1:
            for arg in sys.argv[1:]:
                open_file(os.path.abspath(arg))
        else:
            path = hook_path()
            if path and is_prompt_output(path):
                open_file(path)
    except Exception as e:  # never block Claude, whatever went wrong
        warn(f"{type(e).__name__}: {e}")
    sys.exit(0)


if __name__ == "__main__":
    main()
