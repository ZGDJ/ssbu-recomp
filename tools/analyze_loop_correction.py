"""Strict offline reader for the pending M1.14 bounded loop witness v1.

CLI: --recipe FILE --schema FILE --oracle DIR --correction DIR --output NEW_FILE
Exit 0: limited diagnostic predicate; 1: valid inequality/input-path-only;
2: invalid/incomplete evidence. No exit status asserts native acceptance.

Recipe v1 (all keys required, no defaults):
  v, schema_sha256, interval:[1,64], trace_target:500,
  mapping:{trace_base, fight_frame, first_fight_frame, poll_base},
  config: the exact CONFIG below, reads_per_lane:[n0,n1], work_on:0|1,
  effect_fields:["st","mot","mf","x","y","dmg"], require_effect:0|1,
  expected_inputs: one [local_pad,remote_pad] per finalized frame,
  files:{oracle:{net,trace,logs:[...]}, correction:{net,trace,logs:[...]}}.
Pads have buttons (16 lowercase hex digits) and lx/ly/rx/ry (int16).
Mapping and tape must be frozen independently BEFORE the correction; this tool
checks that declaration, never learns offsets, input schedules or references.
Config is declared intent, not attested environment. File names are relative to
the arm directory. Pass disjoint complete logs, never extracted comparator rows.

External integration MUST bind the recipe/schema/analyzer/helper and all raw
file digests in this result to reviewed prelaunch identity and durable start/exit
receipts, fresh admission/lease, fatal/process, fixture/menu/RNG, original and
new-package disabled/SIM controls, full postidentity, and the one-shot journal.
These gates are unimplemented here; no caller-supplied booleans can waive them.
END can precede a failed close. Log validity cannot attest process exit, package
identity, predeclaration timing, all live writers, or native safety/acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import stat
import struct
import sys


SCHEMA_SHA256 = "23f456f033c2d4ae1c7ffbc68db35177879f865d118dd72500e2d9d5d800f1b7"
HELPER = Path(__file__).resolve().parents[1] / "tests/bounded_trace_cmp.py"
MAX_LINE = 16 * 1024
MAX_DATA = 16 * 1024 * 1024
MAX_LOG = 64 * 1024 * 1024
MAX_TOTAL = 256 * 1024 * 1024
MAX_RECIPE = 1024 * 1024
CONFIG = {
    "SSBU_RB_LOOP_WITNESS": "1", "SSBU_RB_LOOP_VERIFY": "1",
    "SSBU_RB_NET_PLAYER": "0", "SSBU_RB_NET_DELAY": "1",
    "SSBU_RB_NET_BOT": "7", "SSBU_RB_NET_LOOP_BOT2": "19",
    "SSBU_RB_NET_LOOP_LAT2": "11,0", "SSBU_RB_NET_KEEP": "1",
    "SSBU_RB_NET_RECAP": "1", "SSBU_RB_NET_SKIP": "0",
    "SSBU_RB_NET_LITE": "0", "SSBU_RB_NET_LASTLITE": "0",
    "SSBU_RB_NET_PACE": "1", "SSBU_RB_NET_DETAIL": "1",
    "SSBU_RB_NET_CKPADS": "1", "SSBU_TRACE_FRAMES": "500",
}
EFFECT_FIELDS = ["st", "mot", "mf", "x", "y", "dmg"]
EXTERNAL_PREREQUISITES = [
    "reviewed predeclared recipe, oracle/tape and observed base/poll mapping",
    "independent witness runtime/test and analyzer reviews",
    "full prelaunch source/package/host/game/module/content/config/save/tape identity",
    "reviewed native safety prerequisite and applicable integrated controls",
    "fresh admission/capacity and exclusive shared native lease through proven exit",
    "durable one-shot start/end receipts and actual successful child exit",
    "independent complete process/fatal scan including launcher and all native logs",
    "fixture/rules/menu/RNG/hook applicability and original-reference gates",
    "new-package disabled500R/0S and enabled SIM500R/two common depth-one controls",
    "full unchanged postidentity and immutable recipe/analyzer/helper/schema/raw digest binding",
    "historical failed aggregates retained independently; no retry of stopped batch",
]
COMPLETION_LIMITS = [
    "original_pages/replay_only_pages split has no independent legacy log witness",
    "positive load_result magnitude has no independent legacy log witness",
    "speculative R11 full RNG/hash cannot be recomputed from folded RNG alone",
    "BASE pre-reset net accumulator is not serialized for an independent base hash join",
    "tail RNG-call/work fields have raw coverage but no cross-arm equality predicate",
]


class Invalid(ValueError):
    """Evidence cannot support even the limited comparison."""


def need(condition, reason):
    if not condition:
        raise Invalid(reason)


def keys(obj, names, where):
    need(type(obj) is dict and set(obj) == set(names.split()), where + ": keys")


def integer(value, low, high, where):
    need(type(value) is int and low <= value <= high, where + ": integer/range")
    return value


def exact(value, expected, where):
    need(type(value) is type(expected) and value == expected, where + ": expected " + str(expected))


def hexnum(value, digits, where):
    need(type(value) is str and re.fullmatch(r"[0-9a-f]{%d}" % digits, value) is not None,
         where + ": hex width/case")
    return int(value, 16)


def pad(value):
    keys(value, "buttons lx ly rx ry", "pad")
    hexnum(value["buttons"], 16, "pad.buttons")
    for field in ("lx", "ly", "rx", "ry"):
        integer(value[field], -32768, 32767, "pad." + field)
    return value


ZERO = dict(buttons="0000000000000000", lx=0, ly=0, rx=0, ry=0)
ACTUAL = dict(ZERO, lx=32767)


def strict_json(text):
    def pairs(items):
        obj = {}
        for key, value in items:
            need(key not in obj, "duplicate JSON key: " + key)
            obj[key] = value
        return obj

    def constant(value):
        raise Invalid("nonfinite JSON number: " + value)

    try:
        result = json.loads(text, object_pairs_hook=pairs, parse_constant=constant)
    except (ValueError, RecursionError) as exc:
        raise Invalid("invalid JSON: " + str(exc)) from exc

    def finite(value, depth=0):
        need(depth <= 16, "JSON nesting limit")
        if type(value) is float:
            need(math.isfinite(value), "nonfinite JSON number")
        elif type(value) is dict:
            for item in value.values():
                finite(item, depth + 1)
        elif type(value) is list:
            for item in value:
                finite(item, depth + 1)
    finite(result)
    return result


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def stamp(s):
    # Windows Python exposes different legacy ctime semantics for stat/fstat.
    # Use birthtime there; the independent full reread still checks all bytes.
    change = getattr(s, "st_birthtime_ns", None) if os.name == "nt" else s.st_ctime_ns
    return s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, change


class Inputs:
    """Bounded, immutable snapshots; a full second read detects ordinary races."""
    def __init__(self):
        self.seen = {}
        self.total = 0

    def read(self, path, limit, label, lines=True):
        path = Path(path).absolute()
        need(not path.is_symlink(), label + ": linked input")
        for parent in (path, *path.parents):
            need(not getattr(parent, "is_junction", lambda: False)(), label + ": junction input")
            need(not parent.is_symlink(), label + ": linked input ancestor")
        before = path.stat()
        need(stat.S_ISREG(before.st_mode) and 0 < before.st_size <= limit, label + ": file size/type")
        identity = (before.st_dev, before.st_ino)
        need(identity not in self.seen, label + ": reused input file")
        self.total += before.st_size
        need(self.total <= MAX_TOTAL, "aggregate input size limit")
        with path.open("rb") as stream:
            need(stamp(before) == stamp(os.fstat(stream.fileno())), label + ": changed before read")
            raw = stream.read(limit + 1)
            need(stamp(before) == stamp(os.fstat(stream.fileno())), label + ": changed during read")
        need(len(raw) == before.st_size and stamp(before) == stamp(path.stat()), label + ": changed read/size")
        try:
            text = raw.decode("utf-8", errors="strict")
        except UnicodeError as exc:
            raise Invalid(label + ": invalid UTF-8") from exc
        if lines:
            need(raw.endswith(b"\n"), label + ": partial last line")
            # Only LF or CRLF. splitlines() would silently accept other separators.
            need("\r" not in text.replace("\r\n", ""), label + ": stray CR")
            need(all(len(line.rstrip(b"\r\n")) <= MAX_LINE for line in io.BytesIO(raw)), label + ": physical line limit")
        self.seen[identity] = (path, limit, before, sha(raw), label)
        return text, {"sha256": sha(raw), "bytes": len(raw)}

    def verify(self):
        for path, limit, before, digest, label in self.seen.values():
            need(stamp(before) == stamp(path.stat()), label + ": changed after read")
            with path.open("rb") as stream:
                raw = stream.read(limit + 1)
                need(stamp(before) == stamp(os.fstat(stream.fileno())), label + ": changed on recheck")
            need(sha(raw) == digest and stamp(before) == stamp(path.stat()), label + ": changed bytes")


def validate_recipe(recipe):
    keys(recipe, "v schema_sha256 interval trace_target mapping config reads_per_lane work_on "
         "effect_fields require_effect expected_inputs files", "recipe")
    exact(recipe["v"], 1, "recipe.v")
    exact(recipe["schema_sha256"], SCHEMA_SHA256, "recipe.schema")
    exact(recipe["interval"], [1, 64], "recipe.interval")
    for x, expected in zip(recipe["interval"], (1, 64)):
        exact(x, expected, "recipe.interval item")
    exact(recipe["trace_target"], 500, "recipe.trace_target")
    exact(recipe["config"], CONFIG, "recipe.config")
    keys(recipe["mapping"], "trace_base fight_frame first_fight_frame poll_base", "mapping")
    m = recipe["mapping"]
    integer(m["trace_base"], 1, 435, "mapping.trace_base")
    for field in ("fight_frame", "first_fight_frame", "poll_base"):
        integer(m[field], 0, 1000000, "mapping." + field)
    exact(m["fight_frame"], m["first_fight_frame"], "first base observation")
    exact(m["poll_base"], m["fight_frame"], "base poll observation")
    need(type(recipe["reads_per_lane"]) is list and len(recipe["reads_per_lane"]) == 2, "recipe.reads_per_lane")
    for n in recipe["reads_per_lane"]:
        integer(n, 1, 16, "recipe lane reads")
    integer(recipe["work_on"], 0, 1, "recipe.work_on")
    integer(recipe["require_effect"], 0, 1, "recipe.require_effect")
    exact(recipe["effect_fields"], EFFECT_FIELDS, "recipe.effect_fields")
    count = 500 - m["trace_base"]
    tape = recipe["expected_inputs"]
    need(type(tape) is list and len(tape) == count, "recipe complete input tape")
    for values in tape:
        need(type(values) is list and len(values) == 2, "recipe two-lane tape")
        for value in values:
            pad(value)
    exact(tape[0], [ZERO, ZERO], "delay1 initial pads")
    need(all(tape[f - 1][1] == ZERO for f in range(1, 11)), "recipe neutral remote prefix")
    exact(tape[10][1], ACTUAL, "recipe frame11 actual contrast")
    keys(recipe["files"], "oracle correction", "recipe.files")
    for files in recipe["files"].values():
        keys(files, "net trace logs", "recipe arm files")
        need(type(files["logs"]) is list and 1 <= len(files["logs"]) <= 8, "recipe log inventory")
        for name in [files["net"], files["trace"], *files["logs"]]:
            need(type(name) is str and 0 < len(name) <= 200, "input file name")
            p = Path(name)
            need(not p.is_absolute() and not p.drive and ".." not in p.parts and ":" not in name,
                 "input file must stay within arm directory")
    return recipe


FLOAT = r"-?(?:0|[1-9][0-9]*)\.[0-9]+"
DETAIL_ROW = re.compile(r"e(-?[0-9]+) st ([0-9a-f]{1,8}) mot ([0-9a-f]{1,16}) mf (" + FLOAT +
                        r") x (" + FLOAT + r") y (" + FLOAT + r") dmg (" + FLOAT + r") rng ([0-9a-f]{16})")
PAD_TEXT = re.compile(r"p1 ([0-9a-f]{1,16}) (-?[0-9]+) (-?[0-9]+) (-?[0-9]+) (-?[0-9]+) n([0-9]+) "
                      r"p2 ([0-9a-f]{1,16}) (-?[0-9]+) (-?[0-9]+) (-?[0-9]+) (-?[0-9]+) n([0-9]+)")


def physical_lines(text):
    need(text.endswith("\n") and "\r" not in text.replace("\r\n", ""), "partial/invalid physical line")
    for raw in io.StringIO(text):
        yield raw.removesuffix("\n").removesuffix("\r")


def read_net(text):
    """Parse every byte; semantic order/count validation is in validate_arm."""
    records = []
    for line in physical_lines(text):
        if line.startswith("o "):
            obj = strict_json(line[2:])
            need(type(obj) is dict and type(obj.get("kind")) is str, "net witness object/kind")
            records.append((obj["kind"], obj))
        elif re.fullmatch(r"m 1 id [0-9a-f]{8}", line):
            records.append(("m", line))
        elif match := re.fullmatch(r"f ([1-9][0-9]{0,3}) h ([0-9a-f]{16})", line):
            records.append(("f", (int(match[1]), match[2])))
        elif match := re.fullmatch(r"d ([1-9][0-9]{0,3}) (.+)", line):
            parts = match[2].split(" | ")
            need(len(parts) == 3, "detail requires exactly two ordered rows")
            lanes = PAD_TEXT.fullmatch(parts[0])
            need(lanes is not None, "detail pad grammar")
            values = []
            for offset in (0, 6):
                cells = lanes.groups()[offset:offset + 6]
                exact(cells[0], format(int(cells[0], 16), "x"), "detail canonical buttons")
                for cell in cells[1:]:
                    exact(cell, str(int(cell)), "detail canonical integer")
                value = dict(zip(("buttons", "lx", "ly", "rx", "ry"),
                                 [f"{int(cells[0], 16):016x}", *map(int, cells[1:5])]))
                values.append({"value": pad(value), "n": integer(int(cells[5]), 1, 16, "detail reads")})
            rows = []
            for body in parts[1:]:
                row = DETAIL_ROW.fullmatch(body)
                need(row is not None, "detail fighter grammar/nonfinite number")
                cells = row.groups()
                integer(int(cells[0]), -(2**31), 2**31 - 1, "detail entry")
                exact(cells[0], str(int(cells[0])), "detail canonical entry")
                for cell in cells[1:3]:
                    exact(cell, format(int(cell, 16), "x"), "detail canonical hex")
                floats = cells[3:7]
                need(all(math.isfinite(float(s)) for s in floats), "nonfinite detail")
                rows.append(dict(e=int(cells[0]), st=int(cells[1], 16), mot=int(cells[2], 16),
                                 mf=floats[0], x=floats[1], y=floats[2], dmg=floats[3], rng=int(cells[7], 16)))
            records.append(("d", (int(match[1]), values, rows)))
        else:
            raise Invalid("unknown/malformed net record")
        need(len(records) <= 2 * 511 + 70, "net record count limit")
    need(bool(records), "empty net")
    return records


RAW_ROW = re.compile(
    r"F ([1-9][0-9]{0,3}) e (-?[0-9]{1,11}) st ([0-9a-f]{1,8}) mot ([0-9a-f]{1,16}) "
    r"mf ([0-9a-f]{8}) x ([0-9a-f]{8}) y ([0-9a-f]{8}) dmg ([0-9a-f]{8}) "
    r"rngcalls ([0-9]{1,10}) rng ([0-9a-f]{8}) H ([0-9a-f]{16})  "
    r"\((" + FLOAT + r") (" + FLOAT + r") frame (" + FLOAT + r") (" + FLOAT + r")%\)"
    r"(?: w (-?[0-9]{1,11}))? slot ([01])")


def float32(bits):
    return struct.unpack("<f", struct.pack("<I", bits))[0]


def rounded(bits, digits):
    value = float32(bits)
    need(math.isfinite(value), "nonfinite raw fighter float")
    return format(value, ".%df" % digits)


def read_raw_trace(text, helper_text, label, work_on):
    # Run the unchanged whole-trace reader on the COMPLETE immutable snapshot.
    # The injected open supplies only these bounded bytes, never a filtered file.
    namespace = {"__name__": "bounded_trace_snapshot", "open": lambda *a, **kw: io.StringIO(text)}
    exec(compile(helper_text, str(HELPER), "exec"), namespace)
    namespace["read_trace"](label)
    result, pending = [], []
    for line in physical_lines(text):
        need(line.isascii(), "raw trace requires ASCII grammar")
        if line.startswith("F "):
            match = RAW_ROW.fullmatch(line)
            need(match is not None, "raw fighter grammar/width/nonfinite")
            c = match.groups()
            row = dict(ordinal=int(c[0]), e=int(c[1]), st=int(c[2], 16), mot=int(c[3], 16),
                       mf=int(c[4], 16), x=int(c[5], 16), y=int(c[6], 16), dmg=int(c[7], 16),
                       rngcalls=int(c[8]), rng=int(c[9], 16), work_on=int(c[15] is not None),
                       work=int(c[15]) if c[15] is not None else 0, slot=int(c[16]))
            integer(row["e"], -(2**31), 2**31 - 1, "raw entry")
            integer(row["work"], -(2**31), 2**31 - 1, "raw work")
            integer(row["rngcalls"], 0, 2**32 - 1, "raw RNG count")
            for field, cell in (("ordinal", c[0]), ("e", c[1]), ("rngcalls", c[8])):
                exact(cell, str(row[field]), "raw canonical integer")
            for field, cell in (("st", c[2]), ("mot", c[3])):
                exact(cell, format(row[field], "x"), "raw canonical hex")
            if c[15] is not None:
                exact(c[15], str(row["work"]), "raw canonical work")
            exact(row["work_on"], work_on, "raw work configuration")
            for field, suffix, digits in zip(("x", "y", "mf", "dmg"), c[11:15], (3, 3, 2, 2)):
                exact(suffix, rounded(row[field], digits), "raw rounded suffix " + field)
            pending.append(row)
        elif line.startswith("TRACE_PASS "):
            _, ordinal, phase = line.split()
            need(len(pending) == 2 and all(r["ordinal"] == int(ordinal) for r in pending), "raw ordered rows")
            result.append({"phase": phase, "fighters": pending})
            pending = []
        # The unchanged reader already rejects every unknown/trailing record.
    need(len(result) in (500, 501), "raw trace size must be 500/501")
    return result


BASE_FIELDS = "arm match base fight_frame first_fight_frame trace_base trace_target local delay ring keep recap skip lite lastlite pace"
PASS_FIELDS = "seq f trace_pass phase left poll polls h hash_valid fighter_rows lanes fighters"
MISMATCH_FIELDS = "source cur f lane pass_seq predicted actual"
COMPLETE_FIELDS = ("token load target mismatch pass_seq load_result original_pages replay_only_pages pages diff "
                   "begins comparisons completions pre_capture_ok post_capture_ok replayed raw_pending diagnostic authoritative")
END_FIELDS = ("diagnostic authoritative pass_records mismatches completions final_records detail_records final_first final_last "
              "window_finals window_details trace_passes trace_real rows0 rows1 pad_reads predicted_reads padcheck_bad "
              "local_submissions phase left pending_mismatch verifier_pending write_ok")
EVENT_FIELDS = dict(BASE=BASE_FIELDS, PASS=PASS_FIELDS, MISMATCH=MISMATCH_FIELDS,
                    COMPLETE=COMPLETE_FIELDS, END=END_FIELDS)


def witness_row(row):
    keys(row, "slot ordinal e st mot mf x y dmg rngcalls rng work_on work", "witness fighter")
    for field, low, high in (("slot", 0, 1), ("ordinal", 1, 501), ("e", -(2**31), 2**31 - 1),
                             ("rngcalls", 0, 2**32 - 1), ("work_on", 0, 1), ("work", -(2**31), 2**31 - 1)):
        integer(row[field], low, high, "fighter." + field)
    result = dict(row)
    for field in ("st", "mot", "mf", "x", "y", "dmg", "rng"):
        result[field] = hexnum(row[field], 16 if field == "mot" else 8, "fighter." + field)
    need(row["work_on"] or row["work"] == 0, "disabled work must be zero")
    return result


def projection_row(row):
    return {k: v for k, v in row.items() if k != "ordinal"}


def hash_final(rows, detail_rows, lanes):
    data = bytearray()
    for row, detail in zip(rows, detail_rows):
        data.extend(struct.pack("<iI Q IIII Q", row["e"], row["st"], row["mot"], row["mf"],
                                row["x"], row["y"], row["dmg"], detail["rng"]))
    for lane in lanes:
        p = lane["value"]
        data.extend(struct.pack("<QhhhhII", int(p["buttons"], 16), p["lx"], p["ly"], p["rx"], p["ry"], 1, 0))
    h = 0xcbf29ce484222325
    for byte in data:
        h = ((h ^ byte) * 0x100000001b3) & (2**64 - 1)
    return f"{h:016x}"


def validate_arm(records, trace, recipe, arm):
    """Exact event timeline, latest generation, full raw/detail/hash/tail joins."""
    correction = int(arm == "correction")
    count = len(recipe["expected_inputs"])
    mapping = recipe["mapping"]
    base = mapping["trace_base"]
    need(len(trace) == 500 + correction, arm + ": raw count")
    replay_ordinal = base + 12
    for ordinal, record in enumerate(trace, 1):
        exact(record["phase"], "S" if correction and ordinal == replay_ordinal else "R", "whole raw phase order")
    need(records[0][0] == "m" and len(records) > 1 and records[1][0] == "BASE", "m/BASE start order")
    latest, passes, finals, details = {}, [], {}, {}
    mismatch = complete = end = None
    event = 0
    awaiting_detail = None
    expected_timeline = [(f, "R") for f in range(1, 65)]
    if correction:
        expected_timeline.insert(11, (11, "S"))
    for index, (kind, obj) in enumerate(records[1:], 1):
        if awaiting_detail is not None:
            need(kind == "d", "final must have immediate detail")
        if kind in EVENT_FIELDS:
            keys(obj, "v kind event " + EVENT_FIELDS[kind], kind)
            exact(obj["v"], 1, "witness version")
            event += 1
            exact(obj["event"], event, "event order")
        if kind == "BASE":
            need(index == 1, "duplicate/late BASE")
            wanted = dict(arm=arm, match=1, base=0, trace_target=500, local=0, delay=1,
                          ring=1, keep=1, recap=1, skip=0, lite=0, lastlite=0, pace=1,
                          **{k: mapping[k] for k in ("fight_frame", "first_fight_frame", "trace_base")})
            for k, v in wanted.items():
                exact(obj[k], v, "BASE." + k)
        elif kind == "PASS":
            seq = len(passes) + 1
            need(seq <= len(expected_timeline), "extra PASS")
            f, phase = expected_timeline[seq - 1]
            need(f not in finals, "PASS rewrites finalized frame")
            if phase == "S":
                need(mismatch is not None and complete is None, "replay without pending mismatch")
            if f >= 12 and correction:
                need(complete is not None, "pass crosses pending completion")
            for k, v in dict(seq=seq, f=f, phase=phase, left=int(phase == "S"),
                             trace_pass=base + seq, poll=mapping["poll_base"] + seq,
                             polls=1, hash_valid=1, fighter_rows=2).items():
                exact(obj[k], v, "PASS." + k)
            hexnum(obj["h"], 16, "PASS.h")
            need(type(obj["lanes"]) is list and len(obj["lanes"]) == 2, "PASS two lanes")
            for lane_id, lane in enumerate(obj["lanes"]):
                keys(lane, "n varied predicted_reads value", "lane")
                n = recipe["reads_per_lane"][lane_id]
                predicted = lane_id == 1 and phase == "R" and (f <= 11 if correction else f == 1)
                for k, v in dict(n=n, varied=0, predicted_reads=n if predicted else 0).items():
                    exact(lane[k], v, "lane." + k)
                pad(lane["value"])
                wanted = ZERO if predicted else recipe["expected_inputs"][f - 1][lane_id]
                exact(lane["value"], wanted, "consumed pad")
            need(type(obj["fighters"]) is list and len(obj["fighters"]) == 2, "PASS two fighters")
            rows = [witness_row(r) for r in obj["fighters"]]
            exact(rows, trace[base + seq - 1]["fighters"], "PASS/raw ordered ordinal/slot/fields join")
            passes.append(obj)
            latest[f] = obj
        elif kind == "MISMATCH":
            need(correction and mismatch is None and len(passes) == 11 and 11 not in finals,
                 "missing/extra/out-of-order mismatch")
            for k, v in dict(source="remote_actual", cur=11, f=11, lane=1, pass_seq=11,
                             predicted=ZERO, actual=ACTUAL).items():
                exact(obj[k], v, "MISMATCH." + k)
            pad(obj["predicted"])
            pad(obj["actual"])
            mismatch = obj
        elif kind == "COMPLETE":
            need(correction and mismatch is not None and complete is None and len(passes) == 12
                 and 11 not in finals, "early/duplicate/unbound completion")
            for k, v in dict(token=1, load=10, target=11, mismatch=11, pass_seq=12, begins=1,
                             comparisons=1, completions=1, pre_capture_ok=1, post_capture_ok=1,
                             replayed=1, raw_pending=0, diagnostic=1, authoritative=0).items():
                exact(obj[k], v, "COMPLETE." + k)
            integer(obj["load_result"], 1, 2**31 - 1, "load result")
            integer(obj["original_pages"], 1, 2**31 - 1, "original pages")
            integer(obj["replay_only_pages"], 0, 2**31 - 1, "replay-only pages")
            integer(obj["pages"], 1, 2**31 - 1, "compared pages")
            exact(obj["pages"], obj["original_pages"] + obj["replay_only_pages"], "page sum")
            need(type(obj["diff"]) is list and len(obj["diff"]) == 3, "three raw diff counters")
            for value in obj["diff"]:
                integer(value, 0, 2**63 - 1, "raw diff")
            need(sum(obj["diff"]) <= obj["pages"], "raw differences exceed compared pages")
            complete = obj
        elif kind == "f":
            f, h = obj
            exact(f, len(finals) + 1, "contiguous unique finals")
            need(f <= count, "extra final")
            if correction and f >= 11:
                need(complete is not None, "final crosses pending correction/verifier")
            if f <= 64:
                need(f in latest, "final without PASS witness")
                exact(h, latest[f]["h"], "final hash must use latest PASS")
            else:
                need(len(passes) == 64 + correction, "tail before interval witnesses")
            finals[f] = h
            awaiting_detail = f
        elif kind == "d":
            f, lanes, rows = obj
            exact(f, awaiting_detail, "paired ordered detail")
            exact([lane["n"] for lane in lanes], recipe["reads_per_lane"], "detail read counts")
            exact([lane["value"] for lane in lanes], recipe["expected_inputs"][f - 1], "final actual pads")
            ordinal = base + f + int(correction and f >= 11)
            raw_rows = trace[ordinal - 1]["fighters"]
            for raw, detail in zip(raw_rows, rows):
                for k in ("e", "st", "mot"):
                    exact(detail[k], raw[k], "detail/raw " + k)
                for k, digits in (("mf", 3), ("x", 4), ("y", 4), ("dmg", 3)):
                    exact(detail[k], rounded(raw[k], digits), "detail/raw rounded " + k)
                exact((detail["rng"] ^ (detail["rng"] >> 32)) & 0xffffffff, raw["rng"], "detail/raw RNG fold")
            if f <= 64:
                exact(lanes, [{"value": l["value"], "n": l["n"]} for l in latest[f]["lanes"]], "latest detail lanes")
            exact(finals[f], hash_final(raw_rows, rows, lanes), "raw/detail/pad final hash")
            details[f] = {"lanes": lanes, "fighters": rows}
            awaiting_detail = None
        elif kind == "END":
            need(index == len(records) - 1 and end is None, "END must be unique and last")
            need(len(passes) == 64 + correction and len(finals) == count and len(details) == count,
                 "incomplete window/tail before END")
            need(bool(mismatch) == bool(correction) and bool(complete) == bool(correction), "arm correction coverage")
            reads = sum(recipe["reads_per_lane"]) * (count + correction)
            predictions = recipe["reads_per_lane"][1] * (11 if correction else 1)
            wanted = dict(diagnostic=1, authoritative=0, pass_records=64 + correction, mismatches=correction,
                          completions=correction, final_records=count, detail_records=count, final_first=1,
                          final_last=count, window_finals=64, window_details=64, trace_passes=500 + correction,
                          trace_real=500, rows0=500 + correction, rows1=500 + correction, pad_reads=reads,
                          predicted_reads=predictions, padcheck_bad=0, local_submissions=count, phase=0,
                          left=0, pending_mismatch=0, verifier_pending=0, write_ok=1)
            for k, v in wanted.items():
                exact(obj[k], v, "END." + k)
            end = obj
        else:
            raise Invalid("unknown/duplicate/out-of-order net kind: " + kind)
    need(end is not None and awaiting_detail is None, "missing END/incomplete detail")
    return dict(arm=arm, latest=latest, passes=passes, finals=finals, details=details,
                complete=complete, end=end, trace=trace)


LOAD = re.compile(r"r1: RB NET: rollback ([0-9]+) at frame ([0-9]+): wrong guess at ([0-9]+), state of frame ([0-9]+) loaded in (" + FLOAT + r") ms, ([0-9]+) frames again")
RAW_VERIFY = re.compile(r"r1: RB VERIFY rollback to ([0-9]+), back at ([0-9]+): ([0-9]+) pages compared; differ: window 1 (-?[0-9]+), window 2 (-?[0-9]+), extras (-?[0-9]+);[^\r\n]*")
COMPLETE_LOG = re.compile(r"r1: LOOP VERIFY COMPLETE: token ([0-9]+) from ([0-9]+) to ([0-9]+) pages ([0-9]+); diagnostic only, external oracle required")
BAD_LOG = re.compile(r"fatal|refus|abort|exception|WITNESS_REJECT|WITNESS_ASSERT|PAD CHECK:|DESYNC:|"
                     r"watchdog|lockstep|late[- ]base|rollback[- ]off|rollback disabled|"
                     r"TEST_SCHED|TEST_LATEBASE|r1: TEST:|RB NET TEST|RB NET: (?:TEST|EH)|NOT held|"
                     r"snapshot unavailable|failed|error|WITHOUT rollback|\bWARNING\b|"
                     r"the base state was made|the base state is frame|base state was NOT made|"
                     r"no rollback ring|RING: no marks|RING load: .*still busy", re.I)


def check_summary(line, arm, recipe):
    """Known production zero-failure summaries are data, not warning events.

    Summaries are optional after the capture cutoff. Their absence never supplies
    a zero, and their presence never repairs missing PASS/END or process proof.
    """
    late, minimum = int(arm == "correction"), len(recipe["expected_inputs"])
    if line.startswith("[rbnet] report: pad check of the final simulations:"):
        exact(line, "[rbnet] report: pad check of the final simulations: 0 pad values differ from the final ones (first frame -1)", "bad-pad summary")
        return True
    if line.startswith("[rbnet] report: pads given "):
        m = re.fullmatch(r"\[rbnet\] report: pads given ([0-9]+), predicted ([0-9]+) \((" + FLOAT +
                         r")%\), mispredictions ([0-9]+); finalized frames ([0-9]+); checksums compared ([0-9]+), DESYNCS ([0-9]+) \(first (-?[0-9]+)\)", line)
        need(m is not None, "pad summary grammar")
        count, pred, percent, mis, final, checks, bad, first = m.groups()
        need(int(count) >= sum(recipe["reads_per_lane"]) * (minimum + late) and int(final) >= minimum,
             "pad summary undercoverage")
        exact(int(pred), recipe["reads_per_lane"][1] * (11 if late else 1), "pad summary predictions")
        exact(int(mis), late, "pad summary mismatches")
        exact((int(bad), int(first)), (0, -1), "pad summary desync")
        need(math.isfinite(float(percent)) and 0 <= float(percent) <= 100 and int(checks) >= 0, "pad summary percentage/count")
        return True
    if line.startswith("[rbnet] report: packets sent "):
        m = re.fullmatch(r"\[rbnet\] report: packets sent ([0-9]+) \(failed ([0-9]+)\), received ([0-9]+) \(bad ([0-9]+), queue full ([0-9]+)\); remote pads up to ([0-9]+), local up to ([0-9]+)", line)
        need(m is not None, "packet summary grammar")
        exact(tuple(int(m[i]) for i in range(1, 6)), (0, 0, 0, 0, 0), "loop packet summary")
        need(int(m[6]) >= minimum and int(m[7]) >= minimum, "packet summary input coverage")
        return True
    if line.startswith("r1: RB NET report: task-worker watchdog releases "):
        exact(line, "r1: RB NET report: task-worker watchdog releases 0 (since the process start), rollbacks with the workers not held 0 (watchdog paused at H2: yes)", "watchdog summary")
        return True
    if line.startswith("r1: RB NET report: loads that took the sound thread "):
        exact(line, "r1: RB NET report: loads that took the sound thread at another wait after 5 ms 0; threads not at their wait after 500 ms 0 (last load); loads refused, a thread still running (pub1) 0", "load/thread summary")
        return True
    if line.startswith("r1: RB NET report: stalls for the other player "):
        m = re.fullmatch(r"r1: RB NET report: stalls for the other player ([0-9]+) \((" + FLOAT +
                         r") ms in all; ([0-9]+) of them because the ring was short of memory\); captures failed ([0-9]+), re-run captures not needed ([0-9]+); load mean (" + FLOAT + r") ms; peer silent ([0-9]+)", line)
        need(m is not None, "capture summary grammar")
        exact(tuple(int(m[i]) for i in (3, 4, 5, 7)), (0, 0, 0, 0), "capture summary failures/skips")
        need(all(math.isfinite(float(m[i])) and float(m[i]) >= 0 for i in (2, 6)), "capture summary finite timings")
        return True
    if line.startswith("r1: RB NET report: ") and " real frames, " in line:
        m = re.fullmatch(r"r1: RB NET report: ([0-9]+) real frames, ([0-9]+) rollbacks, ([0-9]+) frames run again \(k: 1 ([0-9]+), 2 ([0-9]+), 3 ([0-9]+), 4 ([0-9]+), 5 ([0-9]+), 6 ([0-9]+), 7 ([0-9]+), more ([0-9]+)\); rollbacks impossible \(state not in the ring\) ([0-9]+)", line)
        need(m is not None and int(m[1]) >= minimum, "rollback summary grammar/coverage")
        exact(tuple(map(int, m.groups()[1:])), (late, late, late, 0, 0, 0, 0, 0, 0, 0, 0), "rollback summary counts")
        return True
    if line.startswith("r1: RA holds that failed (attempts):"):
        m = re.fullmatch(r"r1: RA holds that failed \(attempts\): task worker not blocked ([0-9]+), audio thread not blocked ([0-9]+), other thread ([0-9]+), a job fiber running ([0-9]+); site [0-9a-f]+; workers busy at H1 ([0-9]+), watchdog releases ([0-9]+); kicks skipped in speculative passes ([0-9]+), fighters' frame lines skipped ([0-9]+) \(mask ([0-9]+)\); command-buffer recordings saved (" + FLOAT + r") KB \(last\)", line)
        need(m is not None, "hold summary grammar")
        exact(tuple(map(int, m.groups()[:9])), (0,) * 9, "hold summary failures/skips")
        need(math.isfinite(float(m[10])) and float(m[10]) >= 0, "hold summary finite size")
        return True
    return False


def read_loop_successes(logs, arm, complete, recipe, match_id):
    """Cross-check success tuples and warnings across every supplied whole log."""
    loads, raw, completions, seals, bases, matches, exits, latencies = [], [], [], [], [], [], [], []
    for text in logs:
        for line in physical_lines(text):
            summary = check_summary(line, arm, recipe)
            need(summary or BAD_LOG.search(line) is None, arm + ": failure/warning in complete logs: " + line[:240])
            if "RB NET: rollback" in line:
                match = LOAD.fullmatch(line)
                need(match is not None, "unsupported/malformed rollback log")
                need(math.isfinite(float(match[5])) and float(match[5]) >= 0, "load timing")
                loads.append(tuple(int(match[k]) for k in (1, 2, 3, 4, 6)))
            if "RB VERIFY rollback" in line:
                match = RAW_VERIFY.fullmatch(line)
                need(match is not None, "malformed raw verifier log")
                raw.append(tuple(map(int, match.groups())))
            if "LOOP VERIFY COMPLETE" in line:
                match = COMPLETE_LOG.fullmatch(line)
                need(match is not None, "malformed completion log")
                completions.append(tuple(map(int, match.groups())))
            if "[trace]" in line:
                seals.append(line)
            if "RB NET: match start" in line:
                bases.append(line)
            if "[rbnet] match " in line and " start at frame " in line:
                matches.append(line)
            if line.startswith("exit="):
                exits.append(line)
            if "[rbnet] loop:" in line:
                latencies.append(line)
    correction = int(arm == "correction")
    exact(loads, [(1, 11, 11, 10, 1)] if correction else [], "whole-log load tuples")
    exact(raw, [(10, 11, complete["pages"], *complete["diff"])] if correction else [], "whole-log raw verifier tuples")
    exact(completions, [(1, 10, 11, complete["pages"])] if correction else [], "whole-log completion tuples")
    exact(seals, [f"[trace] diagnostic interval sealed: real 500/500 passes {500 + correction} reason none"], "trace success log")
    fight = recipe["mapping"]["fight_frame"]
    exact(bases, [f"r1: RB NET: match start, base state = frame 0 (fight frame {fight}); pacing 60 Hz; re-run skip mask 0, lite mask 0"], "base success log")
    need(len(matches) == 1 and re.fullmatch(r"\[rbnet\] match 1 \(id [0-9a-f]{8}\) start at frame 0: local player 1, input delay 1 frames \(round trip " + FLOAT + r" ms, best " + FLOAT + r" ms\)", matches[0]) is not None,
         "match/delay success log")
    need(f"(id {match_id})" in matches[0], "net/log match id")
    exact(latencies, [f"[rbnet] loop: remote pads arrive {correction} frames after the frame that would send them"], "whole-log loop arm")
    need(not exits or exits == ["exit=0"], "unsuccessful/duplicate supplied exit envelope")
    # A text envelope is only cross-checked. It never becomes exit attestation.
    return {"success_tuples": correction, "supplied_log_scan": "passed", "exit_attestation": "external_required"}


def compare_correction(oracle, correction, recipe):
    divergences, effects = [], []
    for f in range(1, 65):
        a, b = oracle["latest"][f], correction["latest"][f]
        fields = []
        if oracle["finals"][f] != correction["finals"][f]:
            fields.append("hash")
        ar = [projection_row(witness_row(r)) for r in a["fighters"]]
        br = [projection_row(witness_row(r)) for r in b["fighters"]]
        if ar != br:
            fields.append("raw_fighters")
        if oracle["details"][f] != correction["details"][f]:
            fields.append("detail/pads")
        if fields:
            divergences.append({"frame": f, "fields": fields})
    wrong = correction["passes"][10]
    reference = oracle["latest"][11]
    wrong_rows = {r["slot"]: witness_row(r) for r in wrong["fighters"]}
    reference_rows = {r["slot"]: witness_row(r) for r in reference["fighters"]}
    for slot in (0, 1):
        for field in recipe["effect_fields"]:
            if wrong_rows[slot][field] != reference_rows[slot][field]:
                effects.append({"slot": slot, "field": field, "speculative": wrong_rows[slot][field],
                                "oracle": reference_rows[slot][field]})
    equal = not divergences
    limited_pass = equal and (bool(effects) or not recipe["require_effect"])
    return {"projection_equal": equal, "projection_interval": [1, 64], "frames_compared": 64,
            "divergences": divergences, "earliest_divergence": divergences[0] if divergences else None,
            "meaningful_input_effect": bool(effects), "effect_contrast": effects,
            "correction_witness": True, "speculative_branch": wrong,
            "research_verdict": "corrected_projection_and_effect" if equal and effects else
                                "input_correction_path_only" if equal else "projection_inequality",
            "status": "valid_equal" if limited_pass else "valid_inequality", "exit_status": 0 if limited_pass else 1,
            "reasons": ["finalized projection differs"] if not equal else
                       ["predeclared gameplay fields unchanged; input/correction-path evidence only"] if not effects else []}


def fixed_verdict():
    return {"analyzer_version": 1, "resolved": False, "authoritative": 0, "gameplay_qualified": False,
            "native_ready": False, "native_accepted": False, "mutation_coverage": "unknown",
            "identity": "external_required", "admission": "external_required", "fixture": "external_required",
            "process_and_fatal": "external_required", "external_prerequisites": EXTERNAL_PREREQUISITES,
            "independent_binding_limits": COMPLETION_LIMITS,
            "historical_controls": {"november4_disabled_all_pass": True, "november4_enabled_all_pass": False,
                                    "batch_stopped": True, "resolved": False, "required_attempts_per_arm": 11,
                                    "observed_attempts_per_arm": [10, 10], "guest_progress_original_replay": [6, 4],
                                    "equal_x10_x12_triples": 10, "full_contexts_equal": False,
                                    "actual512": "ten source definition-before-use observations only; output convergence unproved",
                                    "older_failures": "8/11, scratch, identity and refusal failures preserved"},
            "known_aggregate_failures": ["audio-analysis", "postload-analysis", "queue-agreement",
                                         "audio-raw-completeness", "postload-raw-completeness",
                                         "postload-positive-source-branch", "independent-semantic-binding-provenance"]}


def analyze_packet(recipe, *, oracle_dir, correction_dir, schema_path, inputs=None):
    """Return deterministic diagnostic JSON data, including invalid evidence.

    The pure recipe object API binds canonical JSON; CLI additionally binds the
    original recipe bytes. No external gate is implemented or accepted by proxy.
    """
    result = fixed_verdict()
    inventory = inputs if inputs is not None else Inputs()
    bindings = result["bindings"] = {}
    try:
        validate_recipe(recipe)
        bindings["recipe_canonical_sha256"] = sha(json.dumps(recipe, sort_keys=True, separators=(",", ":"), allow_nan=False).encode())
        schema, bindings["schema"] = inventory.read(schema_path, MAX_RECIPE, "schema", lines=False)
        exact(bindings["schema"]["sha256"], SCHEMA_SHA256, "candidate schema bytes")
        helper, bindings["helper"] = inventory.read(HELPER, MAX_RECIPE, "whole trace helper", lines=False)
        _, bindings["analyzer"] = inventory.read(Path(__file__), MAX_RECIPE, "analyzer", lines=False)
        for supplied in (oracle_dir, correction_dir):
            path = Path(supplied).absolute()
            for parent in (path, *path.parents):
                need(not parent.is_symlink() and not getattr(parent, "is_junction", lambda: False)(),
                     "linked/junction arm root")
        roots = {"oracle": Path(oracle_dir).resolve(), "correction": Path(correction_dir).resolve()}
        need(roots["oracle"] != roots["correction"] and not any(a in b.parents for a, b in
             ((roots["oracle"], roots["correction"]), (roots["correction"], roots["oracle"]))), "arm directories must be disjoint")
        arms, reports = {}, {}
        for arm, root in roots.items():
            files = recipe["files"][arm]
            texts = {}
            bindings[arm] = {}
            for name in [files["net"], files["trace"], *files["logs"]]:
                path = root / name
                need(path.resolve().is_relative_to(root), "input escapes arm directory")
                texts[name], bindings[arm][name] = inventory.read(path, MAX_LOG if name in files["logs"] else MAX_DATA, arm + "/" + name)
            trace = read_raw_trace(texts[files["trace"]], helper, arm, recipe["work_on"])
            records = read_net(texts[files["net"]])
            evidence = validate_arm(records, trace, recipe, arm)
            logs = read_loop_successes([texts[n] for n in files["logs"]], arm, evidence["complete"], recipe,
                                       records[0][1].split()[-1])
            arms[arm] = evidence
            end = evidence["end"]
            reports[arm] = {"trace_passes": len(trace), "trace_real": 500, "replay_passes": int(arm == "correction"),
                            "net_finals": len(evidence["finals"]), "net_details": len(evidence["details"]),
                            "tail_relation": "coverage_and_internal_raw/detail/hash_join_only; no_cross_arm_equality",
                            "tail": {"first": 65, "last": end["final_last"], "count": max(0, end["final_last"] - 64)},
                            "logs": logs, "raw_completion": evidence["complete"]}
        inventory.verify()
        result.update(compare_correction(arms["oracle"], arms["correction"], recipe))
        result.update(trace_complete=True, net_complete=True, arms=reports)
    except (OSError, ValueError, OverflowError, RecursionError, struct.error) as exc:
        result.update(status="invalid", exit_status=2, reasons=[str(exc)], projection_equal=None,
                      meaningful_input_effect=None, correction_witness=False, trace_complete=False, net_complete=False)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for name in ("recipe", "schema", "oracle", "correction", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        # Reserve before reading: an existing result is never overwritten.
        with args.output.open("x", encoding="utf-8", newline="\n") as output:
            inputs = Inputs()
            try:
                text, binding = inputs.read(args.recipe, MAX_RECIPE, "recipe", lines=False)
                result = analyze_packet(strict_json(text), oracle_dir=args.oracle, correction_dir=args.correction,
                                        schema_path=args.schema, inputs=inputs)
                result["bindings"]["recipe_file"] = binding
            except (OSError, ValueError, RecursionError) as exc:
                result = dict(fixed_verdict(), status="invalid", exit_status=2, reasons=[str(exc)])
            encoded = json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
            output.write(encoded)
            output.flush()
            os.fsync(output.fileno())
        print(encoded, end="")
        return result["exit_status"]
    except OSError as exc:
        print(json.dumps(dict(fixed_verdict(), status="invalid", exit_status=2, reasons=[str(exc)]), sort_keys=True, separators=(",", ":")))
        return 2


if __name__ == "__main__":
    sys.exit(main())
