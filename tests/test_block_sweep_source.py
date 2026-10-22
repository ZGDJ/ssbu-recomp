"""Exact block rebuild and both sweep callers with bounded page fixtures."""
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

def sweep_function(source):
    match = re.search(r"static size_t mark_sweep\([^;{}]*\)\s*\{", source)
    if not match:
        raise AssertionError("missing production mark_sweep")
    index = source.index("{", match.start()) + 1
    depth = 1
    while depth:
        depth += (source[index] == "{") - (source[index] == "}")
        index += 1
    return source[match.start():index]


@unittest.skipUnless(os.name == "nt", "Windows source harness")
class BlockSweepSourceTests(unittest.TestCase):
    def test_rebuild_and_sweeps(self):
        state = (ROOT / "runtime/r1_state.c").read_text()
        ring = (ROOT / "runtime/r1_ring.c").read_text()
        body = "\n".join((function(state, "blk1_rebuild"),
                          sweep_function(state), function(ring, "rg_sweep")))
        fixture = (ROOT / "tests/block_sweep_source_fixture.c").read_text()
        self.assertEqual(fixture.count("/* BLOCK_SOURCE */"), 1)
        directory = ROOT / "artifacts/local/block-sweep-source"
        directory.mkdir(parents=True, exist_ok=True)
        out = Path(tempfile.mkdtemp(prefix="run-", dir=directory))
        translation = out / "block_sweep.c"
        translation.write_text(fixture.replace("/* BLOCK_SOURCE */", body))
        (out / "source-manifest.json").write_text(json.dumps({
            "runtime/r1_state.c": hashlib.sha256(state.encode()).hexdigest(),
            "runtime/r1_ring.c": hashlib.sha256(ring.encode()).hexdigest(),
            "functions": ["blk1_rebuild", "mark_sweep", "rg_sweep"],
        }, indent=2))
        env = dict(os.environ, TMP=str(out), TEMP=str(out), TMPDIR=str(out))
        print(f"Evidence: {out}")
        for optimization in ("-O1", "-O3"):
            exe = out / (optimization[1:] + ".exe")
            command = [resolve_clang(None), "-std=c11", optimization,
                       str(translation), "-o", str(exe)]
            (out / (optimization[1:] + "-command.json")).write_text(json.dumps(command))
            result = subprocess.run(command, capture_output=True, text=True, timeout=60, env=env)
            (out / (optimization[1:] + "-build.log")).write_text(result.stdout + result.stderr)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for case in ("success", "save-1", "save-2", "restore-1", "restore-2"):
                for deferred in (0, 1):
                    result = subprocess.run([str(exe), case, str(deferred)], capture_output=True, text=True, timeout=15)
                    log = result.stdout + result.stderr
                    (out / f"{optimization[1:]}-{case}-{deferred}.log").write_text(f"exit={result.returncode}\n" + log)
                    if case == "success":
                        self.assertEqual(result.returncode, 0, log)
                        self.assertIn("block_sweep_source_test: PASS", log)
                    else:
                        self.assertNotEqual(result.returncode, 0, log)
                        self.assertIn("MARK FATAL", log)
                        self.assertIn("failure-stopped-before-page-copy", log)
                        self.assertNotIn("UNEXPECTED_SUCCESS", log)


if __name__ == "__main__":
    unittest.main()
