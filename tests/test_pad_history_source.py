"""Exact legacy pad helpers and routing; frame transition ordering is structural."""
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


@unittest.skipUnless(os.name == "nt", "Windows pad history harness")
class PadHistorySourceTests(unittest.TestCase):
    def test_exact_helpers(self):
        source = (ROOT / "runtime/r1_state.c").read_text()
        # Discard the non-Windows/no-runtime stub functions at the file head.
        production = source[source.index("static PadRec g_pad["):]
        names = ["pad_history_ready", "pad_history_apply", "pad_history_complete", "r1_poll", "r1_pad"]
        block = "\n".join(function(production, name) for name in names)
        fixture = (ROOT / "tests/pad_history_source_fixture.c").read_text().replace("/* PAD_SOURCE */", block)
        directory = ROOT / "artifacts/local/pad-history-source"
        directory.mkdir(parents=True, exist_ok=True)
        out = Path(tempfile.mkdtemp(prefix="run-", dir=directory))
        translation = out / "pad_history.c"
        translation.write_text(fixture)
        (out / "source-manifest.json").write_text(json.dumps({
            "runtime/r1_state.c": hashlib.sha256(source.encode()).hexdigest(),
            "functions": names,
            "scope": "exact pad history and mode routing; trace failure sink scripted; frame transitions checked structurally",
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
            for mode in ("success", "empty", "exhausted", "negative-index", "oversized-count", "negative-count", "sticky-replay", "incomplete", "overconsumed", "sticky-complete"):
                result = subprocess.run([str(exe), mode], capture_output=True, text=True, timeout=15)
                log = result.stdout + result.stderr
                (out / f"{opt[1:]}-{mode}.log").write_text(f"exit={result.returncode}\n" + log)
                if mode == "success":
                    self.assertEqual(result.returncode, 0, log)
                    self.assertIn("pad_history_source_test: PASS", log)
                else:
                    self.assertNotEqual(result.returncode, 0, log)
                    self.assertIn("FATAL", log)
                    self.assertIn("PAD_FATAL_ORACLE_PASS", log)
                    self.assertNotIn("UNEXPECTED_SUCCESS", log)

    def test_transition_order(self):
        source = (ROOT / "runtime/r1_state.c").read_text()
        frame = function(source, "r1_frame_end")
        first = frame[frame.index("} else if (g_phase == 1"):frame.index("} else if (g_phase == 2")]
        guard = first.index("!pad_history_ready()")
        restore = first.index("mark_restore(c)")
        refusal = first[guard:restore]
        for required in ("release();", "g_phase = 3", "g_fe_busy = 1", "return;"):
            self.assertIn(required, refusal)
        self.assertLess(refusal.index("release();"), refusal.index("return;"))
        second = frame[frame.index("} else if (g_phase == 2"):]
        completion = second.index("pad_history_complete();")
        for action in ('LOG("r1: re-run', "verify();", "release();", "g_cycle++"):
            self.assertLess(completion, second.index(action))
        capture = frame[frame.index("if (g_phase == 0 &&"):frame.index("} else if (g_phase == 1")]
        self.assertIn("g_pad_failed = 0", capture)
        self.assertIn("pad_history_apply(", function(source[source.index("static PadRec g_pad["):], "r1_pad"))


if __name__ == "__main__":
    unittest.main()
