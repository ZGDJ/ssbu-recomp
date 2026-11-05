"""Disposable exact writer-grammar fixtures and independent hostile mutations.

No ignored artifacts, compiler, game, admission, or capacity collection required.
This Python writer reproduces production formatting/packing, not the runtime
coordinator. The separately retained C-produced witnesses are checked offline in
the implementation evidence. A tiny schema sentinel replaces only its digest in
packet tests; the parser, mapping, joins, counts and verdict are never mocked.
"""
from copy import deepcopy
from contextlib import redirect_stdout
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("loop_analyzer", ROOT / "tools/analyze_loop_correction.py")
A = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(A)
SCHEMA = b"self-contained writer grammar sentinel for analyzer unit tests\n"
SCHEMA_HASH = hashlib.sha256(SCHEMA).hexdigest()


def neutral():
    return dict(buttons="0000000000000000", lx=0, ly=0, rx=0, ry=0)


def bot(seed, frame):
    """Independent predeclared BOT7/BOT19 tape, delay1. No log-derived values."""
    def mix(h):
        h = ((h ^ (h >> 16)) * 0x7feb352d) & 0xffffffff
        h = ((h ^ (h >> 15)) * 0x846ca68b) & 0xffffffff
        return h ^ (h >> 16)
    result = neutral()
    if frame == 1:
        return result
    f, start, seg = frame - 1, 1, 0
    while True:
        h = mix(((seed * 0x9e3779b9) ^ (seg * 0x85ebca6b)) & 0xffffffff)
        if f < start + 6 + h % 24:
            break
        start += 6 + h % 24
        seg += 1
    act, direction = (h >> 8) % 10, 1 if seg & 1 else -1
    if act in (2, 3, 7):
        result["lx"] = direction * 32767
    if act in (4, 7) or (act == 9 and (f - start) % 8 < 4):
        result["buttons"] = "0000000000000001"
    if act == 5:
        result["buttons"] = "0000000000000002"
    if act == 6 and (f - start) % 16 < 3:
        result["buttons"] = "0000000000000004"
    if act == 8:
        result["ly"] = -32767
    return result


def recipe(schema_hash=SCHEMA_HASH, *, reads=1, work=0, base=1):
    return dict(v=1, schema_sha256=schema_hash, interval=[1, 64], trace_target=500,
                mapping=dict(trace_base=base, fight_frame=0, first_fight_frame=0, poll_base=0),
                config=dict(A.CONFIG), reads_per_lane=[reads, reads], work_on=work,
                effect_fields=["st", "mot", "mf", "x", "y", "dmg"], require_effect=1,
                expected_inputs=[[bot(7, f), bot(19, f)] for f in range(1, 501 - base)],
                files={arm: dict(net="net.txt", trace="fight.txt", logs=["run.log"])
                       for arm in ("oracle", "correction")})


def fbits(value):
    return struct.unpack("<I", struct.pack("<f", value))[0]


def as_float(bits):
    return struct.unpack("<f", struct.pack("<I", bits))[0]


def hash_bytes(raw):
    value = 0xcbf29ce484222325
    for byte in raw:
        value = ((value ^ byte) * 0x100000001b3) % (1 << 64)
    return f"{value:016x}"


def row_at(f, ordinal, slot, *, wrong=False, effect=True, work=0, changes=None):
    result = dict(slot=slot, ordinal=ordinal, e=-1, st=0x8d + slot,
                  mot=0x100000002 + slot, mf=fbits(float(f)), x=fbits(f / 4 + slot),
                  y=0x80000000, dmg=fbits(1.0), rngcalls=f + slot,
                  rng64=0x1100000022 + f * 65537 + slot, work_on=work, work=-f if work else 0)
    if wrong and effect:
        result["x"] = fbits(99.0 + slot)
    if changes:
        result.update(changes)
    result["rng"] = (result["rng64"] ^ (result["rng64"] >> 32)) & 0xffffffff
    return result


def witness(row):
    result = {k: v for k, v in row.items() if k != "rng64"}
    for key in ("st", "mot", "mf", "x", "y", "dmg", "rng"):
        result[key] = f"{result[key]:0{16 if key == 'mot' else 8}x}"
    return result


def raw_row(row):
    w = f" w {row['work']}" if row["work_on"] else ""
    return (f"F {row['ordinal']} e {row['e']} st {row['st']:x} mot {row['mot']:x} mf {row['mf']:08x} "
            f"x {row['x']:08x} y {row['y']:08x} dmg {row['dmg']:08x} rngcalls {row['rngcalls']} "
            f"rng {row['rng']:08x} H 123456789abcdef0  "
            f"({as_float(row['x']):.3f} {as_float(row['y']):.3f} frame {as_float(row['mf']):.2f} "
            f"{as_float(row['dmg']):.2f}%){w} slot {row['slot']}")


def detail_row(row):
    return (f"e{row['e']} st {row['st']:x} mot {row['mot']:x} mf {as_float(row['mf']):.3f} "
            f"x {as_float(row['x']):.4f} y {as_float(row['y']):.4f} dmg {as_float(row['dmg']):.3f} rng {row['rng64']:016x}")


def pad_text(value, lane, n):
    return (f"p{lane} {int(value['buttons'], 16):x} {value['lx']} {value['ly']} "
            f"{value['rx']} {value['ry']} n{n}")


