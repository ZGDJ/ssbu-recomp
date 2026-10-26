"""Synthetic receipt contracts; these tests do not qualify native gameplay.

The fixture models P/C stores separately from observer receipts because a sink
can run after the P store and before its SignalEvent acceptance receipt.
"""
from __future__ import annotations

import copy
import hashlib
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
ANALYZER_PATH = ROOT / "tools" / "analyze_replay_queue.py"
ANALYZER_BYTES = ANALYZER_PATH.read_bytes()
sys.path.insert(0, str(ROOT / "tools"))
import analyze_replay_queue as analyzer

if ANALYZER_BYTES != ANALYZER_PATH.read_bytes():
    raise RuntimeError("Analyzer changed during import; rerun against a stable source")
ANALYZER_SHA256 = hashlib.sha256(ANALYZER_BYTES).hexdigest()

MASK = 0xFFFFFFFF
Q = 0x710529B840
SUBMIT = 0x710398BC70
SUBMIT_LR = 0x710398B444
CALLBACK_LR = 0x710398B968
TICK_LR = 0x710398BBF0
SIGNAL_EVENT = 0x7106DF60D0
SINK = 0x710373E620
PRODUCER = dict(actor=101, ctx=0x10000000)
CONSUMER = dict(actor=202, ctx=0x20000000)
HEX_FIELDS = {"ctx", "target", "lr", "a", "b", "arg", "p", "c", "value"}
EVENT_FIELDS = (
    "i", "ready", "stage", "kind", "token", "actor", "ctx", "target",
    "lr", "a", "b", "arg", "p", "c", "value", "data",
)
BEGIN = ("r1: QUEUE_PROBE_BEGIN v=1 target=119 queue=710529b840 "
         "capacity=512 authoritative=0")


def payload(seed):
    """Raw B0,A0,...,B3,A3 dwords, including high bits and distinct halves."""
    a = tuple((0xBF000000 + seed * 16 + i) & MASK for i in range(4))
    b = tuple((0x3F000000 + seed * 16 + i) & MASK for i in range(4))
    return tuple(word for pair in zip(b, a) for word in pair)


class QueueTrace:
    """Build receipts from explicit producer/store and sink/commit steps."""

    def __init__(self, p=6, c=4):
        self.p, self.c = p, c
        self.slots = [payload(i + 1) for i in range(4)]
        self.stage = 1
        self.events = []
        self.next_token = 1
        self.pending = None
        self.snapshot = (p, c, list(self.slots))
        self.held(1)

    def event(self, kind, token=0, **fields):
        event = dict.fromkeys(EVENT_FIELDS, 0)
        event.update(ready=1, stage=self.stage, kind=kind, token=token,
                     actor=303, p=self.p, c=self.c, data=(0,) * 8)
        event.update(fields)
        self.events.append(event)
        return event

    def token(self):
        value = self.next_token
        self.next_token += 1
        return value

    def held(self, boundary):
        if self.pending is not None:
            self.confirm(held=True)
        self.event(9, value=boundary, lr=1, target=SINK, arg=0, a=SUBMIT, b=Q)
        for slot, data in enumerate(self.slots):
            self.event(10, value=slot, data=data)

    def submit_enter(self, data, *, a=0x30000000, b=0x30000100):
        args = dict(**PRODUCER, lr=SUBMIT_LR, a=a, b=b, arg=Q)
        self.event(5, target=SUBMIT, **args)
        token = self.token()
        self.event(1, token, data=data, **args)
        return dict(token=token, data=data, args=args)

    def store(self, operation):
        if (self.p - self.c) & MASK >= 4:
            raise AssertionError("Fixture attempted a store into a full queue")
        operation["cursor"] = self.p
        self.slots[self.p & 3] = operation["data"]
        self.p = (self.p + 1) & MASK

    def signal(self, operation):
        args = dict(operation["args"], a=SIGNAL_EVENT)
        self.event(2, operation["token"], value=(operation["cursor"] + 1) & MASK,
                   data=operation["data"], **args)

    def submit_exit(self, operation):
        self.event(4, operation["token"], **operation["args"])

    def put(self, data):
        operation = self.submit_enter(data)
        if (self.p - self.c) & MASK < 4:
            self.store(operation)
            self.signal(operation)
        else:
            self.event(3, operation["token"], value=4, **operation["args"])
        self.submit_exit(operation)
        return operation

    def callback_enter(self, *, target=SINK, context=0):
        if self.p == self.c:
            raise AssertionError("Fixture attempted to consume an empty queue")
        if self.pending is not None:
            self.confirm()
        slot = Q + 0x138 + ((self.c & 3) << 5)
        operation = dict(token=self.token(), cursor=self.c)
        operation["args"] = dict(**CONSUMER, lr=CALLBACK_LR, target=target,
                                 a=slot, b=slot + 16, arg=context)
        self.event(6, operation["token"], value=self.c,
                   data=self.slots[self.c & 3], **operation["args"])
        return operation

    def callback_return(self, operation):
        self.event(7, operation["token"], **operation["args"])

    def commit(self, operation):
        self.c = (self.c + 1) & MASK
        self.pending = operation

    def confirm(self, *, held=False):
        operation = self.pending
        args = {} if held else dict(**CONSUMER, lr=TICK_LR)
        self.event(8, operation["token"], value=self.c, **args)
        self.pending = None

    def get(self, *, target=SINK, context=0, held_confirmation=False):
        operation = self.callback_enter(target=target, context=context)
        self.callback_return(operation)
        self.commit(operation)
        if not held_confirmation:
            self.confirm()
        return operation

    def restore(self, gap=None):
        self.held(2)
        self.stage = 2
        if gap is not None:
            gap(self)
        self.event(11, actor=0, p=0, c=0)
        self.p, self.c, slots = self.snapshot
        self.slots = list(slots)
        self.stage = 3
        self.held(3)

    def finish(self):
        self.held(4)
        return self.events


