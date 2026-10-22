"""Exact full rebase transaction with controlled memory, holds and metadata."""
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


@unittest.skipUnless(os.name == "nt", "Windows rebase source harness")
class RebaseSourceTests(unittest.TestCase):
    def test_exact_rebase(self):
        state = (ROOT / "runtime/r1_state.c").read_text()
        ring = (ROOT / "runtime/r1_ring.c").read_text()
        fixture = (ROOT / "tests/rebase_source_fixture.c").read_text()
        fixture = fixture.replace("/* EXTRA_SOURCE */", function(state, "extra_append"))
        fixture = fixture.replace("/* REBASE_SOURCE */", function(ring, "r1_ring_let_go") + "\n" + function(ring, "rg_rebase_vfree") + "\n" + function(ring, "r1_ring_rebase"))
        directory = ROOT / "artifacts/local/rebase-source"
        directory.mkdir(parents=True, exist_ok=True)
        out = Path(tempfile.mkdtemp(prefix="run-", dir=directory))
        translation = out / "rebase.c"
        translation.write_text(fixture)
        (out / "source-manifest.json").write_text(json.dumps({
            "runtime/r1_state.c": hashlib.sha256(state.encode()).hexdigest(),
            "runtime/r1_ring.c": hashlib.sha256(ring.encode()).hexdigest(),
        }, indent=2))
        environment = dict(os.environ, TMP=str(out), TEMP=str(out), TMPDIR=str(out))
        print(f"Evidence: {out}")
        for optimization in ("-O1", "-O3"):
            executable = out / (optimization[1:] + ".exe")
            command = [resolve_clang(None), "-std=c11", optimization, str(translation), "-o", str(executable)]
            (out / (optimization[1:] + "-command.json")).write_text(json.dumps(command, indent=2))
            result = subprocess.run(command, capture_output=True, text=True, timeout=60, env=environment)
            (out / (optimization[1:] + "-build.log")).write_text(result.stdout + result.stderr)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for case in ("success", "cleanup-free", "old-free", "decommit"):
                with self.subTest(optimization=optimization, case=case):
                    result = subprocess.run([str(executable), case], capture_output=True, text=True, timeout=15)
                    log = result.stdout + result.stderr
                    (out / f"{optimization[1:]}-{case}.log").write_text(f"exit={result.returncode}\n" + log)
                    if case == "success":
                        self.assertEqual(result.returncode, 0, log)
                        self.assertIn("rebase_source_test: PASS", log)
                    else:
                        self.assertNotEqual(result.returncode, 0, log)
                        self.assertIn("fatal", log.lower())
                        self.assertNotIn("UNEXPECTED_SUCCESS", log)
            print(optimization, "rebase cases PASS")


if __name__ == "__main__":
    unittest.main()
