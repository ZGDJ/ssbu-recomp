"""Compile the production catch preflight/commit against controlled OS boundaries."""
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


@unittest.skipUnless(os.name == "nt", "Windows compiler harness")
class CatchPreflightSourceTest(unittest.TestCase):
    def test_production_catch_preflight(self):
        ring = (ROOT / "runtime/r1_ring.c").read_text()
        start = ring.index("typedef struct { uint64_t cfa; uint64_t jb; } RgCatch;")
        end = ring.index("static long long g_rg_refused;", start)
        state = (ROOT / "runtime/r1_state.c").read_text()
        fib = re.search(r"typedef struct \{[^\n]+\} Fib;", state)
        self.assertIsNotNone(fib)
        fixture = (ROOT / "tests/catch_preflight_source_fixture.c").read_text()
        fixture = fixture.replace("/* FIB_TYPE_SOURCE */", fib.group(0))
        unwind = (ROOT / "runtime/nnunwind.c").read_text()
        names = ("catch_hash", "catch_window", "catch_read_slot", "catch_write_slot", "catch_free_slot_in", "catch_insert_slot",
                 "nnunwind_catch_stage_insert", "nnunwind_catch_stage_free")
        bodies = "\n".join(function(unwind, name) for name in names)
        bodies = bodies.replace("nnunwind_catch_stage_insert(", "actual_stage_insert(")
        bodies = bodies.replace("nnunwind_catch_stage_free(", "actual_stage_free(")
        fixture = fixture.replace("/* CATCH_HELPER_SOURCE */", bodies)
        fixture = fixture.replace("/* CATCH_PREFLIGHT_SOURCE */", ring[start:end])
        directory = ROOT / "artifacts/local/catch-preflight-source"
        directory.mkdir(parents=True, exist_ok=True)
        folder = tempfile.mkdtemp(prefix="run-", dir=directory)
        out = Path(folder)
        translation = out / "preflight.c"
        translation.write_text(fixture)
        environment = dict(os.environ, TMP=folder, TEMP=folder, TMPDIR=folder)
        compiler = resolve_clang(None)
        print(f"Evidence: {out}")
        for optimization in ("-O1", "-O3"):
            executable = out / (optimization[1:] + ".exe")
            result = subprocess.run([compiler, "-std=c11", optimization,
                                     "-I" + str(ROOT / "runtime"), str(translation), "-o", str(executable)],
                                    capture_output=True, text=True, timeout=60, env=environment)
            (out / (optimization[1:] + "-build.log")).write_text(result.stdout + result.stderr)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = subprocess.run([str(executable)], capture_output=True, text=True, timeout=10)
            (out / (optimization[1:] + ".log")).write_text(result.stdout + result.stderr)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("catch_preflight_source_test: PASS", result.stdout)
            print(result.stdout.strip())


if __name__ == "__main__":
    unittest.main()
