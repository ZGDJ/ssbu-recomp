"""Exact learned-set guards with controlled protection failures, not writer quiescence."""
from pathlib import Path
import os
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from run_rollback_tests import resolve_clang
from test_catch_source import function


@unittest.skipUnless(os.name == "nt", "Windows learned tracking harness")
class LearnedTrackingSourceTest(unittest.TestCase):
    def test_production_tracking_guards(self):
        source = (ROOT / "runtime/rb_learned.c").read_text()
        bodies = next(line for line in source.splitlines() if line.startswith("static uint8_t *ls_addr("))
        bodies += "\n" + "\n".join(function(source, name) for name in
                           ("ls_id", "ls_ns", "ls_validate_tracking", "ls_open", "ls_range",
                            "ls_after_setup", "ls_rebase"))
        fixture = (ROOT / "tests/learned_tracking_source_fixture.c").read_text()
        directory = ROOT / "artifacts/local/learned-tracking-source"
        directory.mkdir(parents=True, exist_ok=True)
        folder = tempfile.mkdtemp(prefix="run-", dir=directory)
        out = Path(folder)
        translation = out / "learned_tracking.c"
        translation.write_text(fixture.replace("/* LEARNED_TRACKING_SOURCE */", bodies))
        environment = dict(os.environ, TMP=folder, TEMP=folder, TMPDIR=folder)
        compiler = resolve_clang(None)
        print(f"Evidence: {out}")
        for optimization in ("-O1", "-O3"):
            executable = out / (optimization[1:] + ".exe")
            result = subprocess.run([compiler, "-std=c11", optimization,
                                     str(translation), "-o", str(executable)],
                                    capture_output=True, text=True, timeout=60, env=environment)
            (out / (optimization[1:] + "-build.log")).write_text(result.stdout + result.stderr)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = subprocess.run([str(executable)], capture_output=True, text=True, timeout=10)
            (out / (optimization[1:] + ".log")).write_text(result.stdout + result.stderr)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("learned_tracking_source_test: PASS", result.stdout)
            print(result.stdout.strip())

    def test_guard_wiring_order(self):
        # Lexical production wiring checks supplement the executable predicates;
        # they do not execute capture, rebase, eviction, or restore transactions.
        source = (ROOT / "runtime/r1_ring.c").read_text()
        capture = function(source, "r1_ring_capture")
        guards = [m.start() for m in re.finditer(r"if \(!ls_validate_tracking\(\)\)", capture)]
        self.assertEqual(len(guards), 2)
        self.assertLess(capture.index("save(c)"), guards[0])
        self.assertLess(guards[0], capture.index("g_rg_count = 1"))
        self.assertLess(capture.index("ra_hold_quiet("), guards[1])
        self.assertLess(guards[1], capture.index("rg_capture_execute(s, frame)"))
        execute = function((ROOT / "runtime/capture_pages.h").read_text(), "rg_capture_execute")
        self.assertLess(execute.index("rg_slot_drop("), execute.index("g_rg_idx[op->id] = op->value"))
        rebase = function(source, "r1_ring_rebase")
        self.assertLess(rebase.index("ls_rebase();"), rebase.index("if (!ls_validate_tracking())"))
        self.assertLess(rebase.index("if (!ls_validate_tracking())"), rebase.index("g_rg_count = 1"))
        dirty = function(source, "rg_plan_dirty")
        self.assertLess(dirty.index("if (!ls_validate_tracking()) return 0;"), dirty.index("if (g_ls_active)"))


if __name__ == "__main__":
    unittest.main()
