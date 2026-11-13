#!/usr/bin/env python3
"""Open a PLAN<n>.md / RESULT<n>.md in a cmux markdown viewer.
Spec: 03_plans/PLAN2.md (hook and CLI modes) + 03_plans/PLAN4.md (watch mode).

usage: open_in_cmux.py              hook mode: reads a Claude Code PostToolUse (Write) JSON on stdin
       open_in_cmux.py <path>...    CLI mode: open these files (no PLAN/RESULT check)
       open_in_cmux.py --watch [dir] [--interval <seconds>] [--surface <id|ref>]
                                    watch mode: open each PLAN/RESULT that appears under dir

Hook and watch modes open a file only if it is PLAN<n>.md / RESULT<n>.md and a PROMPT<n>.md with
the same number exists.

Hook and CLI modes do nothing outside cmux, always exit 0 and print nothing on stdout, so they can
never block Claude. A failure is one line on stderr.

Watch mode is run by the user in a cmux terminal, at the project root. It is for machines where
user hooks are disabled (managed policy `allowManagedHooksOnly`). It exits 1 outside cmux and
runs until Ctrl-C.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time

OUTPUT_RE = re.compile(r"^(PLAN|RESULT)(\d*)\.md$")
PROMPT_RE = re.compile(r"^PROMPT(\d*)\.md$")
OUTPUT_DIRS = ("03_plans", "04_results")
TIMEOUT = 5  # seconds to wait for cmux


def warn(message):
    print(f"open_in_cmux.py: {message}", file=sys.stderr, flush=True)


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


def open_file(path, surface=None):
    """Open one file in a split to the right. No-op outside cmux.

    surface is the surface to split from. None leaves it to cmux (the focused surface).
    """
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


def watch_dirs(root):
    dirs = [d for d in (os.path.join(root, name) for name in OUTPUT_DIRS) if os.path.isdir(d)]
    return dirs or [root]


def snapshot(root):
    """The PLAN*.md / RESULT*.md files that exist now in the watched directories."""
    found = set()
    for d in watch_dirs(root):
        try:
            names = os.listdir(d)
        except OSError:
            continue
        found.update(os.path.join(d, n) for n in names if OUTPUT_RE.match(n))
    return found


def watch(argv):
    p = argparse.ArgumentParser(prog="open_in_cmux.py --watch",
                                description="Open each new PLAN<n>.md / RESULT<n>.md in cmux.")
    p.add_argument("dir", nargs="?", default=".", help="project root (default: current directory)")
    p.add_argument("--interval", type=float, default=1.0, help="seconds between checks (default: 1)")
    p.add_argument("--surface", help="surface to split from (default: the focused surface)")
    a = p.parse_args(argv)

    root = os.path.abspath(a.dir)
    if not os.path.isdir(root):
        warn(f"not a directory: {a.dir}")
        return 1
    if not os.environ.get("CMUX_WORKSPACE_ID"):
        warn("not inside cmux (CMUX_WORKSPACE_ID is not set); start this in a cmux terminal")
        return 1
    if not find_cmux():
        warn("the cmux command was not found")
        return 1

    seen = snapshot(root)  # files that are already there are never opened
    print("watching: " + ", ".join(watch_dirs(root)) + "  (Ctrl-C to stop)", flush=True)
    try:
        while True:
            time.sleep(a.interval)
            current = snapshot(root)
            for path in sorted(current - seen):
                if is_prompt_output(path):
                    print(f"open: {os.path.relpath(path, root)}", flush=True)
                    open_file(path, a.surface)
            seen = current
    except KeyboardInterrupt:
        return 0


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--watch":
        sys.exit(watch(sys.argv[2:]))
    try:
        surface = os.environ.get("CMUX_SURFACE_ID")
        if len(sys.argv) > 1:
            for arg in sys.argv[1:]:
                open_file(os.path.abspath(arg), surface)
        else:
            path = hook_path()
            if path and is_prompt_output(path):
                open_file(path, surface)
    except Exception as e:  # never block Claude, whatever went wrong
        warn(f"{type(e).__name__}: {e}")
    sys.exit(0)


if __name__ == "__main__":
    main()
