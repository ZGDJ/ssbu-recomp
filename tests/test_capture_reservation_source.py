"""Production capture reservations against fault-injected allocation boundaries."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from run_rollback_tests import resolve_clang
from test_catch_source import function


def branch(source, prefix):
    start = source.index(prefix)
    index = source.index("{", start) + 1
    depth = 1
    while depth:
        depth += (source[index] == "{") - (source[index] == "}")
        index += 1
    return source[start:index]


@unittest.skipUnless(os.name == "nt", "Windows capture reservation harness")
class CaptureReservationSourceTest(unittest.TestCase):
    def test_production_reservations(self):
        ring = (ROOT / "runtime/r1_ring.c").read_text()
        learned = (ROOT / "runtime/rb_learned.c").read_text()
        state = (ROOT / "runtime/r1_state.c").read_text()
        bodies = "\n".join(function(state, name) for name in
                           ("cp_reserve", "cp_reserved_begin", "cp_reserved_end", "cp_add"))
        bodies += "\n" + "\n".join(function(learned, name) for name in ("ls_capture_reserve", "ls_each", "ls_capture"))
        bodies += "\n" + "\n".join(function(ring, name) for name in
                                     ("rg_vcom", "rg_push", "rg_capture_mark_add", "rg_capture_finish", "rg_capture_prepare", "rg_capture_marked"))
        fixture = (ROOT / "tests/capture_reservation_source_fixture.c").read_text()
        directory = ROOT / "artifacts/local/capture-reservation-source"
        directory.mkdir(parents=True, exist_ok=True)
        folder = tempfile.mkdtemp(prefix="run-", dir=directory)
        out = Path(folder)
        translation = out / "capture_reservation.c"
        capture = function(ring, "r1_ring_capture")
        fixture = fixture.replace("/* CAPTURE_RESERVATION_SOURCE */", bodies)
        fixture = fixture.replace("/* CALLER_REFUSAL_BRANCH */", branch(capture, "if (!rg_capture_prepare(s))"))
        fixture = fixture.replace("/* CALLER_POOL_REFUSAL_BRANCH */", branch(capture, "if (!rg_capture_page_plan())"))
        translation.write_text(fixture)
        environment = dict(os.environ, TMP=folder, TEMP=folder, TMPDIR=folder)
        compiler = resolve_clang(None)
        print(f"Evidence: {out}")
        for optimization in ("-O1", "-O3"):
            executable = out / (optimization[1:] + ".exe")
            result = subprocess.run([compiler, "-std=c11", optimization,
                                     "-I" + str(ROOT / "runtime"), str(translation), "-o", str(executable)],
                                    capture_output=True, text=True, timeout=60, env=environment)
            (out / (optimization[1:] + "-build.log")).write_text(result.stdout + result.stderr)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = subprocess.run([str(executable)], capture_output=True, text=True, timeout=10)
            (out / (optimization[1:] + ".log")).write_text(result.stdout + result.stderr)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("capture_reservation_source_test: PASS", result.stdout)
            print(result.stdout.strip())

    def test_caller_ordering(self):
        # Complement extracted preparation/pool refusal branches with placement;
        # this lexical check does not execute the entire capture transaction.
        capture = function((ROOT / "runtime/r1_ring.c").read_text(), "r1_ring_capture")
        prepare = capture.index("if (!rg_capture_prepare(s))")
        self.assertLess(capture.rindex("rg_meta_prepare", 0, prepare), prepare)
        self.assertLess(prepare, capture.index("cp_reserved_begin();"))
        self.assertLess(capture.index("cp_reserved_begin();"), capture.index("if (!rg_capture_page_plan())"))
        self.assertLess(capture.index("if (!rg_capture_page_plan())"), capture.index("rg_capture_execute(s, frame);"))
        self.assertEqual(capture.count("rg_capture_finish();"), 2)
        self.assertNotIn("rg_slot_drop(", capture)
        self.assertNotIn("rg_pool_get_cap(", capture)
        self.assertNotIn("rg_sweep(rg_cap_page)", capture)
        pages = (ROOT / "runtime/capture_pages.h").read_text()
        self.assertIn("g_rg_mark_ids[k]", function(pages, "rg_capture_page_plan"))
        self.assertIn("g_rg_mark_ids[k]", function(pages, "rg_capture_execute"))


if __name__ == "__main__":
    unittest.main()
