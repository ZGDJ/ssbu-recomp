"""Exact module preflight/publication helpers with scripted OS boundaries."""
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


@unittest.skipUnless(os.name == "nt", "Windows module publication harness")
class MarkModulesSourceTests(unittest.TestCase):
    def test_caller_ordering(self):
        state = (ROOT / "runtime/r1_state.c").read_text()
        ring = (ROOT / "runtime/r1_ring.c").read_text()
        setup = function(state, "mark_setup")
        self.assertLess(setup.index("mark_modules_prepare()"), setup.index("VirtualAlloc("))
        self.assertLess(setup.index("mark_modules_prepare()"), setup.index("*pm1 = m1"))
        self.assertGreater(setup.index("mark_modules_publish("), setup.index("*pm1 = m1"))
        rebase = function(ring, "r1_ring_rebase")
        self.assertLess(rebase.index("mark_modules_prepare()"), rebase.index("mark_modules_publish("))
        self.assertLess(rebase.index("mark_modules_publish("), rebase.index("rg_sweep("))
        guard = rebase[rebase.index("mark_modules_prepare()"):rebase.index("mark_modules_publish(")]
        self.assertIn("unpark()", guard)
        self.assertIn("return 0", guard)

    def test_exact_helpers(self):
        source = (ROOT / "runtime/r1_state.c").read_text()
        names = ["mark_modules_close", "mark_modules_prepare", "mark_modules_publish"]
        block = "\n".join(function(source, name) for name in names)
        fixture = (ROOT / "tests/mark_modules_source_fixture.c").read_text()
        directory = ROOT / "artifacts/local/mark-modules-source"
        directory.mkdir(parents=True, exist_ok=True)
        out = Path(tempfile.mkdtemp(prefix="run-", dir=directory))
        translation = out / "mark_modules.c"
        translation.write_text(fixture.replace("/* MODULE_SOURCE */", block))
        (out / "source-manifest.json").write_text(json.dumps({
            "runtime/r1_state.c": hashlib.sha256(source.encode()).hexdigest(),
            "functions": names, "scope": "exact helpers; loader lifetime and writer quiescence unproven",
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
            for mode in ("success", "close", "unprepared"):
                result = subprocess.run([str(exe)] + ([] if mode == "success" else [mode]), capture_output=True, text=True, timeout=15)
                log = result.stdout + result.stderr
                (out / f"{opt[1:]}-{mode}.log").write_text(f"exit={result.returncode}\n" + log)
                if mode == "success":
                    self.assertEqual(result.returncode, 0, log)
                    self.assertIn("mark_modules_source_test: PASS", log)
                else:
                    self.assertNotEqual(result.returncode, 0, log)
                    self.assertIn("MARK MODULE FATAL", log)
                    self.assertNotIn("UNEXPECTED_SUCCESS", log)


if __name__ == "__main__":
    unittest.main()
