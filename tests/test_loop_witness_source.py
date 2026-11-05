"""Production-connected M1.14 witness; platform/ring/fighter values are synthetic."""
from pathlib import Path
import hashlib
import json
import os
import re
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))
from run_rollback_tests import resolve_clang
from test_catch_source import function
from bounded_trace_cmp import read_trace


def speculative_r11_hash():
    """Independent fixture oracle: BOT7 B at2..11, remote prediction neutral.

    Reconstruct full synthetic guest/RNG state, never use emitted hash, rows,
    folded RNG, or consumed-pad records as expected data.
    """
    mask = (1 << 64) - 1
    prime, basis = 0x100000001b3, 0xcbf29ce484222325
    state = basis
    for frame in range(1, 12):
        for buttons in (0 if frame == 1 else 2, 0):
            for value in (buttons, 0, 0, 0, 0):
                state = ((state ^ value) * prime) & mask
    data = b""
    for slot in (0, 1):
        data += struct.pack("<iiQffffQ", -1, (state & 255) + slot,
                            state ^ (slot << 48), 11.0,
                            float((state & 65535) + 100 * slot), -0.0, 1.0,
                            state ^ (slot << 40))
    for buttons in (2, 0):
        data += struct.pack("<QhhhhII", buttons, 0, 0, 0, 0, 1, 0)
    result = basis
    for value in data:
        result = ((result ^ value) * prime) & mask
    return f"{result:016x}"


def validate_event_envelope(events, late):
    """Same strict cardinality/type check for production output and mutations."""
    def scalar_types(value):
        if type(value) is dict:
            for key, item in value.items():
                assert type(key) is str
                scalar_types(item)
        elif type(value) is list:
            for item in value: scalar_types(item)
        else:
            assert type(value) in (int, str), "non-integer JSON counter"
    scalar_types(events)
    expected = {"BASE": 1, "PASS": 64 + late, "MISMATCH": late, "COMPLETE": late, "END": 1}
    counts = {kind: 0 for kind in expected}
    for event in events:
        assert event["kind"] in counts, "unknown witness kind"
        counts[event["kind"]] += 1
    assert counts == expected, "witness cardinality"
    assert events[0]["kind"] == "BASE" and events[-1]["kind"] == "END"
    end = events[-1]
    assert end["completions"] == counts["COMPLETE"]
    assert end["mismatches"] == counts["MISMATCH"]
    assert end["pass_records"] == counts["PASS"]


class EventEnvelopeTests(unittest.TestCase):
    def test_duplicate_completion_and_boolean_rejected(self):
        events = [{"kind": "BASE"}] + [{"kind": "PASS"} for _ in range(65)]
        events += [{"kind": "MISMATCH"}, {"kind": "COMPLETE", "token": 1, "diff": [0, 1, 2]},
                   {"kind": "END", "completions": 1, "mismatches": 1, "pass_records": 65}]
        validate_event_envelope(events, 1)
        duplicate = json.loads(json.dumps(events)); duplicate.insert(-1, dict(duplicate[-2]))
        with self.assertRaisesRegex(AssertionError, "cardinality"):
            validate_event_envelope(duplicate, 1)
        for index, key, value in ((-2, "token", True), (-2, "diff", [False,1,2]), (-1, "completions", True)):
            changed = json.loads(json.dumps(events)); changed[index][key] = value
            with self.assertRaisesRegex(AssertionError, "non-integer"):
                validate_event_envelope(changed, 1)


