"""Exact stack-note helpers; caller guards have structural coverage only."""
from pathlib import Path
import hashlib
import json
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


class HostStackCallerGuards(unittest.TestCase):
    def test_guard_ordering(self):
        state = (ROOT / "runtime/r1_state.c").read_text()
        ring = (ROOT / "runtime/r1_ring.c").read_text()
        capture = function(state, "fibers_save")
        guards = [m.start() for m in re.finditer(r"host_inventory_valid\(\)", capture)]
        self.assertGreaterEqual(len(guards), 2)
        self.assertLess(guards[0], capture.index("os_r1_fibers(fib_cb)"))
        self.assertGreater(guards[-1], capture.index("os_r1_fibers(fib_cb)"))
        setup = function(state, "mark_setup")
        scan = setup.index("hs_exclude_all();")
        guard = setup.index("host_inventory_valid()", scan)
        end = setup.index("g_nx = 0", scan)
        self.assertLess(guard, end)
        self.assertIn("mark_undo()", setup[guard:end])
        self.assertIn("return 0", setup[guard:end])
        rebase = function(ring, "r1_ring_rebase")
        scan = rebase.index("hs_exclude_all();")
        guard = rebase.index("host_inventory_valid()", scan)
        end = rebase.index("int nmod", scan)
        self.assertLess(guard, end)
        for required in ("g_rg_nomem", "unpark()", "return 0"):
            self.assertIn(required, rebase[guard:end])
        restore = function(ring, "r1_ring_load")
        guard = restore.rindex("host_inventory_valid()")
        self.assertGreater(guard, restore.index("rgc_prepare("))
        self.assertLess(guard, restore.index("cp_reserved_begin();"))
        self.assertIn("goto refused", restore[guard:restore.index("cp_reserved_begin();")])


@unittest.skipUnless(os.name == "nt", "Windows host stack note harness")
class HostStackNotesSource(unittest.TestCase):
    def test_notes_and_sticky_validity(self):
        source = (ROOT / "runtime/r1_state.c").read_text()
        names = ["r1_host_stack_note", "host_inventory_valid"]
        block = "\n".join(function(source, name) for name in names)
        fixture = (ROOT / "tests/host_stack_notes_source_fixture.c").read_text()
        directory = ROOT / "artifacts/local/host-stack-notes-source"
        directory.mkdir(parents=True, exist_ok=True)
        out = Path(tempfile.mkdtemp(prefix="run-", dir=directory))
        translation = out / "host_stack_notes.c"
        translation.write_text(fixture.replace("/* NOTE_SOURCE */", block))
        (out / "source-manifest.json").write_text(json.dumps({
            "runtime/r1_state.c": hashlib.sha256(source.encode()).hexdigest(),
            "functions": names, "scope": "exact helpers; caller guards structural only",
        }, indent=2))
        print(f"Evidence: {out}")
        env = dict(os.environ, TMP=str(out), TEMP=str(out), TMPDIR=str(out))
        for opt in ("-O1", "-O3"):
            exe = out / (opt[1:] + ".exe")
            command = [resolve_clang(None), "-std=c11", opt, str(translation), "-o", str(exe)]
            (out / (opt[1:] + "-command.json")).write_text(json.dumps(command))
            result = subprocess.run(command, capture_output=True, text=True, timeout=60, env=env)
            (out / (opt[1:] + "-build.log")).write_text(result.stdout + result.stderr)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=15)
            (out / (opt[1:] + "-run.log")).write_text(f"exit={result.returncode}\n" + result.stdout + result.stderr)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("host_stack_notes_source_test: PASS", result.stdout)


if __name__ == "__main__":
    unittest.main()
