"""Exact inventory functions with injected enumeration and tracked ownership."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from run_rollback_tests import resolve_clang
from test_catch_source import function
from test_capture_reservation_source import branch


@unittest.skipUnless(os.name == "nt", "Windows range inventory harness")
class RangeInventorySourceTest(unittest.TestCase):
    def test_production_inventory(self):
        source = (ROOT / "runtime/r1_state.c").read_text()
        names = ("inventory_query", "inventory_bounds", "add_range", "find_heaps", "ex_cb", "cmp_rng", "release", "collect")
        block = "\n".join(function(source, name) for name in names)
        fixture = (ROOT / "tests/range_inventory_source_fixture.c").read_text()
        ring = (ROOT / "runtime/r1_ring.c").read_text()
        fixture = fixture.replace("/* SAVE_BRANCH */", branch(function(source, "save"), "if (!collect(c))"))
        fixture = fixture.replace("/* MARK_BRANCH */", branch(function(source, "mark_save"), "if (g_mcheck)"))
        fixture = fixture.replace("/* REBASE_BRANCH */", branch(function(ring, "r1_ring_rebase"), "if (!collect(c))"))
        directory = ROOT / "artifacts/local/range-inventory-source"
        directory.mkdir(parents=True, exist_ok=True)
        out = Path(tempfile.mkdtemp(prefix="run-", dir=directory))
        translation = out / "range_inventory.c"
        translation.write_text(fixture.replace("/* INVENTORY_SOURCE */", block))
        (out / "source-manifest.json").write_text(json.dumps({
            "runtime/r1_state.c": hashlib.sha256(source.encode()).hexdigest(),
            "runtime/r1_ring.c": hashlib.sha256(ring.encode()).hexdigest(),
            "functions": names,
            "caller_branches": ["save collect refusal", "mark_save g_mcheck", "rebase collect refusal"],
        }, indent=2))
        environment = dict(os.environ, TMP=str(out), TEMP=str(out), TMPDIR=str(out))
        compiler = resolve_clang(None)
        print(f"Evidence: {out}")
        for optimization in ("-O1", "-O3"):
            executable = out / (optimization[1:] + ".exe")
            command = [compiler, "-std=c11", optimization, str(translation), "-o", str(executable)]
            (out / (optimization[1:] + "-command.json")).write_text(json.dumps(command, indent=2))
            result = subprocess.run(command, capture_output=True, text=True, timeout=60, env=environment)
            (out / (optimization[1:] + "-build.log")).write_text(result.stdout + result.stderr)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = subprocess.run([str(executable)], capture_output=True, text=True, timeout=15)
            (out / (optimization[1:] + "-run.log")).write_text(
                f"exit={result.returncode}\n" + result.stdout + result.stderr)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("range_inventory_source_test: PASS", result.stdout)
            print(optimization, result.stdout.strip())

    def test_caller_refusal_ordering(self):
        # Placement complements executed collect/refusal cleanup, but does not
        # execute the complete save/mark-save/rebase transactions.
        state = (ROOT / "runtime/r1_state.c").read_text()
        ring = (ROOT / "runtime/r1_ring.c").read_text()
        save = function(state, "save")
        mark = function(state, "mark_save")
        rebase = function(ring, "r1_ring_rebase")
        for body in (save, mark, rebase):
            self.assertIn("if (!collect(c))", body)
        self.assertLess(save.index("if (!collect(c))"), save.index("rs_alloc("))
        self.assertLess(mark.index("if (!collect(c))"), mark.index("park(0)"))
        self.assertLess(rebase.index("if (!collect(c))"), rebase.index("calloc(nwin"))


if __name__ == "__main__":
    unittest.main()
