"""Exact raw verifier + coordinator/dispatch/frame-end; no native game/restore."""
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


@unittest.skipUnless(os.name == "nt", "Windows source harness")
class LoopVerifierSourceTests(unittest.TestCase):
    def test_transaction(self):
        paths = ("runtime/r1_ring.c", "runtime/rb_rollback.c", "runtime/r1_state.c",
                 "tests/loop_verifier_source_fixture.c", "tests/test_loop_verifier_source.py")
        sources = {p: (ROOT / p).read_text() for p in paths}
        ring, coord, state = (sources[p] for p in paths[:3])
        raw = ring[ring.index("static int g_rgv_on ="):ring.index("static int rgs_skip_now(")]
        globals_ = coord[:coord.index("static double rbg_pace_now")]
        names = ("rbg_correction_pending", "rbg_correction_fatal", "rbg_rollback", "rbg_sched",
                 "rbg_step_body", "rbg_terminal", "rbg_fight_off")
        bodies = "\n".join(function(coord, n) for n in names)
        load = function(ring, "r1_ring_load")
        prepare = re.search(r"if\(g_rgs_on>0 && !rgv_prepare\(\)\) goto refused;", load)[0]
        before = re.search(r"if \(g_rgs_on > 0\) rgv_before\(si, r1_ring_newest\(\)\);", load)[0]
        self.assertLess(load.index(prepare), load.index(before))
        self.assertLess(load.index(before), load.index("cp_reserved_begin();"))
        template = sources[paths[3]]
        for marker, value in {
            "/* CONSTANT */": re.search(r"^#define RG_MAXSLOT[^\n]+", ring, re.M)[0],
            "/* RAW_SOURCE */": raw,
            "/* COORD_GLOBALS */": globals_,
            "/* COORD_SOURCE */": bodies,
            "/* DISPATCH_SOURCE */": function(ring, "rgs_step") + "\n" + function(ring, "r1_ring_release"),
            "/* FRAME_SOURCE */": function(state, "r1_frame_end"),
            "/* COMMON_PREPARE */": prepare,
            "/* COMMON_BEFORE */": before,
        }.items():
            self.assertEqual(template.count(marker), 1, marker)
            template = template.replace(marker, value)
        parent = ROOT / "artifacts/local/loop-verifier-implementation-20261105"
        parent.mkdir(parents=True, exist_ok=True)
        out = Path(tempfile.mkdtemp(prefix="source-", dir=parent))
        print("Evidence:", out, flush=True)
        compiler = resolve_clang(None)
        (out / "manifest.json").write_text(json.dumps({
            "sources": {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in paths},
            "compiler": compiler, "compiler_sha256": hashlib.sha256(Path(compiler).read_bytes()).hexdigest(),
            "functions": list(names) + ["rgs_step", "r1_ring_release", "r1_frame_end", "entire raw verifier span"],
            "scope": "Exact bodies; synthetic ring/capture/load/hash/finalizer/trace boundaries. Common-load reservation/arm lines exact; remaining native load not executed.",
        }, indent=2) + "\n")
        env = {k: v for k, v in os.environ.items() if not k.upper().startswith(("SSBU_", "RECOMP_"))}
        env.update(TMP=str(out), TEMP=str(out), TMPDIR=str(out))
        variants = [("production", template, range(70), None)]
        for name, old, new, modes, reason in (
            ("missing-completion", "if (rgv_loop_on() && !rgv_loop_after_pass(g_rbg_loop_token, i, capture_ok, g_rgs_left))",
             "if (0)", [0], "LOOP_FATAL_ORACLE"),
            ("clear-target-only", "    rgv_after();", "    g_rgv_target = -1;", [0], "LOOP_FATAL_ORACLE"),
            ("missing-capture-check", "g_rbg_loop_capture_ok != 1", "0", [9], "LOOP_ASSERT REQUIRED_REFUSAL"),
            ("unbound-newest", "r1_ring_newest() != to)", "0)", [10], "LOOP_FATAL_ORACLE"),
            ("missing-left-check", "left != 1 || capture_ok != 1", "capture_ok != 1", [27], "LOOP_ASSERT REQUIRED_REFUSAL"),
            ("skip-comparison", "    rgv_after();", "    g_rgv_runs++; g_rgv_target=-1; g_rgv_pages+=g_rgv_n;", [0], "LOOP_FATAL_ORACLE"),
            ("hide-difference", "g_rgv_loop.diff[k] = g_rgv_diff[k] - diff[k]", "g_rgv_loop.diff[k] = 0", [0], "LOOP_ASSERT RAW_DIFFERENCE_RETAINED"),
            ("hide-other-regions", "    g_rgv_loop.comparisons = 1;", "    g_rgv_loop.diff[1]=g_rgv_loop.diff[2]=0; g_rgv_loop.comparisons = 1;", [67,68,69], "LOOP_ASSERT RAW_DIFFERENCE_RETAINED"),
            ("drop-trace-pending", " || rgv_loop_pending());", ");", [31], "LOOP_ASSERT TRACE_PENDING_LOOP"),
        ):
            self.assertEqual(template.count(old), 1, name)
            variants.append((name, template.replace(old, new), modes, reason))
        results = []
        for name, source, modes, reason in variants:
            cfile = out / (name + ".c")
            cfile.write_text(source)
            for opt in ("-O1", "-O3"):
                exe = out / (name + opt + ".exe")
                command = [compiler, "-std=c11", opt, "-I", str(ROOT / "runtime"), str(cfile), "-o", str(exe)]
                p = subprocess.run(command, capture_output=True, text=True, timeout=60, env=env)
                (out / (exe.stem + "-build.log")).write_text(p.stdout + p.stderr)
                (out / (exe.stem + "-command.json")).write_text(json.dumps(command))
                self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
                for mode in modes:
                    command = [str(exe), str(mode)] + (["fault"] if reason == "LOOP_FATAL_ORACLE" else [])
                    p = subprocess.run(command, capture_output=True, text=True, timeout=20, env=env)
                    log = p.stdout + p.stderr
                    (out / f"{exe.stem}-{mode}.log").write_text(f"exit={p.returncode}\n" + log)
                    results.append({"variant": name, "opt": opt, "mode": mode, "exit": p.returncode})
                    (out / "results.json").write_text(json.dumps(results, indent=2))
                    if reason:
                        self.assertIn(reason, log)
                        self.assertIn(p.returncode, (42, 73), log)
                        self.assertNotIn("LOOP_PASS", log)
                    elif (6 <= mode <= 39 and mode != 31) or mode in (43, 45, 47, 48, 49) or (54 <= mode <= 66 and mode not in (63, 65)):
                        self.assertEqual(p.returncode, 73, log)
                        self.assertIn(f"LOOP_FATAL_ORACLE {mode} ", log)
                    else:
                        self.assertEqual(p.returncode, 0, log)
                        self.assertIn("LOOP_PASS", log)


if __name__ == "__main__":
    unittest.main()
