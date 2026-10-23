"""Offline synthetic pair artifacts: no games, compilers, or private inputs."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
import uuid
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
sys.path.insert(0,str(ROOT/'scripts'))
from check_initialization_pair import (inspect_pair, REQUIRED, PROBES, ENABLED, AGREED,
                                      digest, file_id, scalar, immutable_digest, REQUIRED_OUTPUTS)
from run_initialization_pair import admit, main
from check_runtime_trial import inspect_trial


def trace():
    rows=[]
    for i in range(1,501):
        for s in (0,1): rows.append(f'F {i} e {s} st 0 mot 0 mf 0 x 0 y 0 dmg 0 rngcalls 0 rng 0 H 0  () slot {s}')
        rows.append(f'TRACE_PASS {i} R')
    return '\n'.join(rows)+'\nTRACE_END diagnostic=1 target=500 real=500 passes=500 rows0=500 rows1=500 pending=0\n'


class PairTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.out=Path(self.temp.name)
        self.reference=self.out/'original.txt'; self.reference.write_text(trace())
        self.tape=self.out/'tape.txt'; self.tape.write_text('@fight NONE:500\n')
        self.plan=dict(instrumented=False,seed=1,port=39520,seconds=900,exe='probe.exe',
                       reference=str(self.reference),reference_identity=file_id(self.reference),
                       environment={'SSBU_ROMFS':str(self.out/'romfs'),'SSBU_DEBUG_MATCH':'p1=mario,p2=human,stage=end,stock=1'},
                       expected_match=dict(p1_chara=1,p1_colour=0,p1_controls='none',p2_chara=2,p2_colour=0,p2_controls='none',stage=1,form=0,flags=0,second=0,hazards=0,items=0,rule_kind=1,stocks=1),
                       expected_ready=dict(p1_kind=0,p2_kind=1,stage_id=1,rule_stock=1),
                       package_source='a'*64,package_executable={'sha256':'b'*64,'size':1},
                       save_identity={'sha256':'c'*64,'files':1,'bytes':1},
                       cache_identity={'sha256':'d'*64,'files':1,'bytes':1},
                       peers={r:dict(build=str(self.out/(r+'-build')),sequence=str(self.tape)) for r in ('host','join')})
        self.attempt_id=str(uuid.uuid4())
        self.ids={}; self.commands={}
        for role in ('host','join'):
            p=self.out/role; p.mkdir()
            env=dict(self.plan['environment'],**REQUIRED)
            env.update(SSBU_RB_NET_SEED='1',SSBU_FIXED_SEED='1',SSBU_ONLINE=('host:' if role=='host' else 'join:127.0.0.1:')+'39520',
                       SSBU_USERDATA=str(p/'userdata'),SSBU_R1_LOG=str(p/'r1.log'),SSBU_SEQ='@fight NONE:500',SSBU_TRACE_FRAMES='500',SSBU_FIGHT_HASH=str(p/'fight.txt'))
            env.update({k:'0' for k in PROBES})
            settings={k:scalar(v) for k,v in env.items()}
            settings.update(SSBU_USERDATA={'tree':'initial_userdata'},SSBU_ROMFS={'tree':'content'})
            ident=dict(format=1,game_version='13.0.5',executable_name='probe.exe',launcher_seconds=900,
                       pair_launcher=file_id(ROOT/'tools/run_initialization_pair.py'),effective_settings=settings,
                       sequence_file=file_id(self.tape),inputs={'initial_userdata':self.plan['save_identity'],'content':{'sha256':'e'*64}},
                       executable=self.plan['package_executable'],tree_digest=self.plan['package_source'])
            for k in ('runtime_manifest','modules','game_inputs','binary_input_directory','runtime_toolchain_declared','setup_compiler_observed'): ident[k]={'test':'synthetic'}
            fid={'sha256':'f'*64,'size':1}
            for k in ('runtime_manifest','setup_compiler_observed','setup_state'): ident[k]=fid
            ident['launcher']=file_id(ROOT/'scripts/run.py')
            ident['identity_tool']=file_id(ROOT/'scripts/battle_identity.py')
            ident['modules']={'main.dll':fid}; ident['game_inputs']={'main.elf':fid,'sdk.elf':fid}
            self.ids[role]=ident
            build=Path(self.plan['peers'][role]['build'])
            self.commands[role]=dict(argv=[str(build/'work/probe.exe'),str(build/'binaries/13.0.5/main.elf'),'900'],cwd=str(build/'work'),environment=env,
                                     pair_launcher=ident['pair_launcher'],fresh_userdata=self.plan['save_identity'],initial_cache=self.plan['cache_identity'])
            self.write(p/'result.json',{'exit':0})
            (p/'fight.txt').write_text(trace())
            who='host (player 1)' if role=='host' else 'joiner (player 2)'
            (p/'game.log').write_text('\n'.join([ENABLED,
                '[rbnet] handshake 1: this game is the '+who+'; own choice ui_chara 0000000000000001 colour 0; waiting for the other game (at most 60 s; nonce 12345678)',
                '[rbnet] handshake 1 agreed after 1.00 s (messages sent 1, received 1; match id 00000001; notice updates 1, frames shown again 1)',
                '[rbnet] handshake: the match: player 1 ui_chara 0000000000000001 colour 0 controls none, player 2 ui_chara 0000000000000002 colour 0 controls none; stage entry 0000000000000001 form 0 flags 0 second 0000000000000000; hazards 0, items 0, rule kind 1, stocks 1; seed 0000000000000001',AGREED,
                'debug match: player 0: screen choice 1 type 0 level 0 -> record 100: ui_chara 1, fighter kind 0, type 0, colour 0, cpu level 0',
                'debug match: player 1: screen choice 2 type 0 level 0 -> record 200: ui_chara 2, fighter kind 1, type 0, colour 0, cpu level 0',
                *[f'debug match: player {i}: screen choice c1ffff0000000000 type 3 level 4294967295 -> record {300+i:x}: ui_chara c1ffff0000000000, fighter kind -1, type 2, colour 0, cpu level 0' for i in range(2,8)],
                "debug match: fight 0 on (the game's ready-go) at presented frame 1: p1 kind 0 (mario), p2 kind 1 (donkey) type 0 cpu power 0 | stage id 0x1 (match block + 0x420), chosen ui_stage 1 form 0 (0 normal, 1 battlefield, 2 omega) flags 0/0 (end) | rule: stock 1, item appear 0; stocks in the fighters' records 1 / 1"])+'\n')
        self.save()

    def write(self,p,value): p.write_text(json.dumps(value))

    def save(self):
        self.write(self.out/'plan.json',self.plan)
        self.write(self.out/'attempt.json',dict(format=2,attempt_id=self.attempt_id,plan_sha256=digest(self.plan),created_at=90))
        for role in ('host','join'):
            p=self.out/role; identity=dict(self.ids[role]); identity['identity_sha256']=digest(identity)
            self.write(p/'prelaunch-identity.json',identity)
            self.commands[role].update(attempt_id=self.attempt_id,identity_sha256=identity['identity_sha256'],plan_sha256=digest(self.plan))
            self.write(p/'command.json',self.commands[role])
            (p/'launcher.log').write_text('prelaunch battle identity: '+identity['identity_sha256']+'\ngame exited with code 0\n')

        checks={r:immutable_digest(dict(i,inputs=i.get('inputs',{}))) for r,i in self.ids.items()}
        self.write(self.out/'inventory-rechecks.json',dict(plan_sha256=digest(self.plan), errors=[],
                   after_preparation=checks, after_admission=checks, post_run=checks, prelaunch_metadata_sha256='a'*64, verification_methods=dict(after_preparation='full',after_admission='metadata',post_run='full')))

        self.seal_fixture()

    def seal_fixture(self):
        sample=dict(time=100,available_commit=20*1024**3,available_mib=20480,committed=0,processes=[])
        samples=[sample,dict(sample,time=115)]
        self.write(self.out/'admission.json',samples)
        record=dict(format=2,attempt_id=self.attempt_id,plan_sha256=digest(self.plan),admission_sha256=digest(samples),errors=[],peers={},outputs={})
        for i,role in enumerate(('host','join')):
            row=dict(pid=1000+i,start_requested_at=116+i,start_returned_at=116+i,ended_at=200+i,exit=0,timed_out=False,closed=True,outputs={})
            result={k:row[k] for k in ('pid','start_requested_at','start_returned_at','ended_at','exit','timed_out')}
            self.write(self.out/role/'result.json',dict(result,attempt_id=self.attempt_id,role=role))
            for name in REQUIRED_OUTPUTS | ({'r1.log'} if (self.out/role/'r1.log').exists() else set()):
                row['outputs'][name]=file_id(self.out/role/name)
            record['peers'][role]=row
        for name in ('plan.json','attempt.json','admission.json','inventory-rechecks.json'): record['outputs'][name]=file_id(self.out/name)
        self.write(self.out/'completion.json',record)

    def launch_fixture(self):
        self.plan['output']=str(self.out); self.save()
        for name in ('inventory-rechecks.json','completion.json','admission.json'): (self.out/name).unlink()

    def verdict(self,passed=False):
        result=inspect_pair(self.out)
        self.assertEqual(result['status'],'passed' if passed else 'failed',result)
        self.assertFalse(result['gameplay_certified']); return result

    def test_complete_uninstrumented_artifacts(self):
        r=self.verdict(True)
        self.assertEqual('passed',r['peers']['host']['original_reference'])

    def test_forward_gate_still_rejects_net(self):
        self.assertEqual(inspect_trial(self.out/'host',forward_only=True)['status'],'failed')

    def test_missing_every_peer_artifact(self):
        for role in ('host','join'):
            for name in ('prelaunch-identity.json','command.json','launcher.log','game.log','result.json'):
                with self.subTest(role=role,name=name):
                    p=self.out/role/name; old=p.read_bytes(); p.unlink(); self.verdict(); p.write_bytes(old)

    def test_identity_and_command_contradictions(self):
        for role in ('host','join'):
            for k in REQUIRED:
                with self.subTest(role=role,key=k):
                    old=self.ids[role]['effective_settings'][k]
                    self.ids[role]['effective_settings'][k]=scalar('wrong'); self.save(); self.verdict()
                    self.ids[role]['effective_settings'][k]=old
            self.commands[role]['argv'][-1]='0'; self.save(); self.verdict(); self.commands[role]['argv'][-1]='900'
        self.save(); self.verdict(True)

    def test_false_agreement_and_seed(self):
        p=self.out/'join/game.log'; original=p.read_text()
        changes=[(AGREED,''),(ENABLED,''),('joiner (player 2)','host (player 1)'),('messages sent 1','messages sent 0'),
                 ('received 1','received 0'),('seed 0000000000000001','seed 0000000000000002'),
                 ('match id 00000001','match id 00000002'),('handshake 1 agreed','handshake 2 agreed'),
                 ('stocks 1','stocks 2')]
        for a,b in changes:
            with self.subTest(a=a): p.write_text(original.replace(a,b)); self.verdict()
        for extra in (AGREED,'[rbnet] handshake 1 FAILED: timed out','[rbnet] handshake: disabled','RING on: capture'):
            p.write_text(original+extra+'\n'); self.verdict()

    def test_zero_exit_fatal_and_failed_peer(self):
        for role in ('host','join'):
            for name in ('game.log','r1.log','launcher.log'):
                p=self.out/role/name; old=p.read_bytes() if p.exists() else None
                for fatal in ('FATAL EXCEPTION','HOLD RELEASE FAILED','Unhandled exception'):
                    p.write_bytes((old or b'')+fatal.encode()+b'\n'); self.verdict()
                if old is None: p.unlink()
                else: p.write_bytes(old)
            for code in (-1,1,False,None):
                self.write(self.out/role/'result.json',{'exit':code}); self.verdict()
            self.write(self.out/role/'result.json',{'exit':0})

    def test_instrumented_requires_trace_and_real_endpoints(self):
        self.plan['instrumented']=True
        for role in ('host','join'):
            env=self.commands[role]['environment']; env.update({k:'1' for k in PROBES})
            env.update(SSBU_TRACE_FRAMES='500',SSBU_FIGHT_HASH=str(self.out/role/'fight.txt'))
            self.ids[role]['effective_settings'].update({k:scalar(env[k]) for k in (*PROBES,'SSBU_TRACE_FRAMES','SSBU_FIGHT_HASH')})
        self.save(); self.verdict()
        for role in ('host','join'): (self.out/role/'fight.txt').write_text(trace())
        r=self.verdict()
        self.assertEqual(r['peers']['host']['original_reference'],'passed')
        self.assertTrue(r['peers']['host']['errors']) # no origin/reset/raw endpoints
        p=self.out/'host/fight.txt'; p.write_text(trace().replace('rng 0','rng 1',1))
        r=self.verdict(); self.assertEqual(r['peers']['host']['original_reference'],'failed')
        p.write_text(trace().replace('TRACE_PASS 1 R','TRACE_PASS 1 S')); self.verdict()
        p.write_text(trace().split('TRACE_END')[0]); self.verdict()

    def test_complete_instrumented_endpoints_and_peer_difference(self):
        import struct
        from test_rng_seed_origin_analysis import fixture as origin_fixture
        from test_rng_reset_analysis import fixture as reset_fixture
        from rng_reset_analysis import recurrence
        origin=origin_fixture().replace('b77b0413','12345678').splitlines()
        reset=reset_fixture().splitlines()
        # Constructor surrounds selector; a later reset retains the same owner.
        lines=[reset[0],origin[0],reset[3],*origin[1:3],reset[4],reset[1],reset[2],*reset[5:],*origin[3:]]
        words=recurrence(0x12345678); h=0xcbf29ce484222325
        for b in struct.pack('<45I',*words): h=((h^b)*0x100000001b3)&0xffffffffffffffff
        folded=f'{(h^(h>>32))&0xffffffff:08x}'
        for f in (1,2,3):
            for slot in (0,1):
                for phase in ('before','after'):
                    lines.append(f'[rng-probe] phase={phase} slot={slot} frame={f} thread=7 base=5000 words='+','.join(f'{v:08x}' for v in words))
        self.plan['instrumented']=True
        self.reference.write_text(trace().replace('rng 0','rng '+folded))
        self.plan['reference_identity']=file_id(self.reference)
        for role in ('host','join'):
            env=self.commands[role]['environment']; env.update({k:'1' for k in PROBES})
            env.update(SSBU_TRACE_FRAMES='500',SSBU_FIGHT_HASH=str(self.out/role/'fight.txt'))
            self.ids[role]['effective_settings'].update({k:scalar(env[k]) for k in (*PROBES,'SSBU_TRACE_FRAMES','SSBU_FIGHT_HASH')})
            (self.out/role/'fight.txt').write_text(self.reference.read_text())
            p=self.out/role/'game.log'; p.write_text(p.read_text()+'\n'.join(lines)+'\n')
        self.save(); self.verdict(True)
        p=self.out/'join/game.log'; old=p.read_text()
        p.write_text(old.replace('alternate=12345678','alternate=12345679'))
        r=self.verdict(); self.assertIn('observed peer endpoints differ',r['errors'])
        p.write_text(old.replace('[rng-probe] phase=after slot=1 frame=3','[rng-probe] phase=before slot=1 frame=3'))
        self.verdict()

    def test_launch_admission_failure_creates_no_process(self):
        from run_initialization_pair import launch
        self.launch_fixture()
        sample=dict(time=100,available_commit=0,available_mib=20480,committed=0,processes=[])
        with patch('run_initialization_pair.metadata_snapshot',return_value='a'*64), patch('run_initialization_pair.recheck',return_value={}), patch('run_initialization_pair.host_sample',side_effect=[sample,dict(sample,time=115)]), patch('run_initialization_pair.time.sleep'), patch('run_initialization_pair.time.time',return_value=116), patch('run_initialization_pair.subprocess.Popen') as popen:
            with self.assertRaises(ValueError): launch(self.plan,{})
            popen.assert_not_called()

    def test_missing_identity_sections(self):
        for key in ('runtime_manifest','modules','game_inputs','executable','setup_state','identity_tool','effective_settings','inputs'):
            old=self.ids['join'].pop(key); self.save(); self.verdict(); self.ids['join'][key]=old
        self.save(); self.verdict(True)

    def test_uninstrumented_still_requires_trace_reference_and_inventory(self):
        for role in ('host','join'):
            p=self.out/role/'fight.txt'; old=p.read_text()
            for bad in ('', old.replace('rng 0','rng 1',1),old.split('TRACE_END')[0]):
                p.write_text(bad); self.verdict()
            p.write_text(old)
        checks=self.out/'inventory-rechecks.json'; old=checks.read_text()
        checks.unlink(); self.verdict(); checks.write_text(old)
        record=json.loads(old); record['post_run'].pop('join'); self.write(checks,record); self.verdict()

    def test_real_recheck_rejects_mutations_and_excludes_only_userdata(self):
        from run_initialization_pair import recheck
        package=self.out/'package'; package.mkdir()
        (package/'asset').write_text('pinned')
        self.write(package/'manifest.json',dict(files={'asset':file_id(package/'asset')}))
        self.plan.update(runtime=str(package),output=str(self.out))
        for role in ('host','join'):
            current=dict(self.ids[role])
            with patch('run_initialization_pair.capture',return_value=current), patch('run_initialization_pair.tree_id',return_value=self.plan['cache_identity']):
                recheck(self.plan,{role:self.commands[role]},before_launch=True)
            changed=copy.deepcopy(current); changed['modules']['main.dll']['sha256']='0'*64
            with patch('run_initialization_pair.capture',return_value=changed),self.assertRaises(ValueError):
                recheck(self.plan,{role:self.commands[role]},before_launch=False)
            changed=copy.deepcopy(current); changed['inputs']['initial_userdata']['sha256']='0'*64
            with patch('run_initialization_pair.capture',return_value=changed):
                recheck(self.plan,{role:self.commands[role]},before_launch=False)
                with self.assertRaises(ValueError): recheck(self.plan,{role:self.commands[role]},before_launch=True)
        (package/'asset').write_text('changed')
        with self.assertRaises(ValueError): recheck(self.plan,self.commands,before_launch=False)

    def test_partial_launch_cleanup_and_post_recheck(self):
        from unittest.mock import MagicMock
        from run_initialization_pair import launch
        self.launch_fixture()
        for role in ('host','join'):
            for name in ('game.log','launcher.log','result.json'): (self.out/role/name).unlink()
        sample=dict(time=100,available_commit=20*1024**3,available_mib=20480,committed=0,processes=[])
        proc=MagicMock(pid=1234); proc.poll.return_value=None; proc.wait.return_value=-9
        with patch('run_initialization_pair.metadata_snapshot',return_value='a'*64), patch('run_initialization_pair.recheck',return_value={}) as check, patch('run_initialization_pair.host_sample',side_effect=[sample,dict(sample,time=115)]), patch('run_initialization_pair.time.sleep'), patch('run_initialization_pair.time.time',return_value=116), patch('run_initialization_pair.subprocess.Popen',side_effect=[proc,OSError('synthetic second peer failure')]), patch('run_initialization_pair.subprocess.run') as kill:
            with self.assertRaises(OSError): launch(self.plan,self.commands)
            kill.assert_called_once_with(['taskkill','/PID','1234','/T','/F'],capture_output=True,check=True,timeout=10)
            proc.wait.assert_called_once_with(timeout=30)
            self.assertEqual([c.kwargs['before_launch'] for c in check.call_args_list],[True,False])
        self.assertTrue(json.loads((self.out/'inventory-rechecks.json').read_text())['errors'])

    def test_slow_post_admission_metadata_refuses_launch(self):
        from run_initialization_pair import launch
        self.launch_fixture()
        sample=dict(time=100,available_commit=20*1024**3,available_mib=20480,committed=0,processes=[])
        with patch('run_initialization_pair.metadata_snapshot',return_value='a'*64), patch('run_initialization_pair.recheck',return_value={}), patch('run_initialization_pair.host_sample',side_effect=[sample,dict(sample,time=115)]), patch('run_initialization_pair.time.sleep'), patch('run_initialization_pair.time.time',side_effect=[116,121]), patch('run_initialization_pair.subprocess.Popen') as popen:
            with self.assertRaises(ValueError): launch(self.plan,self.commands)
            popen.assert_not_called()

    def test_metadata_screen_detects_critical_change_and_ignores_cache(self):
        from run_initialization_pair import metadata_snapshot
        package=self.out/'package'; package.mkdir()
        self.write(package/'manifest.json',dict(files={},tree_files={}))
        self.plan.update(output=str(self.out),runtime=str(package))
        for role in ('host','join'):
            build=Path(self.plan['peers'][role]['build']); (build/'work').mkdir(parents=True)
            self.write(build/'state.json',dict(tools={'clang':str(self.tape)}))
            (build/'work/probe.exe').write_text('synthetic exe')
        before=metadata_snapshot(self.plan,self.commands)
        build=Path(self.plan['peers']['host']['build']); (build/'cache').mkdir(); (build/'cache/new').write_text('mutable')
        self.assertEqual(before,metadata_snapshot(self.plan,self.commands))
        (build/'work/probe.exe').write_text('changed synthetic exe')
        self.assertNotEqual(before,metadata_snapshot(self.plan,self.commands))

    def test_reviewer_counterexamples_remain_preserved_and_now_fail(self):
        retained=ROOT/'artifacts/local/initialization-pair-review-20261022/reproductions.json'
        if retained.exists():
            before=file_id(retained)
            evidence=json.loads(retained.read_text())
            for name in ('missing_admission','actual_rule_not_applied','missing_player_panel','both_rules_changed'):
                self.assertEqual(evidence[name]['status'],'passed')  # retained failed counterexamples
        p=self.out/'join/game.log'; old=p.read_text()
        for diagnostic in (
            '[rbnet] handshake: player 2: rule kind 1 here, 0 agreed (not changed: set the same rules on both)',
            "[rbnet] handshake: player 2 has NO panel on this game's select screen and player 1's state was not read: this match will not be the agreed one"):
            p.write_text(old+diagnostic+'\n'); self.seal_fixture()
            report=self.verdict()
            self.assertIn('production handshake application failed',report['peers']['join']['errors'])
            self.assertEqual(report['peers']['join']['original_reference'],'passed')
        p.write_text(old)
        for role in ('host','join'):
            q=self.out/role/'game.log'; q.write_text(q.read_text().replace('stocks 1','stocks 99').replace('hazards 0','hazards 1'))
        self.seal_fixture(); report=self.verdict()
        self.assertTrue(all('negotiated fields differ from reviewed plan' in report['peers'][r]['errors'] for r in ('host','join')))
        (self.out/'admission.json').unlink(); report=self.verdict()
        self.assertTrue(any('completion:' in e for e in report['errors']))
        if retained.exists(): self.assertEqual(file_id(retained),before)

    def test_applied_readbacks_fail_closed_even_with_resealed_outputs(self):
        p=self.out/'host/game.log'; old=p.read_text()
        for a,b in (("chosen ui_stage 1", "chosen ui_stage 2"),('rule: stock 1','rule: stock 2'),
                    ("records 1 / 1","records 1 / -1"),('fighter kind 0, type 0','fighter kind 0, type 1'),
                    ('fighter kind -1, type 2','fighter kind 2, type 0'),('debug match: player 1:','debug match: player 0:'),
                    ("debug match: fight 0 on","missing ready-go")):
            p.write_text(old.replace(a,b)); self.seal_fixture(); self.verdict()
        p.write_text(old); self.seal_fixture(); self.verdict(True)
        self.plan.pop('expected_match'); self.save(); self.verdict()

    def test_completion_and_admission_membership_and_substitution(self):
        original=(self.out/'completion.json').read_text()
        for name in ('completion.json','attempt.json','admission.json'):
            p=self.out/name; old=p.read_bytes(); p.unlink(); r=self.verdict(); p.write_bytes(old)
            self.assertEqual(r['peers']['host']['original_reference'],'passed')
        mutations=(lambda r:r.update(attempt_id=str(uuid.uuid4())),
                   lambda r:r['peers'].pop('join'),lambda r:r['outputs'].pop('admission.json'),
                   lambda r:r['peers']['join']['outputs'].pop('fight.txt'),
                   lambda r:r['peers']['join'].update(start_requested_at=121,start_returned_at=121),
                   lambda r:r['peers']['join'].update(closed=False),lambda r:r['peers']['join'].update(pid=1000),
                   lambda r:r['peers']['join'].update(timed_out=True),lambda r:r.update(admission_sha256='0'*64))
        for mutate in mutations:
            record=json.loads(original); mutate(record); self.write(self.out/'completion.json',record); self.verdict()
        (self.out/'completion.json').write_text(original)
        p=self.out/'join/game.log'; old=p.read_text()
        p.write_text(old.replace('nonce 12345678','nonce abcdef01')) # prior same-role otherwise valid output
        report=self.verdict(); self.assertTrue(any('closed peer output changed' in e for e in report['errors']))
        p.write_text(old)
        self.write(self.out/'join/result.json',{'exit':0}); self.verdict()

    def test_budget_rejection_with_consistent_manifest_hashes(self):
        for change in (dict(available_commit=20*1024**3-1),dict(available_mib=20479),dict(time=114),dict(processes=[{'Name':'ssbu.exe'}])):
            self.seal_fixture(); samples=json.loads((self.out/'admission.json').read_text()); samples[1].update(change)
            self.write(self.out/'admission.json',samples)
            record=json.loads((self.out/'completion.json').read_text()); record['admission_sha256']=digest(samples)
            record['outputs']['admission.json']=file_id(self.out/'admission.json'); self.write(self.out/'completion.json',record)
            self.verdict()

    def test_each_native_start_rechecks_freshness(self):
        from unittest.mock import MagicMock
        from run_initialization_pair import launch
        self.launch_fixture()
        for role in ('host','join'):
            for name in ('game.log','launcher.log','result.json'): (self.out/role/name).unlink()
        sample=dict(time=100,available_commit=20*1024**3,available_mib=20480,committed=0,processes=[])
        proc=MagicMock(pid=1234); proc.poll.return_value=None; proc.wait.return_value=-9
        # admission, metadata, host request, host return, join request (expired), cleanup end
        with patch('run_initialization_pair.metadata_snapshot',return_value='a'*64), patch('run_initialization_pair.recheck',return_value={}), patch('run_initialization_pair.host_sample',side_effect=[sample,dict(sample,time=115)]), patch('run_initialization_pair.time.sleep'), patch('run_initialization_pair.time.time',side_effect=[116,116,116,117,121,122]), patch('run_initialization_pair.subprocess.Popen',return_value=proc) as popen, patch('run_initialization_pair.subprocess.run') as kill:
            with self.assertRaises(ValueError): launch(self.plan,self.commands)
            self.assertEqual(popen.call_count,1)
            self.assertEqual(kill.call_args.kwargs['timeout'],10)
        report=json.loads((self.out/'completion.json').read_text())
        self.assertEqual(set(report['peers']),{'host'}); self.assertTrue(report['errors'])

    def test_successful_mocked_launch_seals_real_closed_output_hashes(self):
        from unittest.mock import MagicMock
        from run_initialization_pair import launch
        self.launch_fixture()
        logs={r:(self.out/r/'game.log').read_bytes() for r in ('host','join')}
        for role in ('host','join'):
            for name in ('game.log','launcher.log','result.json','fight.txt'): (self.out/role/name).unlink()
        sample=dict(time=100,available_commit=20*1024**3,available_mib=20480,committed=0,processes=[])
        hashes={r:immutable_digest(i) for r,i in self.ids.items()}
        calls=[]
        def start(*args,**kwargs):
            role=('host','join')[len(calls)]; calls.append(role)
            kwargs['stdout'].write(logs[role]); kwargs['stdout'].flush()
            (self.out/role/'fight.txt').write_text(trace())
            proc=MagicMock(pid=1000+len(calls)); proc.wait.return_value=0; proc.poll.return_value=0
            return proc
        with patch('run_initialization_pair.metadata_snapshot',return_value='a'*64), patch('run_initialization_pair.recheck',return_value=hashes), patch('run_initialization_pair.host_sample',side_effect=[sample,dict(sample,time=115)]), patch('run_initialization_pair.time.sleep'), patch('run_initialization_pair.time.time',side_effect=[116,116,116,116.1,116.2,116.3,118,119]), patch('run_initialization_pair.subprocess.Popen',side_effect=start):
            result=launch(self.plan,self.commands)
        self.assertEqual(result['status'],'passed',result)
        record=json.loads((self.out/'completion.json').read_text())
        self.assertEqual(record['peers']['join']['outputs']['game.log'],file_id(self.out/'join/game.log'))
        self.assertEqual(record['attempt_id'],self.attempt_id)

    def test_bounded_cleanup_failure_is_preserved(self):
        import subprocess
        from unittest.mock import MagicMock
        from run_initialization_pair import launch
        self.launch_fixture()
        for role in ('host','join'):
            for name in ('game.log','launcher.log','result.json'): (self.out/role/name).unlink()
        sample=dict(time=100,available_commit=20*1024**3,available_mib=20480,committed=0,processes=[])
        proc=MagicMock(pid=1234); proc.poll.return_value=None
        with patch('run_initialization_pair.metadata_snapshot',return_value='a'*64), patch('run_initialization_pair.recheck',return_value={}), patch('run_initialization_pair.host_sample',side_effect=[sample,dict(sample,time=115)]), patch('run_initialization_pair.time.sleep'), patch('run_initialization_pair.time.time',return_value=116), patch('run_initialization_pair.subprocess.Popen',side_effect=[proc,OSError('second peer refused')]), patch('run_initialization_pair.subprocess.run',side_effect=subprocess.TimeoutExpired('taskkill',10)) as kill:
            with self.assertRaises(OSError): launch(self.plan,self.commands)
            self.assertEqual(kill.call_args.kwargs['timeout'],10)
        record=json.loads((self.out/'completion.json').read_text())
        self.assertFalse(record['peers']['host']['closed'])
        self.assertTrue(any('cleanup failed' in e for e in record['errors']))
        self.verdict()

    def test_delayed_native_creation_fails_and_cleans_owned_process(self):
        from unittest.mock import MagicMock
        from run_initialization_pair import launch
        self.launch_fixture()
        for role in ('host','join'):
            for name in ('game.log','launcher.log','result.json'): (self.out/role/name).unlink()
        sample=dict(time=100,available_commit=20*1024**3,available_mib=20480,committed=0,processes=[])
        proc=MagicMock(pid=1234); proc.poll.return_value=None; proc.wait.return_value=-9
        with patch('run_initialization_pair.metadata_snapshot',return_value='a'*64), patch('run_initialization_pair.recheck',return_value={}), patch('run_initialization_pair.host_sample',side_effect=[sample,dict(sample,time=115)]), patch('run_initialization_pair.time.sleep'), patch('run_initialization_pair.time.time',side_effect=[116,116,116,121,122]), patch('run_initialization_pair.subprocess.Popen',return_value=proc) as popen, patch('run_initialization_pair.subprocess.run') as kill:
            with self.assertRaises(ValueError): launch(self.plan,self.commands)
            self.assertEqual(popen.call_count,1); self.assertEqual(kill.call_args.kwargs['timeout'],10)
        self.assertTrue((self.out/'pair-gate.json').exists())
        report=json.loads((self.out/'pair-gate.json').read_text())
        self.assertEqual(report['status'],'failed')
        self.assertEqual(report['peers']['host']['original_reference'],'passed')

    def test_original_reference_is_not_relabelled(self):
        self.reference.write_text(trace().replace('rng 0','rng 2',1)); self.verdict()

    def test_resource_admission(self):
        sample=dict(time=100,available_commit=20*1024**3,available_mib=20480,committed=5*1024**3,processes=[])
        a=sample; b=dict(sample,time=115)
        admit([a,b],116)
        for change in (dict(available_commit=20*1024**3-1),dict(available_mib=20479),dict(processes=[{'Name':'ssbu.exe'}]),dict(committed=6*1024**3),dict(time=114)):
            with self.subTest(change=change),self.assertRaises(ValueError): admit([a,dict(b,**change)],116)
        with self.assertRaises(ValueError): admit([a,b],121)

    def test_launch_requires_review_before_prepare(self):
        with patch.object(sys,'argv',['run_initialization_pair.py',str(self.out/'plan.json'),'--launch']),patch('run_initialization_pair.prepare') as prepare:
            self.assertEqual(main(),1); prepare.assert_not_called()

if __name__=='__main__': unittest.main()
