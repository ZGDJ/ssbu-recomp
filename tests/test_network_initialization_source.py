"""Exact initialization isolation policy and capture activation chain; no game."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from run_rollback_tests import resolve_clang
from test_catch_source import function


class NetworkInitializationTests(unittest.TestCase):
    def test_caller_boundaries(self):
        debug = (ROOT / 'runtime/debug_mode.c').read_text()
        apply = function(debug, 'hs_apply')
        self.assertLess(apply.index('rbn_init_only_begin_setup();'), apply.index('rbn_handshake(&me'))
        self.assertLess(apply.index('rbn_handshake(&me'), apply.index('rbn_init_only_agreement(g_hs_ok);'))
        self.assertLess(apply.index('rbn_init_only_agreement(g_hs_ok);'), apply.index('rbn_match_cancelled() == 2'))
        startup = function(debug, 'debug_mode_init')
        self.assertLess(startup.index('rbn_init_only();'), startup.index('CreateThread'))
        self.assertIn('init_only ? hook_install_required(FN_PLAYER_RECORD', startup)
        self.assertIn('void rbn_init(void); rbn_init();', startup)
        net = (ROOT / 'runtime/rb_net.c').read_text()
        self.assertIn('hs_rx(p, n)', function(net, 'rbn_rx'))
        self.assertNotIn('rbn_init_only', function(net, 'rbn_rx'))
        state = (ROOT / 'runtime/r1_state.c').read_text()
        state = state[state.index('#else\n#include <stdio.h>'):]
        self.assertEqual(function(state, 'r1_net_on'), 'int r1_net_on(void) { return rbn_on() > 0; }')
        self.assertLess(function(state, 'r1_init').index('if (!r1_on())'), function(state, 'r1_init').index('ls_init();'))

    @unittest.skipUnless(os.name == 'nt', 'Windows source harness')
    def test_exact_activation_and_refusal(self):
        paths = ['runtime/rb_net.c', 'runtime/rb_rollback.c', 'runtime/r1_ring.c', 'runtime/r1_state.c']
        sources = [(ROOT / p).read_text() for p in paths]
        sources[3] = sources[3][sources[3].index('#else\n#include <stdio.h>'):]
        bodies = '\n'.join(function(sources[0], n) for n in ('rbn_init_only_fatal', 'rbn_init_only', 'rbn_init_only_begin_setup', 'rbn_init_only_agreement'))
        bodies += '\n' + function(sources[1], 'rbg_on') + '\n' + function(sources[2], 'rgs_wanted')
        bodies += '\n' + function(sources[3], 'legacy_restore_unsupported') + '\n' + function(sources[3], 'ra_wanted') + '\n' + function(sources[3], 'r1_on')
        fixture = r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <assert.h>
static int failed;
void fight_trace_fail(const char *why) { assert(!strcmp(why,"network_initialization_diagnostic")); failed++; }
static void test_abort(void) { assert(failed == 1); puts("EXPECTED_FATAL"); fflush(stdout); _Exit(29); }
#define abort test_abort
typedef struct { long long QuadPart; } LARGE_INTEGER;
static void QueryPerformanceFrequency(LARGE_INTEGER *p) { p->QuadPart=1000; }
static int net_calls, gfx_calls;
int rbn_on(void) { net_calls++; const char *p=getenv("SSBU_RB_NET"); return p && *p && *p!='0'; }
int gfx_runahead(void) { gfx_calls++; return 1; }
static int g_rbg=-1,g_rgs_on=-1,g_rgs_n=10,g_rgs_k=7,g_rgs_warm=30;
#define RG_MAXSLOT 16
static int g_on=-1,g_n,g_k,g_p,g_c,g_target;
static double g_qpf;
static FILE *g_log;
/* BODIES */
int main(int argc,char **argv) {
 assert(argc==2); const char *test=argv[1];
 const char *zero[]={"SSBU_R1","SSBU_RUNAHEAD","SSBU_RB_SIM","SSBU_LS","SSBU_MEM_KEEP","SSBU_SKYLINE","SSBU_RB_NET_AUTOP2","SSBU_RB_NET_P2NONE"};
 _putenv_s("SSBU_RB_NET_INIT_ONLY","1"); _putenv_s("SSBU_RB_NET","net"); _putenv_s("SSBU_RB_NET_HANDSHAKE","");
 for(size_t i=0;i<sizeof zero/sizeof zero[0];i++) _putenv_s(zero[i],"0");
 if(!strncmp(test,"missing:",8)) _putenv_s(test+8,"");
 if(!strncmp(test,"conflict:",9)) _putenv_s(test+9,"1");
 if(!strcmp(test,"malformed")) _putenv_s("SSBU_RB_NET_INIT_ONLY","yes");
 if(!strcmp(test,"loop")) _putenv_s("SSBU_RB_NET","loop");
 if(!strcmp(test,"network-off")) _putenv_s("SSBU_RB_NET","0");
 if(!strcmp(test,"handshake-off")) _putenv_s("SSBU_RB_NET_HANDSHAKE","0");
 if(!strcmp(test,"disabled-net") || !strcmp(test,"disabled-off") || !strcmp(test,"absent-net")) {
   _putenv_s("SSBU_RB_NET_INIT_ONLY",!strcmp(test,"absent-net") ? "" : "0");
   int wanted=strcmp(test,"disabled-off")!=0;
   if(!wanted) _putenv_s("SSBU_RB_NET","0");
   assert(r1_on()==wanted); assert(rbg_on()==wanted); assert(ra_wanted()==wanted);
   rbn_init_only_begin_setup();rbn_init_only_begin_setup();rbn_init_only_agreement(0);
   puts("PASS_DEFAULT");return 0;
 }
 assert(r1_on()==0); assert(rbg_on()==0); assert(rgs_wanted()==0); assert(ra_wanted()==0);
 assert(net_calls==0 && gfx_calls==0 && g_log==NULL);
 rbn_init_only_begin_setup();
 if(!strcmp(test,"second-setup")) rbn_init_only_begin_setup();
 rbn_init_only_agreement(strcmp(test,"failed-handshake")!=0);
 assert(!strcmp(test,"enabled")); puts("PASS_ISOLATED");return 0;
}
'''.replace('/* BODIES */', bodies)
        parent = ROOT / 'artifacts/local/handshake-isolation-20261022'
        parent.mkdir(parents=True, exist_ok=True)
        out = Path(tempfile.mkdtemp(prefix='source-', dir=parent))
        print('Evidence:', out)
        (out / 'fixture.c').write_text(fixture)
        (out / 'manifest.json').write_text(json.dumps({p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths}, indent=2))
        zero = ['SSBU_R1', 'SSBU_RUNAHEAD', 'SSBU_RB_SIM', 'SSBU_LS', 'SSBU_MEM_KEEP', 'SSBU_SKYLINE', 'SSBU_RB_NET_AUTOP2', 'SSBU_RB_NET_P2NONE']
        good = ['enabled', 'disabled-net', 'absent-net', 'disabled-off']
        bad = ['malformed', 'loop', 'network-off', 'handshake-off', 'second-setup', 'failed-handshake']
        bad += [prefix+n for prefix in ('missing:', 'conflict:') for n in zero]
        env = {k:v for k,v in os.environ.items() if not k.startswith(('SSBU_', 'RECOMP_'))}
        for opt in ('O1', 'O3'):
            exe = out / (opt+'.exe')
            cmd = [resolve_clang(None), '-std=c11', '-'+opt, str(out/'fixture.c'), '-o', str(exe)]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, env=env)
            (out/(opt+'-build.log')).write_text(result.stdout+result.stderr)
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
            for n, case in enumerate(good+bad):
                with self.subTest(opt=opt, case=case):
                    result = subprocess.run([str(exe), case], capture_output=True, text=True, timeout=15, env=env)
                    log = result.stdout+result.stderr
                    (out/f'{opt}-{n}.log').write_text(f'case={case} exit={result.returncode}\n'+log)
                    self.assertEqual(result.returncode, 0 if case in good else 29, log)
                    self.assertIn('PASS_' if case in good else 'EXPECTED_FATAL', log)


if __name__ == '__main__':
    unittest.main()
