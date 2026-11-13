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
printf '%s\\n' "$@" > "$FAKE_CMUX_LOG"
printf '%s\\n' "$3" >> "$FAKE_CMUX_LOG.calls"
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


class WatchMode(Base):
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
                         "open: " + os.path.join("04_results", "RESULT2.md"))

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