def final_hash(rows, pads):
    # Explicit byte order/offsets independent of analyzer.hash_final.
    raw = b""
    for row in rows:
        raw += row["e"].to_bytes(4, "little", signed=True)
        for field, width in (("st", 4), ("mot", 8), ("mf", 4), ("x", 4), ("y", 4), ("dmg", 4), ("rng64", 8)):
            raw += row[field].to_bytes(width, "little")
    for value in pads:
        raw += int(value["buttons"], 16).to_bytes(8, "little")
        for field in ("lx", "ly", "rx", "ry"):
            raw += value[field].to_bytes(2, "little", signed=True)
        raw += b"\x01\x00\x00\x00\x00\x00\x00\x00"
    return hash_bytes(raw)


def make_arm(arm, r, *, effect=True, reverse=False, change=None):
    """Complete compact production grammar including every tail and both seals."""
    late, base = int(arm == "correction"), r["mapping"]["trace_base"]
    count, reads, work = 500 - base, r["reads_per_lane"], r["work_on"]
    net, fight = ["m 1 id 00000000"], []
    event, seq = 0, 0

    def emit(kind, **values):
        nonlocal event
        event += 1
        net.append("o " + json.dumps(dict(v=1, kind=kind, event=event, **values), separators=(",", ":")))

    def raw_pass(f, ordinal, phase, wrong=False):
        rows = [row_at(f, ordinal, slot, wrong=wrong, effect=effect, work=work,
                       changes=change(f, phase, slot) if change else None) for slot in (0, 1)]
        if reverse:
            rows.reverse()
        fight.extend(raw_row(row) for row in rows)
        fight.append(f"TRACE_PASS {ordinal} {phase}")
        return rows

    for ordinal in range(1, base + 1):
        raw_pass(0, ordinal, "R")
    emit("BASE", arm=arm, match=1, base=0, fight_frame=0, first_fight_frame=0, trace_base=base,
         trace_target=500, local=0, delay=1, ring=1, keep=1, recap=1, skip=0, lite=0, lastlite=0, pace=1)
    for f in range(1, count + 1):
        for phase in (["R", "S"] if late and f == 11 else ["R"]):
            seq += 1
            wrong = bool(late and f == 11 and phase == "R")
            rows = raw_pass(f, base + seq, phase, wrong)
            pads = deepcopy(r["expected_inputs"][f - 1])
            if late and f <= 11 and phase == "R":
                pads[1] = neutral()
            h = final_hash(rows, pads)
            if f <= 64:
                lanes = [dict(n=reads[q], varied=0,
                              predicted_reads=reads[q] if q == 1 and phase == "R" and (f <= 11 if late else f == 1) else 0,
                              value=pads[q]) for q in (0, 1)]
                emit("PASS", seq=seq, f=f, trace_pass=base + seq, phase=phase, left=int(phase == "S"),
                     poll=seq, polls=1, h=h, hash_valid=1, fighter_rows=2,
                     lanes=lanes, fighters=[witness(row) for row in rows])
            if wrong:
                emit("MISMATCH", source="remote_actual", cur=11, f=11, lane=1, pass_seq=11,
                     predicted=neutral(), actual=dict(neutral(), lx=32767))
                continue
            if phase == "S":
                emit("COMPLETE", token=1, load=10, target=11, mismatch=11, pass_seq=12, load_result=1,
                     original_pages=3, replay_only_pages=0, pages=3, diff=[1, 1, 1], begins=1, comparisons=1,
                     completions=1, pre_capture_ok=1, post_capture_ok=1, replayed=1, raw_pending=0,
                     diagnostic=1, authoritative=0)
            net.append(f"f {f} h {h}")
            net.append(f"d {f} " + " ".join(pad_text(pads[q], q + 1, reads[q]) for q in (0, 1)) +
                       " | " + " | ".join(detail_row(row) for row in rows))
    emit("END", diagnostic=1, authoritative=0, pass_records=64 + late, mismatches=late, completions=late,
         final_records=count, detail_records=count, final_first=1, final_last=count, window_finals=64,
         window_details=64, trace_passes=500 + late, trace_real=500, rows0=500 + late, rows1=500 + late,
         pad_reads=(count + late) * sum(reads), predicted_reads=(11 if late else 1) * reads[1],
         padcheck_bad=0, local_submissions=count, phase=0, left=0, pending_mismatch=0, verifier_pending=0, write_ok=1)
    fight.append(f"TRACE_END diagnostic=1 target=500 real=500 passes={500 + late} rows0={500 + late} rows1={500 + late} pending=0")
    log = ["exit=0", f"[rbnet] loop: remote pads arrive {late} frames after the frame that would send them",
           "[rbnet] match 1 (id 00000000) start at frame 0: local player 1, input delay 1 frames (round trip -1.0 ms, best -1.0 ms)",
           f"[trace] diagnostic interval sealed: real 500/500 passes {500 + late} reason none",
           "r1: RB NET: match start, base state = frame 0 (fight frame 0); pacing 60 Hz; re-run skip mask 0, lite mask 0"]
    if late:
        log += ["r1: RB NET: rollback 1 at frame 11: wrong guess at 11, state of frame 10 loaded in 0.000 ms, 1 frames again",
                "r1: RB VERIFY rollback to 10, back at 11: 3 pages compared; differ: window 1 1, window 2 1, extras 1; synthetic",
                "r1: LOOP VERIFY COMPLETE: token 1 from 10 to 11 pages 3; diagnostic only, external oracle required"]
    return {"net.txt": "\n".join(net) + "\n", "fight.txt": "\n".join(fight) + "\n", "run.log": "\n".join(log) + "\n"}


