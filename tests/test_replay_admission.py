"""Default replay adapter: injected native boundary, no game or capacity sampling."""
from pathlib import Path
import importlib.util
import json
import tempfile
import unittest
from unittest.mock import patch, Mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('replay_admission', ROOT/'tools/replay_admission.py')
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)

class ReplayAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.trial = self.root/'trial'; self.trial.mkdir()
        self.identity = self.trial/'prelaunch-identity.json'; self.identity.write_text('{}')
        self.runtime = self.root/'runtime'/'package'; self.runtime.mkdir(parents=True)
        self.env = dict(a.EXPECTED, SSBU_FIGHT_HASH=str(self.trial/'fight.txt'),
                        SSBU_R1_LOG=str(self.trial/'r1.log'), SSBU_SHOT_DIR=str(self.trial),
                        SSBU_USERDATA=str(self.trial/'userdata'), SSBU_ROMFS='fixture', SSBU_SEQ='fixture')
        self.rows = [dict(time=t, available_commit=11*1024**3, committed=20*1024**3,
                          available_mib=12000, processes=[]) for t in (100,115)]
        self.kw = dict(cwd=self.root, env=self.env, stdout=None, stderr=None,
                       identity_path=self.identity, runtime=self.runtime, build=self.root, sequence='fixture')

    def invoke(self, rows=None, times=None, metadata=None, launch=None):
        with patch.object(a,'sample',side_effect=rows or self.rows), patch.object(a.time,'sleep'), \
             patch.object(a.time,'time',side_effect=times or [115]*10), \
             patch.object(a,'metadata',side_effect=metadata or ['same','same']), \
             patch.object(a.subprocess,'run',side_effect=launch,return_value=Mock(returncode=0)) as native:
            try: a.run_admitted(['fixture.exe','main.elf','900'],**self.kw)
            finally: self.calls=native.call_count

    def test_collection_latency_counts_toward_freshness(self):
        # A slow process query reports a late shell timestamp; sample must retain
        # its pre-collection Python timestamp so the old memory row is refused.
        late = dict(self.rows[1], time=121)
        with patch.object(a.time, 'time', return_value=115), \
             patch.object(a.subprocess, 'run', return_value=Mock(stdout=json.dumps(late))):
            row = a.sample()
        self.assertEqual(row['time'], 115)
        a.validate([self.rows[0], row], 120)
        with self.assertRaisesRegex(ValueError, 'stale'):
            a.validate([self.rows[0], row], 121)

    def test_exact_configuration(self):
        a.validate_configuration(self.env,self.identity)
        for key in a.EXPECTED:
            with self.subTest(key=key):
                env=dict(self.env);env[key]='wrong'
                with self.assertRaises(ValueError):a.validate_configuration(env,self.identity)
                env=dict(self.env);env.pop(key)
                with self.assertRaises(ValueError):a.validate_configuration(env,self.identity)
        for key in ('SSBU_RB_NET_TEST_POOL','RECOMP_EXE','VK_DRIVER_FILES'):
            with self.assertRaises(ValueError):a.validate_configuration(dict(self.env,**{key:'1'}),self.identity)
        with self.assertRaises(ValueError):a.validate_configuration(dict(self.env,SSBU_FIGHT_HASH='elsewhere'),self.identity)

    def test_positive_boundary_and_exclusive_receipt(self):
        def launch(*args,**kwargs):
            self.assertTrue((self.root/'native-trial.lock').exists())
            self.assertTrue((self.trial/'native-admission.json').exists())
            return Mock(returncode=0)
        self.invoke(launch=launch)
        self.assertEqual(self.calls,1)
        record=json.loads((self.trial/'native-admission.json').read_text())
        self.assertEqual(record['status'],'admitted');self.assertTrue(record['native_launch_attempted'])
        self.assertFalse((self.root/'native-trial.lock').exists())
        with self.assertRaises(ValueError):self.invoke()
        self.assertEqual(self.calls,0)

    def test_refusals_prevent_native_call(self):
        cases=[('commit',{'available_commit':10*1024**3-1}),('physical',{'available_mib':10239}),
               ('process',{'processes':[{'Name':'ssbu_native.exe'}]}),('nan',{'committed':float('nan')}),
               ('drift',{'committed':21*1024**3}),('interval',{'time':114})]
        for name,change in cases:
            with self.subTest(case=name):
                rows=[dict(x) for x in self.rows];rows[1].update(change)
                with self.assertRaises(ValueError):self.invoke(rows=rows)
                self.assertEqual(self.calls,0)
                p=self.trial/'native-admission.json';record=json.loads(p.read_text());self.assertFalse(record['native_launch_attempted']);p.unlink()
        for times,meta in [([121]*10,None),([115,115,121],None),(None,['same','changed'])]:
            with self.assertRaises(ValueError):self.invoke(times=times,metadata=meta)
            self.assertEqual(self.calls,0);(self.trial/'native-admission.json').unlink()

    def test_lock_and_config_refuse_before_sampling(self):
        lock=self.root/'native-trial.lock';lock.write_text('prior owner')
        with self.assertRaises(FileExistsError):self.invoke()
        self.assertEqual(self.calls,0);self.assertEqual(lock.read_text(),'prior owner');lock.unlink()
        self.env['SSBU_LS']='0'
        with patch.object(a,'sample') as sample:
            with self.assertRaises(ValueError):self.invoke()
            sample.assert_not_called()
        self.assertEqual(self.calls,0)

    def test_native_failure_recorded_and_lease_released(self):
        with self.assertRaises(OSError):self.invoke(launch=OSError('injected'))
        record=json.loads((self.trial/'native-admission.json').read_text())
        self.assertEqual(record['status'],'failed');self.assertTrue(record['native_launch_attempted'])
        self.assertFalse((self.root/'native-trial.lock').exists())

if __name__=='__main__':unittest.main()
