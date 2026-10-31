"""Game-free Windows tests of exact queue observer and dispatch/import sources.

Run with deps/python/Scripts/python.exe -I -m unittest discover -s tests
-p test_replay_queue_source.py -v. This is source evidence, not gameplay proof.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(os.environ.get("AUDIO_TEST_REPO",str(Path(__file__).resolve().parents[1])))
SOURCE = Path(os.environ.get("AUDIO_TEST_SOURCE",str(ROOT)))
def source_path(path):
    candidate=SOURCE/path
    return candidate if candidate.is_file() else ROOT/path
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))
from run_rollback_tests import resolve_clang
from test_catch_source import function


@unittest.skipUnless(os.name == "nt", "Windows production queue fixture")
class ReplayQueueSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        parent = Path(os.environ.get("AUDIO_TEST_OUTPUT",str(ROOT / "artifacts/local/audio-continuation-tests")))
        parent.mkdir(parents=True, exist_ok=True)
        cls.out = Path(tempfile.mkdtemp(prefix="run-", dir=parent))
        cls.environment = dict(os.environ, TMP=str(cls.out), TEMP=str(cls.out), TMPDIR=str(cls.out))
        # Capture once: both optimization levels exercise the same source snapshot.
        paths = ("runtime/replay_queue_probe.h", "runtime/hostrt.c", "runtime/hostrt.h",
                 "runtime/runtime.h", "runtime/nnsdk.c", "runtime/r1_ring.c",
                 "runtime/r1_state.c", "runtime/boot.c", "runtime/game_data.h",
                 "tests/replay_queue_source_fixture.c", "tests/test_replay_queue_source.py",
                 "runtime/replay_audio_probe.h","runtime/audio_continuation.h","tests/audio_continuation_cases.h")
        source_bytes = {path: source_path(path).read_bytes() for path in paths}
        cls.sources = {path: body.decode("utf-8").replace("\r\n", "\n") for path, body in source_bytes.items()}
        cls.report = {"started_utc": datetime.now(timezone.utc).isoformat(),
                      "scope": "game-free exact-source observer and wrapper tests; no runtime build or native trial",
                      "source_sha256": {p: hashlib.sha256(s).hexdigest() for p, s in source_bytes.items()},
                      "normalized_source_sha256": {p: hashlib.sha256(s.encode()).hexdigest()
                                                   for p, s in cls.sources.items()}, "steps": []}
        cls.write_report()
        host = cls.sources["runtime/hostrt.c"]
        replacements = {
            "/* QUEUE_OBSERVER_SOURCE */": cls.sources["runtime/replay_queue_probe.h"],
            "/* AUDIO_OBSERVER_SOURCE */": cls.sources["runtime/replay_audio_probe.h"],
            "/* AUDIO_CASES */": cls.sources["tests/audio_continuation_cases.h"],
            "/* DISPATCH_SOURCE */": "\n".join(function(host, name) for name in
                                                  ("call_indirect_body", "call_indirect")),
            "/* IMPORT_SOURCE */": "\n".join(function(host, name) for name in
                                                ("host_import_watch", "host_import_observed", "host_import", "host_import_binding", "host_import_real",
                                                 "host_audio_require_handlers","host_audio_import_binding")),
            "/* TICK_SOURCE */": function(cls.sources["runtime/nnsdk.c"], "os_GetSystemTick"),
            "/* H2_SOURCE */": function(cls.sources["runtime/r1_state.c"], "ra_kick2"),
        }
        fixture = cls.sources["tests/replay_queue_source_fixture.c"]
        for marker, body in replacements.items():
            if fixture.count(marker) != 1:
                raise AssertionError(f"missing/ambiguous fixture marker: {marker}")
            fixture = fixture.replace(marker, body)
        # Keep the public ABI headers in the captured snapshot, too.
        for path in ("runtime/hostrt.h", "runtime/runtime.h", "runtime/game_data.h","runtime/audio_continuation.h"):
            (cls.out / Path(path).name).write_text(cls.sources[path], encoding="utf-8")
        translation = cls.out / "queue.c"
        translation.write_text(fixture, encoding="utf-8")
        compiler = resolve_clang(None)
        version = cls.run_command("compiler", [compiler, "--version"])
        if version.returncode:
            raise AssertionError(version.stdout + version.stderr)
        cls.executables = []
        print(f"Queue source evidence: {cls.out}", flush=True)
        for optimization in ("O1", "O3"):
            executable = cls.out / (optimization + ".exe")
            result = cls.run_command(optimization + "-build", [compiler, "-std=c11", "-" + optimization,
                "-I" + str(cls.out), "-I" + str(ROOT / "runtime"), str(translation), "-o", str(executable)], 60)
            if result.returncode:
                raise AssertionError(result.stdout + result.stderr)
            cls.executables.append((optimization, executable))

    def test_audio_drain_races(self):
        for optimization,exe in self.executables:
            result=self.run_command(optimization+'-audio-drain-races',[str(exe),'audio-drain-races'])
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    @classmethod
    def write_report(cls):
        (cls.out / "results.json").write_text(json.dumps(cls.report, indent=2) + "\n", encoding="utf-8")

    @classmethod
    def run_command(cls, label, command, timeout=10, expected=0):
        step = {"name": label, "command": [str(x) for x in command], "expected_returncode": expected}
        cls.report["steps"].append(step)
        try:
            result = subprocess.run(command, cwd=ROOT, env=cls.environment, capture_output=True,
                                    text=True, errors="replace", timeout=timeout, check=False)
            step.update(returncode=result.returncode, stdout=result.stdout, stderr=result.stderr,
                        status="passed" if result.returncode == expected else "failed")
            (cls.out / (label + ".log")).write_text(result.stdout + result.stderr, encoding="utf-8")
            return result
        except (OSError, subprocess.TimeoutExpired) as exc:
            step["error"] = str(exc)
            raise
        finally:
            cls.write_report()

    @classmethod
    def tearDownClass(cls):
        cls.report["source_changed_during_tests"] = [p for p, s in cls.sources.items()
            if source_path(p).read_text(encoding="utf-8") != s]
        cls.report["commands_matched_expected_status"] = all(s.get("status") == "passed" for s in cls.report["steps"])
        cls.write_report()

    def case(self, name, code=0):
        for optimization, executable in self.executables:
            with self.subTest(optimization=optimization, case=name):
                result = self.run_command(optimization + "-" + name, [str(executable), name], expected=code)
                self.assertEqual(result.returncode, code, result.stdout + result.stderr)
                if code == 0:
                    self.assertIn("QUEUE_SOURCE_PASS " + name, result.stdout)

    def test_complete_original_and_replay_interval(self):
        self.case("complete")

    def test_callback_return_is_pending_until_checkpoint(self):
        self.case("pending-tick")

    def test_held_boundary_confirms_pending_commit(self):
        self.case("pending-held")

    def test_next_callback_confirms_prior_commit(self):
        self.case("pending-next")

    def test_missing_or_unexplained_consumer_commit_is_incomplete(self):
        self.case("pending-invalid")

    def test_generation_crossing_and_stale_native_token(self):
        self.case("stale")

    def test_inflight_tracking_precedes_capture118(self):
        self.case("inflight-start")

    def test_producer_and_consumer_overlap_is_permitted(self):
        self.case("producer-consumer-overlap")

    def test_overlapping_producers_and_foreign_identity_refuse(self):
        self.case("producer-overlap")

    def test_missing_signal_cannot_be_inferred_as_valid_rejection(self):
        self.case("missing-signal")

    def test_valid_full_branch_and_unsigned_cursor_wrap(self):
        self.case("rejected")

    def test_unqualified_inputs_are_not_read(self):
        self.case("unqualified-inputs")

    def test_signal_identity_and_duplicate_receipts(self):
        self.case("signal-identity")

    def test_callback_and_submission_identities(self):
        self.case("dispatch-identity")

    def test_callback_overlap_and_context_identity_refuse(self):
        self.case("consumer-identity")

    def test_foreign_consumer_cannot_confirm_or_replace_pending_operation(self):
        self.case("foreign-consumer")

    def test_unheld_boundaries_avoid_queue_memory_reads(self):
        self.case("unheld-boundaries")

    def test_overflow_and_unpublished_records_are_visible_without_waiting(self):
        self.case("bounded")
        self.case("drain-active")

    def test_payload_reads_refuse_unreadable_and_cross_region_memory(self):
        self.case("protected-read")

    def test_all_dispatch_families_preserve_context_and_last_error(self):
        self.case("dispatch-families")

    def test_producer_import_and_tick_preserve_context_and_last_error(self):
        self.case("preservation")

    def test_disabled_unset_and_explicit_zero(self):
        self.case("disabled")
        self.case("unset")

    def test_exact_h2_caller_preserves_error_across_actual_queue_logging(self):
        self.case("h2-drain")

    def test_configuration_refuses_unqualified_fixture(self):
        for name in ("bad-enable", "bad-build", "bad-sim", "bad-verify", "bad-net",
                     "bad-skip", "bad-lite", "bad-symbol"):
            self.case(name, 74)

    def test_audio_observer_cases(self):
        for name in ("off","null-zero","chain","masks","stale","generation","bad-frame","orphan","integrated","integrated-complete",
                     "bad-order","import-paths","bindings","unresolved","capacity","unready","wrap",
                     "wrong-actor","prewindow","prewindow-import","ticket-capacity","read-failure","sp-overflow",
                     "wrong-ctx","x8-mismatch","unrelated","overlap","gap-activity","missing-load-ready",
                     "wrong-boundary","stale-import-begin","stale-import-end","stale-producer","post-seal","main-bindings"):
            self.case("audio-"+name)
        for name in ("bad-option","needs-qp","watch-refusal"):
            self.case("audio-"+name,74)

    def test_boundary_and_boot_seams_are_before_release(self):
        ring = self.sources["runtime/r1_ring.c"]
        capture = function(ring, "r1_ring_capture")
        self.assertLess(capture.index("rg_meta_capture("), capture.index("qp_capture(frame)"))
        self.assertLess(capture.index("qp_capture(frame)"), capture.index("else unpark()"))
        load = function(ring, "r1_ring_load")
        self.assertLess(load.index("qp_load_begin(frame)"), load.index("rg_restore_config()"))
        self.assertLess(load.index("incomplete native continuation commit"), load.index("qp_load_ready(frame)"))
        self.assertLess(load.index("qp_load_ready(frame)"), load.index("unpark()", load.index("qp_load_ready(frame)")))
        boot = self.sources["runtime/boot.c"]
        self.assertLess(boot.index("display_init();"), boot.index("r1_queue_init();"))
        self.assertLess(boot.index("r1_queue_init();"), boot.index("CreateThread(NULL,", boot.index("display_init();")))
        kick = function(self.sources["runtime/r1_state.c"], "ra_kick2")
        self.assertLess(kick.index("ra_workers_release()"), kick.index("qp_drain()"))


if __name__ == "__main__":
    unittest.main()
