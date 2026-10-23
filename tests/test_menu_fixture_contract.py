"""M3.5 fixture contract: an original forward reference is comparable only under the pre-fight RNG identity it was
recorded with. Offline falsification test over retained records only (no game, no build, no runtime source).

Identity of the reference `bounded-forward-500-a` as the retained records define it (see
evidence/2026-10-23-menu-fixture-contract.md): menu interval length in sequence ticks, the sampled global xorshift128
vector at wait-begin, the sampled vector at confirm, the begin->confirm recurrence distance (the menu-interval
consumption count), the sampled vectors before and after the selector call that seeds the fight, the confirm->selector
distance (the post-confirm consumption count) and the owner seed (last word of the selector-after vector). Both
distances are recomputed here from the vectors rather than trusted from any file. The contract's verdict never reads
the reference gate: the gate is read separately to check that the contract's prediction agrees with what was retained.
Every retained file this test opens is named by repository path and pinned by SHA-256 below. Tape provenance is taken
from the absolute `--seq` path each command.json recorded, resolved relative to this checkout: on a relocated checkout
that raises rather than misclassifies.
"""
from pathlib import Path
import copy
import hashlib
import json
import unittest

ROOT = Path(__file__).resolve().parents[1]
MASK = 0xffffffff
DISTANCE_BOUND = 10000

# Pre-fight identity of the original reference, as carried by the earliest retained arm that records the interval
# (offline-initialization-next-20261022/baseline, executable 8b91dbf8...). Every accepted arm must reproduce it.
IDENTITY = {
    'interval_ticks': 91,
    'begin': [0x270810be, 0xd5359241, 0x34690e0d, 0xfc2d6112],
    'confirm': [0xc453539a, 0xb42451fb, 0x66af19c2, 0xec155499],
    'consumption': 78,
    'selector_before': [0xe85db69b, 0xd55f4f49, 0x1443f6da, 0xb29795b4],
    'selector_after': [0xd55f4f49, 0x1443f6da, 0xb29795b4, 0xb77b0413],
    'post_confirm_consumption': 20,
    'owner_seed': 0xb77b0413,
}
# The +60 arm as retained: same begin, 151 ticks, 130 advances, 40 more to the selector, owner seed fa10bec7. Used
# only to assert what the contract must reject.
WAIT_CONFIRM = [0xfec6ba1d, 0x669c9f22, 0x2aeec16b, 0x9acb5375]
WAIT_OWNER_SEED = 0xfa10bec7

INIT = 'artifacts/local/offline-initialization-next-20261022'
CONSUMER = 'artifacts/local/menu-consumer-20261023'
WRITER = 'artifacts/local/menu-writer-20261023'
CONTROLLED_TAPE = 'artifacts/local/save-import-20261021/controlled-sequence.txt'
WAIT_TAPE = INIT + '/wait-sequence.txt'

# Arms with an interval record on the original tape: the five agreeing same-tape runs.
ACCEPTED = [INIT + '/baseline', CONSUMER + '/disabled', CONSUMER + '/baseline', WRITER + '/disabled', WRITER + '/enabled']
# The preserved +60 reference failure (wait 150 instead of 90 at step 15).
REJECTED = [INIT + '/wait']
# Same tape, reference passed, menu observer disabled: no interval record, so the contract cannot classify it.
UNEVALUABLE = [INIT + '/disabled-attempt2']

