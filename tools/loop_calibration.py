"""Small observation over the existing witness; no launch, approval or defaults.

Only the separately admitted loop,0 calibration may discover B/P/read counts.
The final oracle is checked against a frozen declaration, never used to fit it.
Pass already verified analyzer/recipe modules from the packet driver. All raw
data is reread/rehash checked; END/exit/seals alone do not authenticate a trial.
"""
from pathlib import Path


POLICY = 'unordered-selected-fighters-v1'


def observe(directory, *, schema_path, analyzer, recipe_tool):
    root = Path(directory)
    inputs, bindings, texts = analyzer.Inputs(), {}, {}
    _, bindings['schema'] = inputs.read(schema_path, analyzer.MAX_RECIPE, 'schema', lines=False)
    analyzer.exact(bindings['schema']['sha256'], analyzer.SCHEMA_SHA256, 'calibration schema')
    helper, bindings['helper'] = inputs.read(analyzer.HELPER, analyzer.MAX_RECIPE, 'trace helper', lines=False)
    for name in ('fight.txt', 'net.log', 'game.log', 'r1.log', 'launcher.log'):
        texts[name], bindings[name] = inputs.read(root / name,
            analyzer.MAX_LOG if name.endswith('.log') and name != 'net.log' else analyzer.MAX_DATA, name)
    records = analyzer.read_net(texts['net.log'])
    analyzer.need(len(records) > 2 and records[1][0] == 'BASE' and records[2][0] == 'PASS',
                  'calibration m/BASE/PASS required')
    base, first = records[1][1], records[2][1]
    # These are observations, not defaults. Full validate_arm below checks
    # every witness, exact tail/read counts, and all raw/detail/hash joins.
    mapping = dict(trace_base=base['trace_base'], fight_frame=base['fight_frame'],
                   first_fight_frame=base['first_fight_frame'], poll_base=first['poll'] - 1)
    reads = [lane['n'] for lane in first['lanes']]
    recipe = recipe_tool.analysis_recipe(mapping, reads, POLICY)
    analyzer.validate_recipe(recipe)
    trace = analyzer.read_raw_trace(texts['fight.txt'], helper, 'calibration', 0)
    arm = analyzer.validate_arm(records, trace, recipe, 'oracle')
    analyzer.read_loop_successes([texts[n] for n in ('game.log', 'r1.log', 'launcher.log')],
                                'oracle', None, recipe, records[0][1].split()[-1])
    inputs.verify()
    return dict(format=1, kind='loop-calibration-observation', comparison=POLICY,
                mapping=mapping, reads_per_lane=reads, analysis_recipe=recipe,
                final_frames=len(arm['finals']), bindings=bindings,
                native_ready=False, authoritative=0, resolved=False,
                claims=['observed B/P, one-poll/+1 cadence and exact two-lane reads',
                        'all-correct BOT7/BOT19 tape and complete internal joins'],
                excluded_claims=['lane/profile-to-fighter association', 'cross-arm fighter identity',
                                 'corrected gameplay', 'native admission or safety acceptance'])