def ordinary_work(trace):
    trace.put(payload(10))
    trace.get()
    trace.put(payload(11))
    trace.get(held_confirmation=True)


def paired(original=ordinary_work, replay=None, *, p=6, c=4, gap=None):
    trace = QueueTrace(p=p, c=c)
    original(trace)
    trace.restore(gap)
    (original if replay is None else replay)(trace)
    return trace.finish()


def decisions_differ(*, target=SINK, context=0, replay_payload=None):
    def original(trace):
        trace.put(payload(10))  # full: rejected attempt still belongs in sequence
        trace.get()
        trace.put(payload(11))

    def replay(trace):
        trace.get(target=target, context=context)
        trace.put(payload(10) if replay_payload is None else replay_payload)
        trace.put(payload(11))  # full again after the one accepted enqueue

    return paired(original, replay, p=4, c=0)


def record(event, index):
    event = dict(event, i=index)
    fields = []
    for key in EVENT_FIELDS:
        value = event[key]
        if key == "data":
            value = ",".join(f"{word:08x}" for word in value)
        elif key in HEX_FIELDS:
            value = f"{value:x}"
        fields.append(f"{key}={value}")
    return "r1: QUEUE_PROBE_EVENT " + " ".join(fields)


def log(events, **end_changes):
    end = dict(count=len(events), errors=0, producer_active=0,
               consumer_active=0, pending=0, stage=4)
    end.update(end_changes)
    lines = [BEGIN, *(record(event, i) for i, event in enumerate(events))]
    lines.append("r1: QUEUE_PROBE_END " + " ".join(f"{k}={v}" for k, v in end.items()))
    return "\n".join(lines) + "\n"


def select(events, kind, *, stage=1, occurrence=0):
    return [event for event in events
            if event["stage"] == stage and event["kind"] == kind][occurrence]