RECORDS = {
    'artifacts/local/offline-initialization-next-20261022/baseline/boundary-analysis.json': '477c49261764ae023a512b338b2345948b64f6c95e5d1245c36a0b61f6ab2a26',
    'artifacts/local/offline-initialization-next-20261022/baseline/gates.json': 'b583c19dfadabab4db444fd2b86ba46e035716a130a62ca591898b5804c46202',
    'artifacts/local/offline-initialization-next-20261022/baseline/result.json': 'b7e95823f6a6e343c9539bdc269449d777a7d1cc4703dc1d710ff4fa36955cd1',
    'artifacts/local/offline-initialization-next-20261022/baseline/command.json': '9d7d0711eaa18bda0d2cb5a36c89ca2531fbd41764341b6e148630f71efe35c3',
    'artifacts/local/offline-initialization-next-20261022/baseline/reference.log': 'ae211e7170939f56c63b434904fa148659416820dc8324eeadbe1a75c891490c',
    'artifacts/local/offline-initialization-next-20261022/disabled-attempt2/boundary-analysis.json': 'd97fe8665b24628e9f8720be5fb61a88b0b439e2f522efaa53e35f5509ae93d3',
    'artifacts/local/offline-initialization-next-20261022/disabled-attempt2/gates.json': 'b583c19dfadabab4db444fd2b86ba46e035716a130a62ca591898b5804c46202',
    'artifacts/local/offline-initialization-next-20261022/disabled-attempt2/result.json': 'a0658c64f90ee844c853f54a0d4aa0c42738fb180f944b7db54c67916f7e899f',
    'artifacts/local/offline-initialization-next-20261022/disabled-attempt2/command.json': 'a2b8ba29ddb1726a725fd0ac910803ac79ebc25473a4c7ab2305bd9235658fdd',
    'artifacts/local/offline-initialization-next-20261022/disabled-attempt2/reference.log': 'ae211e7170939f56c63b434904fa148659416820dc8324eeadbe1a75c891490c',
    'artifacts/local/offline-initialization-next-20261022/wait/boundary-analysis.json': 'b963278561b130f6544f2cb8aaa3c7f079382f2cb2c95ca934fbe22f1f6231c4',
    'artifacts/local/offline-initialization-next-20261022/wait/gates.json': 'd754ba1b1246c550594dd925b2cfdd93b4144a0733fc6558ff0160a2ce725468',
    'artifacts/local/offline-initialization-next-20261022/wait/result.json': 'ad966355878df802ddf516cbef5bba5728e6ef15c75200cfe8ef0b2706e6ee0f',
    'artifacts/local/offline-initialization-next-20261022/wait/command.json': '34503d709cc332532aed7d12d3240349269bb45e8013bb706901fb5aa477f68f',
    'artifacts/local/offline-initialization-next-20261022/wait/reference.log': '975302c6fa22b149b203a4dd1504d5703bcd9af9ed2bcb254c4ff6530e36a3eb',
    'artifacts/local/menu-consumer-20261023/disabled/boundary-analysis.json': '50c0fd2f81b60b0c7929ba69628288d3a2805c5c5cc4e6192e54e4ad1b2d60e3',
    'artifacts/local/menu-consumer-20261023/disabled/gates.json': 'b583c19dfadabab4db444fd2b86ba46e035716a130a62ca591898b5804c46202',
    'artifacts/local/menu-consumer-20261023/disabled/result.json': '1b570866a82a35dc83968c6ec322ba03949cdb6a18eda167ddc38c2541ca8015',
    'artifacts/local/menu-consumer-20261023/disabled/command.json': '8fb89b71fa6b9145b1c53713e8bddc6684f00383adb8b040d8a78e5def250b22',
    'artifacts/local/menu-consumer-20261023/disabled/reference.log': 'ae211e7170939f56c63b434904fa148659416820dc8324eeadbe1a75c891490c',
    'artifacts/local/menu-consumer-20261023/baseline/boundary-analysis.json': '53f78a653211a605dbdd2628b8c0e1003d6cff6d06d7fbde3f82531f5bea37fb',
    'artifacts/local/menu-consumer-20261023/baseline/gates.json': 'b583c19dfadabab4db444fd2b86ba46e035716a130a62ca591898b5804c46202',
    'artifacts/local/menu-consumer-20261023/baseline/result.json': '56a84a381bdf34f394aadd086aae2e70781cfac6a359fe8629c940046c1cffa4',
    'artifacts/local/menu-consumer-20261023/baseline/command.json': 'f58f0c9409967449bc796503ada244721eb8afd87e9b884ca5c1ba27239859c2',
    'artifacts/local/menu-consumer-20261023/baseline/reference.log': 'ae211e7170939f56c63b434904fa148659416820dc8324eeadbe1a75c891490c',
    'artifacts/local/menu-writer-20261023/disabled/boundary-analysis.json': 'a3b27895469389cc9b6566373ce2eaea66d9918de786a4706f9cff66b6f30326',
    'artifacts/local/menu-writer-20261023/disabled/gates.json': '38378dd958661c07759e1e244a515acd74df51353cb9b73a7e0cdecbdfbc3eb1',
    'artifacts/local/menu-writer-20261023/disabled/result.json': '5bcf7caa8f74a475972aa2e40941ca698f342d42e6b79ab454530f70eb17651b',
    'artifacts/local/menu-writer-20261023/disabled/command.json': '8aaa556b68493443d29b537a4d35380f68ce4a77deb03db0531601a667163f26',
    'artifacts/local/menu-writer-20261023/disabled/reference.log': 'ae211e7170939f56c63b434904fa148659416820dc8324eeadbe1a75c891490c',
    'artifacts/local/menu-writer-20261023/enabled/boundary-analysis.json': '3a7f53b356b879c78a1d0752a1b39b4c73bf47b232379179822cb248f9b2206e',
    'artifacts/local/menu-writer-20261023/enabled/gates.json': '38378dd958661c07759e1e244a515acd74df51353cb9b73a7e0cdecbdfbc3eb1',
    'artifacts/local/menu-writer-20261023/enabled/result.json': '7e5c72b083f6eafd95d6eff97cf2d721e2a0479b2d7944e825b11692eb2ac53d',
    'artifacts/local/menu-writer-20261023/enabled/command.json': 'af20e9340f9c218e61ecd9b8c5e69ec6fc7c7b18b00dfa45f75cb17559edebcd',
    'artifacts/local/menu-writer-20261023/enabled/reference.log': 'ae211e7170939f56c63b434904fa148659416820dc8324eeadbe1a75c891490c',
    'artifacts/local/save-import-20261021/controlled-sequence.txt': '2fd61c62b48cd52c909eb44b08b51832a9294b25bf1bd26b0a629652089f8760',
    'artifacts/local/offline-initialization-next-20261022/wait-sequence.txt': '05307f1ab26d16f7dd85b1e42fda14e0b168f016e77f120c1de6019a9f2bc77c',
}


