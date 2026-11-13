#!/usr/bin/env python3
"""Open a PLAN<n>.md / RESULT<n>.md in a cmux markdown viewer.
Spec: 03_plans/PLAN2.md (hook and CLI modes) + 03_plans/PLAN4.md (watch mode)
+ 03_plans/PLAN6.md (reuse the pane on the right).

usage: open_in_cmux.py              hook mode: reads a Claude Code PostToolUse (Write) JSON on stdin
       open_in_cmux.py <path>...    CLI mode: open these files (no PLAN/RESULT check)
       open_in_cmux.py --watch [dir] [--interval <seconds>] [--surface <id|ref>]
                                    watch mode: open each PLAN/RESULT that appears under dir

Hook and watch modes open a file only if it is PLAN<n>.md / RESULT<n>.md and a PROMPT<n>.md with
the same number exists.

Where it opens: if there is already a pane to the right of the base pane (the pane this runs in),
as a tab in that pane; otherwise in a new split to the right.

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


class LayoutError(Exception):
    """The workspace layout could not be read or does not contain what we look for."""


def leaf_panes(node):
    """Pane refs under a layout node, first child first (so the top-left pane comes first)."""
    if not isinstance(node, dict):
        return []
    pane = node.get("pane")
    if isinstance(pane, dict):
        return [pane.get("ref")] if pane.get("ref") else []
    refs = []
    for child in node.get("children") or []:
        refs += leaf_panes(child)
    return refs


def right_subtree(node, pane_ref):
    """(found, subtree): whether pane_ref is under node, and the layout subtree right of it.

    The subtree is the next sibling in the nearest side-by-side ("horizontal") split that has
    pane_ref on its left. It is None if there is nothing to the right.
    """
    if not isinstance(node, dict):
        return False, None
    pane = node.get("pane")
    if isinstance(pane, dict):
        return pane.get("ref") == pane_ref, None
    children = node.get("children") or []
    for i, child in enumerate(children):
        found, subtree = right_subtree(child, pane_ref)
        if found:
            if subtree is None and node.get("direction") == "horizontal" and i + 1 < len(children):
                subtree = children[i + 1]
            return True, subtree
    return False, None


def choose_target(layout, panes, pane_ref):
    """The pane to open a viewer tab in: one to the right of pane_ref, or None to split instead.

    Among the panes on the right, one that already shows a markdown tab is preferred, else the
    top-left one. Raises LayoutError if pane_ref is not in the layout.
    """
    found, subtree = right_subtree(layout, pane_ref)
    if not found:
        raise LayoutError(f"{pane_ref} is not in the layout")
    candidates = leaf_panes(subtree)
    if not candidates:
        return None
    with_markdown = {p.get("ref") for p in panes or [] if isinstance(p, dict)
                     and any(isinstance(s, dict) and s.get("type") == "markdown"
                             for s in p.get("surfaces") or [])}
    for ref in candidates:
        if ref in with_markdown:
            return ref
    return candidates[0]


def run_cmux(cmd, capture=False):
    """Run cmux. Returns (stdout, error): error is None on success, else a short reason."""
    try:
        r = subprocess.run(cmd, stdin=subprocess.DEVNULL,
                           stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
                           stderr=subprocess.PIPE, text=True, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        return "", f"cmux did not answer within {TIMEOUT}s"
    if r.returncode != 0:
        lines = (r.stderr or "").strip().splitlines()
        return "", f"cmux exited {r.returncode}: {lines[-1] if lines else 'no message'}"
    return r.stdout or "", None


def read_layout(cmux, workspace):
    """(workspace dict, caller dict) from `cmux tree --json`. Raises LayoutError."""
    out, error = run_cmux([cmux, "tree", "--json", "--workspace", workspace], capture=True)
    if error:
        raise LayoutError(error)
    try:
        data = json.loads(out)
        found = [ws for w in data["windows"] for ws in w["workspaces"]]
    except (ValueError, KeyError, TypeError):
        raise LayoutError("unexpected output from cmux tree")
    match = [ws for ws in found if isinstance(ws, dict) and workspace in (ws.get("id"), ws.get("ref"))]
    if not match and len(found) == 1 and isinstance(found[0], dict):
        match = found
    if not match:
        raise LayoutError("workspace not found in cmux tree")
    caller = data.get("caller")
    return match[0], caller if isinstance(caller, dict) else {}


def plan_open(cmux, workspace, path, surface, by_surface):
    """(command, how) for opening path, decided from the workspace layout. Raises LayoutError."""
    ws, caller = read_layout(cmux, workspace)
    panes = [p for p in ws.get("panes") or [] if isinstance(p, dict)]
    if by_surface:
        base = next((p.get("ref") for p in panes for s in p.get("surfaces") or []
                     if isinstance(s, dict) and surface in (s.get("ref"), s.get("id"))), None)
        if not base:
            raise LayoutError(f"surface {surface} not found")
    else:
        base = caller.get("pane_ref")
        if not base:
            raise LayoutError("cmux tree did not report the caller's pane")
    target = choose_target(ws.get("layout"), panes, base)
    if target:
        return [cmux, "open", path, "--workspace", workspace, "--pane", target, "--no-focus"], \
            f"tab in {target}"
    selected = next((p.get("selected_surface_ref") for p in panes if p.get("ref") == base), None)
    return split_command(cmux, workspace, path, selected or surface), "new split"


def split_command(cmux, workspace, path, surface):
    cmd = [cmux, "markdown", "open", path, "--workspace", workspace]
    if surface:
        cmd += ["--surface", surface]
    return cmd + ["--focus", "false"]


def open_file(path, surface=None, by_surface=False):
    """Open one file in a markdown viewer. No-op outside cmux. Returns how, or None if not opened.

    If there is already a pane to the right of the base pane, the file opens there as a tab.
    Otherwise the base pane is split to the right. The base pane is the one this process runs in
    ($CMUX_SURFACE_ID), or the one holding `surface` when by_surface is set.

    If the layout can't be read, the file opens in a new split from `surface` (None leaves the
    choice to cmux: the focused surface).
    """
    workspace = os.environ.get("CMUX_WORKSPACE_ID")
    if not workspace:
        return None
    cmux = find_cmux()
    if not cmux:
        return None
    if not os.path.isfile(path):
        warn(f"not a file: {path}")
        return None
    try:
        cmd, how = plan_open(cmux, workspace, path, surface, by_surface)
    except LayoutError as e:
        warn(f"layout not available ({e}); opening a new split")
        cmd, how = split_command(cmux, workspace, path, surface), "new split"
    _, error = run_cmux(cmd)
    if error:
        warn(error)
        return None
    return how


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
    p.add_argument("--surface", help="surface whose pane is the base: the viewer opens to its right "
                                     "(default: the surface this watcher runs in)")
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
                    how = open_file(path, a.surface, by_surface=bool(a.surface))
                    print(f"open: {os.path.relpath(path, root)} ({how or 'failed'})", flush=True)
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
