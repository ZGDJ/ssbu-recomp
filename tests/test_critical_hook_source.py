"""Exact critical hook policy and RA caller; synthetic tables/guest/patch boundaries."""
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
sys.path.insert(0, str(ROOT / 'tools'))
from run_rollback_tests import resolve_clang
from test_catch_source import function


def zero_hash(count):
    value = 0xcbf29ce484222325
    for _ in range(count):
        value = (value * 0x100000001b3) & ((1 << 64) - 1)
    return value


@unittest.skipUnless(os.name == 'nt', 'Windows critical hook source harness')
class CriticalHookSourceTests(unittest.TestCase):
    def test_exact_policy_and_callers(self):
        source = (ROOT / 'fighter_sdk/hook_host.c').read_text()
        # Queue range lengths/addresses stay pinned; synthetic zero guest bytes.
        source = re.sub(r'(0x[0-9a-f]+ULL,)0x[0-9a-f]+ULL,(\d+)',
                        lambda m: m[1]+hex(zero_hash(int(m[2])))+'ULL,'+m[2], source)
        state = (ROOT / 'runtime/r1_state.c').read_text()
        state = state[state.index('#else\n#include <stdio.h>'):]
        learned = (ROOT / 'runtime/rb_learned.c').read_text()
        identity = (ROOT / 'fighter_sdk/critical_hook_identity.h').read_text()
        # Preserve pinned address/name inventory; replace only expected digests.
        # Guest read boundary returns synthetic zeros; no private bytes in fixtures.
        identity = re.sub(r'(0x[0-9a-f]+ull, 0x[0-9a-f]+ull, )0x[0-9a-f]+ull',
                          lambda m: m[1] + hex(zero_hash(32)) + 'ull', identity)
        identity = re.sub(r'(#define HK_CRITICAL_FIGHTER_HASH )0x[0-9a-f]+ull',
                          lambda m: m[1] + hex(zero_hash(32)) + 'ull', identity)
        identity = re.sub(r'(#define HK_CRITICAL_FIGHTER_BUILD_ID_HASH )0x[0-9a-f]+ull',
                          lambda m: m[1] + hex(zero_hash(20)) + 'ull', identity)
        names = ['hk_required_fatal', 'hk_required_build', 'hk_required_entry',
                 'hk_required_fingerprint', 'hk_required_main', 'hook_require_run_ahead_sites',
                 'hook_require_presentation_sites', 'hook_install_required', 'hook_install_queue_probe', 'hk_required_named_address', 'hook_install_name_required',
                 'hook_require_critical_ready', 'hook_install', 'hook_install_name', 'hook_remove', 'hook_module_loaded']
        layer = next(line for line in source.splitlines() if line.startswith('typedef struct { HkSite *site;'))
        fixture = (ROOT / 'tests/critical_hook_source_fixture.c').read_text()
        fixture = fixture.replace('/* LAYER_TYPE */', layer).replace('/* IDENTITY */', identity)
        fixture = fixture.replace('/* SOURCE */', 'static int g_hk_required;\n' + '\n'.join(function(source, n) for n in names))
        fixture = fixture.replace('/* RA_SOURCE */', function(state, 'ra_init'))
        fixture = fixture.replace('/* R1_INIT_SOURCE */', 'static void r1_protection_observation_init(void) {}\n' + function(state, 'r1_init'))
        fixture = fixture.replace('/* FIGHT_ON_SOURCE */', function(state, 'ra_fight_on'))
        fixture = fixture.replace('/* PRESENTATION_SOURCE */', '\n'.join(function(learned, n) for n in ('lp_hooks_install', 'ls_init')))
        directory = ROOT / 'artifacts/local/m13-hook-validation'
        directory.mkdir(parents=True, exist_ok=True)
        out = Path(tempfile.mkdtemp(prefix='source-', dir=directory))
        translation = out / 'critical_hook.c'
        translation.write_text(fixture)
        manifest = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in
                    ('fighter_sdk/hook_host.c', 'fighter_sdk/critical_hook_identity.h', 'runtime/r1_state.c', 'runtime/rb_learned.c')}
        (out / 'source-manifest.json').write_text(json.dumps({'sources': manifest, 'functions': names + ['ra_init', 'r1_init', 'ra_fight_on', 'lp_hooks_install', 'ls_init'],
             'scope': 'exact policy and RA caller; synthetic expected digests, guest reads, tables, patching and locks; no loaded game execution'}, indent=2))
        print(f'Evidence: {out}')
        success = ['frame-valid', 'fight-menu', 'fight-ready', 'presentation-off', 'presentation-valid', 'main-valid', 'all-main-valid', 'named-valid', 'deferred-valid', 'later-reload',
                   'presentation-site-valid', 'ready-valid', 'generic', 'ra-valid', 'ra-submit', 'no-hooks-1304']
        failure = ['frame-trace-off-refusal', 'frame-trace-only-refusal', 'fight-pending', 'presentation-custom', 'presentation-site-fingerprint', 'ra-second-worker', 'ready-pending', 'ready-unregistered', 'ready-unloaded', 'version', 'missing', 'null', 'duplicate', 'duplicate-null', 'fingerprint', 'unlisted',
                   'attach', 'capacity', 'site-override', 'site-fingerprint', 'ra-refusal', 'ra-site-override']
        named = ['missing', 'duplicate', 'duplicate-null', 'wrong-module', 'wrong-offset', 'null-entry',
                 'missing-entry', 'fingerprint', 'build-id', 'version', 'registry', 'main-export']
        failure += [prefix + case for prefix in ('named-', 'deferred-', 'later-') for case in named]
        failure += ['named-attach', 'deferred-attach']
        success += ['queue-valid']
        failure += ['queue-version','queue-missing','queue-duplicate','queue-fingerprint','queue-attach','queue-capacity']
        env = dict(os.environ, TMP=str(out), TEMP=str(out), TMPDIR=str(out))
        for opt in ('-O1', '-O3'):
            exe = out / (opt[1:] + '.exe')
            command = [resolve_clang(None), '-std=c11', opt, str(translation), '-o', str(exe)]
            (out / (opt[1:] + '-command.json')).write_text(json.dumps(command))
            result = subprocess.run(command, capture_output=True, text=True, timeout=60, env=env)
            (out / (opt[1:] + '-build.log')).write_text(result.stdout + result.stderr)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for case in success + failure:
                with self.subTest(optimization=opt, case=case):
                    result = subprocess.run([str(exe), case], capture_output=True, text=True, timeout=15)
                    log = result.stdout + result.stderr
                    (out / f'{opt[1:]}-{case}.log').write_text(f'exit={result.returncode}\n' + log)
                    if case in success:
                        self.assertEqual(result.returncode, 0, log)
                        self.assertIn('CRITICAL_HOOK_SOURCE_PASS', log)
                    else:
                        self.assertNotEqual(result.returncode, 0, log)
                        self.assertIn('PRESENTATION HOOK FATAL:' if case == 'presentation-custom' else 'CRITICAL HOOK FATAL:', log)
                        self.assertIn('CRITICAL_HOOK_FATAL_ORACLE_PASS', log)
                        self.assertNotIn('UNEXPECTED_SUCCESS', log)

    def test_critical_callers_use_required_api(self):
        state = (ROOT / 'runtime/r1_state.c').read_text()
        state = state[state.index('#else\n#include <stdio.h>'):]
        ring = (ROOT / 'runtime/r1_ring.c').read_text()
        fighter = (ROOT / 'fighter_sdk/fighter_host.c').read_text()
        for source, names in ((state, ('ra_init', 'r1_init')), (ring, ('rgs_lite_init', 'rgp_init')),
                              (fighter, ('fight_hash_start', 'fighter_debug_start'))):
            for name in names:
                body = function(source, name)
                self.assertNotRegex(body, r'\bhook_install(?:_name)?\(')
        self.assertIn('hook_require_run_ahead_sites(g_ra_site);', function(state, 'ra_init'))
        self.assertIn('if (on) hook_require_critical_ready();', function(state, 'ra_fight_on'))
        body = function(state, 'ra_init')
        self.assertLess(body.index('hook_require_run_ahead_sites'), body.index('hook_install_required'))


if __name__ == '__main__':
    unittest.main()
