"""Exact watchdog startup with scripted failures and a real event/thread handoff."""
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
class WatchdogStartupSourceTests(unittest.TestCase):
    def test_exact_initialization(self):
        source = (ROOT / "runtime/r1_state.c").read_text()
        names = ["ra_watchdog_prepare", "ra_watchdog_signal"]
        fixture = (ROOT / "tests/watchdog_startup_source_fixture.c").read_text()
        fixture = fixture.replace("/* SOURCE */", "\n".join(function(source, n) for n in names))
        directory = ROOT / "artifacts/local/watchdog-startup-source"
        directory.mkdir(parents=True, exist_ok=True)
        out = Path(tempfile.mkdtemp(prefix="run-", dir=directory))
        translation = out / "watchdog_startup.c"
        translation.write_text(fixture)
        (out / "source-manifest.json").write_text(json.dumps({"runtime/r1_state.c": hashlib.sha256(source.encode()).hexdigest(), "functions": names, "scope": "exact watchdog startup; scripted failures, real thread/event handoff, concurrent callers with real SRW lock and scripted resource handles"}, indent=2))
        env = dict(os.environ, TMP=str(out), TEMP=str(out), TMPDIR=str(out))
        print(f"Evidence: {out}")
        for opt in ("-O1", "-O3"):
            exe = out / (opt[1:] + ".exe")
            command = [resolve_clang(None), "-std=c11", opt, str(translation), "-o", str(exe)]
            (out / (opt[1:] + "-command.json")).write_text(json.dumps(command))
            build = subprocess.run(command, capture_output=True, text=True, timeout=60, env=env)
            (out / (opt[1:] + "-build.log")).write_text(build.stdout + build.stderr)
            self.assertEqual(build.returncode, 0, build.stderr)
            for mode in ["", "partial-event", "partial-thread", "close", "signal", "signal-absent"]:
                result = subprocess.run([str(exe)] + ([mode] if mode else []), capture_output=True, text=True, timeout=15)
                log = result.stdout + result.stderr
                (out / f"{opt[1:]}-{mode or 'matrix'}.log").write_text(f"exit={result.returncode}\n" + log)
                if mode:
                    self.assertNotEqual(result.returncode, 0, log)
                    self.assertIn("FATAL", log)
                    self.assertIn("WATCHDOG_FATAL_ORACLE_PASS", log)
                    self.assertNotIn("UNEXPECTED SUCCESS", log)
                else:
                    self.assertEqual(result.returncode, 0, log)
                    self.assertIn("watchdog_startup_source_test: PASS", log)
                    self.assertIn("CONCURRENT_STARTUP_PASS", log)

    def test_caller_order_and_signals(self):
        source = (ROOT / "runtime/r1_state.c").read_text()
        init = function(source, "ra_init")
        self.assertLess(init.index("ra_watchdog_prepare()"), init.index("g_ra = 1"))
        self.assertLess(init.index("ra_watchdog_prepare()"), init.index("hook_install_required("))
        hold = function(source, "ra_workers_hold")
        self.assertLess(hold.index("ra_workers_publish("), hold.index("ra_watchdog_signal()"))
        kick = function(source, "ra_kick2")
        self.assertIn("ra_workers_release(); ra_watchdog_signal();", kick)
        self.assertNotIn("SetEvent(", hold + kick)

if __name__ == "__main__":
    unittest.main()