class ReplayQueueAnalysisTests(unittest.TestCase):
    maxDiff = 2000

    def complete(self, events):
        result = analyzer.analyze(log(events))
        self.assertTrue(result["complete"], result.get("errors"))
        self.assertEqual(result["errors"], [])
        self.assertIn("bookkeeping", result["scope"])
        self.assertIn("not gameplay", result["scope"])
        return result

    def incomplete(self, events=None, *, text=None):
        result = analyzer.analyze(log(events) if text is None else text)
        self.assertFalse(result["complete"], result.get("finding", result))
        self.assertTrue(result["errors"], result)
        self.assertNotIn("consumer progress ordering is implicated", result.get("finding", ""))
        return result

    def ownership_finding(self, events):
        result = self.complete(events)
        self.assertRegex(result["finding"].lower(), r"ownership|callback.*(?:target|context|identity)")
        self.assertNotIn("consumer progress ordering is implicated", result["finding"])
        return result

    def test_complete_original_replay_pair_and_physical_slot_order(self):
        result = self.complete(paired())
        for name in ("original", "replay"):
            interval = result[name]
            self.assertEqual((interval["attempts"], interval["accepted"],
                              interval["rejected"], interval["dequeues"]), (2, 2, 0, 2))
            self.assertEqual((interval["start_occupancy"], interval["end_occupancy"]), (2, 2))
            self.assertEqual(interval["attempt_payloads"], [payload(10), payload(11)])
            self.assertEqual([callback["payload"] for callback in interval["callbacks"]],
                             [payload(1), payload(2)])
        self.assertEqual(result["gap_records"], 1)
        self.assertIn("decisions agree", result["finding"])

    def test_wraps_both_full_width_cursors_and_slot_indices(self):
        result = self.complete(paired(p=0xFFFFFFFF, c=0xFFFFFFFD))
        self.assertEqual(result["original"]["accepted"], 2)
        self.assertEqual(result["replay"]["dequeues"], 2)

    def test_accepts_fourth_slot_then_rejects_actual_full_attempt(self):
        def work(trace):
            trace.put(payload(10))
            trace.put(payload(11))
            trace.get()
        result = self.complete(paired(work, p=7, c=4))
        self.assertEqual(result["original"]["decisions"], [2, 3])
        self.assertEqual(result["original"]["attempts"], 2)
        self.assertEqual(result["original"]["accepted"], 1)
        self.assertEqual(result["original"]["rejected"], 1)

    def test_equal_ordered_attempts_different_full_decisions(self):
        result = self.complete(decisions_differ())
        self.assertEqual(result["original"]["attempt_payloads"], result["replay"]["attempt_payloads"])
        self.assertEqual(result["original"]["decisions"], [3, 2])
        self.assertEqual(result["replay"]["decisions"], [2, 3])
        self.assertIn("consumer progress ordering is implicated", result["finding"])

    def test_different_attempts_redirect_upstream_even_if_only_rejected_payload_differs(self):
        def work(data):
            def run(trace):
                trace.put(data)  # always rejected; accepted sequence remains empty
                trace.get()
            return run
        result = self.complete(paired(work(payload(10)), work(payload(12)), p=4, c=0))
        self.assertEqual(result["original"]["accepted"], 0)
        self.assertEqual(result["replay"]["accepted"], 0)
        self.assertIn("asynchronous submission sequence differs", result["finding"])

    def test_attempt_sequence_is_ordered_and_preserves_duplicate_occurrences(self):
        def work(items):
            def run(trace):
                trace.get()
                for item in items:
                    trace.put(payload(item))
            return run
        for left, right in (([10, 11], [11, 10]), ([10, 10], [10])):
            with self.subTest(left=left, right=right):
                result = self.complete(paired(work(left), work(right), p=4, c=0))
                self.assertIn("asynchronous submission sequence differs", result["finding"])

    def test_actual_callback_target_difference_takes_precedence_over_full_decisions(self):
        events = decisions_differ(target=SINK + 0x100)
        self.assertEqual(select(events, 9, stage=3)["target"], SINK)
        self.assertEqual(select(events, 6, stage=3)["target"], SINK + 0x100)
        self.ownership_finding(events)

    def test_actual_callback_context_difference_takes_precedence_over_full_decisions(self):
        self.ownership_finding(decisions_differ(context=0xDEAD0000))

    def test_actual_callback_identity_difference_is_reported_when_decisions_agree(self):
        def replay(trace):
            trace.put(payload(10))
            trace.get(target=SINK + 0x100, context=0x90000000)
            trace.put(payload(11))
            trace.get(target=SINK + 0x100, context=0x90000000)
        self.ownership_finding(paired(replay=replay))

    def test_callback_ownership_precedes_payload_sequence_comparison(self):
        self.ownership_finding(decisions_differ(target=SINK + 0x100,
                                               replay_payload=payload(12)))

    def test_changed_producer_context_cannot_support_equal_attempt_inference(self):
        events = decisions_differ()
        for event in events:
            if event["stage"] == 3 and event["kind"] in (1, 2, 3, 4, 5):
                event["ctx"] += 0x1000
        self.incomplete(events)

    def test_signal_receipt_can_follow_callback_return_and_c_commit(self):
        def work(trace):
            operation = trace.submit_enter(payload(10))
            trace.store(operation)
            trace.get()  # P store is visible before SignalEvent observation
            trace.signal(operation)
            trace.submit_exit(operation)
        result = self.complete(paired(work, p=0, c=0))
        self.assertEqual(result["original"]["callbacks"][0]["payload"], payload(10))

    def test_producer_and_consumer_may_overlap_without_two_producers(self):
        def work(trace):
            callback = trace.callback_enter()
            trace.put(payload(10))
            trace.callback_return(callback)
            trace.commit(callback)
            trace.confirm()
        self.complete(paired(work))

    def test_committed_c_can_free_capacity_before_its_confirmation_receipt(self):
        def work(trace):
            callback = trace.callback_enter()
            trace.callback_return(callback)
            trace.commit(callback)
            trace.put(payload(10))  # uses the freed fourth slot before kind 8
            trace.get()  # entry confirms the previous callback before starting
        result = self.complete(paired(work, p=4, c=0))
        self.assertEqual(result["original"]["decisions"], [2])
        self.assertEqual(result["original"]["dequeues"], 2)

    def test_repeated_payloads_reuse_slots_without_losing_cursor_identity(self):
        def work(trace):
            for _ in range(6):
                trace.put(payload(10))
                trace.get()
        result = self.complete(paired(work, p=0xFFFFFFFD, c=0xFFFFFFFD))
        self.assertEqual(result["original"]["attempts"], 6)
        self.assertEqual(result["original"]["dequeues"], 6)
        self.assertEqual(result["original"]["end_occupancy"], 0)

    def test_final_c_commit_may_be_confirmed_by_held_boundary(self):
        events = paired()
        confirmation = select(events, 8, occurrence=1)
        self.assertEqual((confirmation["ctx"], confirmation["lr"]), (0, 0))
        self.complete(events)

    def test_independent_complete_gap_work_is_retained_but_not_counted_as_replay(self):
        def gap(trace):
            trace.put(payload(50))
            trace.get()
        result = self.complete(paired(gap=gap))
        self.assertEqual(result["gap_records"], 8)
        self.assertEqual(result["original"]["attempts"], 2)
        self.assertEqual(result["replay"]["attempts"], 2)

    def test_rejects_empty_missing_duplicate_and_truncated_envelopes(self):
        good = log(paired())
        lines = good.splitlines()
        cases = {
            "empty": "", "no begin": "\n".join(lines[1:]),
            "no end": "\n".join(lines[:-1]), "duplicate": good + good,
            "duplicate begin": lines[0] + "\n" + good,
            "duplicate end": good + lines[-1],
            "truncated event": good.replace("data=00000000,", "data=", 1),
            "wrong queue": good.replace("queue=710529b840", "queue=710529b844"),
            "authoritative": good.replace("authoritative=0", "authoritative=1"),
            "wrong version": good.replace("v=1 target=119", "v=2 target=119"),
        }
        for name, text in cases.items():
            with self.subTest(case=name):
                self.incomplete(text=text)

    def test_envelope_must_surround_events(self):
        lines = log(paired()).splitlines()
        for name, changed in (
            ("late begin", [*lines[1:-1], lines[0], lines[-1]]),
            ("early end", [lines[0], lines[-1], *lines[1:-1]]),
        ):
            with self.subTest(case=name):
                self.incomplete(text="\n".join(changed))

    def test_unrelated_log_lines_are_allowed_but_unknown_probe_records_are_not(self):
        text = "runtime started\n" + log(paired()) + "runtime stopped\n"
        self.assertTrue(analyzer.analyze(text)["complete"])
        self.incomplete(text=text + "r1: QUEUE_PROBE_LOST count=1\n")

    def test_malformed_missing_extra_duplicate_and_nonnumeric_event_fields(self):
        good = log(paired())
        event = good.splitlines()[1]
        variants = (
            event.replace("actor=303 ", ""), event + " unexpected=1",
            event + " token=0", event.replace("ready=1", "ready=no"),
            event.replace("data=", "data=xyz,", 1),
            event.replace(" kind=9 ", " kind=9 broken "),
        )
        for replacement in variants:
            with self.subTest(record=replacement[:110]):
                self.incomplete(text=good.replace(event, replacement, 1))

    def test_incomplete_end_and_explicit_error_bits_fail_closed(self):
        for key, value in (("count", 513), ("count", 0), ("producer_active", 1),
                           ("consumer_active", 1), ("pending", 1), ("stage", 3),
                           *(("errors", 1 << bit) for bit in range(8))):
            with self.subTest(field=key, value=value):
                self.incomplete(text=log(paired(), **{key: value}))

    def test_refuses_missing_unpublished_or_misnumbered_records(self):
        events = paired()
        missing = copy.deepcopy(events)
        missing.remove(select(missing, 4))
        self.incomplete(missing)
        for key, value in (("ready", 0), ("stage", 0), ("kind", 12),
                           ("data", (0,) * 7)):
            with self.subTest(field=key):
                changed = copy.deepcopy(events)
                changed[0][key] = value
                self.incomplete(changed)
        self.incomplete(text=log(events).replace("i=1 ready=", "i=0 ready=", 1))

    def test_event_capacity_overflow_is_not_silently_truncated(self):
        events = paired()
        gap = next(i for i, event in enumerate(events) if event["kind"] == 11)
        events[gap:gap] = [copy.deepcopy(events[gap]) for _ in range(513 - len(events))]
        self.assertEqual(len(events), 513)
        self.incomplete(events)

    def test_numeric_records_obey_native_unsigned_and_token_widths(self):
        cases = (("p", 1 << 32), ("p", -1), ("c", 1 << 32),
                 ("value", 1 << 32), ("ctx", 1 << 64), ("target", -1),
                 ("actor", 1 << 32), ("actor", -1), ("token", -1),
                 ("token", 1 << 31), ("data", (1 << 32,) + (0,) * 7),
                 ("data", (-1,) + (0,) * 7))
        for field, value in cases:
            with self.subTest(field=field, value=value):
                events = paired()
                # Dispatch fields still have native widths even if not used in inference.
                select(events, 5)[field] = value
                self.incomplete(events)

    def test_consistent_but_out_of_range_actor_and_operation_tokens_are_invalid(self):
        for field, value in (("actor", 1 << 32), ("actor", -1),
                             ("token", 1 << 31)):
            with self.subTest(field=field, value=value):
                events = paired()
                if field == "actor":
                    # Preserve every identity equality so range checking is decisive.
                    for event in events:
                        if event["actor"] == PRODUCER["actor"]:
                            event["actor"] = value
                else:
                    token = select(events, 1)["token"]
                    for event in events:
                        if event["token"] == token:
                            event["token"] = value
                self.incomplete(events)

    def test_held_boundary_identity_occupancy_and_four_slots_are_required(self):
        for field, value in (("lr", 0), ("a", SUBMIT + 4), ("b", Q + 4), ("p", 20)):
            with self.subTest(field=field):
                events = paired()
                boundary = select(events, 9, occurrence=1)
                boundary[field] = value
                self.incomplete(events)
        for field, value in (("value", 3), ("p", 99), ("stage", 2)):
            with self.subTest(slot_field=field):
                events = paired()
                select(events, 10)[field] = value
                self.incomplete(events)
        events = paired()
        events.remove(select(events, 10))
        self.incomplete(events)

    def test_restored_start_includes_all_slots_and_callback_ownership(self):
        for field, value in (("p", 7), ("c", 3), ("target", SINK + 4), ("arg", 123)):
            with self.subTest(field=field):
                events = paired()
                select(events, 9, stage=3)[field] = value
                self.incomplete(events)
        events = paired()
        select(events, 10, stage=3, occurrence=3)["data"] = payload(90)
        self.incomplete(events)

    def test_unexplained_endpoint_cursor_advances_fail_even_with_valid_occupancy(self):
        for cursor in ("p", "c"):
            with self.subTest(cursor=cursor):
                events = paired()
                boundary_index = next(i for i, event in enumerate(events)
                                      if event["kind"] == 9 and event["value"] == 2)
                for event in events[boundary_index:boundary_index + 5]:
                    event[cursor] += 1
                self.incomplete(events)

    def test_fifo_checks_full_cursor_raw_payload_and_interleaved_input_words(self):
        for kind, field, value in ((2, "value", 8), (6, "value", 8),
                                   (6, "data", payload(90))):
            with self.subTest(kind=kind, field=field):
                events = paired()
                select(events, kind)[field] = value
                self.incomplete(events)
        events = paired()
        attempt = select(events, 1)
        data = attempt["data"]
        self.assertEqual(data[0::2], tuple(0x3F000000 + 160 + i for i in range(4)))
        self.assertEqual(data[1::2], tuple(0xBF000000 + 160 + i for i in range(4)))
        select(events, 2)["data"] = data[1::2] + data[0::2]  # concatenated A,B is wrong
        self.incomplete(events)

    def test_initial_and_newly_enqueued_fifo_entries_both_require_exact_payloads(self):
        def work(trace):
            trace.put(payload(10))
            trace.get()
            trace.get()
        events = paired(work, p=5, c=4)
        self.complete(events)
        for occurrence in (0, 1):
            with self.subTest(callback=occurrence):
                changed = copy.deepcopy(events)
                select(changed, 6, occurrence=occurrence)["data"] = payload(99)
                self.incomplete(changed)

    def test_final_slot_mutation_is_not_hidden_by_fifo_consumption(self):
        events = paired()
        select(events, 10, occurrence=4)["data"] = payload(99)
        self.incomplete(events)

    def test_full_rejection_must_be_actual_sampled_capacity(self):
        for value, p, c in ((3, 4, 0), (5, 5, 0), (4, 3, 0), (4, 4, 1)):
            with self.subTest(value=value, p=p, c=c):
                events = decisions_differ()
                select(events, 3).update(value=value, p=p, c=c)
                self.incomplete(events)

    def test_full_rejection_cannot_sample_cursors_that_never_existed(self):
        events = decisions_differ()
        select(events, 3).update(p=8, c=4)  # no four intervening C/P commits
        self.incomplete(events)

    def test_submission_dispatch_identity_and_acceptance_witness_are_required(self):
        for kind, field, value in ((5, "target", SUBMIT + 4), (5, "arg", Q + 4),
                                   (5, "ctx", 0), (1, "lr", SUBMIT_LR + 4),
                                   (2, "a", SIGNAL_EVENT + 4), (2, "p", 100),
                                   (2, "lr", SUBMIT_LR + 4)):
            with self.subTest(kind=kind, field=field):
                events = paired()
                select(events, kind)[field] = value
                self.incomplete(events)
        for kind in (2, 4, 5, 7, 8):
            with self.subTest(missing_kind=kind):
                events = paired()
                events.remove(select(events, kind))
                self.incomplete(events)

    def test_callback_return_alone_is_not_committed_dequeue(self):
        events = paired()
        events.remove(select(events, 8))
        self.incomplete(events)

    def test_callback_slot_addresses_return_cursor_and_confirmation_are_checked(self):
        for kind, field, value in ((6, "a", Q + 0x158), (6, "b", Q + 0x138),
                                   (6, "lr", CALLBACK_LR + 4), (7, "c", 5),
                                   (8, "c", 4), (8, "value", 6),
                                   (8, "actor", 999), (8, "ctx", 0x9999)):
            with self.subTest(kind=kind, field=field):
                events = paired()
                select(events, kind)[field] = value
                self.incomplete(events)

    def test_actor_identity_changes_and_producer_consumer_alias_are_incomplete(self):
        for kind in (1, 2, 4, 6, 7):
            with self.subTest(kind=kind):
                events = paired()
                select(events, kind)["actor"] = 909
                self.incomplete(events)
        events = paired()
        for event in events:
            if event["kind"] in (6, 7, 8) and event["ctx"]:
                event.update(PRODUCER)
        self.incomplete(events)

    def test_reused_or_stale_operation_tokens_cannot_claim_a_new_generation(self):
        events = paired()
        old = select(events, 1)["token"]
        replay_token = select(events, 1, stage=3)["token"]
        for event in events:
            if event["stage"] == 3 and event["token"] == replay_token:
                event["token"] = old
        self.incomplete(events)
        events = paired()
        select(events, 7, stage=3)["token"] = select(events, 6)["token"]
        self.incomplete(events)

    def test_stale_gap_signal_return_and_confirmation_are_not_ignored(self):
        for kind in (2, 7, 8):
            with self.subTest(kind=kind):
                events = paired()
                stale = dict(select(events, kind), stage=2)
                index = next(i for i, event in enumerate(events) if event["kind"] == 11)
                events.insert(index, stale)
                self.incomplete(events)

    def test_gap_operation_cannot_cross_restore_or_be_left_unresolved(self):
        def gap(trace):
            trace.put(payload(50))
        events = paired(gap=gap)
        exit_event = select(events, 4, stage=2)
        events.remove(exit_event)
        self.incomplete(events)
        events = paired(gap=gap)
        exit_event = select(events, 4, stage=2)
        events.remove(exit_event)
        exit_event["stage"] = 3
        boundary = next(i for i, event in enumerate(events)
                        if event["kind"] == 9 and event["value"] == 3)
        events.insert(boundary + 5, exit_event)
        self.incomplete(events)

    def test_load_preparation_must_occur_in_gap_exactly_once(self):
        events = paired()
        select(events, 11, stage=2)["stage"] = 1
        self.incomplete(events)
        events = paired()
        events.remove(select(events, 11, stage=2))
        self.incomplete(events)

    def test_work_cannot_appear_after_held_end_or_before_restored_start(self):
        events = paired()
        operation = [event for event in events if event["stage"] == 1 and event["kind"] in (1, 2, 4, 5)][:4]
        for event in operation:
            events.remove(event)
        boundary = next(i for i, event in enumerate(events)
                        if event["kind"] == 9 and event["value"] == 2)
        events[boundary + 5:boundary + 5] = operation
        self.incomplete(events)

    def test_two_producers_may_not_overlap_even_with_consistent_final_counters(self):
        def work(trace):
            trace.put(payload(10))
            trace.put(payload(11))
            trace.get()
        events = paired(work)
        first_exit = select(events, 4)
        second_start = select(events, 1, occurrence=1)
        second_dispatch = select(events, 5, occurrence=1)
        events.remove(second_dispatch)
        events.remove(second_start)
        position = events.index(first_exit)
        events[position:position] = [second_dispatch, second_start]
        self.incomplete(events)

    def test_second_callback_cannot_start_before_previous_c_commit_confirmation(self):
        events = paired()
        second_enter = select(events, 6, occurrence=1)
        events.remove(second_enter)
        position = events.index(select(events, 7))
        events.insert(position, second_enter)
        self.incomplete(events)

    def test_callback_cannot_consume_new_payload_before_its_submission_attempt(self):
        def work(trace):
            trace.put(payload(10))
            trace.get()
        events = paired(work, p=0, c=0)
        callbacks = [select(events, kind) for kind in (6, 7, 8)]
        for event in callbacks:
            events.remove(event)
        position = events.index(select(events, 5))
        events[position:position] = callbacks
        self.incomplete(events)

    def test_rejection_cannot_ignore_commit_confirmed_before_producer_entry(self):
        def work(trace):
            trace.get()
            operation=trace.submit_enter(payload(10))
            trace.event(3,operation['token'],value=4,p=4,c=0,**operation['args'])
            trace.submit_exit(operation)
        self.incomplete(paired(work,p=4,c=0))

    def test_rejection_may_precede_confirmation_after_producer_entry(self):
        def work(trace):
            operation=trace.submit_enter(payload(10))
            trace.get()
            trace.event(3,operation['token'],value=4,p=4,c=0,**operation['args'])
            trace.submit_exit(operation)
        self.complete(paired(work,p=4,c=0))

    def test_full_queue_cannot_accept_before_any_callback_has_returned(self):
        def work(trace):
            trace.get()
            trace.put(payload(10))
        events = paired(work, p=4, c=0)
        submission = [select(events, kind) for kind in (5, 1, 2, 4)]
        for event in submission:
            events.remove(event)
        position = events.index(select(events, 6))
        events[position:position] = submission
        self.incomplete(events)


if __name__ == "__main__":
    print(f"Analyzer SHA-256: {ANALYZER_SHA256}", file=sys.stderr, flush=True)
    unittest.main(verbosity=2)
