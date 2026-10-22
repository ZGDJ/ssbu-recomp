"""Exact optional diagnostic resource helpers; authoritative arrays excluded."""
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


@unittest.skipUnless(os.name == "nt", "Windows diagnostic resource harness")
class DiagnosticResourcesSourceTests(unittest.TestCase):
    @staticmethod
    def percentile(source):
        match = re.search(r"static double rg_pct\([^;{}]*\)\s*\{", source)
        if not match:
            raise AssertionError("missing production rg_pct")
        end = source.index("{", match.start()) + 1
        depth = 1
        while depth:
            depth += (source[end] == "{") - (source[end] == "}")
            end += 1
        return source[match.start():end]

    def test_exact_helpers(self):
        state = (ROOT / "runtime/r1_state.c").read_text()
        ring = (ROOT / "runtime/r1_ring.c").read_text()
        names = ["cmp_os", "os_cb", "os_snapshot", "os_compare", "ra_kind_append", "cmp_d"]
        block = "\n".join(function(state, name) for name in names)
        block += "\n" + self.percentile(ring)
        fixture = (ROOT / "tests/diagnostic_resources_source_fixture.c").read_text()
        directory = ROOT / "artifacts/local/diagnostic-resources-source"
        directory.mkdir(parents=True, exist_ok=True)
        out = Path(tempfile.mkdtemp(prefix="run-", dir=directory))
        translation = out / "diagnostic_resources.c"
        translation.write_text(fixture.replace("/* DIAGNOSTIC_SOURCE */", block))
        (out / "source-manifest.json").write_text(json.dumps({
            "runtime/r1_state.c": hashlib.sha256(state.encode()).hexdigest(),
            "runtime/r1_ring.c": hashlib.sha256(ring.encode()).hexdigest(),
            "functions": names + ["rg_pct"],
            "scope": "optional diagnostic helpers; scripted allocations/enumeration/trace failure sink",
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
            log = result.stdout + result.stderr
            (out / (opt[1:] + "-run.log")).write_text(f"exit={result.returncode}\n" + log)
            self.assertEqual(result.returncode, 0, log)
            self.assertIn("diagnostic_resources_source_test: PASS", log)

    def test_caller_routes(self):
        state = (ROOT / "runtime/r1_state.c").read_text()
        self.assertIn("os_snapshot(0)", function(state, "save"))
        self.assertIn("os_snapshot(1)", function(state, "os_compare"))
        frame = function(state, "ra_frame_end")
        self.assertIn("ra_kind_append(", frame)
        self.assertNotIn("realloc(", frame)
        self.assertIn('fight_trace_fail("trace_history_allocation")', function(state, "ra_kind_append"))


if __name__ == "__main__":
    unittest.main()
