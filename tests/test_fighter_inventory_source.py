"""Exact fighter PE inventory and saved-range cleanup."""
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

@unittest.skipUnless(os.name == "nt", "Windows source harness")
class FighterInventorySourceTests(unittest.TestCase):
    def test_exact_initialization(self):
        source = (ROOT / "runtime/r1_state.c").read_text()
        names = ["fighter_close", "fighter_sections", "add_fighter_dlls", "rs_free", "release"]
        fixture = (ROOT / "tests/fighter_inventory_source_fixture.c").read_text()
        fixture = fixture.replace("/* FIGHTER_SOURCE */", "\n".join(function(source, n) for n in names[:3]))
        fixture = fixture.replace("/* RELEASE_SOURCE */", "\n".join(function(source, n) for n in names[3:]))
        directory = ROOT / "artifacts/local/fighter-inventory-source"
        directory.mkdir(parents=True, exist_ok=True)
        out = Path(tempfile.mkdtemp(prefix="run-", dir=directory))
        translation = out / "fighter_inventory.c"
        translation.write_text(fixture)
        (out / "source-manifest.json").write_text(json.dumps({"runtime/r1_state.c": hashlib.sha256(source.encode()).hexdigest(), "functions": names, "scope": "exact PE helpers/enumerator and release; scripted guarded reads/add_span/OS cleanup"}, indent=2))
        env = dict(os.environ, TMP=str(out), TEMP=str(out), TMPDIR=str(out))
        print(f"Evidence: {out}")
        for opt in ("-O1", "-O3"):
            exe = out / (opt[1:] + ".exe")
            command = [resolve_clang(None), "-std=c11", opt, str(translation), "-o", str(exe)]
            (out / (opt[1:] + "-command.json")).write_text(json.dumps(command))
            build = subprocess.run(command, capture_output=True, text=True, timeout=60, env=env)
            (out / (opt[1:] + "-build.log")).write_text(build.stdout + build.stderr)
            self.assertEqual(build.returncode, 0, build.stderr)
            for mode in ["", "close", "count", "1", "2"]:
                result = subprocess.run([str(exe)] + ([mode] if mode else []), capture_output=True, text=True, timeout=15)
                log = result.stdout + result.stderr
                (out / f"{opt[1:]}-{mode or 'matrix'}.log").write_text(f"exit={result.returncode}\n" + log)
                if mode:
                    self.assertNotEqual(result.returncode, 0, log)
                    self.assertIn("FATAL", log)
                    self.assertNotIn("UNEXPECTED SUCCESS", log)
                else:
                    self.assertEqual(result.returncode, 0, log)
                    self.assertIn("fighter_inventory_source_test: PASS", log)

if __name__ == "__main__":
    unittest.main()
