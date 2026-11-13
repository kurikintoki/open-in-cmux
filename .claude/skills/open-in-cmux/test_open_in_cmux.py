#!/usr/bin/env python3
"""Tests for open_in_cmux.py. Run: python3 test_open_in_cmux.py

A fake `cmux` is put on PATH. It records its arguments, so no real cmux is touched.
"""
import json
import os
import signal
import stat
import subprocess
import sys
import tempfile
import time
import unittest

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "open_in_cmux.py")
sys.path.insert(0, HERE)
import open_in_cmux  # noqa: E402

FAKE_CMUX = """#!/bin/sh
if [ "$1" = tree ]; then
  printf '%s\\n' "$@" > "$FAKE_CMUX_LOG.tree"
  [ -n "$FAKE_CMUX_TREE_FAIL" ] && { echo "tree boom" >&2; exit 5; }
  [ -n "$FAKE_CMUX_TREE" ] && cat "$FAKE_CMUX_TREE"
  exit 0
fi
printf '%s\\n' "$@" > "$FAKE_CMUX_LOG"
if [ "$1" = open ]; then opened="$2"; else opened="$3"; fi
printf '%s\\n' "$opened" >> "$FAKE_CMUX_LOG.calls"
[ -n "$FAKE_CMUX_SLEEP" ] && sleep "$FAKE_CMUX_SLEEP"
[ -n "$FAKE_CMUX_FAIL" ] && { echo "boom" >&2; exit 7; }
exit 0
"""


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = os.path.realpath(self.tmp.name)
        self.bin = os.path.join(self.root, "bin")
        os.mkdir(self.bin)
        fake = os.path.join(self.bin, "cmux")
        with open(fake, "w") as f:
            f.write(FAKE_CMUX)
        os.chmod(fake, os.stat(fake).st_mode | stat.S_IXUSR)
        self.log = os.path.join(self.root, "cmux.log")
        self.proj = os.path.join(self.root, "proj")
        os.mkdir(self.proj)

    def tearDown(self):
        self.tmp.cleanup()

    def touch(self, rel):
        path = os.path.join(self.proj, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "w").close()
        return path

    def env(self, in_cmux=True, **extra):
        env = {k: v for k, v in os.environ.items() if not k.startswith("CMUX_")}
        env["PATH"] = self.bin + os.pathsep + "/usr/bin:/bin"
        env["FAKE_CMUX_LOG"] = self.log
        if in_cmux:
            env["CMUX_WORKSPACE_ID"] = "WS"
            env["CMUX_SURFACE_ID"] = "SF"
        env.update(extra)
        return env

    def run_script(self, args=(), stdin="", env=None):
        return subprocess.run([sys.executable, SCRIPT, *args], input=stdin, text=True,
                              capture_output=True, env=env or self.env(), timeout=30)

    def hook(self, file_path, cwd=None, env=None, tool="Write"):
        payload = {"hook_event_name": "PostToolUse", "tool_name": tool,
                   "cwd": cwd or self.proj, "tool_input": {"file_path": file_path}}
        return self.run_script(stdin=json.dumps(payload), env=env)

    def called(self):
        if not os.path.exists(self.log):
            return None
        with open(self.log) as f:
            return f.read().splitlines()

    def assertQuiet(self, r):
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout, "")