def read_retained(rel):
    """Bytes of a pinned retained file; a missing, moved or edited record fails rather than being reinterpreted."""
    path = ROOT / rel
    if not path.is_file():
        raise AssertionError(f'retained record missing: {rel}')
    data = path.read_bytes()
    actual = hashlib.sha256(data).hexdigest()
    if actual != RECORDS[rel]:
        raise AssertionError(f'retained record changed: {rel} {actual} != {RECORDS[rel]}')
    return data


def advance(state):
    """One xorshift128 step of the four global words (the recurrence the boundary analyzers used)."""
    a, b, c, d = state
    t = (a ^ (a << 11)) & MASK
    return [b, c, d, (t ^ (t >> 8) ^ d ^ (d >> 19)) & MASK]


def recurrence_distance(begin, confirm, bound=DISTANCE_BOUND):
    """Smallest n <= bound with advance^n(begin) == confirm, else None. Algebraic distance, not an observed call count."""
    state = list(begin)
    for n in range(bound + 1):
        if state == list(confirm):
            return n
        state = advance(state)
    return None


def prefight_identity(boundary):
    """The contract's identity fields from a boundary-analysis.json record, or None when the arm has no interval record
    (menu observer disabled or unusable). The consumption count is recomputed from the vectors."""
    if boundary.get('menu_disabled') or not boundary.get('usable') or 'vectors' not in boundary:
        return None
    menu = boundary['menu']
    if not menu.get('usable') or len(menu.get('records', [])) != 2:
        return None
    vectors = boundary['vectors']
    if 'interval_sequence_ticks' not in menu:
        return None
    try:
        begin, confirm = vectors['begin'], vectors['confirm']
        before, after = vectors['selector_before'], vectors['selector_after']
    except KeyError:
        return None
    if any(len(v) != 4 for v in (begin, confirm, before, after)):
        return None
    return {'interval_ticks': menu['interval_sequence_ticks'], 'begin': list(begin), 'confirm': list(confirm),
            'consumption': recurrence_distance(begin, confirm),
            'selector_before': list(before), 'selector_after': list(after),
            'post_confirm_consumption': recurrence_distance(confirm, before), 'owner_seed': after[3]}


