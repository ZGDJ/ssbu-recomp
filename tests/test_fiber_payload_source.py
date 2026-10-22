"""Compile the exact suspended fiber payload visitor against a bounded fake inventory."""
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
    match = re.search(r"static int fibers_audit_payload\([^;{}]*\)\s*\{", source)
    if not match:
        raise AssertionError("missing production fibers_audit_payload")
    index = source.index("{", match.start()) + 1
    depth = 1
    while depth:
        depth += (source[index] == "{") - (source[index] == "}")
        index += 1
    return source[match.start():index]


@unittest.skipUnless(os.name == "nt", "Windows native type harness")
class FiberPayloadSourceTest(unittest.TestCase):
    def test_production_payload_observations(self):
        source = (ROOT / "runtime/r1_state.c").read_text()
        body = visitor(source)
        fixture = (ROOT / "tests/fiber_payload_source_fixture.c").read_text().replace("/* FIBER_PAYLOAD_SOURCE */", body)
        fib = re.search(r"typedef struct \{[^\n]+\} Fib;", source)
        self.assertIsNotNone(fib, "missing production Fib type")
        fixture = fixture.replace("/* FIB_TYPE_SOURCE */", fib.group(0))
        ring = (ROOT / "runtime/r1_ring.c").read_text()
        start = ring.index("typedef struct {\n    RefusalAudit bytes; const Fib *saved; int count;")
        end = ring.index("static RestorePlan *g_restore_collect;", start)
        fixture = fixture.replace("/* RING_PAYLOAD_SOURCE */", ring[start:end])
        directory = ROOT / "artifacts/local/fiber-payload-source"
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
            self.assertIn("fiber_payload_source_test: PASS", result.stdout)
            print(result.stdout.strip())


if __name__ == "__main__":
    unittest.main()
