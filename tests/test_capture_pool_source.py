"""Exact production capture pool planning with deterministic OS boundaries.

This is a source transaction fixture, not a native scheduling or gameplay test.
Generated translation units and compiler/run logs are retained for inspection.
"""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from run_rollback_tests import resolve_clang
from test_catch_source import function


@unittest.skipUnless(os.name == "nt", "Windows capture pool source harness")
class CapturePoolSourceTest(unittest.TestCase):
    def test_production_pool_transaction(self):
        ring = (ROOT / "runtime/r1_ring.c").read_text()
        self.assertIn('#include "capture_pool.h"', ring)
        self.assertIn('#include "capture_pages.h"', ring)
        learned = (ROOT / "runtime/rb_learned.c").read_text()
        fixture = (ROOT / "tests/capture_pool_source_fixture.c").read_text()
        bodies = "\n".join(function(learned, name) for name in
                           ("ls_capture_plan", "ls_capture_plan_commit"))
        bodies += "\n" + "\n".join(function(ring, name) for name in ("rg_push", "rg_slot_drop"))
        fixture = fixture.replace("/* CAPTURE_POOL_SOURCE */", bodies)
        directory = ROOT / "artifacts/local/capture-pool-source"
        directory.mkdir(parents=True, exist_ok=True)
        out = Path(tempfile.mkdtemp(prefix="run-", dir=directory))
        # Keep the actual shared implementation with each generated fixture,
        # so later runtime edits cannot change the retained evidence source.
        for name in ("capture_pool.h", "capture_pages.h", "restore_resources.h"):
            (out / name).write_bytes((ROOT / "runtime" / name).read_bytes())
        translation = out / "capture_pool.c"
        translation.write_text(fixture)
        environment = dict(os.environ, TMP=str(out), TEMP=str(out), TMPDIR=str(out))
        compiler = resolve_clang(None)
        print(f"Evidence: {out}")
        for optimization in ("-O1", "-O3"):
            executable = out / (optimization[1:] + ".exe")
            command = [compiler, "-std=c11", optimization,
                       "-I" + str(ROOT / "runtime"), str(translation), "-o", str(executable)]
            result = subprocess.run(command, capture_output=True, text=True,
                                    timeout=60, env=environment)
            (out / (optimization[1:] + "-build.log")).write_text(
                repr(command) + "\n" + result.stdout + result.stderr)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = subprocess.run([str(executable)], capture_output=True,
                                    text=True, timeout=30, env=environment)
            (out / (optimization[1:] + ".log")).write_text(result.stdout + result.stderr)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("capture_pool_source_test: PASS", result.stdout)
            print(result.stdout.strip())
            for failure in ("ownership-disagreement", "undo-disagreement"):
                result = subprocess.run([str(executable), failure], capture_output=True,
                                        text=True, timeout=30, env=environment)
                (out / (optimization[1:] + "-" + failure + ".log")).write_text(
                    result.stdout + result.stderr)
                self.assertNotEqual(result.returncode, 0, "post-mutation disagreement resumed")
                self.assertIn("fatal: prepared capture operation changed after mutation", result.stderr)


if __name__ == "__main__":
    unittest.main()