def evaluate(boundary, identity=IDENTITY):
    """Contract verdict for one arm against the reference identity: ('comparable', []) or ('not_comparable', reasons)
    or ('no_interval_record', ['missing']). Reads no gate result and no file name."""
    actual = prefight_identity(boundary)
    if actual is None:
        return 'no_interval_record', ['missing']
    reasons = []
    if actual['interval_ticks'] != identity['interval_ticks']:
        reasons.append(f"interval {actual['interval_ticks']} != {identity['interval_ticks']}")
    if actual['begin'] != identity['begin']:
        reasons.append('begin vector differs')
    if actual['confirm'] != identity['confirm']:
        reasons.append('confirm vector differs')
    if actual['consumption'] != identity['consumption']:
        reasons.append(f"consumption {actual['consumption']} != {identity['consumption']}")
    if actual['selector_before'] != identity['selector_before'] or actual['selector_after'] != identity['selector_after']:
        reasons.append('selector vectors differ')
    if actual['post_confirm_consumption'] != identity['post_confirm_consumption']:
        reasons.append(f"post-confirm consumption {actual['post_confirm_consumption']} != {identity['post_confirm_consumption']}")
    if actual['owner_seed'] != identity['owner_seed']:
        reasons.append(f"owner seed {actual['owner_seed']:08x} != {identity['owner_seed']:08x}")
    return ('comparable' if not reasons else 'not_comparable'), reasons


def falsified(verdict, reference_passed):
    """The contract is falsified by a comparable run that fails the original reference. A non-comparable run passing
    it does not falsify (the contract states a necessary condition), and an unevaluable run says nothing."""
    return verdict == 'comparable' and not reference_passed


def load_arm(rel):
    boundary = json.loads(read_retained(rel + '/boundary-analysis.json'))
    gates = {g['name']: g['exit'] for g in json.loads(read_retained(rel + '/gates.json'))}
    result = json.loads(read_retained(rel + '/result.json'))
    command = json.loads(read_retained(rel + '/command.json'))
    reference_log = read_retained(rel + '/reference.log').decode()
    tape = Path(command[command.index('--seq') + 1])
    tape_rel = tape.resolve().relative_to(ROOT).as_posix()
    return {'boundary': boundary, 'gates': gates, 'result': result, 'tape': tape_rel,
            'tape_sha256': hashlib.sha256(read_retained(tape_rel)).hexdigest(), 'reference_log': reference_log}


class RetainedRecordTests(unittest.TestCase):
    def test_every_pinned_record_present_and_unchanged(self):
        for rel in RECORDS:
            read_retained(rel)

    def test_identity_constants_match_the_baseline_record(self):
        arm = load_arm(INIT + '/baseline')
        self.assertEqual(prefight_identity(arm['boundary']), IDENTITY)
        self.assertEqual(arm['boundary']['algebraic_distances']['begin_to_confirm'], [IDENTITY['consumption']])
        self.assertEqual(arm['boundary']['algebraic_distances']['confirm_to_selector_before'], [IDENTITY['post_confirm_consumption']])
        self.assertEqual(arm['boundary']['algebraic_distances']['selector_before_to_selector_after'], [1])
        self.assertEqual(arm['tape_sha256'], RECORDS[CONTROLLED_TAPE])
        self.assertEqual([r['wait'] for r in arm['boundary']['menu']['records']], [90, 90])

    def test_tapes_differ_only_in_the_step_15_wait(self):
        controlled = read_retained(CONTROLLED_TAPE).decode().splitlines()
        wait = read_retained(WAIT_TAPE).decode().splitlines()
        self.assertEqual(len(controlled), len(wait))
        diff = [(a, b) for a, b in zip(controlled, wait) if a != b]
        self.assertEqual(diff, [('90:Z', '150:Z')])


