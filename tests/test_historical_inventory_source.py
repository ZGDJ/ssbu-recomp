"""Exact historical fiber inventory and catch-preparation eligibility."""
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


@unittest.skipUnless(os.name == "nt", "Windows historical inventory harness")
class HistoricalInventorySourceTests(unittest.TestCase):
    def test_exact_history_and_preparation(self):
        state = (ROOT / "runtime/r1_state.c").read_text()
        ring = (ROOT / "runtime/r1_ring.c").read_text()
        fixture = (ROOT / "tests/historical_inventory_source_fixture.c").read_text()
        fixture = fixture.replace("/* HISTORICAL_SOURCE */", "\n".join(function(state, name) for name in ("bf_reserve", "bf_add")))
        fixture = fixture.replace("/* CATCH_SOURCE */", "\n".join(function(ring, name) for name in ("rgc_release", "rgc_prepare")))
        directory = ROOT / "artifacts/local/historical-inventory-source"
        directory.mkdir(parents=True, exist_ok=True)
        out = Path(tempfile.mkdtemp(prefix="run-", dir=directory))
        translation = out / "historical_inventory.c"
        translation.write_text(fixture)
        (out / "source-manifest.json").write_text(json.dumps({
            "runtime/r1_state.c": hashlib.sha256(state.encode()).hexdigest(),
            "runtime/r1_ring.c": hashlib.sha256(ring.encode()).hexdigest(),
            "functions": ["bf_reserve", "bf_add", "rgc_release", "rgc_prepare"],
            "scope": "historical ownership and preflight eligibility; catch overlay/live helpers controlled",
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
            result = subprocess.run([str(executable)], capture_output=True, text=True, timeout=15)
            log = result.stdout + result.stderr
            (out / (optimization[1:] + "-run.log")).write_text(f"exit={result.returncode}\n" + log)
            self.assertEqual(result.returncode, 0, log)
            self.assertIn("historical_inventory_source_test: PASS", log)
            print(optimization, "historical inventory PASS")


if __name__ == "__main__":
    unittest.main()
