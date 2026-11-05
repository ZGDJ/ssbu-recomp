"""M1.14: exact loop/input/coordinator bodies, with a synthetic H2 and ring.

This proves the input/capture schedule with the opt-in verifier disabled,
not native restoration, raw verifier completion or gameplay.
The unchanged M7.3 fixture owns refusal/fatal coverage.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))
from run_rollback_tests import resolve_clang
from test_catch_source import function


@unittest.skipUnless(os.name == "nt", "Windows source harness")
class LoopCorrectionSourceTests(unittest.TestCase):
    def test_proposed_schedule(self):
        parent = ROOT / "artifacts/local/loop-endpoint-schedule-20261105"
        parent.mkdir(parents=True, exist_ok=True)
        out = Path(tempfile.mkdtemp(prefix="run-", dir=parent))
        print(f"Evidence: {out}", flush=True)
        paths = ("runtime/rb_net.c", "runtime/rb_rollback.c", "runtime/r1_ring.c",
                 "runtime/r1_state.c", "runtime/rb_input.c", "runtime/rb.h",
                 "runtime/rb_timesync.c", "tests/test_loop_correction_source.py",
                 "tests/test_catch_source.py", "tools/run_rollback_tests.py",
                 "runtime/loop_witness.h", "tests/loop_correction_source_fixture.c")
        raw_sources = {p: (ROOT / p).read_bytes() for p in paths}
        sources = {p: data.decode("utf-8").replace("\r\n", "\n") for p, data in raw_sources.items()}
        # Compile the saved include bodies, so a concurrent runtime edit cannot
        # silently mix new rb_input/rb.h bytes with an older coordinator slice.
        for p, data in raw_sources.items():
            saved = out / "source-snapshot" / p
            saved.parent.mkdir(parents=True, exist_ok=True)
            saved.write_bytes(data)
        source_hashes = {p: hashlib.sha256(data).hexdigest() for p, data in raw_sources.items()}
        hashes, comparisons, policy_runs, steps = {}, [], {}, []
        results = {"status": "failed_or_incomplete", "comparisons": comparisons,
                   "resolved": False, "authoritative": 0, "native_launched": False,
                   "gameplay_qualified": False, "verifier_completion_tested": False}

        def save_attempt():
            after = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in paths}
            results["source_stable"] = after == source_hashes
            results["changed_sources_during_attempt"] = [p for p in paths if after[p] != source_hashes[p]]
            if not results["source_stable"]:
                results["status"] = "failed_source_mutation"
            (out / "read-identity-after.json").write_text(json.dumps(after, indent=2) + "\n")
            (out / "hashes.json").write_text(json.dumps(hashes, indent=2) + "\n")
            (out / "results.json").write_text(json.dumps(results, indent=2) + "\n")
            self.assertTrue(results["source_stable"], results["changed_sources_during_attempt"])

        self.addCleanup(save_attempt)
        (out / "read-identity.json").write_text(json.dumps(source_hashes, indent=2) + "\n")
        ring, state = (sources[p] for p in paths[2:4])
        extracted = []

        def record(path, label, block):
            source = sources[path]
            start = source.index(block)
            extracted.append({"path": path, "label": label,
                              "first_line": source.count("\n", 0, start) + 1,
                              "lines": block.count("\n") + 1,
                              "sha256_utf8_lf": hashlib.sha256(block.encode()).hexdigest()})
            return block

        def span(path, first, end):
            source = sources[path]
            start = source.index(first)
            return record(path, first, source[start:source.index(end, start)])

        def bodies(path, names, source=None):
            return "\n".join(record(path, name, function(source or sources[path], name))
                             for name in names)

        # Contiguous slices retain typed-return functions and their static storage
        # verbatim; function() is the existing exact-body fixture extractor.
        net_source = "\n".join((
            span(paths[0], "static int g_on =", "static LARGE_INTEGER g_qpf;"),
            span(paths[0], "static void rbn_init_only_fatal", "/* ---------------------------------------------------------------- the match handshake"),
            span(paths[0], "#define RQ_N ", "static void send_msg("),
            span(paths[0], "static long long g_f0;", "/* ---------------------------------------------------------------- checksums:"),
            span(paths[0], "static uint8_t g_lacc[", "/* ---------------------------------------------------------------- time sync: extra wait"),
            span(paths[0], "static double g_tsbias", "/* (hs12) the end of a match"),
            bodies(paths[0], ("rbn_match_number",)),
        ))
        coord_globals = span(paths[1], '#include "rb.h"', "static double rbg_pace_now")
        coord_body = bodies(paths[1], ("rbg_correction_pending", "rbg_correction_fatal",
                                      "rbg_rollback", "rbg_sched", "rbg_step_body", "rbg_pad"))
        ring_source = "\n".join((
            span(paths[2], "static int g_rgs_lastlite;", "static double g_rgs_pass_t0"),
            bodies(paths[2], ("rgs_wanted", "rgs_skip_now", "rgs_poll", "rgs_pad")),
        ))
        # Do not select the no-runtime stubs at the head of r1_state.c.
        state_source = bodies(paths[3], ("r1_poll", "r1_pad_id", "r1_pad"),
                              state[state.index("static PadRec g_pad["):])
        template = sources[paths[-1]]
        replacements = {
            "/* CONSTANT */": record(paths[2], "RG_MAXSLOT", re.search(r"^#define RG_MAXSLOT[^\n]+", ring, re.M)[0]),
            "/* NET_SOURCE */": net_source,
            "/* COORD_GLOBALS */": coord_globals,
            "/* COORD_SOURCE */": coord_body,
            "/* RING_SOURCE */": ring_source,
            "/* STATE_SOURCE */": state_source,
        }
        for marker, block in replacements.items():
            self.assertEqual(template.count(marker), 1, marker)
            template = template.replace(marker, block)

        policies = {
            "default": {},
            "keep1-recap0": {"SSBU_RB_NET_KEEP": "1", "SSBU_RB_NET_RECAP": "0"},
            "keep1-recap1": {"SSBU_RB_NET_KEEP": "1", "SSBU_RB_NET_RECAP": "1"},
        }
        manifest = {
            "started_utc": datetime.now(timezone.utc).isoformat(),
            "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "sources": {p: {"sha256": source_hashes[p],
                            "sha256_utf8_lf": hashlib.sha256(s.encode()).hexdigest()}
                        for p, s in sources.items()},
            "extracted": extracted,
            "included_whole": ["runtime/rb_input.c", "runtime/rb.h", "runtime/rb_timesync.c"],
            "schedule": {"local_bot": 7, "remote_bot": 19, "delay": 1,
                         "oracle_latency": 0, "late_latency": 1, "switch": [11, 0],
                         "base": 0, "interval": [1, 64], "skip": 0, "lite": 0,
                         "lastlite": 0, "pace": 1, "policies": policies,
                         "default_effective": {"keep": 2, "recap": 5}},
            "limits": [
                "Synthetic one-poll/two-lane H2 driver calls exact rbg_step_body; no native hooks, nnhid fill_pad, rgs_step or host-stack wrapper.",
                "Bounded synthetic ring copies only Ctx boundary/witness; actual rb_input arrays are compared across pre-capture/load/replay/recapture. g_rg_need is asserted at the capture boundary; production eviction/page/continuation restore and exclusion are not tested.",
                "Virtual clock/wait and worker holds; skip/lite zero are fixture-initialized, not ra_init/hook installation. Actual NET/DELAY/BOT/BOT2/LAT2/KEEP/RECAP/PACE/LASTLITE parsing runs.",
                "Agreed nonterminal loop only; handshake/transport paths trap if reached. No private game, audio, effects, native admission or verifier completion.",
                "Witness recurrence is a synthetic consumption/restore check, not fighter state or a gameplay oracle. Historical failed gates remain resolved=false, authoritative=0.",
                "Coordinator drain/take/local-submit calls are instrumented by macros that call the unmodified production bodies, record events and optionally repeat drains; replay resubmission is rejected.",
                "KEEP1 worker-held acknowledgement is synthetic. Capture/load events describe successful fixture storage, not raw verifier targets/comparison coverage/completion or native capture success.",
                "SSBU_RB_LOOP_VERIFY is absent. rgv_loop_on returns 0, rgv_loop_load_result returns its disabled-mode 1; install/after_pass/require_idle/debug_writer_probe_end trap. All extracted production call sites remain; the opt-in lifecycle belongs to its separate fixture.",
            ],
        }
        (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        env = {k: v for k, v in os.environ.items() if not k.upper().startswith(("SSBU_", "RECOMP_"))}
        env.update(TMP=str(out), TEMP=str(out), TMPDIR=str(out))
        compiler = resolve_clang(None)
        manifest["compiler"] = {"path": compiler, "sha256": hashlib.sha256(Path(compiler).read_bytes()).hexdigest()}
        (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        def run(label, command, environment):
            step = {"label": label, "command": command,
                    "configuration": {k: v for k, v in environment.items() if k.startswith("SSBU_")}}
            steps.append(step)
            try:
                result = subprocess.run(command, cwd=ROOT, env=environment, capture_output=True,
                                        text=True, timeout=60)
                step["returncode"] = result.returncode
                (out / (label + ".log")).write_text(result.stdout + result.stderr)
            except (OSError, subprocess.TimeoutExpired) as error:
                step["error"] = repr(error)
                (out / (label + ".log")).write_text(repr(error) + "\n" +
                    str(getattr(error, "stdout", "")) + str(getattr(error, "stderr", "")))
                raise
            finally:
                (out / "commands-results.json").write_text(json.dumps(steps, indent=2) + "\n")
            return result

        version = run("compiler", [compiler, "--version"], env)
        self.assertEqual(version.returncode, 0, version.stderr)
        variants = [("production", template, None, tuple(policies))]
        # Each weakening must be detected by a named fixture invariant, rather
        # than counting a compiler error/crash/timeout as successful falsification.
        for name, old, new, failure, applicable in (
            ("missing-delivery", "rb_input_remote_put(g_remote, (int)f, loop_remote_pad(f));",
             "if (f != 11) rb_input_remote_put(g_remote, (int)f, loop_remote_pad(f));", "DELIVERY_HORIZON", tuple(policies)),
            ("wrong-delivery", "bot_pad(loop_bot2(), f - g_delay)",
             "bot_pad(loop_bot2(), f)", "DELIVERY_VALUE", tuple(policies)),
            ("wrong-boundary", "long long target = m - 1, best = -1;",
             "long long target = m - 2, best = -1;", "LOAD_BOUNDARY", tuple(policies)),
            ("missing-replay", "g_rgs_next = best + 1; g_ra_phase = 2;",
             "g_rgs_next = best + 1; g_ra_phase = 0;", "REPLAY_SCHEDULE", tuple(policies)),
            ("wrong-replay", "g_rgs_next = best + 1; g_ra_phase = 2;",
             "g_rgs_next = best + 2; g_ra_phase = 2;", "REPLAY_SCHEDULE", tuple(policies)),
            ("rewound-history", "/* HISTORY_FAULT */",
             "rb_input_reset(2, 0, 1);", "HISTORY_SURVIVAL", tuple(policies)),
            ("missing-lane", "rbg_pad(id, b, lx, ly, rx, ry); }",
             "(void)id; }", "CONSUMED_LANES", tuple(policies)),
            ("missing-pre-capture", "if (g_rbg_keep == 1) { g_rg_keep = 1;",
             "if (0) { g_rg_keep = 1;", "PRELOAD_CAPTURE11", ("keep1-recap0", "keep1-recap1")),
            ("missing-pending-publication", "            m = rbg_correction_pending(m);",
             "            (void)0;", "PENDING_CAPTURE_HORIZON", ("keep1-recap0", "keep1-recap1")),
            ("wrong-retention-horizon", "if (g_rbg_pend > 0 && g_rbg_pend - 1 < g_rg_need)",
             "if (0)", "PENDING_CAPTURE_HORIZON", ("keep1-recap0", "keep1-recap1")),
            ("missing-endpoint-recapture", "if (want) { double tc = now_ms();",
             "if (want && i != 11) { double tc = now_ms();", "ENDPOINT_RECAPTURE11", tuple(policies)),
            ("replay-resubmission", "if (id == 0 && g_ra_phase != 2 && f > g_rbg_lastlocal)",
             "if (id == 0)", "NO_REPLAY_RESUBMISSION", tuple(policies)),
        ):
            self.assertEqual(template.count(old), 1, name)
            variants.append((name, template.replace(old, new), failure, applicable))

        for name, translation, failure, applicable in variants:
            cfile = out / (name + ".c")
            cfile.write_text(translation)
            hashes[cfile.name] = hashlib.sha256(cfile.read_bytes()).hexdigest()
            builds = []
            for opt in ("-O1", "-O3"):
                label = name + opt
                exe = out / (label + ".exe")
                cmd = [compiler, "-std=c11", opt, "-I", str(out / "source-snapshot/runtime"),
                       str(cfile), "-o", str(exe)]
                result = run(label + "-build", cmd, env)
                builds.append((opt, label, exe, result))
            # Save both optimization attempts even when a new production API is
            # absent from the fixture. A compiler failure is never a rejected mutant.
            for opt, label, exe, result in builds:
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                hashes[exe.name] = hashlib.sha256(exe.read_bytes()).hexdigest()
                for policy in applicable:
                    for repeated in ((0, 1) if failure is None else (0,)):
                        arms = {}
                        for arm in (("oracle", "late") if failure is None else ("late",)):
                            case = f"{label}-{policy}-{arm}-repeat{repeated}"
                            configured = dict(env, SSBU_RB_NET="loop,0" if arm == "oracle" else "loop,1",
                                              SSBU_RB_NET_PLAYER="0", SSBU_RB_NET_DELAY="1", SSBU_RB_NET_BOT="7",
                                              SSBU_RB_NET_LOOP_BOT2="19", SSBU_RB_NET_LOOP_LAT2="11,0",
                                              SSBU_RB_NET_PACE="1", SSBU_RB_NET_LASTLITE="0",
                                              SSBU_RB_SIM_SKIP="0", SSBU_RB_SIM_LITE="0", SSBU_RB_NET_DETAIL="1")
                            configured.update(policies[policy])
                            result = run(case, [str(exe), arm, str(repeated), policy], configured)
                            log = result.stdout + result.stderr
                            if failure:
                                self.assertEqual(result.returncode, 42, log)
                                self.assertIn("LOOP_ASSERT " + failure, log)
                                self.assertNotIn("LOOP_PASS", log)
                                steps[-1]["rejected_by"] = failure
                                continue
                            self.assertEqual(result.returncode, 0, log)
                            self.assertIn("LOOP_PASS", log)
                            rows = [json.loads(line) for line in result.stdout.splitlines() if line.startswith("{")]
                            events = [json.loads(line.removeprefix("LOOP_EVENT "))
                                      for line in result.stderr.splitlines() if line.startswith("LOOP_EVENT ")]
                            policy_runs[opt, policy, repeated, arm] = (rows, events)
                            arms[arm] = rows
                            capture = [e for e in events if e["kind"] == "capture"]
                            load = [e for e in events if e["kind"] == "load"]
                            keep1 = policy != "default"
                            expected_frames = list(range(11)) + ([11] if arm == "late" and keep1 else []) + list(range(11, 65))
                            self.assertEqual([e["frame"] for e in capture], expected_frames)
                            self.assertEqual(len(load), int(arm == "late"))
                            if arm == "late":
                                self.assertEqual(load[0], {"kind": "load", "frame": 10,
                                    "newest_before": 11 if keep1 else 10, "pending": 11,
                                    "actual11_lx": 32767, "history_equal": 1})
                                endpoint = [e for e in capture if e["frame"] == 11 and e["phase"] == 2]
                                self.assertEqual(len(endpoint), 1)
                                self.assertEqual((endpoint[0]["pending"], endpoint[0]["need"], endpoint[0]["confirmed"]), (0, 12, 12))
                                self.assertLess(events.index(load[0]), events.index(endpoint[0]))
                                corrected = [r for r in rows if r["replay"]]
                                self.assertEqual(endpoint[0]["witness"], corrected[0]["witness"])
                                if keep1:
                                    pre = [e for e in capture if e["frame"] == 11 and e["phase"] == 0]
                                    self.assertEqual(len(pre), 1)
                                    self.assertEqual((pre[0]["pending"], pre[0]["need"], pre[0]["confirmed"], pre[0]["kept"]), (11, 10, 12, 1))
                                    self.assertLess(events.index(pre[0]), events.index(load[0]))
                                    speculative = [r for r in rows if r["frame"] == 11 and not r["replay"]]
                                    self.assertEqual(pre[0]["witness"], speculative[0]["witness"])
                        if failure is None:
                            oracle, late = (arms[arm] for arm in ("oracle", "late"))
                            self.assertEqual(len(oracle), 64)
                            self.assertEqual(len(late), 65)
                            wrong = [row for row in late if row["frame"] == 11 and not row["replay"]]
                            replay = [row for row in late if row["replay"]]
                            self.assertEqual([row["frame"] for row in replay], [11])
                            self.assertNotEqual(wrong[0]["witness"], replay[0]["witness"])
                            final = {row["frame"]: row for row in late}
                            for expected in oracle:
                                actual = final[expected["frame"]]
                                for field in ("p1", "p2", "witness"):
                                    self.assertEqual(actual[field], expected[field], (field, expected, actual))
                            comparisons.append({"optimization": opt, "policy": policy, "repeated_drains": repeated,
                                                "final_frames_equal": 64, "speculative_difference": 11,
                                                "mismatch": 11, "load": 10, "replay": [11],
                                                "preload_capture11": int(policy != "default"),
                                                "endpoint_recapture11": 1, "actual_history_preserved": True})
        for opt in ("-O1", "-O3"):
            for repeated in (0, 1):
                for arm in ("oracle", "late"):
                    self.assertEqual(policy_runs[opt, "keep1-recap0", repeated, arm],
                                     policy_runs[opt, "keep1-recap1", repeated, arm])
        results.update(status="source_schedule_pass", positive_runs=len(policy_runs),
                       weakenings_rejected_each_optimization=len(variants) - 1,
                       weakening_runs=sum(1 for step in steps if "rejected_by" in step),
                       recap0_recap1_depth_one_schedule_equal=True)
        (out / "commands-results.json").write_text(json.dumps(steps, indent=2) + "\n")


if __name__ == "__main__":
    unittest.main()
