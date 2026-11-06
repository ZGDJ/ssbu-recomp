"""Source/synthetic only. No compiler, native child, build or capacity query.

Fixed segment/action vectors are independent expected values, not inferred from
the recipe generator or correction output. Existing analyzer writer fixtures are
reused for complete raw grammar and hostile mutations. Only the schema digest
gets a synthetic sentinel in binding tests, as in the existing analyzer tests;
the recipe/mapping/tape/parser/admission validators themselves are unmocked.
All disposable files live in this scope's ignored artifact directory.
"""
from contextlib import contextmanager
from copy import deepcopy
import hashlib
from pathlib import Path
import shutil
import sys
import tempfile
from types import ModuleType
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / 'artifacts/local/loop-packet-20261105/recipe'


def load(path, name):
    m = ModuleType(name)
    m.__file__ = str(path)
    sys.modules[name] = m
    exec(compile(path.read_bytes(), str(path), 'exec'), m.__dict__)
    return m


R = load(ROOT / 'tools/loop_experiment_recipe.py', 'loop_recipe_tests_subject')
W = load(ROOT / 'tests/test_loop_correction_analyzer.py', 'loop_recipe_existing_writer')

# (first raw bot frame, last, action, direction), computed independently from
# the accepted uint32 source segment words. No mixing/generator code in the
# expected-value builder; cover every segment through raw frame499.
SEGMENTS = {
    7: [(1, 24, 5, -1), (25, 41, 0, 1), (42, 70, 6, -1), (71, 80, 0, 1),
        (81, 105, 4, -1), (106, 121, 0, 1), (122, 145, 3, -1), (146, 170, 3, 1),
        (171, 197, 3, -1), (198, 208, 2, 1), (209, 225, 0, -1), (226, 245, 3, 1),
        (246, 274, 3, -1), (275, 285, 7, 1), (286, 298, 4, -1), (299, 304, 4, 1),
        (305, 314, 0, -1), (315, 332, 4, 1), (333, 342, 8, -1), (343, 351, 1, 1),
        (352, 367, 1, -1), (368, 387, 3, 1), (388, 416, 5, -1), (417, 432, 0, 1),
        (433, 461, 4, -1), (462, 482, 2, 1), (483, 498, 5, -1), (499, 499, 1, 1)],
    19: [(1, 9, 0, -1), (10, 17, 3, 1), (18, 33, 3, -1), (34, 57, 7, 1),
         (58, 70, 2, -1), (71, 76, 6, 1), (77, 84, 4, -1), (85, 100, 6, 1),
         (101, 117, 6, -1), (118, 127, 6, 1), (128, 155, 2, -1), (156, 171, 1, 1),
         (172, 187, 3, -1), (188, 205, 3, 1), (206, 214, 3, -1), (215, 228, 1, 1),
         (229, 237, 6, -1), (238, 261, 2, 1), (262, 274, 2, -1), (275, 291, 2, 1),
         (292, 315, 3, -1), (316, 339, 4, 1), (340, 349, 3, -1), (350, 375, 9, 1),
         (376, 401, 8, -1), (402, 417, 6, 1), (418, 435, 0, -1), (436, 444, 4, 1),
         (445, 457, 5, -1), (458, 480, 8, 1), (481, 497, 3, -1), (498, 499, 3, 1)],
}


def z():
    return dict(buttons='0000000000000000', lx=0, ly=0, rx=0, ry=0)


def known_pad(seed, raw_frame):
    first, last, action, direction = next(row for row in SEGMENTS[seed] if row[0] <= raw_frame <= row[1])
    result = z()
    if action in (2, 3, 7):
        result['lx'] = direction * 32767
    if action in (4, 7) or (action == 9 and (raw_frame - first) % 8 < 4):
        result['buttons'] = '0000000000000001'
    elif action == 5:
        result['buttons'] = '0000000000000002'
    elif action == 6 and (raw_frame - first) % 16 < 3:
        result['buttons'] = '0000000000000004'
    if action == 8:
        result['ly'] = -32767
    return result


