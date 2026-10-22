"""Exact watchdog ownership helpers with real SRW locks and scripted timing."""
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


def resume_operation(source):
    start = source.index("static uint32_t r1_resume_operation(")
    end = source.index("\n}", start) + 2
    return source[start:end]


@unittest.skipUnless(os.name == "nt", "Windows watchdog harness")
class WatchdogSourceTests(unittest.TestCase):
    def test_exact_ownership_and_watchdog(self):
        source = (ROOT / "runtime/r1_state.c").read_text()
        start = source.index("static HANDLE g_ra_wh[16];")
        end = source.index("static void ra_workers_hold(void)", start)
        block = source[start:end]
        for name in ("ra_workers_generation", "ra_workers_release_generation", "ra_workers_publish", "ra_watchdog"):
            self.assertIn(name + "(", block)
        resume = "typedef struct { DWORD result,error; } R1HoldResult;\n" + resume_operation(source)
        resume += "\n" + function(source, "r1_hold_fatal") + "\n" + function(source, "r1_resume_owned")
        fixture = (ROOT / "tests/watchdog_source_fixture.c").read_text()
        fixture = fixture.replace("/* RESUME_SOURCE */", resume).replace("/* WATCHDOG_SOURCE */", block)
        directory = ROOT / "artifacts/local/watchdog-source"
        directory.mkdir(parents=True, exist_ok=True)
        out = Path(tempfile.mkdtemp(prefix="run-", dir=directory))
        translation = out / "watchdog.c"
        translation.write_text(fixture)
        header = (ROOT / "runtime/native_hold.h").read_bytes()
        (out / "native_hold.h").write_bytes(header)
        (out / "source-manifest.json").write_text(json.dumps({
            "runtime/r1_state.c": hashlib.sha256(source.encode()).hexdigest(),
            "runtime/native_hold.h": hashlib.sha256(header).hexdigest(),
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
            for case in ("success", "overlap", "resume-failed", "resume-zero",
                         "count-negative", "count-large", "generation-wrap",
                         "idle-wait-failed", "timed-wait-failed"):
                with self.subTest(optimization=optimization, case=case):
                    result = subprocess.run([str(executable), case], capture_output=True, text=True, timeout=15)
                    log = result.stdout + result.stderr
                    (out / f"{optimization[1:]}-{case}.log").write_text(f"exit={result.returncode}\n" + log)
                    if case == "success":
                        self.assertEqual(result.returncode, 0, log)
                        self.assertIn("watchdog_source_test: PASS", log)
                    else:
                        self.assertNotEqual(result.returncode, 0, log)
                        self.assertIn("HOLD FATAL", log)
                        self.assertNotIn("UNEXPECTED_SUCCESS", log)
            print(optimization, "watchdog cases PASS")


if __name__ == "__main__":
    unittest.main()
