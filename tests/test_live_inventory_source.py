"""Exact live-thread enumeration and fiber capture status propagation."""
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


@unittest.skipUnless(os.name == "nt", "Windows live inventory harness")
class LiveInventorySourceTests(unittest.TestCase):
    def test_capture_completeness(self):
        source = (ROOT / "runtime/r1_state.c").read_text()
        block = function(source, "live_rsps") + "\n" + function(source, "fibers_save")
        fixture = (ROOT / "tests/live_inventory_source_fixture.c").read_text()
        directory = ROOT / "artifacts/local/live-inventory-source"
        directory.mkdir(parents=True, exist_ok=True)
        out = Path(tempfile.mkdtemp(prefix="run-", dir=directory))
        translation = out / "live_inventory.c"
        translation.write_text(fixture.replace("/* LIVE_SOURCE */", block))
        (out / "source-manifest.json").write_text(json.dumps({
            "runtime/r1_state.c": hashlib.sha256(source.encode()).hexdigest(),
            "functions": ["live_rsps", "fibers_save"],
        }, indent=2))
        env = dict(os.environ, TMP=str(out), TEMP=str(out), TMPDIR=str(out))
        print(f"Evidence: {out}")
        for opt in ("-O1", "-O3"):
            exe = out / (opt[1:] + ".exe")
            command = [resolve_clang(None), "-std=c11", opt, str(translation), "-o", str(exe)]
            (out / (opt[1:] + "-command.json")).write_text(json.dumps(command))
            result = subprocess.run(command, capture_output=True, text=True, timeout=60, env=env)
            (out / (opt[1:] + "-build.log")).write_text(result.stdout + result.stderr)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=15)
            (out / (opt[1:] + "-run.log")).write_text(f"exit={result.returncode}\n" + result.stdout + result.stderr)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("live_inventory_source_test: PASS", result.stdout)


if __name__ == "__main__":
    unittest.main()