class ContractTests(unittest.TestCase):
    def test_accepted_same_tape_arms(self):
        executables = set()
        for rel in ACCEPTED:
            with self.subTest(arm=rel):
                arm = load_arm(rel)
                verdict, reasons = evaluate(arm['boundary'])
                self.assertEqual((verdict, reasons), ('comparable', []))
                self.assertEqual(arm['tape_sha256'], RECORDS[CONTROLLED_TAPE])
                self.assertEqual([r['wait'] for r in arm['boundary']['menu']['records']], [90, 90])
                self.assertEqual(arm['boundary']['reference'], 'passed')
                self.assertEqual(arm['gates']['reference'], 0)
                self.assertEqual(arm['gates']['fatal'], 0)
                self.assertIn('IDENTICAL fighter telemetry: real=500', arm['reference_log'])
                self.assertFalse(falsified(verdict, arm['gates']['reference'] == 0))
                executables.add(arm['result']['sha256'])
        self.assertEqual(len(ACCEPTED), 5)
        # Three distinct frozen executables reproduce the same identity on the same tape.
        self.assertEqual(len(executables), 3)

    def test_rejected_wait_arm_by_criterion(self):
        arm = load_arm(REJECTED[0])
        verdict, reasons = evaluate(arm['boundary'])
        self.assertEqual(verdict, 'not_comparable')
        self.assertEqual(reasons, ['interval 151 != 91', 'confirm vector differs', 'consumption 130 != 78',
                                   'selector vectors differ', 'post-confirm consumption 40 != 20',
                                   'owner seed fa10bec7 != b77b0413'])
        actual = prefight_identity(arm['boundary'])
        self.assertEqual(actual['begin'], IDENTITY['begin'])
        self.assertEqual(actual['confirm'], WAIT_CONFIRM)
        self.assertEqual(actual['owner_seed'], WAIT_OWNER_SEED)
        self.assertEqual(arm['boundary']['algebraic_distances']['begin_to_confirm'], [130])
        self.assertEqual(arm['boundary']['algebraic_distances']['confirm_to_selector_before'], [40])
        self.assertEqual(arm['tape_sha256'], RECORDS[WAIT_TAPE])
        self.assertEqual([r['wait'] for r in arm['boundary']['menu']['records']], [150, 150])
        # The retained outcome: the reference gate failed at real frame 2. The contract predicts non-comparability
        # and therefore is not falsified by this failure.
        self.assertEqual(arm['boundary']['reference'], 'FAILED')
        self.assertEqual(arm['gates']['reference'], 1)
        self.assertEqual(arm['gates']['fatal'], 0)
        self.assertIn('differs at real frame 2', arm['reference_log'])
        self.assertFalse(falsified(verdict, False))

    def test_unevaluable_arm_is_not_classified(self):
        arm = load_arm(UNEVALUABLE[0])
        self.assertTrue(arm['boundary']['menu_disabled'])
        self.assertEqual(evaluate(arm['boundary']), ('no_interval_record', ['missing']))
        self.assertEqual(arm['boundary']['reference'], 'passed')
        self.assertEqual(arm['tape_sha256'], RECORDS[CONTROLLED_TAPE])
        self.assertFalse(falsified('no_interval_record', True))

    def test_no_accepted_arm_is_listed_twice_or_as_rejected(self):
        listed = ACCEPTED + REJECTED + UNEVALUABLE
        self.assertEqual(len(listed), len(set(listed)))


