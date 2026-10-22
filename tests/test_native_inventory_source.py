"""Exact raw thread eligibility and cached/direct fiber enumeration."""
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


@unittest.skipUnless(os.name == "nt", "Windows native inventory source harness")
class NativeInventorySourceTests(unittest.TestCase):
    def test_exact_inventory(self):
        source = (ROOT / "runtime/os_threads.c").read_text()
        declaration = source[source.index("typedef struct Obj {"):source.index("} Obj;") + len("} Obj;")]
        cache = re.search(r"^static volatile LONG g_fib_gen[^\n]+", source, re.MULTILINE)
        buckets = re.search(r"^#define BUCKETS[^\n]+", source, re.MULTILINE)
        self.assertIsNotNone(cache)
        self.assertIsNotNone(buckets)
        names = ("guest_thread_info", "os_r1_thread_inventory_count", "os_r1_thread_inventory_valid", "os_r1_fibers_direct", "os_r1_fibers")
        body = "\n".join(function(source, name) for name in names)
        fixture = (ROOT / "tests/native_inventory_source_fixture.c").read_text()
        fixture = fixture.replace("/* OBJ_DECLARATION */", declaration)
        fixture = fixture.replace("/* CACHE_DECLARATIONS */", buckets.group() + "\n" + cache.group())
        fixture = fixture.replace("/* INVENTORY_SOURCE */", body)
        directory = ROOT / "artifacts/local/native-inventory-source"
        directory.mkdir(parents=True, exist_ok=True)
        out = Path(tempfile.mkdtemp(prefix="run-", dir=directory))
        translation = out / "native_inventory.c"
        translation.write_text(fixture)
        (out / "source-manifest.json").write_text(json.dumps({
            "runtime/os_threads.c": hashlib.sha256(source.encode()).hexdigest(),
            "functions": names,
            "declarations": ["Obj", "BUCKETS", "fiber cache globals"],
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
            log = result.stdout + result.stderr
            (out / (optimization[1:] + "-run.log")).write_text(f"exit={result.returncode}\n" + log)
            self.assertEqual(result.returncode, 0, log)
            self.assertIn("native_inventory_source_test: PASS", log)
            print(optimization, "native inventory PASS")

    def test_cache_growth_size_guard(self):
        # Executing integer-capacity overflow would require billions of nodes;
        # this source check supplements the executable allocation-failure cases.
        source = (ROOT / "runtime/os_threads.c").read_text()
        cache = function(source, "os_r1_fibers")
        self.assertRegex(cache, r"INT_MAX\s*/\s*2")
        self.assertIn("SIZE_MAX", cache)
        self.assertIn("!g_fib_cvalid", cache)
        self.assertIn("os_r1_fibers_direct(cb)", cache)


if __name__ == "__main__":
    unittest.main()
