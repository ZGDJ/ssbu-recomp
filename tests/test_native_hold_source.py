"""Compile exact production hold bodies against deterministic OS boundaries."""
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
    match = re.search(r"static (?:int|void|uint32_t) " + re.escape(name) + r"\([^;{}]*\)\s*\{", source)
    if not match:
        raise AssertionError(f"missing production function {name}")
    start = source.index("{", match.start())
    depth = 1
    index = start + 1
    while depth:
        depth += (source[index] == "{") - (source[index] == "}")
        index += 1
    return source[match.start():index]


@unittest.skipUnless(os.name == "nt", "Windows runtime hold harness")
class NativeHoldSourceTest(unittest.TestCase):
    def test_production_hold_lifecycle(self):
        source = (ROOT / "runtime/r1_state.c").read_text()
        names = ("r1_suspend_operation", "r1_resume_operation", "r1_hold_fatal",
                 "r1_suspend_owned", "r1_resume_owned", "unpark", "ra_hold_save",
                 "ra_release_save", "ra_hold_restore", "ra_hold_quiet")
        bodies = "\n".join(function(source, name) for name in names)
        fixture = (ROOT / "tests/native_hold_source_fixture.c").read_text().replace("/* HOLD_SOURCE */", bodies)
        directory = ROOT / "artifacts/local/native-hold-source"
        directory.mkdir(parents=True, exist_ok=True)
        folder = tempfile.mkdtemp(prefix="run-", dir=directory)
        out = Path(folder)
        translation = out / "hold.c"
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
            for all_first in ("0", "1"):
                result = subprocess.run([str(executable), all_first], capture_output=True, text=True, timeout=10)
                (out / (optimization[1:] + "-allfirst-" + all_first + ".log")).write_text(result.stdout + result.stderr)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("native_hold_source_test: PASS", result.stdout)
                print(result.stdout.strip())


if __name__ == "__main__":
    unittest.main()
