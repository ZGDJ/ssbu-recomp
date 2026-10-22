"""Compile exact copy-pool source at O1/O3 with real Win32 concurrency."""
from pathlib import Path
import os
import json
import hashlib
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from run_rollback_tests import resolve_clang


@unittest.skipUnless(os.name == "nt", "Windows copy-worker harness")
class CopyWorkersSourceTest(unittest.TestCase):
    def test_production_workers(self):
        source = (ROOT / "runtime/r1_state.c").read_text()
        start = source.index("typedef struct { uint8_t *d; const uint8_t *s; } CopyJob;")
        end = source.index("static int g_cp_defer;", start)
        block = source[start:end]
        for name in ("cp_init", "cp_thread", "cp_run", "cp_fatal"):
            self.assertIn(name + "(", block)
        fixture = (ROOT / "tests/copy_workers_source_fixture.c").read_text()
        self.assertEqual(fixture.count("/* COPY_WORKERS_SOURCE */"), 1)
        directory = ROOT / "artifacts/local/copy-workers-source"
        directory.mkdir(parents=True, exist_ok=True)
        out = Path(tempfile.mkdtemp(prefix="run-", dir=directory))
        translation = out / "copy_workers.c"
        translation.write_text(fixture.replace("/* COPY_WORKERS_SOURCE */", block))
        header = (ROOT / "runtime/restore_resources.h").read_bytes()
        (out / "restore_resources.h").write_bytes(header)
        (out / "source-manifest.json").write_text(json.dumps({
            "runtime/r1_state.c": hashlib.sha256(source.encode()).hexdigest(),
            "runtime/restore_resources.h": hashlib.sha256(header).hexdigest(),
            "extraction": "CopyJob declaration through immediately before g_cp_defer",
        }, indent=2))
        environment = dict(os.environ, TMP=str(out), TEMP=str(out), TMPDIR=str(out))
        compiler = resolve_clang(None)
        print(f"Evidence: {out}")
        cases = [("success", 0, n, True) for n in (0, 1, 2, 8)]
        cases += [("priority", 0, 8, True)]
        cases += [("event", n, 8, True) for n in range(1, 17)]
        cases += [("thread", n, 8, True) for n in range(1, 9)]
        cases += [("dispatch", n, 8, False) for n in range(1, 9)]
        cases += [(name, 1, 8, False) for name in (
            "completion", "completion-abandoned")]
        cases += [(name, n, 8, False) for name in ("worker-wait", "worker-signal", "cleanup-close")
                  for n in range(1, 9)]
        cases += [(name, n, 8, False) for name in ("cleanup-signal", "cleanup-join")
                  for n in (1, 2)]
        for optimization in ("-O1", "-O3"):
            executable = out / (optimization[1:] + ".exe")
            command = [compiler, "-std=c11", optimization,
                       "-I" + str(out), str(translation), "-o", str(executable)]
            (out / (optimization[1:] + "-command.json")).write_text(json.dumps(command, indent=2))
            result = subprocess.run(command, capture_output=True, text=True, timeout=60, env=environment)
            (out / (optimization[1:] + "-build.log")).write_text(result.stdout + result.stderr)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for name, position, workers, succeeds in cases:
                with self.subTest(optimization=optimization, fault=name, position=position, workers=workers):
                    result = subprocess.run([str(executable), name, str(position), str(workers)],
                                            capture_output=True, text=True, timeout=15)
                    log = result.stdout + result.stderr
                    (out / f"{optimization[1:]}-{name}-{position}-{workers}.log").write_text(
                        f"exit={result.returncode}\n" + log)
                    if succeeds:
                        self.assertEqual(result.returncode, 0, log)
                        self.assertIn("copy_workers_source_test: PASS", result.stdout)
                    else:
                        self.assertNotEqual(result.returncode, 0, log)
                        self.assertIn("fatal", result.stderr)
                        if not name.startswith("cleanup-"):
                            self.assertIn("queue-preserved-before-fail-stop", log)
                        self.assertNotIn("UNEXPECTED_SUCCESS", log)
                        self.assertNotIn("copy_workers_source_test: PASS", log)
            print(f"{optimization}: {len(cases)} copy-worker cases")


if __name__ == "__main__":
    unittest.main()
