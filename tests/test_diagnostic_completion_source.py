"""Exact scratch benchmark and production trace invalidation linkage."""
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


@unittest.skipUnless(os.name == "nt", "Windows completion harness")
class DiagnosticCompletionSourceTests(unittest.TestCase):
    def test_exact_completion(self):
        state = (ROOT / "runtime/r1_state.c").read_text()
        host = (ROOT / "fighter_sdk/fighter_host.c").read_text()
        match = re.search(r"static double learned_copy_ms\([^;{}]*\)\s*\{", state)
        self.assertIsNotNone(match)
        end = state.index("{", match.start()) + 1
        depth = 1
        while depth:
            depth += (state[end] == "{") - (state[end] == "}")
            end += 1
        scratch = state[match.start():end]
        fixture = (ROOT / "tests/diagnostic_completion_source_fixture.c").read_text()
        fixture = fixture.replace("/* SCRATCH_SOURCE */", scratch)
        fixture = fixture.replace("/* TRACE_SOURCE */", function(host, "fight_trace_fail"))
        fixture = fixture.replace("/* APPEND_SOURCE */", function(state, "ra_kind_append"))
        directory = ROOT / "artifacts/local/diagnostic-completion-source"
        directory.mkdir(parents=True, exist_ok=True)
        out = Path(tempfile.mkdtemp(prefix="run-", dir=directory))
        translation = out / "diagnostic_completion.c"
        translation.write_text(fixture)
        files = ["runtime/r1_state.c", "fighter_sdk/fighter_host.c", "runtime/bounded_trace.h"]
        manifest = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in files}
        manifest["scope"] = "exact scratch/append/fail functions; actual bounded trace header and SRW; bounded scratch tokens"
        (out / "source-manifest.json").write_text(json.dumps(manifest, indent=2))
        print(f"Evidence: {out}")
        env = dict(os.environ, TMP=str(out), TEMP=str(out), TMPDIR=str(out))
        for opt in ("-O1", "-O3"):
            exe = out / (opt[1:] + ".exe")
            command = [resolve_clang(None), "-std=c11", opt, "-I", str(ROOT / "runtime"), str(translation), "-o", str(exe)]
            (out / (opt[1:] + "-command.json")).write_text(json.dumps(command))
            result = subprocess.run(command, capture_output=True, text=True, timeout=60, env=env)
            (out / (opt[1:] + "-build.log")).write_text(result.stdout + result.stderr)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=15)
            log = result.stdout + result.stderr
            (out / (opt[1:] + "-run.log")).write_text(f"exit={result.returncode}\n" + log)
            self.assertEqual(result.returncode, 0, log)
            self.assertIn("diagnostic_completion_source_test: PASS", log)


if __name__ == "__main__":
    unittest.main()
