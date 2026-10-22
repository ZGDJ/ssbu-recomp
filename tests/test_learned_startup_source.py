"""Exact memory inventory walks with scripted OS regions."""
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
class LearnedStartupSourceTests(unittest.TestCase):
    def test_caller_order(self):
        state = (ROOT / "runtime/r1_state.c").read_text()
        ring = (ROOT / "runtime/r1_ring.c").read_text()
        setup = function(state, "mark_setup")
        self.assertLess(setup.index("ls_startup_prepare("), setup.index("g_win1 = base"))
        rebase = function(ring, "r1_ring_rebase")
        self.assertLess(rebase.index("ls_startup_prepare("), rebase.index("r1_ring_let_go("))
        self.assertLess(rebase.index("ls_startup_prepare("), rebase.index("r1_ring_release("))

    def test_exact_initialization(self):
        source = (ROOT / "runtime/rb_learned.c").read_text()
        names = ["ls_startup_vfree", "ls_startup_prepare", "ls_after_setup", "ls_rebase"]
        fixture = (ROOT / "tests/learned_startup_source_fixture.c").read_text()
        fixture = fixture.replace("/* SOURCE */", "\n".join(function(source, n) for n in names))
        directory = ROOT / "artifacts/local/learned-startup-source"
        directory.mkdir(parents=True, exist_ok=True)
        out = Path(tempfile.mkdtemp(prefix="run-", dir=directory))
        translation = out / "learned_startup.c"
        translation.write_text(fixture)
        (out / "source-manifest.json").write_text(json.dumps({"runtime/rb_learned.c": hashlib.sha256(source.encode()).hexdigest(), "functions": names, "scope": "exact learned startup; scripted OS resources and protect boundary"}, indent=2))
        env = dict(os.environ, TMP=str(out), TEMP=str(out), TMPDIR=str(out))
        print(f"Evidence: {out}")
        for opt in ("-O1", "-O3"):
            exe = out / (opt[1:] + ".exe")
            command = [resolve_clang(None), "-std=c11", opt, str(translation), "-o", str(exe)]
            (out / (opt[1:] + "-command.json")).write_text(json.dumps(command))
            build = subprocess.run(command, capture_output=True, text=True, timeout=60, env=env)
            (out / (opt[1:] + "-build.log")).write_text(build.stdout + build.stderr)
            self.assertEqual(build.returncode, 0, build.stderr)
            for mode in ["", "1", "2", "3", "activation", "rebase"]:
                result = subprocess.run([str(exe)] + ([mode] if mode else []), capture_output=True, text=True, timeout=15)
                log = result.stdout + result.stderr
                (out / f"{opt[1:]}-{mode or 'matrix'}.log").write_text(f"exit={result.returncode}\n" + log)
                if mode:
                    self.assertNotEqual(result.returncode, 0, log)
                    self.assertIn("FATAL", log)
                    self.assertNotIn("UNEXPECTED SUCCESS", log)
                else:
                    self.assertEqual(result.returncode, 0, log)
                    self.assertIn("learned_startup_source_test: PASS", log)

if __name__ == "__main__":
    unittest.main()
