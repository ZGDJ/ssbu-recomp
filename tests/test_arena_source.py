"""Exact memory inventory walks with scripted OS regions."""
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
def function(source, name):
    match = re.search(r"static (?:int|size_t|void(?:\s*\*)?)\s*" + name + r"\([^;{}]*\)\s*\{", source)
    if not match:
        raise AssertionError(f"missing {name}")
    end = source.index("{", match.start()) + 1
    depth = 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[match.start():end]

@unittest.skipUnless(os.name == "nt", "Windows source harness")
class ArenaSourceTests(unittest.TestCase):
    def test_requested_startup_failure_is_fatal(self):
        source = (ROOT / "runtime/r1_state.c").read_text()
        # Public function occurs once in each compile branch; inspect enabled branch.
        start = source.rindex("void r1_register_heap(void)")
        caller = source[start:]
        bypass = caller.index('getenv("SSBU_R1_CRT_HEAP")')
        guard = caller.index("!ar_prepare()")
        registration = caller.index("register_imports(defs")
        self.assertLess(bypass, guard)
        self.assertLess(guard, registration)
        refused = caller[guard:caller.index("static const ImportDef defs", guard)]
        self.assertIn('fight_trace_fail("guest_arena_startup")', refused)
        self.assertIn("ARENA FATAL", refused)
        self.assertIn("abort()", refused)

    def test_exact_initialization(self):
        source = (ROOT / "runtime/r1_state.c").read_text()
        names = ["ar_prepare", "ar_alloc", "ar_usable", "ar_free", "r_calloc"]
        fixture = (ROOT / "tests/arena_source_fixture.c").read_text()
        fixture = fixture.replace("/* SOURCE */", "\n".join(function(source, n) for n in names))
        directory = ROOT / "artifacts/local/arena-source"
        directory.mkdir(parents=True, exist_ok=True)
        out = Path(tempfile.mkdtemp(prefix="run-", dir=directory))
        translation = out / "arena.c"
        translation.write_text(fixture)
        (out / "source-manifest.json").write_text(json.dumps({"runtime/r1_state.c": hashlib.sha256(source.encode()).hexdigest(), "functions": names, "scope": "exact arena bodies; bounded backing, scripted OS and real SRW lock"}, indent=2))
        env = dict(os.environ, TMP=str(out), TEMP=str(out), TMPDIR=str(out))
        print(f"Evidence: {out}")
        for opt in ("-O1", "-O3"):
            exe = out / (opt[1:] + ".exe")
            command = [resolve_clang(None), "-std=c11", opt, str(translation), "-o", str(exe)]
            (out / (opt[1:] + "-command.json")).write_text(json.dumps(command))
            build = subprocess.run(command, capture_output=True, text=True, timeout=60, env=env)
            (out / (opt[1:] + "-build.log")).write_text(build.stdout + build.stderr)
            self.assertEqual(build.returncode, 0, build.stderr)
            for mode in ["", "cleanup"]:
                result = subprocess.run([str(exe)] + ([mode] if mode else []), capture_output=True, text=True, timeout=15)
                log = result.stdout + result.stderr
                (out / f"{opt[1:]}-{mode or 'matrix'}.log").write_text(f"exit={result.returncode}\n" + log)
                if mode:
                    self.assertNotEqual(result.returncode, 0, log)
                    self.assertIn("FATAL", log)
                    self.assertNotIn("UNEXPECTED SUCCESS", log)
                else:
                    self.assertEqual(result.returncode, 0, log)
                    self.assertIn("arena_source_test: PASS", log)

if __name__ == "__main__":
    unittest.main()
