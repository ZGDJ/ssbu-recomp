"""Compile the exact native inventory visitor against a bounded fake inventory."""
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


def visitor(source):
    match = re.search(r"int os_r1_native_audit\([^;{}]*\)\s*\{", source)
    if not match:
        raise AssertionError("missing production os_r1_native_audit")
    index = source.index("{", match.start()) + 1
    depth = 1
    while depth:
        depth += (source[index] == "{") - (source[index] == "}")
        index += 1
    return source[match.start():index]


@unittest.skipUnless(os.name == "nt", "Windows native type harness")
class NativeAuditSourceTest(unittest.TestCase):
    def test_production_inventory_observations(self):
        body = visitor((ROOT / "runtime/os_threads.c").read_text())
        fixture = (ROOT / "tests/native_audit_source_fixture.c").read_text().replace("/* NATIVE_AUDIT_SOURCE */", body)
        directory = ROOT / "artifacts/local/native-audit-source"
        directory.mkdir(parents=True, exist_ok=True)
        folder = tempfile.mkdtemp(prefix="run-", dir=directory)
        out = Path(folder)
        translation = out / "audit.c"
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
            self.assertIn("native_audit_source_test: PASS", result.stdout)
            print(result.stdout.strip())


if __name__ == "__main__":
    unittest.main()
