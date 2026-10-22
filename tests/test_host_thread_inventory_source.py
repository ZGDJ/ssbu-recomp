"""Exact host thread inventory helper with scripted OS boundaries."""
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


@unittest.skipUnless(os.name == "nt", "Windows host-thread harness")
class HostThreadInventorySourceTests(unittest.TestCase):
    def test_caller_contract(self):
        source = (ROOT / "runtime/r1_state.c").read_text()
        body = function(source, "hs_exclude_all")
        self.assertIn("hs_threads_exclude(&nth)", body)
        gate = body[body.index("hs_threads_exclude(&nth)"):body.index("os_r1_fibers(hs_fiber_cb)")]
        self.assertIn("return", gate)
        self.assertIn("g_hs_thread_failed", function(source, "host_inventory_valid"))

    def test_exact_walk(self):
        source = (ROOT / "runtime/r1_state.c").read_text()
        names = ["hs_thread_close", "hs_threads_exclude"]
        block = "\n".join(function(source, name) for name in names)
        fixture = (ROOT / "tests/host_thread_inventory_source_fixture.c").read_text()
        directory = ROOT / "artifacts/local/host-thread-inventory-source"
        directory.mkdir(parents=True, exist_ok=True)
        out = Path(tempfile.mkdtemp(prefix="run-", dir=directory))
        translation = out / "host_threads.c"
        translation.write_text(fixture.replace("/* THREAD_SOURCE */", block))
        (out / "source-manifest.json").write_text(json.dumps({
            "runtime/r1_state.c": hashlib.sha256(source.encode()).hexdigest(),
            "functions": names, "scope": "exact thread walker; OS boundaries scripted; quiescence unproven",
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
            for mode in ("success", "1", "2", "3"):
                result = subprocess.run([str(exe)] + ([] if mode == "success" else [mode]), capture_output=True, text=True, timeout=15)
                log = result.stdout + result.stderr
                (out / f"{opt[1:]}-{mode}.log").write_text(f"exit={result.returncode}\n" + log)
                if mode == "success":
                    self.assertEqual(result.returncode, 0, log)
                    self.assertIn("host_thread_inventory_source_test: PASS", log)
                else:
                    self.assertNotEqual(result.returncode, 0, log)
                    self.assertIn("FATAL", log)
                    self.assertNotIn("UNEXPECTED_SUCCESS", log)


if __name__ == "__main__":
    unittest.main()
