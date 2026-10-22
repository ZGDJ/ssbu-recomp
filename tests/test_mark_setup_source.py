"""Exact mark setup/cleanup; bounded OS allocation and saved-backing fixtures."""
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


def pointer_function(source, name):
    start = source.index("static uint8_t *" + name + "(")
    end = source.index("\n}", start) + 2
    return source[start:end]


@unittest.skipUnless(os.name == "nt", "Windows mark setup harness")
class MarkSetupSourceTests(unittest.TestCase):
    def test_exact_setup(self):
        source = (ROOT / "runtime/r1_state.c").read_text()
        block = "\n".join(function(source,n) for n in ("inventory_query", "inventory_bounds", "inventory_alloc_span")) + "\n" + function(source, "extra_append") + "\n" + pointer_function(source, "in_shadow")
        block += "\n" + function(source, "sh_commit")
        block += "\n" + function(source, "mark_vfree")
        block += "\n" + function(source, "mark_undo") + "\n" + function(source, "mark_setup")
        fixture = (ROOT / "tests/mark_setup_source_fixture.c").read_text().replace("/* MARK_SOURCE */", block)
        directory = ROOT / "artifacts/local/mark-setup-source"
        directory.mkdir(parents=True, exist_ok=True)
        out = Path(tempfile.mkdtemp(prefix="run-", dir=directory))
        translation = out / "mark_setup.c"
        translation.write_text(fixture)
        (out / "source-manifest.json").write_text(json.dumps({
            "runtime/r1_state.c": hashlib.sha256(source.encode()).hexdigest(),
            "checked_cleanup": True,
            "retry_limitation": "Saved copies are rebuilt before retry; retired source backing is not reusable.",
        }, indent=2))
        environment = dict(os.environ, TMP=str(out), TEMP=str(out), TMPDIR=str(out))
        print(f"Evidence: {out}")
        cases = ["success", "shadow-free", "orphan-first", "orphan-second", "decommit"]
        for optimization in ("-O1", "-O3"):
            executable = out / (optimization[1:] + ".exe")
            command = [resolve_clang(None), "-std=c11", optimization, str(translation), "-o", str(executable)]
            (out / (optimization[1:] + "-command.json")).write_text(json.dumps(command, indent=2))
            result = subprocess.run(command, capture_output=True, text=True, timeout=60, env=environment)
            (out / (optimization[1:] + "-build.log")).write_text(result.stdout + result.stderr)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for case in cases:
                with self.subTest(optimization=optimization, case=case):
                    result = subprocess.run([str(executable), case], capture_output=True, text=True, timeout=15)
                    log = result.stdout + result.stderr
                    (out / f"{optimization[1:]}-{case}.log").write_text(f"exit={result.returncode}\n" + log)
                    if case == "success":
                        self.assertEqual(result.returncode, 0, log)
                        self.assertIn("mark_setup_source_test: PASS", log)
                    else:
                        self.assertNotEqual(result.returncode, 0, log)
                        self.assertIn("fatal", log.lower())
                        self.assertNotIn("UNEXPECTED_SUCCESS", log)
            print(optimization, "mark setup cases PASS including checked cleanup")


if __name__ == "__main__":
    unittest.main()
