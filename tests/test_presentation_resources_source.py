"""Exact presentation resource helpers; bounded reservations and hook stubs."""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from run_rollback_tests import resolve_clang
from test_catch_source import function


def allocation_body(source):
    match = re.search(r"static uint64_t lp_alloc\([^;{}]*\)\s*\{", source)
    if not match:
        raise AssertionError("missing production lp_alloc")
    end = source.index("{", match.start()) + 1
    depth = 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[match.start():end]


@unittest.skipUnless(os.name == "nt", "Windows presentation resource harness")
class PresentationResourcesSourceTests(unittest.TestCase):
    def test_exact_resources(self):
        source = (ROOT / "runtime/rb_learned.c").read_text()
        names = ["lp_resource_free", "lp_resources_prepare", "lpb_put", "lpb_get", "lp_hooks_install"]
        block = "\n".join(function(source, name) for name in names) + "\n" + allocation_body(source)
        fixture = (ROOT / "tests/presentation_resources_source_fixture.c").read_text().replace("/* SOURCE */", block)
        directory = ROOT / "artifacts/local/presentation-resources-source"
        directory.mkdir(parents=True, exist_ok=True)
        out = Path(tempfile.mkdtemp(prefix="run-", dir=directory))
        translation = out / "presentation_resources.c"
        translation.write_text(fixture)
        (out / "source-manifest.json").write_text(json.dumps({
            "runtime/rb_learned.c": hashlib.sha256(source.encode()).hexdigest(),
            "functions": names + ["lp_alloc"],
            "scope": "exact helpers; bounded reservation tokens and ordered hook stubs; no hook rollback claim",
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
            for mode in ("success", "cleanup", "1", "2", "3", "4", "5"):
                result = subprocess.run([str(exe)] + ([] if mode == "success" else [mode]), capture_output=True, text=True, timeout=15)
                log = result.stdout + result.stderr
                (out / f"{opt[1:]}-{mode}.log").write_text(f"exit={result.returncode}\n" + log)
                if mode == "success":
                    self.assertEqual(result.returncode, 0, log)
                    self.assertIn("presentation_resources_source_test: PASS", log)
                else:
                    self.assertNotEqual(result.returncode, 0, log)
                    self.assertIn("FATAL", log)
                    self.assertIn("READY_AT_FATAL 0", log)
                    self.assertNotIn("UNEXPECTED_SUCCESS", log)
                    if mode.isdigit():
                        self.assertEqual(log.count("HOOK_CALL"), int(mode), log)

    def test_startup_order(self):
        source = (ROOT / "runtime/rb_learned.c").read_text()
        body = function(source, "ls_init")
        self.assertLess(body.index("lp_resources_prepare()"), body.index("lp_hooks_install()"))
        self.assertIn("return", body[body.index("lp_resources_prepare()"):body.index("lp_hooks_install()")])


if __name__ == "__main__":
    unittest.main()
