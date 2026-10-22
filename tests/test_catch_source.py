"""Compile exact production catch bodies against deterministic OS boundaries."""
from pathlib import Path
import os
import re
import subprocess
import tempfile
import unittest
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from run_rollback_tests import resolve_clang


def function(source, name):
    match = re.search(r"(?:static )?(?:int|void|unsigned) " + re.escape(name) + r"\([^;{}]*\)\s*\{", source)
    if not match:
        raise AssertionError(f"missing production function {name}")
    start = source.index("{", match.start())
    depth = 1
    index = start + 1
    while depth:
        depth += (source[index] == "{") - (source[index] == "}")
        index += 1
    return source[match.start():index]


@unittest.skipUnless(os.name == "nt", "Windows runtime catch harness")
class CatchSourceTest(unittest.TestCase):
    def test_production_catch_capacity(self):
        source = (ROOT / "runtime/nnunwind.c").read_text()
        names = ("nnunwind_catch_try_lock", "nnunwind_catch_unlock", "catch_here",
                 "catch_hash", "catch_window", "catch_read_slot", "catch_write_slot", "catch_free_slot_in", "catch_free_slot", "catch_insert_slot", "catch_insert",
                 "nnunwind_catch_reinsert", "nnunwind_catch_reinsert_checked",
                 "nnunwind_catch_stage_insert", "nnunwind_catch_stage_free")
        bodies = "\n".join(function(source, name) for name in names)
        fixture = (ROOT / "tests/catch_source_fixture.c").read_text().replace("/* CATCH_SOURCE */", bodies)
        directory = ROOT / "artifacts/local/catch-source"
        directory.mkdir(parents=True, exist_ok=True)
        folder = tempfile.mkdtemp(prefix="run-", dir=directory)
        out = Path(folder)
        translation = out / "catch.c"
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
            self.assertIn("catch_source_test: PASS", result.stdout)
            print(result.stdout.strip())


if __name__ == "__main__":
    unittest.main()