class HookMode(Base):
    def test_opens_plan_with_matching_prompt(self):
        self.touch("02_prompts/PROMPT2.md")
        plan = self.touch("03_plans/PLAN2.md")
        r = self.hook(plan)
        self.assertQuiet(r)
        self.assertEqual(self.called(), ["markdown", "open", plan, "--workspace", "WS",
                                         "--surface", "SF", "--focus", "false"])

    def test_opens_result_with_matching_prompt(self):
        self.touch("02_prompts/PROMPT7.md")
        result = self.touch("04_results/RESULT7.md")
        self.assertQuiet(self.hook(result))
        self.assertEqual(self.called()[2], result)

    def test_relative_path_is_resolved_against_cwd(self):
        self.touch("02_prompts/PROMPT2.md")
        plan = self.touch("03_plans/PLAN2.md")
        self.assertQuiet(self.hook("03_plans/PLAN2.md", cwd=self.proj))
        self.assertEqual(self.called()[2], plan)

    def test_numbers_compare_as_integers(self):
        self.touch("02_prompts/PROMPT03.md")
        self.assertQuiet(self.hook(self.touch("03_plans/PLAN3.md")))
        self.assertIsNotNone(self.called())

    def test_unnumbered_counts_as_one(self):
        self.touch("02_prompts/PROMPT1.md")
        self.assertQuiet(self.hook(self.touch("03_plans/PLAN.md")))
        self.assertIsNotNone(self.called())

    def test_no_prompt_with_that_number(self):
        self.touch("02_prompts/PROMPT2.md")
        self.assertQuiet(self.hook(self.touch("03_plans/PLAN3.md")))
        self.assertIsNone(self.called())

    def test_no_prompt_at_all(self):
        self.assertQuiet(self.hook(self.touch("PLAN.md")))
        self.assertIsNone(self.called())

    def test_prompt_next_to_output_when_no_prompt_dir(self):
        self.touch("PROMPT4.md")
        self.assertQuiet(self.hook(self.touch("RESULT4.md")))
        self.assertIsNotNone(self.called())

    def test_prompt_dir_wins_over_same_dir(self):
        # 02_prompts/ exists, so a PROMPT next to the output is not looked at.
        self.touch("02_prompts/PROMPT9.md")
        self.touch("03_plans/PROMPT5.md")
        self.assertQuiet(self.hook(self.touch("03_plans/PLAN5.md")))
        self.assertIsNone(self.called())

    def test_other_file_names_are_ignored(self):
        self.touch("02_prompts/PROMPT2.md")
        for rel in ("03_plans/INDEX.md", "03_plans/PLAN2.txt", "03_plans/MYPLAN2.md",
                    "03_plans/plan2.md", "02_prompts/PROMPT2.md", "03_plans/PLAN2a.md"):
            self.assertQuiet(self.hook(self.touch(rel)))
            self.assertIsNone(self.called(), rel)

    def test_outside_cmux_does_nothing(self):
        self.touch("02_prompts/PROMPT2.md")
        plan = self.touch("03_plans/PLAN2.md")
        r = self.hook(plan, env=self.env(in_cmux=False))
        self.assertQuiet(r)
        self.assertEqual(r.stderr, "")
        self.assertIsNone(self.called())

    def test_no_cmux_binary_does_nothing(self):
        self.touch("02_prompts/PROMPT2.md")
        plan = self.touch("03_plans/PLAN2.md")
        env = self.env()
        env["PATH"] = "/usr/bin:/bin"
        r = self.hook(plan, env=env)
        self.assertQuiet(r)
        self.assertIsNone(self.called())

    def test_bundled_cli_path_is_the_fallback(self):
        self.touch("02_prompts/PROMPT2.md")
        plan = self.touch("03_plans/PLAN2.md")
        env = self.env(CMUX_BUNDLED_CLI_PATH=os.path.join(self.bin, "cmux"))
        env["PATH"] = "/usr/bin:/bin"
        self.assertQuiet(self.hook(plan, env=env))
        self.assertIsNotNone(self.called())

    def test_no_surface_id_omits_the_flag(self):
        self.touch("02_prompts/PROMPT2.md")
        plan = self.touch("03_plans/PLAN2.md")
        env = self.env()
        del env["CMUX_SURFACE_ID"]
        self.assertQuiet(self.hook(plan, env=env))
        self.assertEqual(self.called(), ["markdown", "open", plan, "--workspace", "WS",
                                         "--focus", "false"])

    def test_cmux_failure_still_exits_zero(self):
        self.touch("02_prompts/PROMPT2.md")
        plan = self.touch("03_plans/PLAN2.md")
        r = self.hook(plan, env=self.env(FAKE_CMUX_FAIL="1"))
        self.assertQuiet(r)
        self.assertIn("cmux exited 7: boom", r.stderr)

    def test_file_missing_on_disk(self):
        self.touch("02_prompts/PROMPT2.md")
        r = self.hook(os.path.join(self.proj, "03_plans", "PLAN2.md"))
        self.assertQuiet(r)
        self.assertIsNone(self.called())

    def test_bad_stdin_still_exits_zero(self):
        for stdin in ("", "not json", "[]", "{}", '{"tool_input": null}',
                      '{"tool_input": {"file_path": 3}}'):
            r = self.run_script(stdin=stdin)
            self.assertQuiet(r)
            self.assertIsNone(self.called(), stdin)