@unittest.skipUnless(os.name == "nt", "Windows source harness")
class LoopWitnessSourceTests(unittest.TestCase):
    def test_producers(self):
        paths = ("runtime/rb_net.c", "runtime/rb_rollback.c", "runtime/r1_ring.c",
                 "runtime/r1_state.c", "fighter_sdk/fighter_host.c", "runtime/rb.h",
                 "runtime/loop_witness.h", "runtime/rb_input.c", "runtime/bounded_trace.h",
                 "tests/loop_witness_source_fixture.c", "tests/test_loop_witness_source.py",
                 "tests/loop_verifier_source_fixture.c", "runtime/rb_timesync.c",
                 "tests/test_catch_source.py", "tools/run_rollback_tests.py", "tests/bounded_trace_cmp.py")
        raw = {p: (ROOT / p).read_bytes() for p in paths}
        s = {p: b.decode().replace("\r\n", "\n") for p, b in raw.items()}
        net, coord, ring, state, fight = [s[p] for p in paths[:5]]
        parent = ROOT / "artifacts/local/loop-witness-20261105"
        parent.mkdir(parents=True, exist_ok=True)
        out = Path(tempfile.mkdtemp(prefix="source-", dir=parent))
        print("Evidence:", out, flush=True)
        for p, b in raw.items():
            saved = out / "snapshot" / p
            saved.parent.mkdir(parents=True, exist_ok=True)
            saved.write_bytes(b)
        compiler = resolve_clang(None)
        manifest = {"sources": {p: hashlib.sha256(b).hexdigest() for p, b in raw.items()},
                    "compiler": compiler, "compiler_sha256": hashlib.sha256(Path(compiler).read_bytes()).hexdigest(),
                    "scope": "Exact production net/input/coordinator/raw-verifier/trace-row/boundary/accessor/frame-end/bridge. Synthetic ring pages, continuation/capture/load operations, OS holds, fighter values, poll and H2 cadence. No native game or gameplay equality claim."}
        (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

        def span(src, first, end):
            a = src.index(first)
            return src[a:src.index(end, a)]

        def bodies(src, names):
            return "\n".join(function(src, n) for n in names)

        net_src = "\n".join((
            span(net, "static int g_on =", "static LARGE_INTEGER g_qpf;"),
            span(net, "static void rbn_init_only_fatal", "/* ---------------------------------------------------------------- the match handshake"),
            span(net, "#define RQ_N ", "static void send_msg("),
            span(net, "static long long g_f0;", "/* ---------------------------------------------------------------- checksums:"),
            span(net, "static uint8_t g_lacc[", "/* ---------------------------------------------------------------- time sync: extra wait"),
            span(net, "static double g_tsbias", "/* (hs12) the end of a match"),
            bodies(net, ("rbn_match_number",)),
        ))
        # Original fixture's legacy-only frame-end scaffold is reused verbatim
        # except declarations/stand-ins replaced by the real trace and RA code.
        scaffold = span(s[paths[11]], "#define GA(x)", "/* FRAME_SOURCE */")
        scaffold = scaffold.replace("g_ra=1,g_phase,", "")  # declarations supplied by fixture
        # After the first replacement the original 'static int ' prefix remains.
        scaffold = scaffold.replace("g_save_ff,g_ra_nkind;static char g_ra_kind[4]={'R'};", "g_save_ff,g_ra_nkind;static char *g_ra_kind;")
        scaffold = scaffold.replace("static double g_t_poll,", "static double ")
        scaffold = scaffold.replace("static void ra_frame_end(double t) { (void)t;g_ra_nkind++; }", "/* real RA frame end below */")
        scaffold = scaffold.replace("static void fight_trace_boundary(char kind,int pending) { bt_boundary(&trace,trace_file,kind,pending); }", "")
        scaffold = scaffold.replace('static void fight_trace_fail(const char *s) { (void)s; }', "")
        scaffold += """
static long long g_ra_kcap,g_ra_fe;static int g_ra_kind_failed,g_ra_ready,g_ra_fe_kind;
static volatile LONG g_ra_lines;
static double g_ra_t_mark,g_rap[3][4],g_rapn[3],g_ra_fe_end;
static void ra_report(void) {}
"""
        scaffold += bodies(state, ("ra_kind_append", "ra_frame_end"))
        load = function(ring, "r1_ring_load")
        prepare = re.search(r"if\(g_rgs_on>0 && !rgv_prepare\(\)\) goto refused;", load)[0]
        before = re.search(r"if \(g_rgs_on > 0\) rgv_before\(si, r1_ring_newest\(\)\);", load)[0]
        self.assertLess(load.index(prepare), load.index(before))
        self.assertLess(load.index(before), load.index("cp_reserved_begin();"))
        # Verify actual native wrapper has the only drain after release.
        kick = function(state, "ra_kick2")
        self.assertLess(kick.index("ra_workers_release();"), kick.index("r1_loop_witness_drain();"))
        frame = function(state, "r1_frame_end")
        self.assertLess(frame.index("fight_trace_boundary("), frame.index("r1_loop_witness_trace();"))
        row = span(fight, "            struct { long long f; int k, st;", "            if (k == 0 && f % 300")
        fixture = s[paths[9]]
        replacements = {
            "/* CONSTANT */": re.search(r"^#define RG_MAXSLOT[^\n]+", ring, re.M)[0],
            "/* NET_SOURCE */": net_src,
            "/* RAW_SOURCE */": span(ring, "static int g_rgv_on =", "static int rgs_skip_now("),
            "/* COORD_GLOBALS */": span(coord, '#include "rb.h"', "static double rbg_pace_now"),
            "/* COORD_SOURCE */": bodies(coord, ("rbg_correction_pending", "rbg_correction_fatal", "rbg_rollback", "rbg_sched", "rbg_step_body", "rbg_pad")),
            "/* RING_SOURCE */": span(ring, "static int g_rgs_lastlite;", "static double g_rgs_pass_t0") + bodies(ring, ("rgs_wanted", "rgs_poll", "rgs_pad", "rgs_skip_now")),
            "/* PAD_SOURCE */": bodies(state[state.index("static PadRec g_pad["):], ("r1_poll", "r1_pad_id", "r1_pad")),
            "/* BRIDGE_SOURCE */": bodies(state, ("r1_loop_witness_held", "r1_loop_witness_drain", "r1_loop_witness_trace")),
            "/* FIGHT_SOURCE */": span(fight, "static uint64_t fh_fnv(", "static uint64_t fh_rng_base(") + bodies(fight, ("fight_trace_enabled", "fight_trace_fail", "fight_trace_boundary", "fight_trace_completed")),
            "/* ROW_SOURCE */": row,
            "/* FRAME_SCAFFOLD */": scaffold,
            "/* FRAME_SOURCE */": frame,
            "/* COMMON_PREPARE */": prepare,
            "/* COMMON_BEFORE */": before,
        }
        for marker, value in replacements.items():
            self.assertEqual(fixture.count(marker), 1, marker)
            fixture = fixture.replace(marker, value)
        cfile = out / "production.c"
        cfile.write_text(fixture)
        manifest["translation_sha256"] = hashlib.sha256(cfile.read_bytes()).hexdigest()
        (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        env = {k: v for k, v in os.environ.items() if not k.upper().startswith(("SSBU_", "RECOMP_"))}
        env.update(TMP=str(out), TEMP=str(out), TMPDIR=str(out))
        results = []
        good = [(0, late, disabled, repeat) for late in (0, 1) for disabled in (0, 1, 2) for repeat in (0, 1)]
        good += [(39, 1, 0, 0)]
        good += [(mode, late, 0, 0) for mode in (1, 65, 66) for late in (0, 1)]
        good += [(67, 1, 0, 0), (82, 1, 0, 0)]
        good += [(mode, 1, 0, 0) for mode in range(84,89)]
        bad = [(mode, 1, 0, 0) for mode in range(2, 65) if mode != 39]
        bad += [(mode, 1, 0, 0) for mode in range(68, 82)]
        bad += [(83, 1, 0, 0)]
        captures = {}
        for opt in ("-O1", "-O3"):
            exe = out / f"witness{opt}.exe"
            cmd = [compiler, "-std=c11", "-Werror=implicit-function-declaration", opt, "-I", str(out / "snapshot/runtime"), str(cfile), "-o", str(exe)]
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=60, env=env)
            (out / f"build{opt}.json").write_text(json.dumps({"command": cmd, "exit": p.returncode, "stdout": p.stdout, "stderr": p.stderr}, indent=2))
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
            for mode, late, disabled, repeat in good + bad:
                label = f"{opt}-m{mode}-l{late}-d{disabled}-r{repeat}"
                run = out / label
                run.mkdir()
                callenv = dict(env, SSBU_RB_NET=f"loop,{late}", SSBU_RB_NET_PLAYER="0", SSBU_RB_NET_DELAY="1", SSBU_RB_NET_BOT="7",
                               SSBU_RB_NET_LOOP_BOT2="19", SSBU_RB_NET_LOOP_LAT2="11,0", SSBU_RB_NET_KEEP="1", SSBU_RB_NET_RECAP="1",
                               SSBU_RB_NET_PACE="1", SSBU_RB_NET_LASTLITE="0", SSBU_RB_NET_DETAIL="1", SSBU_RB_NET_CKPADS="1",
                               SSBU_RB_LOOP_VERIFY="1", SSBU_RB_SIM_VERIFY="1", SSBU_TRACE_FRAMES="500", SSBU_RB_NET_LOG="net.txt")
                if not disabled:
                    callenv["SSBU_RB_LOOP_WITNESS"] = "1"
                elif disabled == 2:
                    callenv["SSBU_RB_LOOP_WITNESS"] = "0"
                if mode == 1:
                    callenv["SSBU_FIGHT_HASH_WORK"] = "10"
                if 75 <= mode <= 81:
                    changes = {75: {"SSBU_RB_LOOP_WITNESS": ""}, 76: {"SSBU_RB_LOOP_WITNESS": "2"},
                               77: {"SSBU_RB_LOOP_VERIFY": "0"}, 78: {"SSBU_RB_LOOP_VERIFY": ""},
                               79: {"SSBU_TRACE_FRAMES": "499"}, 80: {"SSBU_RB_NET_CKPADS": "0"},
                               81: {"SSBU_RB_NET_DETAIL": "0"}}
                    callenv.update(changes[mode])
                p = subprocess.run([str(exe), str(mode), str(late), str(disabled), str(repeat)], cwd=run, env=callenv,
                                   capture_output=True, text=True, timeout=20)
                log = p.stdout + p.stderr
                (run / "run.log").write_text(f"exit={p.returncode}\n" + log)
                results.append({"label": label, "exit": p.returncode})
                (out / "results.json").write_text(json.dumps(results, indent=2))
                if (mode, late, disabled, repeat) in bad:
                    self.assertEqual(p.returncode, 73, log)
                    self.assertIn("WITNESS_REJECT", log)
                    if mode == 83: self.assertIn("pad frame/order/read capacity", log)
                    self.assertNotIn("WITNESS_PASS", log)
                    # A close failure can occur after END bytes reached disk;
                    # process/fatal/identity gates remain mandatory with any seal.
                    if mode not in (42, 71):
                        self.assertFalse('"kind":"END"' in (run / "net.txt").read_text(), label)
                else:
                    self.assertEqual(p.returncode, 0, log)
                    self.assertIn("WITNESS_PASS", log)
                    data = (run / "net.txt").read_text()
                    if not disabled:
                        events = [json.loads(line[2:]) for line in data.splitlines() if line.startswith("o ")]
                        validate_event_envelope(events, late)
                        self.assertEqual([e["event"] for e in events], list(range(1, len(events) + 1)))
                        self.assertEqual(events[0]["kind"], "BASE")
                        self.assertEqual(events[-1]["kind"], "END")
                        self.assertEqual(events[-1]["final_records"], 499)
                        self.assertTrue(data.endswith("\n"))
                        self.assertEqual(json.loads(data.splitlines()[-1][2:])["kind"], "END")
                        finals = [line for line in data.splitlines() if line.startswith("f ")]
                        details = [line for line in data.splitlines() if line.startswith("d ")]
                        self.assertEqual([int(line.split()[1]) for line in finals], list(range(1, 500)))
                        self.assertEqual([int(line.split()[1]) for line in details], list(range(1, 500)))
                        passes = [e for e in events if e["kind"] == "PASS"]
                        self.assertEqual(len(passes), 64 + late)
                        self.assertEqual([p["seq"] for p in passes], list(range(1, 65 + late)))
                        self.assertTrue(all(p["hash_valid"] and {r["slot"] for r in p["fighters"]} == {0, 1} and all(r["e"] == -1 for r in p["fighters"]) for p in passes))
                        for record in passes:
                            for lane in record["lanes"]:
                                self.assertEqual(lane["n"], 16 if mode == 82 else (2 if mode == 65 else 1))
                            self.assertEqual(record["lanes"][0]["predicted_reads"], 0)
                            predicted = record["phase"] == "R" and (record["f"] <= 11 if late else record["f"] == 1)
                            self.assertEqual(record["lanes"][1]["predicted_reads"], record["lanes"][1]["n"] if predicted else 0)
                        if late:
                            complete = next(e for e in events if e["kind"] == "COMPLETE")
                            self.assertEqual({k: v for k, v in complete.items() if k != "event"}, {
                                "v": 1, "kind": "COMPLETE", "token": 1, "load": 10, "target": 11,
                                "mismatch": 11, "pass_seq": 12, "load_result": 1, "original_pages": 5 if mode == 88 else 3,
                                "replay_only_pages": 1 if mode == 88 else 0, "pages": 6 if mode == 88 else 3,
                                "diff": [0,0,0] if mode == 84 else [int(i==mode-85) for i in range(3)] if 85 <= mode <= 87 else [1,2,3] if mode == 88 else [1,1,1], "begins": 1,
                                "comparisons": 1, "completions": 1, "pre_capture_ok": 1, "post_capture_ok": 1,
                                "replayed": 1, "raw_pending": 0, "diagnostic": 1, "authoritative": 0})
                            self.assertLess(data.index('"kind":"COMPLETE"'), data.index("\nf 11 "))
                            mismatch = next(e for e in events if e["kind"] == "MISMATCH")
                            self.assertEqual((mismatch["f"], mismatch["lane"], mismatch["pass_seq"]), (11, 1, 11))
                            self.assertEqual(mismatch["predicted"], dict(buttons="0000000000000000", lx=0, ly=0, rx=0, ry=0))
                            self.assertEqual(mismatch["actual"], dict(buttons="0000000000000000", lx=32767, ly=0, rx=0, ry=0))
                        # Check serialized final values independently against the latest observed pass.
                        latest = {}
                        for line in data.splitlines():
                            if line.startswith("o "):
                                event = json.loads(line[2:])
                                if event["kind"] == "PASS": latest[event["f"]] = event
                            elif line.startswith("f "):
                                cells = line.split(); f = int(cells[1])
                                if f <= 64: self.assertEqual(cells, ["f", str(f), "h", latest[f]["h"]])
                            elif line.startswith("d "):
                                chunks = line.split(" | "); cells = chunks[0].split(); f = int(cells[1])
                                if f > 64: continue
                                record = latest[f]
                                expected = ["d", str(f)]
                                for q, lane in enumerate(record["lanes"]):
                                    pad = lane["value"]
                                    expected += [f"p{q+1}", format(int(pad["buttons"],16),"x")]
                                    expected += [str(pad[k]) for k in ("lx","ly","rx","ry")]
                                    expected += [f"n{lane['n']}"]
                                self.assertEqual(cells, expected)
                                self.assertEqual(len(chunks), 3)
                                for chunk, fighter in zip(chunks[1:], record["fighters"]):
                                    cells = chunk.split()
                                    self.assertEqual(cells[0], f"e{fighter['e']}")
                                    fields = dict(zip(cells[1::2], cells[2::2]))
                                    for key in ("st", "mot"): self.assertEqual(int(fields[key],16),int(fighter[key],16))
                                    for key, digits in (("mf",3),("x",4),("y",4),("dmg",3)):
                                        value = struct.unpack("<f", bytes.fromhex(fighter[key])[::-1])[0]
                                        self.assertEqual(fields[key], format(value, f".{digits}f"))
                                    rng = int(fields["rng"],16)
                                    self.assertEqual((rng ^ (rng >> 32)) & 0xffffffff, int(fighter["rng"],16))
                        reads = 16 if mode == 82 else (2 if mode == 65 else 1)
                        self.assertEqual({k:v for k,v in events[-1].items() if k != "event"}, {
                            "v":1,"kind":"END","diagnostic":1,"authoritative":0,
                            "pass_records":64+late,"mismatches":late,"completions":late,
                            "final_records":499,"detail_records":499,"final_first":1,"final_last":499,
                            "window_finals":64,"window_details":64,"trace_passes":500+late,"trace_real":500,
                            "rows0":500+late,"rows1":500+late,"pad_reads":2*(499+late)*reads,
                            "predicted_reads":(11 if late else 1)*reads,"padcheck_bad":0,
                            "local_submissions":499,"phase":0,"left":0,"pending_mismatch":0,
                            "verifier_pending":0,"write_ok":1})
                        trace = read_trace(run / "fight.txt")  # unchanged strict old parser/seal
                        for record in passes:
                            kind, rows = trace[record["trace_pass"] - 1]
                            self.assertEqual(kind, record["phase"])
                            for fighter in record["fighters"]:
                                cells = rows[fighter["slot"]].split()
                                fields = dict(zip(cells[::2], cells[1::2]))
                                for key in ("e", "st", "mot", "mf", "x", "y", "dmg", "rngcalls", "rng"):
                                    base = 10 if key in ("e", "rngcalls") else 16
                                    value = fighter[key] if isinstance(fighter[key], int) else int(fighter[key], base)
                                    self.assertEqual(value, int(fields[key], base), (label, key))
                                if mode == 1:
                                    self.assertEqual(fighter["work_on"], 1)
                                    self.assertEqual(fighter["work"], int(fields["w"]))
                    else:
                        self.assertNotIn("o {", data)
                    captures[opt, mode, late, disabled, repeat] = data
            # Named guard weakening: the same 17-read driver must expose removal
            # of the bound, and its sealed output must fail our read-count oracle.
            weakened = out / f"missing-read-cap{opt}.c"
            guard = " || g_wreads[player] >= 16"
            self.assertEqual(fixture.count(guard), 1)
            weakened.write_text(fixture.replace(guard, ""))
            mutant = out / f"missing-read-cap{opt}.exe"
            build = subprocess.run([compiler, "-std=c11", "-Werror=implicit-function-declaration", opt,
                "-I", str(out / "snapshot/runtime"), str(weakened), "-o", str(mutant)],
                capture_output=True, text=True, timeout=60, env=env)
            self.assertEqual(build.returncode, 0, build.stderr)
            run = out / f"missing-read-cap{opt}"; run.mkdir()
            mutant_env = dict(callenv, SSBU_RB_LOOP_WITNESS="1")
            result = subprocess.run([str(mutant), "83", "1", "0", "0"], cwd=run,
                env=mutant_env, capture_output=True, text=True, timeout=20)
            (run / "run.log").write_text(result.stdout + result.stderr)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            records = [json.loads(x[2:]) for x in (run / "net.txt").read_text().splitlines() if x.startswith("o ")]
            with self.assertRaises(AssertionError):
                for record in records:
                    if record["kind"] == "PASS":
                        for lane in record["lanes"]: self.assertLessEqual(lane["n"], 16)
            results.append({"label": f"missing-read-cap{opt}", "exit": result.returncode,
                            "weakening_detected": True})
            # Serializer mutations must be caught by independent output joins.
            for name, old, new in (
                ("speculative-hash", "(unsigned long long)hash, p->valid, g_hlines);", "(unsigned long long)(hash ^ ((frame == 11 && p->trace.kind == 'R') ? 1 : 0)), p->valid, g_hlines);"),
                ("complete-token", "(unsigned long long)token, from, to, mismatch, p->seq", "(unsigned long long)token + 1, from, to, mismatch, p->seq"),
                ("final-hash", "(unsigned long long)g_hash[f % HR]);", "(unsigned long long)(g_hash[f % HR] ^ 1));"),
                ("detail-pad", "g_upad[x][0].lx, g_upad[x][0].ly,", "g_upad[x][0].lx + 1, g_upad[x][0].ly,"),
            ):
                self.assertEqual(fixture.count(old), 1, name)
                source = out / f"{name}{opt}.c"; source.write_text(fixture.replace(old,new))
                exe_mut = out / f"{name}{opt}.exe"
                build = subprocess.run([compiler,"-std=c11","-Werror=implicit-function-declaration",opt,
                    "-I",str(out / "snapshot/runtime"),str(source),"-o",str(exe_mut)],
                    capture_output=True,text=True,timeout=60,env=env)
                self.assertEqual(build.returncode,0,build.stderr)
                case = out / f"{name}{opt}"; case.mkdir()
                result = subprocess.run([str(exe_mut),"0","1","0","0"],cwd=case,env=mutant_env,
                    capture_output=True,text=True,timeout=20)
                (case / "run.log").write_text(result.stdout+result.stderr)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                lines = (case / "net.txt").read_text().splitlines()
                records = [json.loads(x[2:]) for x in lines if x.startswith("o ")]
                first = next(e for e in records if e["kind"]=="PASS")
                with self.assertRaises(AssertionError):
                    if name=="speculative-hash": self.assertEqual(next(e for e in records if e["kind"]=="PASS" and e["f"]==11 and e["phase"]=="R")["h"], speculative_r11_hash())
                    elif name=="complete-token": self.assertEqual(next(e for e in records if e["kind"]=="COMPLETE")["token"],1)
                    elif name=="final-hash": self.assertEqual(next(x for x in lines if x.startswith("f 1 ")).split()[3],first["h"])
                    else: self.assertEqual(int(next(x for x in lines if x.startswith("d 1 ")).split()[4]),first["lanes"][0]["value"]["lx"])
                results.append({"label":f"{name}{opt}","exit":result.returncode,"weakening_detected":True})
            # Legacy and witness m/f/d bytes must agree, including all raw tails.
            for late in (0, 1):
                enabled = captures[opt, 0, late, 0, 0]
                legacy = captures[opt, 0, late, 1, 0]
                self.assertEqual(legacy, captures[opt, 0, late, 2, 0])
                self.assertEqual("\n".join(x for x in enabled.splitlines() if not x.startswith("o ")), legacy.strip())
            # Corrected latest PASS projection equals the independently executed
            # oracle in this synthetic state fixture; wrong R11 stays distinct.
            def projection(data):
                records = [json.loads(x[2:]) for x in data.splitlines() if x.startswith("o ")]
                return {r["f"]: r for r in records if r["kind"] == "PASS"}, records
            oracle, _ = projection(captures[opt, 0, 0, 0, 0])
            corrected, records = projection(captures[opt, 0, 1, 0, 0])
            for f in range(1, 65):
                self.assertEqual(oracle[f]["h"], corrected[f]["h"])
                for a, b in zip(oracle[f]["fighters"], corrected[f]["fighters"]):
                    self.assertEqual({k: v for k, v in a.items() if k != "ordinal"}, {k: v for k, v in b.items() if k != "ordinal"})
            wrong = next(r for r in records if r["kind"] == "PASS" and r["f"] == 11 and r["phase"] == "R")
            self.assertEqual(wrong["h"], speculative_r11_hash())
            self.assertNotEqual(wrong["h"], oracle[11]["h"])
            self.assertNotEqual(wrong["fighters"][0]["x"], oracle[11]["fighters"][0]["x"])
        self.assertEqual(manifest["sources"], {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in paths})
        (out / "SUMMARY.json").write_text(json.dumps({"status": "passed", "executions": len(results),
            "positive": len(good) * 2, "negative": len(bad) * 2, "weakening_rejections": 10, "optimizations": ["O1", "O3"],
            "sources_stable": True, "native_launched": False, "host_build": False,
            "resolved": False, "authoritative": 0, "independent_review": "pending"}, indent=2) + "\n")


if __name__ == "__main__":
    unittest.main()
