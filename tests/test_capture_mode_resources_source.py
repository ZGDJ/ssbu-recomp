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
class CaptureModeResourcesSourceTests(unittest.TestCase):
    def test_caller_order(self):
        source = (ROOT / "runtime/r1_state.c").read_text()
        save = function(source, "save")
        self.assertLess(save.index("g_capture_mode_failed"), save.index("collect("))
        self.assertIn("!async_learn()) { release(); g_save_failed = 2; return; }", save)
        at = save.index("!async_add(")
        refusal = save[at:at+220]
        for item in ("unpark()", "release()", "g_save_failed", "return"):
            self.assertIn(item, refusal)
        self.assertIn("if (!g_save_failed) fast_save(c)", source)
        self.assertIn("if (!g_save_failed && g_fcheck) save(c)", source)
        self.assertIn("!fast_build()", source)
        check = function(source, "fast_check")
        self.assertLess(check.index("g_nfp >= g_fcap"), check.index("memcpy("))

    def test_exact_initialization(self):
        source = (ROOT / "runtime/r1_state.c").read_text()
        names = ["legacy_restore_unsupported", "cmp_ptr", "is_async", "learn_merge", "async_add", "async_learn", "fast_build", "fast_check", "fast_save", "fast_restore"]
        fixture = (ROOT / "tests/capture_mode_resources_source_fixture.c").read_text()
        fixture = fixture.replace("/* SOURCE */", "\n".join(function(source, n) for n in names))
        directory = ROOT / "artifacts/local/capture-mode-resources-source"
        directory.mkdir(parents=True, exist_ok=True)
        out = Path(tempfile.mkdtemp(prefix="run-", dir=directory))
        translation = out / "capture_mode_resources.c"
        translation.write_text(fixture)
        (out / "source-manifest.json").write_text(json.dumps({"runtime/r1_state.c": hashlib.sha256(source.encode()).hexdigest(), "functions": names, "scope": "exact capture-mode helpers; scripted allocations and writer; caller integration structural"}, indent=2))
        env = dict(os.environ, TMP=str(out), TEMP=str(out), TMPDIR=str(out))
        print(f"Evidence: {out}")
        for opt in ("-O1", "-O3"):
            exe = out / (opt[1:] + ".exe")
            command = [resolve_clang(None), "-std=c11", opt, str(translation), "-o", str(exe)]
            (out / (opt[1:] + "-command.json")).write_text(json.dumps(command))
            build = subprocess.run(command, capture_output=True, text=True, timeout=60, env=env)
            (out / (opt[1:] + "-build.log")).write_text(build.stdout + build.stderr)
            self.assertEqual(build.returncode, 0, build.stderr)
            for mode in ["", "async", "check", "restore", "failed-save"]:
                result = subprocess.run([str(exe)] + ([mode] if mode else []), capture_output=True, text=True, timeout=15)
                log = result.stdout + result.stderr
                (out / f"{opt[1:]}-{mode or 'matrix'}.log").write_text(f"exit={result.returncode}\n" + log)
                if mode:
                    self.assertNotEqual(result.returncode, 0, log)
                    self.assertIn("FATAL", log)
                    self.assertNotIn("UNEXPECTED SUCCESS", log)
                else:
                    self.assertEqual(result.returncode, 0, log)
                    self.assertIn("capture_mode_resources_source_test: PASS", log)

if __name__ == "__main__":
    unittest.main()
