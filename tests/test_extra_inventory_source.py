"""Exact extras descriptor append policy; full caller transactions are separate."""
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
from test_capture_reservation_source import branch


@unittest.skipUnless(os.name == "nt", "Windows source-harness compiler")
class ExtraInventorySourceTests(unittest.TestCase):
    def test_exact_append(self):
        source = (ROOT / "runtime/r1_state.c").read_text()
        helper = function(source, "extra_append")
        declaration = re.search(r"typedef struct \{[^\n]+\} Extra;", source)
        page_size = re.search(r"^#define PG \d+\s*$", source, re.MULTILINE)
        self.assertIsNotNone(declaration)
        self.assertIsNotNone(page_size)
        fixture = (ROOT / "tests/extra_inventory_source_fixture.c").read_text()
        fixture = fixture.replace("/* EXTRA_DECLARATIONS */", page_size.group().strip() + "\n" + declaration.group())
        fixture = fixture.replace("/* EXTRA_SOURCE */", helper)
        directory = ROOT / "artifacts/local/extra-inventory-source"
        directory.mkdir(parents=True, exist_ok=True)
        out = Path(tempfile.mkdtemp(prefix="run-", dir=directory))
        translation = out / "extra_inventory.c"
        translation.write_text(fixture)
        (out / "source-manifest.json").write_text(json.dumps({
            "runtime/r1_state.c": hashlib.sha256(source.encode()).hexdigest(),
            "extraction": "extra_append, Extra declaration and PG definition",
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
            result = subprocess.run([str(executable)], capture_output=True, text=True, timeout=15)
            (out / (optimization[1:] + "-run.log")).write_text(
                f"exit={result.returncode}\n" + result.stdout + result.stderr)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("extra_inventory_source_test: PASS", result.stdout)
            print(optimization, result.stdout.strip())

    def test_callers_check_refusal(self):
        # Lexical guard coverage only: cleanup/publication of the surrounding
        # mark_setup and rebase transactions require their own source fixtures.
        state = (ROOT / "runtime/r1_state.c").read_text()
        ring = (ROOT / "runtime/r1_ring.c").read_text()
        setup = function(state, "mark_setup")
        rebase = function(ring, "r1_ring_rebase")
        for body in (setup, rebase):
            guard = re.search(r"if\s*\(!extra_append\(", body)
            self.assertIsNotNone(guard)
            refusal = branch(body, guard.group())
            self.assertRegex(refusal, r"\b(?:return\s+0|goto\s+\w+)\s*;")
        self.assertIn("mark_undo();", branch(setup, re.search(r"if\s*\(!extra_append\(", setup).group()))


if __name__ == "__main__":
    unittest.main()