def fixture():
    identities = {key: dict(sha256=hashlib.sha256(key.encode()).hexdigest(), size=12)
                  for key in R.IDENTITIES}
    return dict(identities=identities, settings=dict(R.FIXTURE_SETTINGS, SSBU_DEBUG_END='600'), native_seconds=900)


def admission_recipe(base, f):
    inputs = base / 'inputs'
    build, runtime, seq = inputs / 'build', inputs / 'runtime/package', inputs / 'setup.seq'
    seq.parent.mkdir(parents=True, exist_ok=True)
    seq.write_text('# synthetic setup\n0 A\n\n1 NONE\n', encoding='utf-8')
    arms = {}
    admission = R._existing_tool(ROOT, 'loop_replay_admission')
    for label, mode in (('loop-oracle', 'loop,0'), ('loop-correction', 'loop,1')):
        trial = base / label
        env = dict(R.ADMISSION_SETTINGS, **f['settings'], SSBU_RB_NET=mode,
                   SSBU_ROMFS=str(inputs / 'romfs'), SSBU_SEQ='0 A 1 NONE')
        env.update({key: str(trial / name) for key, name in admission.PATH_ENV.items()})
        arms[label] = dict(identity_path=str(trial / 'prelaunch-identity.json'), runtime=str(runtime),
                           build=str(build), sequence=str(seq), cwd=str(build / 'work'),
                           cmd=[str(build / 'work/synthetic-never-launch.exe'), str(inputs / 'code.bin'), '900'],
                           env=env, launcher=str(inputs / 'launcher.py'), identity_tool=str(inputs / 'identity.py'))
    return dict(format=1, interval=[1, 64], mismatch=11, load=10, replay=[11, 11], arms=arms)


def mapping(base=37, poll=142):
    return dict(trace_base=base, fight_frame=poll, first_fight_frame=poll, poll_base=poll)


SCHEMA = b'synthetic mapping binder grammar sentinel; never native evidence\n'
SCHEMA_HASH = hashlib.sha256(SCHEMA).hexdigest()


@contextmanager
def synthetic_schema():
    old_loader = R._existing_tool

    def loader(root, name):
        module = old_loader(root, name)
        if name == 'analyze_loop_correction':
            module.SCHEMA_SHA256 = SCHEMA_HASH
        return module
    with patch.object(R, 'SCHEMA_SHA256', SCHEMA_HASH), patch.object(R, '_existing_tool', loader):
        yield