class CliMode(Base):
    def test_opens_any_file_without_the_prompt_check(self):
        notes = self.touch("notes.md")
        self.assertQuiet(self.run_script([notes]))
        self.assertEqual(self.called()[:3], ["markdown", "open", notes])

    def test_outside_cmux_does_nothing(self):
        notes = self.touch("notes.md")
        self.assertQuiet(self.run_script([notes], env=self.env(in_cmux=False)))
        self.assertIsNone(self.called())

    def test_missing_file_is_reported_not_opened(self):
        r = self.run_script([os.path.join(self.proj, "nope.md")])
        self.assertQuiet(r)
        self.assertIn("not a file", r.stderr)
        self.assertIsNone(self.called())


class WatchBase(Base):
    """Start and stop a watcher, and see what it asked cmux to open."""

    def setUp(self):
        super().setUp()
        self.proc = None

    def tearDown(self):
        self.stop()
        super().tearDown()

    def start(self, args=(), env=None, cwd=None):
        self.proc = subprocess.Popen(
            [sys.executable, SCRIPT, "--watch", *args, "--interval", "0.05"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            env=env or self.env(), cwd=cwd or self.proj)
        line = self.proc.stdout.readline()  # the baseline is taken before this line is printed
        self.assertTrue(line.startswith("watching: "), line)
        return line

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            self.proc.wait(timeout=10)
        if self.proc:
            self.proc.stdout.close()
            self.proc.stderr.close()

    def calls(self):
        path = self.log + ".calls"
        if not os.path.exists(path):
            return []
        with open(path) as f:
            return f.read().splitlines()

    def wait_calls(self, n, timeout=5.0):
        deadline = time.time() + timeout
        while time.time() < deadline and len(self.calls()) < n:
            time.sleep(0.02)
        return self.calls()

    def settle(self):
        time.sleep(0.4)  # several polling intervals


class WatchMode(WatchBase):
    def test_opens_a_file_created_after_start(self):
        self.touch("02_prompts/PROMPT2.md")
        os.mkdir(os.path.join(self.proj, "04_results"))
        line = self.start()
        self.assertIn(os.path.join(self.proj, "04_results"), line)
        result = self.touch("04_results/RESULT2.md")
        self.assertEqual(self.wait_calls(1), [result])
        self.assertEqual(self.called(), ["markdown", "open", result, "--workspace", "WS",
                                         "--focus", "false"])
        self.assertEqual(self.proc.stdout.readline().strip(),
                         "open: " + os.path.join("04_results", "RESULT2.md") + " (new split)")

    def test_surface_flag_is_passed_on(self):
        self.touch("02_prompts/PROMPT2.md")
        self.start(["--surface", "surface:7"])
        plan = self.touch("03_plans/PLAN2.md")
        self.wait_calls(1)
        self.assertEqual(self.called(), ["markdown", "open", plan, "--workspace", "WS",
                                         "--surface", "surface:7", "--focus", "false"])

    def test_dir_argument(self):
        self.touch("02_prompts/PROMPT2.md")
        self.start([self.proj], cwd=self.root)
        plan = self.touch("03_plans/PLAN2.md")
        self.assertEqual(self.wait_calls(1), [plan])

    def test_files_present_at_start_are_not_opened(self):
        self.touch("02_prompts/PROMPT2.md")
        self.touch("03_plans/PLAN2.md")
        self.start()
        self.settle()
        self.assertEqual(self.calls(), [])

    def test_rewriting_an_existing_file_does_not_open_it(self):
        self.touch("02_prompts/PROMPT2.md")
        plan = self.touch("03_plans/PLAN2.md")
        self.start()
        with open(plan, "w") as f:
            f.write("> Status: Superseded\n")
        self.settle()
        self.assertEqual(self.calls(), [])

    def test_no_matching_prompt_is_not_opened(self):
        self.touch("02_prompts/PROMPT2.md")
        self.start()
        self.touch("03_plans/PLAN3.md")
        self.touch("03_plans/INDEX.md")
        self.settle()
        self.assertEqual(self.calls(), [])

    def test_each_file_is_opened_once(self):
        self.touch("02_prompts/PROMPT2.md")
        self.touch("02_prompts/PROMPT3.md")
        os.mkdir(os.path.join(self.proj, "03_plans"))
        self.start()
        plan2 = self.touch("03_plans/PLAN2.md")
        self.wait_calls(1)
        plan3 = self.touch("03_plans/PLAN3.md")
        self.wait_calls(2)
        self.settle()
        self.assertEqual(self.calls(), [plan2, plan3])

    def test_recreated_file_is_opened_again(self):
        self.touch("02_prompts/PROMPT2.md")
        self.start()
        plan = self.touch("03_plans/PLAN2.md")
        self.wait_calls(1)
        os.remove(plan)
        self.settle()
        self.touch("03_plans/PLAN2.md")
        self.assertEqual(self.wait_calls(2), [plan, plan])

    def test_watches_dir_itself_without_output_dirs(self):
        self.touch("PROMPT4.md")
        line = self.start()
        self.assertIn(self.proj, line)
        result = self.touch("RESULT4.md")
        self.assertEqual(self.wait_calls(1), [result])

    def test_output_dir_created_later_is_picked_up(self):
        self.touch("02_prompts/PROMPT2.md")
        self.start()
        plan = self.touch("03_plans/PLAN2.md")
        self.assertEqual(self.wait_calls(1), [plan])

    def test_keeps_going_after_cmux_fails(self):
        self.touch("02_prompts/PROMPT2.md")
        self.touch("02_prompts/PROMPT3.md")
        self.start(env=self.env(FAKE_CMUX_FAIL="1"))
        plan2 = self.touch("03_plans/PLAN2.md")
        self.wait_calls(1)
        plan3 = self.touch("03_plans/PLAN3.md")
        self.assertEqual(self.wait_calls(2), [plan2, plan3])
        self.assertIsNone(self.proc.poll())

    def test_ctrl_c_exits_zero_without_traceback(self):
        self.start()
        self.proc.send_signal(signal.SIGINT)
        self.assertEqual(self.proc.wait(timeout=10), 0)
        self.assertEqual(self.proc.stderr.read(), "")

    def test_outside_cmux_exits_one(self):
        r = self.run_script(["--watch", self.proj], env=self.env(in_cmux=False))
        self.assertEqual(r.returncode, 1)
        self.assertEqual(r.stdout, "")
        self.assertIn("not inside cmux", r.stderr)

    def test_no_cmux_binary_exits_one(self):
        env = self.env()
        env["PATH"] = "/usr/bin:/bin"
        r = self.run_script(["--watch", self.proj], env=env)
        self.assertEqual(r.returncode, 1)
        self.assertIn("cmux command was not found", r.stderr)

    def test_missing_dir_exits_one(self):
        r = self.run_script(["--watch", os.path.join(self.root, "nope")])
        self.assertEqual(r.returncode, 1)
        self.assertIn("not a directory", r.stderr)


def leaf(ref):
    return {"pane": {"ref": ref}}


def split(direction, first, second):
    return {"direction": direction, "split": 0.5, "children": [first, second]}


def pane(ref, *types):
    n = ref.split(":")[1]
    surfaces = [{"ref": f"surface:{n}{i}", "type": t} for i, t in enumerate(types or ("terminal",))]
    return {"ref": ref, "selected_surface_ref": surfaces[0]["ref"], "surfaces": surfaces}


def tree(layout, panes, caller_pane="pane:1", workspace_id="WS"):
    return {"caller": {"pane_ref": caller_pane, "surface_ref": "surface:10"},
            "windows": [{"workspaces": [{"id": workspace_id, "ref": "workspace:1",
                                         "layout": layout, "panes": panes}]}]}


class ChooseTarget(unittest.TestCase):
    """The pure decision: which pane gets the viewer tab (None = split instead)."""

    def choose(self, layout, panes, base="pane:1"):
        return open_in_cmux.choose_target(layout, panes, base)

    def test_two_panes_side_by_side(self):
        layout = split("horizontal", leaf("pane:1"), leaf("pane:2"))
        self.assertEqual(self.choose(layout, [pane("pane:1"), pane("pane:2")]), "pane:2")

    def test_base_is_the_rightmost_pane(self):
        layout = split("horizontal", leaf("pane:1"), leaf("pane:2"))
        self.assertIsNone(self.choose(layout, [pane("pane:1"), pane("pane:2")], base="pane:2"))

    def test_single_pane(self):
        self.assertIsNone(self.choose(leaf("pane:1"), [pane("pane:1")]))

    def test_only_stacked_panes(self):
        layout = split("vertical", leaf("pane:1"), leaf("pane:2"))
        self.assertIsNone(self.choose(layout, [pane("pane:1"), pane("pane:2")]))

    def test_right_side_split_prefers_the_pane_with_markdown(self):
        layout = split("horizontal", leaf("pane:1"),
                       split("vertical", leaf("pane:2"), leaf("pane:3")))
        panes = [pane("pane:1"), pane("pane:2", "terminal"), pane("pane:3", "terminal", "markdown")]
        self.assertEqual(self.choose(layout, panes), "pane:3")

    def test_right_side_split_without_markdown_takes_top_left(self):
        layout = split("horizontal", leaf("pane:1"),
                       split("vertical", leaf("pane:2"), leaf("pane:3")))
        panes = [pane("pane:1"), pane("pane:2", "browser"), pane("pane:3")]
        self.assertEqual(self.choose(layout, panes), "pane:2")

    def test_markdown_pane_on_the_left_is_not_a_target(self):
        layout = split("horizontal", leaf("pane:0"),
                       split("horizontal", leaf("pane:1"), leaf("pane:2")))
        panes = [pane("pane:0", "markdown"), pane("pane:1"), pane("pane:2")]
        self.assertEqual(self.choose(layout, panes), "pane:2")

    def test_base_nested_on_the_left(self):
        # Left column is stacked (1 over 4); the right column is pane 2.
        layout = split("horizontal", split("vertical", leaf("pane:1"), leaf("pane:4")), leaf("pane:2"))
        panes = [pane("pane:1"), pane("pane:4"), pane("pane:2")]
        self.assertEqual(self.choose(layout, panes, base="pane:4"), "pane:2")

    def test_nearest_split_to_the_right_wins(self):
        # ((1 | 2) | 3): right of 1 is 2, right of 2 is 3.
        layout = split("horizontal", split("horizontal", leaf("pane:1"), leaf("pane:2")), leaf("pane:3"))
        panes = [pane("pane:1"), pane("pane:2"), pane("pane:3", "markdown")]
        self.assertEqual(self.choose(layout, panes), "pane:2")
        self.assertEqual(self.choose(layout, panes, base="pane:2"), "pane:3")

    # Nothing to the right of the base pane: reuse a pane that already shows markdown (PLAN10).

    def test_nothing_right_reuses_markdown_pane_below(self):
        # Claude left; right column stacked: base (watcher) on top, markdown below.
        layout = split("horizontal", leaf("pane:0"),
                       split("vertical", leaf("pane:1"), leaf("pane:2")))
        panes = [pane("pane:0"), pane("pane:1"), pane("pane:2", "markdown")]
        self.assertEqual(self.choose(layout, panes), "pane:2")

    def test_nothing_right_reuses_markdown_pane_on_the_left(self):
        layout = split("horizontal", leaf("pane:0"), leaf("pane:1"))
        panes = [pane("pane:0", "terminal", "markdown"), pane("pane:1")]
        self.assertEqual(self.choose(layout, panes), "pane:0")

    def test_markdown_only_in_the_base_pane_is_not_reused(self):
        layout = split("horizontal", leaf("pane:0"), leaf("pane:1"))
        panes = [pane("pane:0"), pane("pane:1", "terminal", "markdown")]
        self.assertIsNone(self.choose(layout, panes))

    def test_nothing_right_and_no_markdown_anywhere(self):
        layout = split("horizontal", leaf("pane:0"),
                       split("vertical", leaf("pane:1"), leaf("pane:2")))
        self.assertIsNone(self.choose(layout, [pane("pane:0"), pane("pane:1"), pane("pane:2")]))

    def test_pane_on_the_right_wins_over_markdown_elsewhere(self):
        # (0 | (1 over 3)) | 2: right of 1 is 2, although 3 (below) and 0 show markdown.
        layout = split("horizontal",
                       split("horizontal", leaf("pane:0"),
                             split("vertical", leaf("pane:1"), leaf("pane:3"))),
                       leaf("pane:2"))
        panes = [pane("pane:0", "markdown"), pane("pane:1"), pane("pane:3", "markdown"), pane("pane:2")]
        self.assertEqual(self.choose(layout, panes), "pane:2")

    def test_several_markdown_panes_takes_the_top_left_one(self):
        # Base is bottom right; markdown at top left and top right.
        layout = split("vertical", split("horizontal", leaf("pane:2"), leaf("pane:3")),
                       split("horizontal", leaf("pane:0"), leaf("pane:1")))
        panes = [pane("pane:2", "markdown"), pane("pane:3", "markdown"), pane("pane:0"), pane("pane:1")]
        self.assertEqual(self.choose(layout, panes), "pane:2")

    def test_base_not_in_layout(self):
        layout = split("horizontal", leaf("pane:1"), leaf("pane:2"))
        for bad_layout in (layout, None, {}, "x"):
            with self.assertRaises(open_in_cmux.LayoutError):
                self.choose(bad_layout, [], base="pane:9")


class Placement(Base):
    """Where the viewer goes, with a fake `cmux tree --json` answer. CLI, hook and watch modes."""

    SIDE_BY_SIDE = tree(split("horizontal", leaf("pane:1"), leaf("pane:2")),
                        [pane("pane:1"), pane("pane:2", "markdown")])
    ALONE = tree(leaf("pane:1"), [pane("pane:1", "terminal", "terminal")])

    def tree_env(self, data, **extra):
        path = os.path.join(self.root, "tree.json")
        with open(path, "w") as f:
            f.write(data if isinstance(data, str) else json.dumps(data))
        return self.env(FAKE_CMUX_TREE=path, **extra)

    def tree_args(self):
        with open(self.log + ".tree") as f:
            return f.read().splitlines()

    def test_pane_on_the_right_gets_a_tab(self):
        notes = self.touch("notes.md")
        r = self.run_script([notes], env=self.tree_env(self.SIDE_BY_SIDE))
        self.assertQuiet(r)
        self.assertEqual(r.stderr, "")
        self.assertEqual(self.tree_args(), ["tree", "--json", "--workspace", "WS"])
        self.assertEqual(self.called(), ["open", notes, "--workspace", "WS",
                                         "--pane", "pane:2", "--no-focus"])

    def test_no_pane_on_the_right_splits_from_the_base_pane(self):
        notes = self.touch("notes.md")
        r = self.run_script([notes], env=self.tree_env(self.ALONE))
        self.assertQuiet(r)
        self.assertEqual(r.stderr, "")
        self.assertEqual(self.called(), ["markdown", "open", notes, "--workspace", "WS",
                                         "--surface", "surface:10", "--focus", "false"])

    def test_hook_mode_uses_the_same_rule(self):
        self.touch("02_prompts/PROMPT2.md")
        plan = self.touch("03_plans/PLAN2.md")
        payload = {"cwd": self.proj, "tool_input": {"file_path": plan}}
        r = self.run_script(stdin=json.dumps(payload), env=self.tree_env(self.SIDE_BY_SIDE))
        self.assertQuiet(r)
        self.assertEqual(self.called(), ["open", plan, "--workspace", "WS",
                                         "--pane", "pane:2", "--no-focus"])

    def test_workspace_matched_by_ref_or_when_alone(self):
        notes = self.touch("notes.md")
        data = tree(split("horizontal", leaf("pane:1"), leaf("pane:2")),
                    [pane("pane:1"), pane("pane:2")], workspace_id="SOME-OTHER-UUID")
        self.assertQuiet(self.run_script([notes], env=self.tree_env(data)))
        self.assertEqual(self.called()[0], "open")

    def fallback(self, env, reason):
        notes = self.touch("notes.md")
        r = self.run_script([notes], env=env)
        self.assertQuiet(r)
        self.assertIn(reason, r.stderr)
        self.assertIn("opening a new split", r.stderr)
        self.assertEqual(self.called(), ["markdown", "open", notes, "--workspace", "WS",
                                         "--surface", "SF", "--focus", "false"])

    def test_tree_failure_falls_back_to_a_split(self):
        self.fallback(self.env(FAKE_CMUX_TREE_FAIL="1"), "cmux exited 5: tree boom")

    def test_tree_not_json_falls_back(self):
        self.fallback(self.tree_env("not json"), "unexpected output from cmux tree")

    def test_tree_wrong_shape_falls_back(self):
        self.fallback(self.tree_env({"windows": [{"no": "workspaces"}]}), "unexpected output")

    def test_tree_without_caller_falls_back(self):
        data = dict(self.SIDE_BY_SIDE, caller=None)
        self.fallback(self.tree_env(data), "did not report the caller's pane")

    def test_caller_pane_missing_from_layout_falls_back(self):
        data = tree(split("horizontal", leaf("pane:1"), leaf("pane:2")), [], caller_pane="pane:9")
        self.fallback(self.tree_env(data), "pane:9 is not in the layout")


class WatchPlacement(WatchBase):
    THREE = tree(split("horizontal", split("horizontal", leaf("pane:1"), leaf("pane:2")), leaf("pane:3")),
                 [pane("pane:1"), pane("pane:2"), pane("pane:3")])

    def tree_env(self, data):
        path = os.path.join(self.root, "tree.json")
        with open(path, "w") as f:
            json.dump(data, f)
        return self.env(FAKE_CMUX_TREE=path)

    def test_tab_in_the_pane_right_of_the_watcher(self):
        self.touch("02_prompts/PROMPT2.md")
        self.start(env=self.tree_env(self.THREE))
        plan = self.touch("03_plans/PLAN2.md")
        self.assertEqual(self.wait_calls(1), [plan])
        self.assertEqual(self.called(), ["open", plan, "--workspace", "WS",
                                         "--pane", "pane:2", "--no-focus"])
        self.assertEqual(self.proc.stdout.readline().strip(),
                         "open: " + os.path.join("03_plans", "PLAN2.md") + " (tab in pane:2)")

    def test_surface_flag_moves_the_base_pane(self):
        self.touch("02_prompts/PROMPT2.md")
        self.start(["--surface", "surface:20"], env=self.tree_env(self.THREE))
        plan = self.touch("03_plans/PLAN2.md")
        self.wait_calls(1)
        self.assertEqual(self.called(), ["open", plan, "--workspace", "WS",
                                         "--pane", "pane:3", "--no-focus"])

    def test_unknown_surface_falls_back_to_a_split_from_it(self):
        self.touch("02_prompts/PROMPT2.md")
        self.start(["--surface", "surface:99"], env=self.tree_env(self.THREE))
        plan = self.touch("03_plans/PLAN2.md")
        self.wait_calls(1)
        self.assertEqual(self.called(), ["markdown", "open", plan, "--workspace", "WS",
                                         "--surface", "surface:99", "--focus", "false"])

    def test_watcher_top_right_reuses_markdown_pane_below(self):
        # The layout of RESULT9: Claude left, watcher top right, markdown bottom right.
        self.touch("02_prompts/PROMPT2.md")
        data = tree(split("horizontal", leaf("pane:57"),
                          split("vertical", leaf("pane:64"), leaf("pane:65"))),
                    [pane("pane:57"), pane("pane:64"), pane("pane:65", "markdown")],
                    caller_pane="pane:64")
        self.start(env=self.tree_env(data))
        plan = self.touch("03_plans/PLAN2.md")
        self.wait_calls(1)
        self.assertEqual(self.called(), ["open", plan, "--workspace", "WS",
                                         "--pane", "pane:65", "--no-focus"])
        self.assertEqual(self.proc.stdout.readline().strip(),
                         "open: " + os.path.join("03_plans", "PLAN2.md") + " (tab in pane:65)")

    def test_first_split_then_tabs(self):
        # No pane on the right for the first file; the layout then has one for the second.
        self.touch("02_prompts/PROMPT2.md")
        self.touch("02_prompts/PROMPT3.md")
        env = self.tree_env(tree(leaf("pane:1"), [pane("pane:1")]))
        self.start(env=env)
        plan2 = self.touch("03_plans/PLAN2.md")
        self.wait_calls(1)
        self.assertEqual(self.called()[:2], ["markdown", "open"])
        with open(env["FAKE_CMUX_TREE"], "w") as f:
            json.dump(tree(split("horizontal", leaf("pane:1"), leaf("pane:2")),
                           [pane("pane:1"), pane("pane:2", "markdown")]), f)
        plan3 = self.touch("03_plans/PLAN3.md")
        self.assertEqual(self.wait_calls(2), [plan2, plan3])
        self.assertEqual(self.called(), ["open", plan3, "--workspace", "WS",
                                         "--pane", "pane:2", "--no-focus"])


class Timeout(Base):
    def test_slow_cmux_is_abandoned(self):
        plan = self.touch("03_plans/PLAN2.md")
        old_env, old_timeout = dict(os.environ), open_in_cmux.TIMEOUT
        os.environ.clear()
        os.environ.update(self.env(FAKE_CMUX_SLEEP="3"))
        open_in_cmux.TIMEOUT = 0.3
        try:
            open_in_cmux.open_file(plan)  # must return, not raise
        finally:
            open_in_cmux.TIMEOUT = old_timeout
            os.environ.clear()
            os.environ.update(old_env)


if __name__ == "__main__":
    unittest.main()