class NegativeMutationTests(unittest.TestCase):
    """Mutations are applied to in-memory copies of the retained records; no retained file is written."""

    def setUp(self):
        self.baseline = load_arm(INIT + '/baseline')['boundary']
        self.wait = load_arm(INIT + '/wait')['boundary']

    def mutated(self, record, **changes):
        copy_ = copy.deepcopy(record)
        for key, value in changes.items():
            target = copy_
            parts = key.split('.')
            for part in parts[:-1]:
                target = target[part]
            target[parts[-1]] = value
        return copy_

    def test_wait_vectors_with_matching_interval_are_still_rejected(self):
        m = self.mutated(self.wait, **{'menu.interval_sequence_ticks': 91})
        verdict, reasons = evaluate(m)
        self.assertEqual(verdict, 'not_comparable')
        self.assertEqual(reasons[:2], ['confirm vector differs', 'consumption 130 != 78'])

    def test_baseline_vectors_with_wait_interval_are_rejected(self):
        m = self.mutated(self.baseline, **{'menu.interval_sequence_ticks': 151})
        self.assertEqual(evaluate(m), ('not_comparable', ['interval 151 != 91']))

    def test_one_extra_advance_is_rejected(self):
        m = self.mutated(self.baseline, **{'vectors.confirm': advance(IDENTITY['confirm'])})
        self.assertEqual(evaluate(m), ('not_comparable', ['confirm vector differs', 'consumption 79 != 78',
                                                          'post-confirm consumption 19 != 20']))

    def test_different_begin_with_same_distance_is_rejected(self):
        begin = advance(IDENTITY['begin'])
        confirm = advance(IDENTITY['confirm'])
        before, after = advance(IDENTITY['selector_before']), advance(IDENTITY['selector_after'])
        m = self.mutated(self.baseline, **{'vectors.begin': begin, 'vectors.confirm': confirm,
                                           'vectors.selector_before': before, 'vectors.selector_after': after})
        self.assertEqual(prefight_identity(m)['consumption'], 78)
        self.assertEqual(prefight_identity(m)['post_confirm_consumption'], 20)
        self.assertEqual(evaluate(m)[0], 'not_comparable')
        self.assertEqual(evaluate(m)[1][:3], ['begin vector differs', 'confirm vector differs', 'selector vectors differ'])

    def test_equal_interval_identity_with_wait_selector_segment_is_rejected(self):
        """The round-1 objection: equal interval, begin, confirm and 78, but the post-confirm segment of the wait arm."""
        m = self.mutated(self.baseline, **{'vectors.selector_before': self.wait['vectors']['selector_before'],
                                           'vectors.selector_after': self.wait['vectors']['selector_after']})
        verdict, reasons = evaluate(m)
        self.assertEqual(verdict, 'not_comparable')
        self.assertEqual(reasons[0], 'selector vectors differ')
        self.assertEqual(reasons[-1], 'owner seed fa10bec7 != b77b0413')
        self.assertIn('post-confirm consumption', ' '.join(reasons))

    def test_one_extra_post_confirm_advance_is_rejected(self):
        before, after = advance(IDENTITY['selector_before']), advance(IDENTITY['selector_after'])
        m = self.mutated(self.baseline, **{'vectors.selector_before': before, 'vectors.selector_after': after})
        self.assertEqual(evaluate(m)[1][:2], ['selector vectors differ', 'post-confirm consumption 21 != 20'])

    def test_recorded_distance_field_is_not_trusted(self):
        m = self.mutated(self.wait, **{'algebraic_distances.begin_to_confirm': [78]})
        verdict, reasons = evaluate(m)
        self.assertEqual(verdict, 'not_comparable')
        self.assertIn('consumption 130 != 78', reasons)

    def test_gate_result_does_not_drive_the_verdict(self):
        m = self.mutated(self.wait, reference='passed')
        self.assertEqual(evaluate(m)[0], 'not_comparable')
        m = self.mutated(self.baseline, reference='FAILED')
        self.assertEqual(evaluate(m)[0], 'comparable')

    def test_comparable_run_failing_the_reference_would_falsify(self):
        m = self.mutated(self.baseline, reference='FAILED')
        self.assertTrue(falsified(evaluate(m)[0], False))

    def test_unreachable_confirm_is_rejected(self):
        m = self.mutated(self.baseline, **{'vectors.confirm': [0, 0, 0, 0]})
        self.assertIsNone(prefight_identity(m)['consumption'])
        self.assertEqual(evaluate(m)[0], 'not_comparable')

    def test_missing_or_partial_interval_record_is_unevaluable(self):
        self.assertEqual(evaluate(self.mutated(self.baseline, menu_disabled=True))[0], 'no_interval_record')
        self.assertEqual(evaluate(self.mutated(self.baseline, usable=False))[0], 'no_interval_record')
        self.assertEqual(evaluate(self.mutated(self.baseline, **{'menu.usable': False}))[0], 'no_interval_record')
        self.assertEqual(evaluate(self.mutated(self.baseline, **{'menu.records': []}))[0], 'no_interval_record')
        menu = {k: v for k, v in self.baseline['menu'].items() if k != 'interval_sequence_ticks'}
        self.assertEqual(evaluate(self.mutated(self.baseline, menu=menu))[0], 'no_interval_record')
        vectors = {k: v for k, v in self.baseline['vectors'].items() if k != 'selector_after'}
        self.assertEqual(evaluate(self.mutated(self.baseline, vectors=vectors))[0], 'no_interval_record')

    def test_tampered_retained_bytes_are_refused(self):
        rel = INIT + '/wait/boundary-analysis.json'
        original = RECORDS[rel]
        RECORDS[rel] = '0' * 64
        try:
            with self.assertRaises(AssertionError):
                read_retained(rel)
        finally:
            RECORDS[rel] = original


if __name__ == '__main__':
    unittest.main()