def mutate_json(text, kind, mutate, *, occurrence=0):
    lines, seen = text.splitlines(), 0
    for i, line in enumerate(lines):
        if line.startswith("o "):
            obj = json.loads(line[2:])
            if obj["kind"] == kind:
                if seen == occurrence:
                    mutate(obj)
                    lines[i] = "o " + json.dumps(obj, separators=(",", ":"))
                    return "\n".join(lines) + "\n"
                seen += 1
    raise AssertionError("missing mutation target")


class LoopCorrectionAnalyzerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.default_recipe = recipe()
        cls.original = {arm: make_arm(arm, cls.default_recipe) for arm in ("oracle", "correction")}
        cls.helper = A.HELPER.read_text(encoding="utf-8")

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.schema = self.root / "schema.txt"
        self.schema.write_bytes(SCHEMA)
        self.r = deepcopy(self.default_recipe)
        self.data = deepcopy(self.original)

    def write(self):
        for arm in ("oracle", "correction"):
            root = self.root / arm
            root.mkdir(exist_ok=True)
            for name, text in self.data[arm].items():
                (root / name).write_bytes(text.encode("utf-8"))

    def analyze(self):
        self.write()
        with patch.object(A, "SCHEMA_SHA256", SCHEMA_HASH):
            return A.analyze_packet(self.r, oracle_dir=self.root / "oracle", correction_dir=self.root / "correction", schema_path=self.schema)

    def invalid(self, needle=None):
        result = self.analyze()
        self.assertEqual((result["status"], result["exit_status"]), ("invalid", 2), result)
        if needle:
            self.assertIn(needle, result["reasons"][0])
        return result

    def event(self, kind, fn, occurrence=0, arm="correction"):
        self.data[arm]["net.txt"] = mutate_json(self.data[arm]["net.txt"], kind, fn, occurrence=occurrence)

    def test_valid_corrected_contrast_and_fixed_nonqualification(self):
        result = self.analyze()
        self.assertEqual(result["exit_status"], 0, result)
        self.assertTrue(result["projection_equal"])
        self.assertTrue(result["meaningful_input_effect"])
        self.assertEqual(result["frames_compared"], 64)
        self.assertEqual(result["speculative_branch"]["phase"], "R")
        self.assertEqual(result["speculative_branch"]["trace_pass"], 12)
        self.assertEqual(result["arms"]["correction"]["raw_completion"]["diff"], [1, 1, 1])
        self.assertEqual(result["arms"]["oracle"]["tail"], dict(first=65, last=499, count=435))
        for flag in ("resolved", "gameplay_qualified", "native_ready", "native_accepted"):
            self.assertIs(result[flag], False)
        self.assertEqual(result["authoritative"], 0)
        self.assertEqual(result["mutation_coverage"], "unknown")
        self.assertFalse(result["historical_controls"]["november4_enabled_all_pass"])
        self.assertTrue(result["historical_controls"]["batch_stopped"])
        self.assertEqual(len(result["known_aggregate_failures"]), 7)
        self.assertEqual(result["admission"], "external_required")
        self.assertEqual(result, self.analyze(), "no timestamps or ordering noise")

    def test_every_finalized_frame_is_compared(self):
        # Full parser and arm validation first, then independently rewrite each
        # complete correction artifact. Prefix, interior and suffix all count.
        for f in range(1, 65):
            with self.subTest(frame=f):
                self.data["correction"] = make_arm("correction", self.r, change=lambda g, phase, slot:
                    {"x": fbits(1000.0)} if g == f and slot == 0 and phase != "S" or
                    (g == f == 11 and slot == 0 and phase == "S") else None)
                result = self.analyze()
                self.assertEqual(result["exit_status"], 1, result)
                self.assertEqual(result["earliest_divergence"]["frame"], f)
                self.assertTrue(result["correction_witness"])

    def test_rounded_equal_raw_unequal(self):
        self.data["correction"] = make_arm("correction", self.r, change=lambda f, phase, slot:
                                           {"x": fbits(4.0) + 1} if f == 16 and slot == 0 else None)
        a = next(x for x in self.data["oracle"]["net.txt"].splitlines() if x.startswith("d 16 "))
        b = next(x for x in self.data["correction"]["net.txt"].splitlines() if x.startswith("d 16 "))
        self.assertEqual(a, b)
        result = self.analyze()
        self.assertEqual(result["exit_status"], 1, result)
        self.assertIn("raw_fighters", result["earliest_divergence"]["fields"])

    def test_pad_only_and_rng_only_are_not_meaningful_gameplay(self):
        for rng_only in (False, True):
            with self.subTest(rng_only=rng_only):
                change = lambda f, phase, slot: {"rng64": 0x555555555} if f == 11 and phase == "R" else None
                self.data["correction"] = make_arm("correction", self.r, effect=False, change=change if rng_only else None)
                result = self.analyze()
                self.assertEqual(result["exit_status"], 1, result)
                self.assertTrue(result["projection_equal"])
                self.assertFalse(result["meaningful_input_effect"])
                self.assertEqual(result["research_verdict"], "input_correction_path_only")
                self.r["require_effect"] = 0
                self.assertEqual(self.analyze()["exit_status"], 0)
                self.r["require_effect"] = 1

    def test_reversed_slots_both_minus_one_and_work_and_multiple_reads(self):
        self.r = recipe(reads=2, work=1)
        self.data = {arm: make_arm(arm, self.r, reverse=True) for arm in ("oracle", "correction")}
        result = self.analyze()
        self.assertEqual(result["exit_status"], 0, result)
        self.assertEqual(result["arms"]["correction"]["raw_completion"]["pages"], 3)

    def test_work_is_compared_even_with_equal_hash_and_detail(self):
        self.r = recipe(work=1)
        self.data = {arm: make_arm(arm, self.r, change=(lambda f, phase, slot:
                     {"work": 123} if f == 64 and slot == 1 else None) if arm == "correction" else None)
                     for arm in ("oracle", "correction")}
        result = self.analyze()
        self.assertEqual(result["exit_status"], 1, result)
        self.assertEqual(result["earliest_divergence"], dict(frame=64, fields=["raw_fighters"]))

    def test_valid_declared_alternate_base_never_fitted(self):
        self.r = recipe(base=2)
        self.data = {arm: make_arm(arm, self.r) for arm in ("oracle", "correction")}
        self.assertEqual(self.analyze()["exit_status"], 0)
        self.r["mapping"]["trace_base"] = 1
        self.invalid("input tape")

    def test_missing_witness_lanes_and_seals(self):
        for target in ('"kind":"BASE"', '"kind":"PASS"', '"kind":"MISMATCH"', '"kind":"COMPLETE"', '"kind":"END"'):
            with self.subTest(target=target):
                self.data = deepcopy(self.original)
                lines = self.data["correction"]["net.txt"].splitlines(keepends=True)
                lines.pop(next(i for i, s in enumerate(lines) if target in s))
                self.data["correction"]["net.txt"] = "".join(lines)
                self.invalid()
        self.data = deepcopy(self.original)
        self.event("PASS", lambda o: o["lanes"].pop())
        self.invalid("two lanes")
        for arm in ("oracle", "correction"):
            self.data = deepcopy(self.original)
            self.data[arm]["fight.txt"] = "\n".join(self.data[arm]["fight.txt"].splitlines()[:-1]) + "\n"
            self.invalid("incomplete")

    def test_bad_pass_and_lane_fields(self):
        mutations = [("seq", 2), ("f", 2), ("phase", "S"), ("left", 1), ("poll", 2), ("polls", 0),
                     ("trace_pass", 3), ("hash_valid", 0), ("fighter_rows", 0), ("h", "0" * 15)]
        for key, value in mutations:
            with self.subTest(key=key):
                self.data = deepcopy(self.original)
                self.event("PASS", lambda o: o.update({key: value}))
                self.invalid()
        for lane in (0, 1):
            for key, value in (("n", 0), ("n", 17), ("varied", 1), ("predicted_reads", 99)):
                with self.subTest(lane=lane, key=key):
                    self.data = deepcopy(self.original)
                    self.event("PASS", lambda o: o["lanes"][lane].update({key: value}))
                    self.invalid()
        self.data = deepcopy(self.original)
        self.event("PASS", lambda o: o["lanes"][1]["value"].update(lx=32768))
        self.invalid()

    def test_every_base_field_is_frozen(self):
        base = next(json.loads(s[2:]) for s in self.original["correction"]["net.txt"].splitlines()
                    if '"kind":"BASE"' in s)
        for key in base.keys() - {"v", "kind", "event"}:
            self.data = deepcopy(self.original)
            changed = "oracle" if key == "arm" else base[key] + 1
            self.event("BASE", lambda o: o.update({key: changed}))
            self.invalid("BASE.")

    def test_zero_summaries_do_not_bypass_missing_evidence_or_create_false_failures(self):
        summary = [
            "[rbnet] report: pad check of the final simulations: 0 pad values differ from the final ones (first frame -1)",
            "[rbnet] report: pads given 1000, predicted 11 (1.1%), mispredictions 1; finalized frames 499; checksums compared 0, DESYNCS 0 (first -1)",
            "[rbnet] report: packets sent 0 (failed 0), received 0 (bad 0, queue full 0); remote pads up to 500, local up to 500",
            "r1: RB NET report: task-worker watchdog releases 0 (since the process start), rollbacks with the workers not held 0 (watchdog paused at H2: yes)",
            "r1: RB NET report: loads that took the sound thread at another wait after 5 ms 0; threads not at their wait after 500 ms 0 (last load); loads refused, a thread still running (pub1) 0",
            "r1: RB NET report: stalls for the other player 0 (0.0 ms in all; 0 of them because the ring was short of memory); captures failed 0, re-run captures not needed 0; load mean 0.000 ms; peer silent 0",
            "r1: RB NET report: 499 real frames, 1 rollbacks, 1 frames run again (k: 1 1, 2 0, 3 0, 4 0, 5 0, 6 0, 7 0, more 0); rollbacks impossible (state not in the ring) 0",
            "r1: RA holds that failed (attempts): task worker not blocked 0, audio thread not blocked 0, other thread 0, a job fiber running 0; site 0; workers busy at H1 0, watchdog releases 0; kicks skipped in speculative passes 0, fighters' frame lines skipped 0 (mask 0); command-buffer recordings saved 0.0 KB (last)"]
        self.data["correction"]["run.log"] += "\n".join(summary) + "\n"
        self.assertEqual(self.analyze()["exit_status"], 0)
        self.event("PASS", lambda o: o["lanes"][0].update(n=0))
        self.invalid("lane.n")
        for old, new in (("0 pad values differ", "1 pad values differ"), ("DESYNCS 0", "DESYNCS 1"),
                         ("failed 0", "failed 1"), ("releases 0", "releases 1"),
                         ("pub1) 0", "pub1) 1"), ("1 rollbacks", "2 rollbacks"),
                         ("thread not blocked 0", "thread not blocked 1")):
            self.data = deepcopy(self.original)
            self.data["correction"]["run.log"] += ("\n".join(summary) + "\n").replace(old, new)
            self.invalid("summary")

    def test_bad_mismatch_and_completion_fields(self):
        mutations = {"MISMATCH": dict(source="TEST_SCHED", cur=12, f=12, lane=0, pass_seq=12, actual=neutral()),
                     "COMPLETE": dict(token=2, load=9, target=10, mismatch=12, pass_seq=11, load_result=0,
                                      original_pages=0, replay_only_pages=1, pages=0, diff=[1, 1], begins=0,
                                      comparisons=0, completions=2, pre_capture_ok=0, post_capture_ok=0,
                                      replayed=0, raw_pending=1, diagnostic=0, authoritative=1)}
        for kind, changes in mutations.items():
            for key, value in changes.items():
                with self.subTest(kind=kind, key=key):
                    self.data = deepcopy(self.original)
                    self.event(kind, lambda o: o.update({key: value}))
                    self.invalid()

    def test_every_seal_counter_is_cross_checked(self):
        obj = json.loads(self.original["correction"]["net.txt"].splitlines()[-1][2:])
        for key in obj.keys() - {"v", "kind", "event"}:
            with self.subTest(counter=key):
                self.data = deepcopy(self.original)
                self.event("END", lambda o: o.update({key: o[key] + 1}))
                self.invalid("END.")

    def test_unknown_missing_and_duplicate_json_keys(self):
        for kind in A.EVENT_FIELDS:
            for mutation in (lambda o: o.update(unknown=1), lambda o: o.pop("v")):
                self.data = deepcopy(self.original)
                self.event(kind, mutation)
                self.invalid("keys")
        for needle, replacement in (( '"v":1', '"v":1,"v":1'),
                                     ('"lx":0', '"lx":0,"lx":0'),
                                     ('"st":"0000008d"', '"st":"0000008d","st":"0000008d"')):
            self.data = deepcopy(self.original)
            self.data["correction"]["net.txt"] = self.data["correction"]["net.txt"].replace(needle, replacement, 1)
            self.invalid("duplicate JSON key")

    def test_nonfinite_and_bool_as_integer(self):
        for value in (True, 1.0, float("nan"), float("inf"), float("-inf")):
            for kind, key in (("BASE", "match"), ("PASS", "seq"), ("COMPLETE", "begins"), ("END", "write_ok")):
                self.data = deepcopy(self.original)
                self.event(kind, lambda o: o.update({key: value}))
                self.invalid()
        self.data = deepcopy(self.original)
        self.data["correction"]["net.txt"] = self.data["correction"]["net.txt"].replace('"seq":1,', '"seq":1e999,', 1)
        self.invalid("nonfinite")
        for field in ("require_effect", "trace_target", "work_on"):
            self.data = deepcopy(self.original)
            self.r = deepcopy(self.default_recipe)
            self.r[field] = True
            self.invalid()

    def test_early_completion_or_final_and_latest_vs_speculative(self):
        lines = self.data["correction"]["net.txt"].splitlines()
        find = lambda token: next(i for i, s in enumerate(lines) if token in s)
        complete, replay, final = find('"kind":"COMPLETE"'), find('"phase":"S"'), find("f 11 h ")
        for source, destination in ((complete, replay), (final, complete), (replay, complete + 2)):
            self.data = deepcopy(self.original)
            changed = lines.copy()
            value = changed.pop(source)
            changed.insert(destination, value)
            self.data["correction"]["net.txt"] = "\n".join(changed) + "\n"
            self.invalid()
        self.data = deepcopy(self.original)
        wrong = next(json.loads(s[2:])["h"] for s in lines if '"kind":"PASS"' in s and '"seq":11,' in s)
        self.data["correction"]["net.txt"] = "\n".join(
            "f 11 h " + wrong if s.startswith("f 11 h ") else s for s in lines) + "\n"
        self.invalid("latest PASS")

    def test_duplicate_gapped_reordered_final_detail_and_events(self):
        original = self.original["correction"]["net.txt"].splitlines()
        for token in ("m 1 id", '"kind":"PASS"', '"kind":"MISMATCH"', '"kind":"COMPLETE"', "f 32 h", "d 32 ", "f 499 h", "d 499 "):
            for operation in ("duplicate", "delete", "reorder"):
                self.data = deepcopy(self.original)
                lines = original.copy()
                i = next(i for i, s in enumerate(lines) if token in s)
                if operation == "duplicate":
                    lines.insert(i, lines[i])
                elif operation == "delete":
                    lines.pop(i)
                else:
                    lines[i], lines[i + 1] = lines[i + 1], lines[i]
                self.data["correction"]["net.txt"] = "\n".join(lines) + "\n"
                self.invalid()

    def test_raw_ordinal_slot_phase_count_and_tail_corruption(self):
        original = self.original["correction"]["fight.txt"]
        mutations = [original.replace("TRACE_PASS 13 S", "TRACE_PASS 13 R"),
                     original.replace("TRACE_PASS 400 R", "TRACE_PASS 400 S"),
                     original.replace("TRACE_PASS 3 R", "TRACE_PASS 4 R"),
                     original.replace(" slot 1", " slot 0", 1),
                     original.replace("rows0=501", "rows0=500"),
                     original.replace("target=500", "target=499"),
                     original.replace("TRACE_PASS 501 R", "TRACE_PASS 501 S"),
                     original.replace("F 501 e -1", "F 500 e -1", 1),
                     original + "TRACE_PASS 502 S\n",
                     "\n".join(original.splitlines()[:-4]) + "\n"]
        for text in mutations:
            with self.subTest(mutation=mutations.index(text)):
                self.data = deepcopy(self.original)
                self.data["correction"]["fight.txt"] = text
                self.invalid()
        self.data = deepcopy(self.original)
        self.data["correction"]["net.txt"] = self.data["correction"]["net.txt"].replace("d 499 p1 2", "d 499 p1 3")
        self.invalid("actual pads")

    def test_raw_pass_joins_and_detail_hash_tails(self):
        for occurrence in (0, 10, 11, 64):
            self.data = deepcopy(self.original)
            self.event("PASS", lambda o: o["fighters"][0].update(rngcalls=999), occurrence)
            self.invalid("PASS/raw")
        for field, text in (("mf", "nan"), ("x", "inf"), ("dmg", "1e999")):
            self.data = deepcopy(self.original)
            old = f"{field} " + {"mf": "499.000", "x": "124.7500", "dmg": "1.000"}[field]
            self.data["correction"]["net.txt"] = self.data["correction"]["net.txt"].replace(old, f"{field} {text}")
            self.invalid()
        self.data = deepcopy(self.original)
        lines = self.data["correction"]["fight.txt"].splitlines()
        i = next(i for i, s in enumerate(lines) if s.startswith("F 501 "))
        lines[i] = lines[i].replace(" x 42f98000", " x 42fa0000").replace("124.750", "125.000")
        self.data["correction"]["fight.txt"] = "\n".join(lines) + "\n"
        self.invalid("detail/raw")

    def test_raw_row_and_work_shape(self):
        for field, value in (("slot", 1), ("ordinal", 1), ("e", -2), ("rngcalls", True), ("work_on", 1),
                             ("work", 5), ("mf", "7f800000"), ("x", "0000000A"), ("mot", "0")):
            self.data = deepcopy(self.original)
            self.event("PASS", lambda o: o["fighters"][0].update({field: value}))
            self.invalid()

    def test_complete_zero_isolated_asymmetric_diffs_and_replay_only_pages(self):
        for diff, original, replay_only in (([0, 0, 0], 3, 0), ([1, 0, 0], 3, 0),
                                             ([0, 2, 0], 3, 0), ([0, 0, 3], 3, 0),
                                             ([0, 2, 3], 3, 2)):
            self.data = deepcopy(self.original)
            pages = original + replay_only
            self.event("COMPLETE", lambda o: o.update(diff=diff, original_pages=original,
                       replay_only_pages=replay_only, pages=pages))
            log = self.data["correction"]["run.log"]
            log = log.replace("3 pages compared", f"{pages} pages compared")
            log = log.replace("window 1 1, window 2 1, extras 1", f"window 1 {diff[0]}, window 2 {diff[1]}, extras {diff[2]}")
            log = log.replace("to 11 pages 3;", f"to 11 pages {pages};")
            self.data["correction"]["run.log"] = log
            result = self.analyze()
            self.assertEqual(result["exit_status"], 0, result)
            self.assertEqual(result["arms"]["correction"]["raw_completion"]["diff"], diff)
            if len(set(diff)) == 3:
                self.event("COMPLETE", lambda o: o.update(diff=list(reversed(diff))))
                self.invalid("verifier tuples")
        self.data = deepcopy(self.original)
        self.event("COMPLETE", lambda o: o.update(pages=6, original_pages=4, replay_only_pages=2))
        self.invalid("verifier tuples")

    def test_impossible_raw_counts_and_unicode_counters(self):
        for diff in ([-1,0,0], [4,0,0], [1,2,3]):
            self.data = deepcopy(self.original)
            self.event("COMPLETE", lambda o: o.update(diff=diff))
            self.data["correction"]["run.log"] = self.data["correction"]["run.log"].replace(
                "window 1 1, window 2 1, extras 1", f"window 1 {diff[0]}, window 2 {diff[1]}, extras {diff[2]}")
            self.invalid()
        for filename, old, new in (("net.txt", "f 12 h", "f 1\u0662 h"),
                                   ("net.txt", "d 12 ", "d 1\u0662 "),
                                   ("fight.txt", "TRACE_PASS 13 S", "TRACE_PASS 1\u0663 S"),
                                   ("fight.txt", "target=500", "target=5\u06600")):
            self.data = deepcopy(self.original)
            self.assertIn(old, self.data["correction"][filename])
            self.data["correction"][filename] = self.data["correction"][filename].replace(old,new)
            self.invalid()

    def test_normative_rounding_signed_zero_canonical_grammar_and_crlf(self):
        self.data = {arm: make_arm(arm, self.r, change=lambda f, phase, slot:
                     {"x": fbits(0.0625), "mf": fbits(-0.0625)} if f == 5 else None)
                     for arm in ("oracle", "correction")}
        self.assertEqual(self.analyze()["exit_status"], 0)
        self.assertIn("mf -0.062 x 0.0625", self.data["correction"]["net.txt"])
        self.data["correction"]["net.txt"] = self.data["correction"]["net.txt"].replace("y -0.0000", "y 0.0000", 1)
        self.invalid("rounded y")
        for old, new, filename in (("e-1 st", "e-01 st", "net.txt"),
                                   ("p1 0 0", "p1 00 0", "net.txt"),
                                   ("e -1 st", "e -01 st", "fight.txt"),
                                   ("st 8d mot", "st 08d mot", "fight.txt"),
                                   ("mf 00000000", "mf 7f800000", "fight.txt")):
            self.data = deepcopy(self.original)
            self.assertIn(old, self.data["correction"][filename])
            self.data["correction"][filename] = self.data["correction"][filename].replace(old, new, 1)
            self.invalid()
        self.data = {arm: {name: value.replace("\n", "\r\n") for name, value in files.items()}
                     for arm, files in self.original.items()}
        self.assertEqual(self.analyze()["exit_status"], 0)

    def test_hash_and_latest_detail_corruptions_are_independently_rejected(self):
        for token, replacement, reason in (("f 499 h ", "f 499 h 0", "malformed"),
                                            ("p1 0 0 0 0 0 n1", "p1 0 1 0 0 0 n1", "actual pads"),
                                            ("n1 p2", "n0 p2", "reads"),
                                            ("rng 0000001100010023", "rng 0000001100010022", "RNG fold")):
            self.data = deepcopy(self.original)
            self.assertIn(token, self.data["correction"]["net.txt"])
            self.data["correction"]["net.txt"] = self.data["correction"]["net.txt"].replace(token, replacement, 1)
            self.invalid(reason)
        self.data = deepcopy(self.original)
        text = self.data["correction"]["net.txt"]
        line = next(s for s in text.splitlines() if s.startswith("f 499 h "))
        changed = line[:-1] + ("0" if line[-1] != "0" else "1")
        self.data["correction"]["net.txt"] = text.replace(line, changed)
        self.invalid("final hash")

    def test_unchanged_old_comparator_rejects_retained_speculation(self):
        def read(text):
            namespace = {"__name__": "strict_helper_test", "open": lambda *a, **k: io.StringIO(text)}
            exec(compile(self.helper, str(A.HELPER), "exec"), namespace)
            return namespace, namespace["read_trace"]("complete fixture")
        n, oracle = read(self.data["oracle"]["fight.txt"])
        _, corrected = read(self.data["correction"]["fight.txt"])
        with self.assertRaisesRegex(ValueError, "real frame 12"):
            n["compare"](corrected, oracle, True)
        self.assertEqual(self.analyze()["exit_status"], 0)

    def test_read_cap_sixteen_positive_seventeen_negative(self):
        self.r = recipe(reads=16)
        self.data = {arm: make_arm(arm, self.r) for arm in ("oracle", "correction")}
        self.assertEqual(self.analyze()["exit_status"], 0)
        self.event("PASS", lambda o: [lane.update(n=17) for lane in o["lanes"]])
        self.invalid("lane.n")
        self.r["reads_per_lane"] = [17, 17]
        self.invalid("recipe lane reads")

    def test_cli_all_statuses_and_deterministic_json(self):
        for status in (0, 1, 2):
            self.data = deepcopy(self.original)
            if status == 1:
                self.data["correction"] = make_arm("correction", self.r, effect=False)
            if status == 2:
                self.event("COMPLETE", lambda o: o.update(raw_pending=1))
            self.write()
            rp = self.root / f"recipe{status}.json"
            rp.write_text(json.dumps(self.r) + "\n")
            output = self.root / f"result{status}.json"
            stream = io.StringIO()
            with patch.object(A, "SCHEMA_SHA256", SCHEMA_HASH), redirect_stdout(stream):
                code = A.main(["--recipe", str(rp), "--schema", str(self.schema),
                               "--oracle", str(self.root / "oracle"), "--correction", str(self.root / "correction"),
                               "--output", str(output)])
            self.assertEqual(code, status)
            self.assertEqual(output.read_text(), stream.getvalue())
            self.assertEqual(json.loads(stream.getvalue())["exit_status"], status)

    def test_empty_partial_trailing_utf8_and_large_inputs(self):
        for filename in ("net.txt", "fight.txt", "run.log"):
            for suffix in ("empty", "half", "trailing", "large_line"):
                self.data = deepcopy(self.original)
                text = self.data["correction"][filename]
                self.data["correction"][filename] = {"empty": "", "half": text[:-1],
                    "trailing": text + ("o {}\n" if filename == "net.txt" else "unparsed\n"),
                    "large_line": text + "x" * (A.MAX_LINE + 1) + "\n"}[suffix]
                if filename == "run.log" and suffix == "trailing":
                    self.assertEqual(self.analyze()["exit_status"], 0, "ordinary log lines are permitted")
                else:
                    self.invalid()
        self.data = deepcopy(self.original)
        self.write()
        path = self.root / "correction/fight.txt"
        path.write_bytes(path.read_bytes().replace(b"slot 0", b"slot \xff", 1))
        with patch.object(A, "SCHEMA_SHA256", SCHEMA_HASH):
            result = A.analyze_packet(self.r, oracle_dir=self.root / "oracle", correction_dir=self.root / "correction", schema_path=self.schema)
        self.assertEqual(result["exit_status"], 2)
        with patch.object(A, "MAX_DATA", 1024):
            self.invalid("size")

    def test_invalid_recipe_mapping_config_and_tape(self):
        mutations = [lambda r: r["mapping"].update(trace_base=0), lambda r: r["mapping"].update(trace_base=436),
                     lambda r: r["mapping"].update(poll_base=1), lambda r: r["mapping"].update(fight_frame=1),
                     lambda r: r["mapping"].update(first_fight_frame=True), lambda r: r.update(interval=[2, 64]),
                     lambda r: r.update(trace_target=499), lambda r: r.update(effect_fields=["x"]),
                     lambda r: r["config"].update(SSBU_RB_NET_KEEP="2"),
                     lambda r: r["config"].update(SSBU_RB_NET_RECAP="0"),
                     lambda r: r["config"].update(SSBU_RB_LOOP_VERIFY="0"),
                     lambda r: r["config"].update(SSBU_RB_NET_LOOP_BOT2="7"),
                     lambda r: r["config"].update(SSBU_RB_NET_CKPADS="0"),
                     lambda r: r["expected_inputs"].pop(),
                     lambda r: r["expected_inputs"][10][1].update(lx=0),
                     lambda r: r["expected_inputs"][20][1].update(lx=True),
                     lambda r: r["files"]["correction"].update(net="../oracle/net.txt"),
                     lambda r: r["files"]["correction"].update(logs=[]),
                     lambda r: r.update(native_accepted=True)]
        for mutate in mutations:
            self.r = deepcopy(self.default_recipe)
            mutate(self.r)
            self.invalid()

    def test_whole_log_failures_missing_or_duplicate_successes_extra_corrections(self):
        lines = self.original["correction"]["run.log"].splitlines(keepends=True)
        for i in range(len(lines)):
            # exit= is optional text, no process qualification is claimed.
            if i == 0:
                continue
            for op in ("missing", "duplicate"):
                self.data = deepcopy(self.original)
                changed = lines.copy()
                if op == "missing":
                    changed.pop(i)
                else:
                    changed.insert(i, changed[i])
                self.data["correction"]["run.log"] = "".join(changed)
                self.invalid()
        for extra in ("LOOP WITNESS FATAL: close", "r1: RB NET: lockstep fallback", "PAD CHECK: wrong",
                      "r1: RB NET: late base", "r1: watchdog release", "TEST_SCHED=11:10", "exit=73",
                      "r1: RB NET: rollback 2 at frame 80: wrong guess at 80, state of frame 79 loaded in 0.001 ms, 1 frames again",
                      "r1: LOOP VERIFY COMPLETE: token 2 from 79 to 80 pages 3; diagnostic only, external oracle required"):
            self.data = deepcopy(self.original)
            self.data["correction"]["run.log"] += extra + "\n"
            self.invalid()

    def test_cross_arm_reuse_and_raw_mutation_screen(self):
        self.write()
        with patch.object(A, "SCHEMA_SHA256", SCHEMA_HASH):
            result = A.analyze_packet(self.r, oracle_dir=self.root / "oracle", correction_dir=self.root / "oracle", schema_path=self.schema)
        self.assertEqual(result["exit_status"], 2)
        snapshot = A.Inputs()
        path = self.root / "correction/net.txt"
        snapshot.read(path, A.MAX_DATA, "test")
        with self.assertRaisesRegex(A.Invalid, "reused"):
            snapshot.read(path, A.MAX_DATA, "duplicate")
        path.write_bytes(path.read_bytes().replace(b"m 1 id", b"m 2 id", 1))
        with self.assertRaisesRegex(A.Invalid, "changed"):
            snapshot.verify()

    def test_late_mutation_has_no_positive_verdict(self):
        self.write()
        class MutatingInputs(A.Inputs):
            def verify(inner):
                path = self.root / "correction/run.log"
                path.write_bytes(path.read_bytes() + b"ordinary late line\n")
                super().verify()
        with patch.object(A, "SCHEMA_SHA256", SCHEMA_HASH):
            result = A.analyze_packet(self.r, oracle_dir=self.root / "oracle",
                correction_dir=self.root / "correction", schema_path=self.schema, inputs=MutatingInputs())
        self.assertEqual(result["exit_status"], 2)
        for key in ("research_verdict", "effect_contrast", "arms"):
            self.assertNotIn(key, result)
        self.assertIsNone(result["projection_equal"])

    @unittest.skipUnless(os.name == "nt", "Windows junction")
    def test_arm_root_junction_rejected(self):
        self.write()
        link = self.root / "correction-junction"
        result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(self.root / "correction")],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        try:
            with patch.object(A, "SCHEMA_SHA256", SCHEMA_HASH):
                result = A.analyze_packet(self.r, oracle_dir=self.root / "oracle",
                    correction_dir=link, schema_path=self.schema)
            self.assertEqual(result["exit_status"], 2)
            self.assertIn("junction", result["reasons"][0])
        finally:
            os.rmdir(link)  # Remove only the junction itself, never its target.

    def test_schema_binding_and_duplicate_recipe_keys(self):
        self.write()
        result = A.analyze_packet(dict(self.r, schema_sha256=A.SCHEMA_SHA256), oracle_dir=self.root / "oracle",
                                  correction_dir=self.root / "correction", schema_path=self.schema)
        self.assertEqual(result["exit_status"], 2)
        self.assertIn("schema bytes", result["reasons"][0])
        for text in ('{"a":1,"a":1}', '{"x":{"a":1,"a":2}}', '{"x":NaN}', '{"x":1e999}'):
            with self.assertRaises(A.Invalid):
                A.strict_json(text)

    def test_cli_invalid_is_json_exclusive_and_no_native_claim(self):
        self.write()
        rp, output = self.root / "recipe.json", self.root / "result.json"
        rp.write_text('{"v":1,"v":1}\n')
        cmd = [sys.executable, "-I", "-B", str(ROOT / "tools/analyze_loop_correction.py"),
               "--recipe", str(rp), "--schema", str(self.schema), "--oracle", str(self.root / "oracle"),
               "--correction", str(self.root / "correction"), "--output", str(output)]
        run = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        self.assertEqual(run.returncode, 2, run.stderr)
        self.assertEqual(json.loads(run.stdout)["exit_status"], 2)
        before = output.read_bytes()
        run = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        self.assertEqual(run.returncode, 2)
        self.assertEqual(before, output.read_bytes())
        self.assertFalse(json.loads(run.stdout)["native_ready"])


if __name__ == "__main__":
    unittest.main()
