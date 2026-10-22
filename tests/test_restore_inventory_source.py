"""Exact restore inventory prefix/refusal tail; not the complete restore."""
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


@unittest.skipUnless(os.name == "nt", "Windows restore inventory harness")
class RestoreInventorySourceTests(unittest.TestCase):
    def test_prefix_refusal_ownership(self):
        source = (ROOT / "runtime/r1_ring.c").read_text()
        body = function(source, "r1_ring_load")
        start = body.index("Th previous[256];")
        stop = body.index("g_nth = g->nth;", start)
        prefix = body[start:stop]
        tail = body[body.index("refused:"):body.rfind("}")]
        self.assertEqual(prefix.count("os_r1_thread_inventory_valid()"), 2)
        guards = list(re.finditer(r"os_r1_thread_inventory_valid\(\)", body))
        self.assertGreaterEqual(len(guards), 3)
        self.assertLess(guards[-1].start(), body.index("cp_reserved_begin();"))
        self.assertGreater(guards[-1].start(), body.index("rgc_prepare("))
        final_guard = body[guards[-1].start():body.index("cp_reserved_begin();")]
        self.assertIn("os_r1_thread_inventory_count() != inventory_count", final_guard)
        fixture = (ROOT / "tests/restore_inventory_source_fixture.c").read_text()
        fixture = fixture.replace("/* PREFIX */", prefix).replace("/* REFUSAL */", tail)
        directory = ROOT / "artifacts/local/restore-inventory-source"
        directory.mkdir(parents=True, exist_ok=True)
        out = Path(tempfile.mkdtemp(prefix="run-", dir=directory))
        translation = out / "restore_inventory.c"
        translation.write_text(fixture)
        (out / "source-manifest.json").write_text(json.dumps({
            "runtime/r1_ring.c": hashlib.sha256(source.encode()).hexdigest(),
            "scope": "exact previous-state snapshot through born inventory check; exact refused tail; remaining APIs stubbed",
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
            result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=15)
            (out / (opt[1:] + "-run.log")).write_text(f"exit={result.returncode}\n" + result.stdout + result.stderr)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("restore_inventory_source_test: PASS", result.stdout)


if __name__ == "__main__":
    unittest.main()
