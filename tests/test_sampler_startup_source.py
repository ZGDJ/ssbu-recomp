"""Exact optional sampler startup; scripted handles, no live sampler thread."""
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


@unittest.skipUnless(os.name == "nt", "Windows sampler startup harness")
class SamplerStartupSourceTests(unittest.TestCase):
    def test_exact_startup(self):
        source = (ROOT / "runtime/r1_ring.c").read_text()
        names = ["rgss_close", "rgss_prepare", "rgs_samp_start"]
        block = "\n".join(function(source, name) for name in names)
        fixture = (ROOT / "tests/sampler_startup_source_fixture.c").read_text().replace("/* SOURCE */", block)
        directory = ROOT / "artifacts/local/sampler-startup-source"
        directory.mkdir(parents=True, exist_ok=True)
        out = Path(tempfile.mkdtemp(prefix="run-", dir=directory))
        translation = out / "sampler_startup.c"
        translation.write_text(fixture)
        (out / "source-manifest.json").write_text(json.dumps({
            "runtime/r1_ring.c": hashlib.sha256(source.encode()).hexdigest(),
            "functions": names,
            "scope": "exact startup helpers; scripted OS ownership, concurrent callers with real SRW lock; worker argument checked structurally, no sampler scheduling claim",
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
            for mode in ("success", "partial-main", "partial-thread", "close"):
                result = subprocess.run([str(exe), mode], capture_output=True, text=True, timeout=15)
                log = result.stdout + result.stderr
                (out / f"{opt[1:]}-{mode}.log").write_text(f"exit={result.returncode}\n" + log)
                if mode == "success":
                    self.assertEqual(result.returncode, 0, log)
                    self.assertIn("sampler_startup_source_test: PASS", log)
                    self.assertIn("CONCURRENT_STARTUP_PASS", log)
                else:
                    self.assertNotEqual(result.returncode, 0, log)
                    self.assertIn("FATAL", log)
                    self.assertIn("SAMPLER_FATAL_ORACLE_PASS", log)
                    self.assertNotIn("UNEXPECTED_SUCCESS", log)

    def test_worker_argument_and_caller_order(self):
        source = (ROOT / "runtime/r1_ring.c").read_text()
        thread = source[source.index("static DWORD WINAPI rgss_thread("):source.index("static void rgs_samp_start(", source.index("static DWORD WINAPI rgss_thread("))]
        # Bound worker body before any newly inserted preparation helpers.
        thread = thread[:thread.index("\n}") + 2]
        self.assertNotIn("g_rgss_main", thread)
        self.assertRegex(thread, r"HANDLE\s+main\s*=\s*(?:\(HANDLE\)\s*)?p\s*;")
        for call in ("SuspendThread(main)", "GetThreadContext(main,", "r1_resume_owned(main)"):
            self.assertIn(call, thread)
        caller = function(source, "rgs_samp_start")
        self.assertLess(caller.index("rgss_prepare()"), caller.index("g_rgss_run = 1"))
        self.assertIn("g_rgss_failed", caller)
        self.assertNotIn("fight_trace_fail", caller)
        report = function(source, "rgs_samp_report")
        self.assertIn("if (!g_rgss_run) return", report)


if __name__ == "__main__":
    unittest.main()