class LoopExperimentRecipeTests(unittest.TestCase):
    def test_distinct_entries_follow_slots_not_write_order(self):
        passes = [dict(fighters=[dict(slot=1, e=3), dict(slot=0, e=5)])]
        R.validate_fighter_entry(passes, 1, 3)
        R.validate_fighter_entry(passes, 0, 5)
        for slot, entry in ((1, 5), (0, 3)):
            with self.assertRaises(R.Invalid):
                R.validate_fighter_entry(passes, slot, entry)
        with self.assertRaises(R.Invalid):
            R.validate_fighter_entry([dict(fighters=[dict(slot=0,e=5)] * 2)], 0, 5)

    def setUp(self):
        ARTIFACTS.mkdir(parents=True, exist_ok=True)
        temp = tempfile.TemporaryDirectory(prefix='synthetic-', dir=ARTIFACTS)
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name).resolve()
        self.fixture = fixture()
        self.admission = admission_recipe(self.base, self.fixture)

    def prepare(self, m=None, reads=None):
        return R.prepare_recipe(mapping=mapping() if m is None else m,
                                reads_per_lane=[2, 3] if reads is None else reads,
                                fixture=self.fixture, admission_recipe=self.admission)

    def test_sequence_is_expanded_frozen_text_not_path(self):
        self.prepare()
        row = self.admission['arms']['loop-oracle']
        for arm in self.admission['arms'].values():
            arm['env']['SSBU_SEQ'] = arm['sequence']
        with self.assertRaisesRegex(R.Invalid, 'expanded sequence'):
            self.prepare()
        for arm in self.admission['arms'].values():
            arm['env']['SSBU_SEQ'] = '0 A 1 NONE'
        Path(row['sequence']).write_text('0 B\n1 NONE\n', encoding='utf-8')
        with self.assertRaisesRegex(R.Invalid, 'expanded sequence'):
            self.prepare()

    def write_evidence(self, declaration):
        """Existing raw writer, with explicitly synthetic nondefault B/P."""
        a = declaration['analyzer']
        arm = W.make_arm('oracle', a)
        # The old writer fixture uses P0; explicitly restamp these known synthetic
        # observations without learning an offset from a correction file.
        poll = a['mapping']['poll_base']
        text = arm['net.txt']
        text = W.mutate_json(text, 'BASE', lambda o: o.update(fight_frame=poll, first_fight_frame=poll))
        for occurrence in range(64):
            text = W.mutate_json(text, 'PASS', lambda o: o.update(poll=poll + o['seq']), occurrence=occurrence)
        root = self.base / 'loop-oracle'
        root.mkdir()
        (root / 'net.log').write_text(text, encoding='utf-8', newline='\n')
        (root / 'fight.txt').write_text(arm['fight.txt'], encoding='utf-8', newline='\n')
        log = arm['run.log'].replace('(fight frame 0)', f'(fight frame {poll})')
        log += ('debug end: the run ends after 600 fight frames\n'
                'debug end: 601 fight frames reached at presented frame 1370 (SSBU_DEBUG_END): exit request, normal shutdown\n')
        (root / 'game.log').write_text(log, encoding='utf-8', newline='\n')
        for name in ('r1.log', 'launcher.log'):
            (root / name).write_text('synthetic complete companion log\n', encoding='utf-8')
        proofs = {}
        for role in R.PROOFS:
            p = self.base / (role + '.txt')
            p.write_bytes(SCHEMA if role == 'schema' else ('synthetic proof only: ' + role).encode())
            raw = p.read_bytes()
            proofs[role] = dict(path=str(p), sha256=hashlib.sha256(raw).hexdigest(), size=len(raw))
        fighters = [dict(lane=i, port=i, slot=1-i, entry=-1,
                         profile_sha256=self.fixture['identities']['profile' + str(i)]['sha256']) for i in (0, 1)]
        return dict(format=1, origin='admitted-oracle-before-correction', declaration_sha256=R.digest(declaration),
                    proofs=proofs, lane_fighters=fighters, debug_end=dict(fight_presents=601, presented_frame=1370))

    def test_all_raw_bot_values_match_fixed_segment_vectors(self):
        for seed in (7, 19):
            for f in range(1, 500):
                self.assertEqual(R.bot_pad(seed, f), known_pad(seed, f), (seed, f))

    def test_entire_delayed_tape_and_every_tail_pad(self):
        for base in (1, 37, 435):
            tape = R.expected_inputs(base)
            self.assertEqual(len(tape), 500 - base)
            self.assertEqual(tape[0], [z(), z()])
            for f in range(2, 501 - base):
                self.assertEqual(tape[f-1], [known_pad(7, f-1), known_pad(19, f-1)], (base, f))

    def test_known_delay_boundary_and_press_release_values(self):
        tape = R.expected_inputs(1)
        self.assertEqual(tape[1], [dict(z(), buttons='0000000000000002'), z()])
        self.assertEqual(tape[9][1], z())
        self.assertEqual(tape[10][1], dict(z(), lx=32767))
        self.assertEqual(tape[17][1], dict(z(), lx=32767))
        self.assertEqual(tape[18][1], dict(z(), lx=-32767))
        self.assertEqual(tape[42][0], dict(z(), buttons='0000000000000004'))
        self.assertEqual(tape[45][0], z())
        self.assertEqual(tape[376][1], dict(z(), ly=-32767))

    def test_invalid_seed_frame_base_and_bool_values(self):
        for seed, frame in ((True, 1), (8, 11), (7, True), (7, 0), (19, 501)):
            with self.subTest(seed=seed, frame=frame), self.assertRaises(R.Invalid):
                R.bot_pad(seed, frame)
        for base in (None, True, 0, 436, 1.0):
            with self.subTest(base=base), self.assertRaises(R.Invalid):
                R.expected_inputs(base)

    def test_nondefault_mapping_wrong_R11_and_final_S11_retained(self):
        oracle = R.expected_passes(mapping(), [2, 3], 'oracle')
        correction = R.expected_passes(mapping(), [2, 3], 'correction')
        wrong, right = correction[10:12]
        self.assertEqual((wrong['f'], wrong['phase'], wrong['trace_pass'], wrong['poll']), (11, 'R', 48, 153))
        self.assertEqual((right['f'], right['phase'], right['trace_pass'], right['poll']), (11, 'S', 49, 154))
        self.assertEqual(wrong['inputs'][1], z())
        self.assertEqual(right['inputs'][1], dict(z(), lx=32767))
        self.assertFalse(wrong['finalized'])
        self.assertTrue(right['finalized'])
        self.assertEqual(len(correction), 464)
        self.assertEqual((correction[-1]['f'], correction[-1]['trace_pass']), (463, 501))
        finals = [p for p in correction if p['finalized']]
        self.assertEqual([p['f'] for p in finals[:64]], list(range(1, 65)))
        self.assertEqual(finals[10], right)
        self.assertEqual((finals[63]['trace_pass'], finals[63]['poll']), (102, 207))
        self.assertEqual(oracle[-1]['trace_pass'], 500)
        self.assertEqual(sum(sum(p['predicted_reads']) for p in correction), 33)
        self.assertEqual(sum(sum(p['reads']) for p in correction), 2320)
        self.assertEqual(sum(sum(p['predicted_reads']) for p in oracle), 3)
        self.assertEqual(sum(sum(p['reads']) for p in oracle), 2315)

    def test_mapping_and_read_counts_have_no_defaults_or_inferred_offsets(self):
        bad = [dict(mapping(), trace_base=436), dict(mapping(), first_fight_frame=143),
               dict(mapping(), poll_base=143), dict(mapping(), trace_base=True), dict(trace_base=37)]
        for value in bad:
            with self.subTest(mapping=value), self.assertRaises(R.Invalid):
                self.prepare(m=value)
        for reads in ([], [1, 0], [1, 17], [True, 1], [2.0, 3], (2, 3)):
            with self.subTest(reads=reads), self.assertRaises(R.Invalid):
                self.prepare(reads=reads)

    def test_expected_counts_match_full_synthetic_writer_and_plan(self):
        declared = self.prepare()
        for arm in ('oracle', 'correction'):
            count = R.expected_counts(mapping(), [2, 3], arm)
            passes = R.expected_passes(mapping(), [2, 3], arm)
            net = W.make_arm(arm, declared['analyzer'])['net.txt']
            end = W.A.read_net(net)[-1][1]
            self.assertEqual(count['final_frames'], 463)
            self.assertEqual(count['pad_reads'], sum(sum(p['reads']) for p in passes))
            self.assertEqual(count['predicted_reads'], sum(sum(p['predicted_reads']) for p in passes))
            self.assertEqual(count['pad_reads'], end['pad_reads'])
            self.assertEqual(count['predicted_reads'], end['predicted_reads'])
            self.assertEqual(count['physical_passes'], end['trace_passes'])
            self.assertEqual(count['witness_passes'], end['pass_records'])

    def test_exact_existing_analyzer_and_admission_interoperability(self):
        declared = self.prepare()
        a = R._existing_tool(ROOT, 'analyze_loop_correction')
        n = R._existing_tool(ROOT, 'loop_replay_admission')
        self.assertEqual(declared['analyzer']['config'], a.CONFIG)
        self.assertEqual(R.ADMISSION_SETTINGS, n.SETTINGS)
        a.validate_recipe(declared['analyzer'])
        for label, row in declared['admission']['arms'].items():
            n.validate_loop_configuration(row['env'], row['identity_path'], recipe=declared['admission'], arm=label)
        self.assertEqual(len(declared['analyzer']['expected_inputs']), 463)
        self.assertEqual(declared['analyzer']['files'], dict(oracle=dict(net='net.log', trace='fight.txt', logs=['game.log', 'r1.log', 'launcher.log']),
                                                         correction=dict(net='net.log', trace='fight.txt', logs=['game.log', 'r1.log', 'launcher.log'])))
        self.assertIsNone(R.validate_recipe(declared))
        self.assertFalse(declared['native_ready'])

    def test_exact_contract_drift_rejected(self):
        for which, value in (('analyzer', dict(R.ANALYZER_CONFIG, SSBU_RB_NET_RECAP='0')),
                             ('analyzer', dict(R.ANALYZER_CONFIG, SSBU_RB_NET_SKIP='0')),
                             ('admission', dict(R.ADMISSION_SETTINGS, SSBU_RB_LOOP_WITNESS='0'))):
            with self.subTest(which=which), self.assertRaises(R.Invalid):
                R.validate_contracts(value if which == 'analyzer' else R.ANALYZER_CONFIG,
                                     value if which == 'admission' else R.ADMISSION_SETTINGS)

    def test_tape_tail_config_and_final_verdict_mutations_rejected(self):
        declared = self.prepare()
        mutations = [lambda b: b['analyzer']['expected_inputs'].pop(),
                     lambda b: b['analyzer']['expected_inputs'][-1][1].update(lx=123),
                     lambda b: b['analyzer']['expected_inputs'][10][1].update(lx=0),
                     lambda b: b['analyzer'].update(require_effect=0),
                     lambda b: b['analyzer'].update(work_on=1),
                     lambda b: b['analyzer'].update(interval=[2, 64]),
                     lambda b: b['analyzer']['config'].update(SSBU_RB_NET_RECAP='0'),
                     lambda b: b.update(native_ready=True), lambda b: b.update(authoritative=True),
                     lambda b: b.update(resolved=True)]
        for i, mutate in enumerate(mutations):
            bad = deepcopy(declared)
            mutate(bad)
            with self.subTest(mutation=i), self.assertRaises(ValueError):
                R.validate_recipe(bad)

    def test_cross_arm_optional_setting_and_schedule_changes_rejected(self):
        for key, value in (('SSBU_RB_NET', 'loop,0'), ('SSBU_FIXED_SEED', '2'),
                           ('SSBU_RB_NET_LOOP_JIT', '1'), ('SSBU_DEBUG_END', '601'),
                           ('SSBU_RB_NET_KEEP', '2'), ('SSBU_RB_SIM_SKIP', '49')):
            bad = deepcopy(self.admission)
            bad['arms']['loop-correction']['env'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                R.prepare_recipe(mapping=mapping(), reads_per_lane=[2, 3], fixture=self.fixture, admission_recipe=bad)

    def test_fixture_initialization_must_be_explicit_and_source_supported(self):
        for key, value in (('SSBU_RB_NET_AUTOP2', '0'), ('SSBU_RB_NET_LOOP_SEED', '1'),
                           ('SSBU_KEYBOARD_PLAYER', '1'), ('SSBU_FIXED_SEED', '0'),
                           ('SSBU_DEBUG_END', '10s'), ('SSBU_DEBUG_END', '500.0'), ('SSBU_DEBUG_END', '0')):
            f = deepcopy(self.fixture)
            f['settings'][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                R.prepare_recipe(mapping=mapping(), reads_per_lane=[2, 3], fixture=f, admission_recipe=admission_recipe(self.base, f))
        del self.fixture['identities']['profile1']
        with self.assertRaises(R.Invalid):
            self.prepare()

    def test_pinned_source_mutation_rejected_without_execution(self):
        mirror = self.base / 'source-mirror'
        for name in R.SOURCE_PINS:
            p = mirror / name
            p.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, p)
        R.validate_sources(mirror)
        with (mirror / 'runtime/rb_input.c').open('ab') as stream:
            stream.write(b'\n/* mutation */\n')
        with self.assertRaisesRegex(R.Invalid, 'source drift: runtime/rb_input.c'):
            R.validate_sources(mirror)

    def test_complete_synthetic_oracle_bind_checks_raws_but_never_readiness(self):
        with synthetic_schema():
            declared = self.prepare()
            evidence = self.write_evidence(declared)
            calls = []
            result = R.bind_oracle_mapping(declared, evidence, authenticate=lambda context: calls.append(context))
        self.assertEqual(len(calls), 1)
        self.assertEqual(result['mapping'], mapping())
        self.assertEqual(result['reads_per_lane'], [2, 3])
        self.assertEqual([f['slot'] for f in result['lane_fighters']], [1, 0])
        self.assertFalse(result['native_ready'])
        self.assertEqual(result['authoritative'], 0)
        self.assertFalse(result['resolved'])
        self.assertEqual(result['declaration_sha256'], R.digest(declared))
        self.assertIn('freeze_journal', result['bindings'])
        self.assertIn('net.log', result['bindings'])

    def test_missing_authenticator_or_proofs_cannot_promote_declaration(self):
        with synthetic_schema():
            declared = self.prepare()
            evidence = self.write_evidence(declared)
            with self.assertRaisesRegex(R.Invalid, 'authenticator required'):
                R.bind_oracle_mapping(declared, evidence, authenticate=None)
            del evidence['proofs']['lane_fighters']
            with self.assertRaisesRegex(R.Invalid, 'proof roles'):
                R.bind_oracle_mapping(declared, evidence, authenticate=lambda _: None)

    def test_no_bool_receipt_or_failed_authentication(self):
        with synthetic_schema():
            declared = self.prepare()
            evidence = self.write_evidence(declared)
            for result in (True, False, {'accepted': True}):
                with self.subTest(result=result), self.assertRaisesRegex(R.Invalid, 'never return a boolean/receipt'):
                    R.bind_oracle_mapping(declared, evidence, authenticate=lambda _: result)
            def refuse(_):
                raise ValueError('no original applied fixture readback')
            with self.assertRaisesRegex(ValueError, 'applied fixture'):
                R.bind_oracle_mapping(declared, evidence, authenticate=refuse)

    def test_correction_or_synthetic_mapping_origin_and_changed_subject_rejected(self):
        with synthetic_schema():
            declared = self.prepare()
            evidence = self.write_evidence(declared)
            for change in ({'origin': 'correction'}, {'origin': 'synthetic'}, {'declaration_sha256': '0' * 64}):
                bad = dict(evidence, **change)
                with self.subTest(change=change), self.assertRaises(R.Invalid):
                    R.bind_oracle_mapping(declared, bad, authenticate=lambda _: None)

    def test_observed_base_cannot_be_adjusted_or_learned_from_correction(self):
        with synthetic_schema():
            declared = self.prepare()
            evidence = self.write_evidence(declared)
            declared['analyzer']['mapping'].update(poll_base=143, fight_frame=143, first_fight_frame=143)
            # Rebuild declaration honestly; raw oracle still has independently
            # fixed P142. Merely freezing a different P cannot make it true.
            declared = self.prepare(m=declared['analyzer']['mapping'])
            evidence['declaration_sha256'] = R.digest(declared)
            with self.assertRaisesRegex(ValueError, 'BASE.fight_frame'):
                R.bind_oracle_mapping(declared, evidence, authenticate=lambda _: None)

    def test_observed_poll_cadence_read_count_and_tail_mutations_rejected(self):
        with synthetic_schema():
            declared = self.prepare()
            evidence = self.write_evidence(declared)
            p = self.base / 'loop-oracle/net.log'
            original = p.read_text(encoding='utf-8')
            mutations = [lambda t: W.mutate_json(t, 'PASS', lambda o: o.update(polls=2)),
                         lambda t: W.mutate_json(t, 'PASS', lambda o: o.update(poll=o['poll'] + 1)),
                         lambda t: W.mutate_json(t, 'PASS', lambda o: o['lanes'][1].update(n=4)),
                         lambda t: W.mutate_json(t, 'PASS', lambda o: o['lanes'][0].update(varied=1)),
                         lambda t: t.replace('d 463 p1 ', 'd 462 p1 ')]
            for i, mutate in enumerate(mutations):
                p.write_text(mutate(original), encoding='utf-8', newline='\n')
                with self.subTest(mutation=i), self.assertRaises(ValueError):
                    R.bind_oracle_mapping(declared, evidence, authenticate=lambda _: None)

    def test_lane_slot_profile_and_present_exit_are_independent_required_evidence(self):
        with synthetic_schema():
            declared = self.prepare()
            evidence = self.write_evidence(declared)
            mutations = [lambda e: e['lane_fighters'][0].update(slot=0),
                         lambda e: e['lane_fighters'][0].update(entry=0),
                         lambda e: e['lane_fighters'][0].update(port=1),
                         lambda e: e['lane_fighters'][0].update(profile_sha256='0' * 64),
                         lambda e: e['debug_end'].update(fight_presents=599),
                         lambda e: e['debug_end'].update(presented_frame=1371)]
            for i, mutate in enumerate(mutations):
                bad = deepcopy(evidence)
                mutate(bad)
                with self.subTest(mutation=i), self.assertRaises(ValueError):
                    R.bind_oracle_mapping(declared, bad, authenticate=lambda _: None)

    def test_debug_end_uses_real_source_grammar_not_trace_ordinal_or_poll(self):
        with synthetic_schema():
            declared = self.prepare()
            evidence = self.write_evidence(declared)
            p = self.base / 'loop-oracle/game.log'
            original = p.read_text(encoding='utf-8')
            mutations = [original.replace('after 600 fight frames', 'after 500 fight frames'),
                         original.replace('at presented frame 1370', 'at presented frame 500'),
                         original.replace('(SSBU_DEBUG_END): exit request, normal shutdown', '(SSBU_DEBUG_END): unknown'),
                         original + 'debug end: 601 fight frames reached at presented frame 1370 (SSBU_DEBUG_END): exit request, normal shutdown\n',
                         '\n'.join(line for line in original.splitlines() if '(SSBU_DEBUG_END)' not in line) + '\n']
            for i, mutated in enumerate(mutations):
                p.write_text(mutated, encoding='utf-8', newline='\n')
                with self.subTest(mutation=i), self.assertRaisesRegex(ValueError, 'DEBUG_END'):
                    R.bind_oracle_mapping(declared, evidence, authenticate=lambda _: None)

    def test_forged_proof_hash_schema_or_reused_file_rejected(self):
        with synthetic_schema():
            declared = self.prepare()
            evidence = self.write_evidence(declared)
            for role in ('schema', 'admission', 'fixture_initialization'):
                bad = deepcopy(evidence)
                bad['proofs'][role]['sha256'] = '0' * 64
                with self.subTest(role=role), self.assertRaises(ValueError):
                    R.bind_oracle_mapping(declared, bad, authenticate=lambda _: None)
            bad = deepcopy(evidence)
            bad['proofs']['postidentity'] = deepcopy(bad['proofs']['preidentity'])
            with self.assertRaisesRegex(ValueError, 'reused input'):
                R.bind_oracle_mapping(declared, bad, authenticate=lambda _: None)

    def test_authenticator_cannot_mutate_input_bytes_or_detached_subject(self):
        with synthetic_schema():
            declared = self.prepare()
            evidence = self.write_evidence(declared)
            def mutate_context(c):
                c['declaration']['analyzer']['mapping']['poll_base'] = 0
                c['evidence']['lane_fighters'][0]['slot'] = 0
            result = R.bind_oracle_mapping(declared, evidence, authenticate=mutate_context)
            self.assertEqual(result['mapping']['poll_base'], 142)
            self.assertEqual(result['lane_fighters'][0]['slot'], 1)
            def mutate_file(_):
                with (self.base / 'loop-oracle/net.log').open('ab') as stream:
                    stream.write(b'after freeze\n')
            with self.assertRaisesRegex(ValueError, 'changed after read'):
                R.bind_oracle_mapping(declared, evidence, authenticate=mutate_file)


if __name__ == '__main__':
    unittest.main()
