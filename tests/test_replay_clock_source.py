"""Exact production clock observer and import bodies; no private game needed."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from run_rollback_tests import resolve_clang
from test_catch_source import function


@unittest.skipUnless(os.name == 'nt', 'Windows production clock fixture')
class ReplayClockSourceTests(unittest.TestCase):
    def test_observer_and_unchanged_clock(self):
        ring = (ROOT / 'runtime/r1_ring.c').read_text()
        block = ring[ring.index('#define RGS_CLOCK_CAP'):ring.index('/* End bounded clock observation. */')]
        sdk = (ROOT / 'runtime/nnsdk.c').read_text()
        handler = sdk[sdk.index('static void os_GetSystemTick(Ctx'):sdk.index('static void os_GetSystemTickFrequency')]
        wrapper = function((ROOT / 'runtime/r1_state.c').read_text(), 'ra_kick2')
        fixture = r'''
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
typedef struct { uint64_t x[32]; } Ctx;
static void r1_queue_tick(const Ctx *c){(void)c;}
static void qp_drain(void){}
#define GAME_13_0_5 1305
#define TICK_HZ 19200000ULL
#define RET(v) (c->x[0]=(uint64_t)(v))
static int g_game_build=GAME_13_0_5,g_rg_ready=1,g_ra_phase;
static long long g_rgs_next=119,g_ff=336;
static int logs,fixed,released,kicks,g_rg_kept,g_nth=1; static DWORD tid=42;
static struct {int held;} g_th[1];
static void r1_hold_fatal(const char *s){puts(s);exit(74);}
static DWORD thread_id(void){SetLastError(1234);return tid;}
static int log_line(const char *fmt,...){(void)fmt;assert(released);logs++;return 0;}
#define GetCurrentThreadId thread_id
#define LOG log_line
/* OBSERVER */
static void host_clock_caller(const char *s,uint64_t lr){(void)s;(void)lr;}
static int host_fixed_clock(uint64_t lr){(void)lr;return fixed;}
static LONGLONG tick=123;
static BOOL qpc(LARGE_INTEGER *v){v->QuadPart=tick;return 1;}
static BOOL qpf(LARGE_INTEGER *v){v->QuadPart=1000;SetLastError(444);return 1;}
#define QueryPerformanceCounter qpc
#define QueryPerformanceFrequency qpf
/* HANDLER */
#define GA(x) (x)
static uint64_t g_ra_site=0x123;
static int g_ra_off,g_ra_wd_pause,g_ra_wd_base,g_ra_skip,g_ra_skipped_kicks;
static long long g_ra_wd_fired;
static void ra_workers_hold(void){assert(0);}
static int ra_fight_on(void){return 1;}
static void ra_step(Ctx*c){(void)c;assert(!released);}
static void ra_workers_release(void){released=1;}
static void ra_watchdog_signal(void){assert(released);}
static void r1_protection_observation_drain(void){assert(released);}
static int rgs_skip_now(void){return 0;}
static uint64_t rd64(uint64_t p){(void)p;assert(0);return 0;}
void r1_wrote(uint64_t p,uint64_t n){(void)p;(void)n;assert(0);}
static void g_orig_kick2(Ctx*c){(void)c;assert(released);kicks++;}
/* WRAPPER */
static void drive_h2(Ctx*c){c->x[30]=g_ra_site;released=0;ra_kick2(c,NULL);c->x[30]=0x710374a238ULL;}
int main(int argc,char **argv){
 assert(argc==2);
 _putenv("SSBU_RB_SIM=120,1,60");_putenv("SSBU_RB_SIM_VERIFY=2");
 _putenv("SSBU_RB_NET=0");_putenv("SSBU_RB_SIM_SKIP=0");_putenv("SSBU_RB_SIM_LITE=0");
 _putenv("SSBU_RB_CLOCK_PROBE=1");
 if(!strcmp(argv[1],"invalid")){_putenv("SSBU_RB_NET=1");rgs_clock_init();return 1;}
 if(!strcmp(argv[1],"disabled"))_putenv("SSBU_RB_CLOCK_PROBE=0");
 rgs_clock_init();
 Ctx c,before;memset(&c,0x6b,sizeof c);c.x[30]=0x710374a238ULL;before=c;
 os_GetSystemTick(&c);assert(c.x[0]==2361600&&GetLastError()==444);
 before.x[0]=c.x[0];assert(!memcmp(&before,&c,sizeof c));
 assert(!g_rgs_clock_count); /* no owner before first H2 */
 if(!strcmp(argv[1],"disabled")){drive_h2(&c);assert(!logs);puts("CLOCK_DISABLED_PASS");return 0;}
 InterlockedExchange(&g_rgs_clock_owner,42);
 os_GetSystemTick(&c);assert(g_rgs_clock_count==1&&!logs&&GetLastError()==444);
 assert(g_rgs_clock_events[0].value==2361600&&g_rgs_clock_events[0].phase==0);
 rgs_clock_capture(119,1);assert(g_rgs_clock_original&&!g_rgs_clock_done);
 g_ra_phase=2;tick=456;os_GetSystemTick(&c);
 assert(c.x[0]==8755200&&GetLastError()==444&&g_rgs_clock_count==2);
 assert(g_rgs_clock_events[1].value==8755200&&g_rgs_clock_events[1].pass==119);
 rgs_clock_capture(119,1);assert(g_rgs_clock_replay&&g_rgs_clock_done);
 os_GetSystemTick(&c);assert(g_rgs_clock_count==2);
 g_rg_kept=1;drive_h2(&c);assert(!logs);g_rg_kept=0;
 g_th[0].held=1;drive_h2(&c);assert(!logs);g_th[0].held=0;
 drive_h2(&c);assert(logs==4&&kicks==3);drive_h2(&c);assert(logs==4&&kicks==4);
 /* Wrong caller/pass, foreign calls, cap and failed capture cannot silently pass. */
 InterlockedExchange(&g_rgs_clock_done,0);logs=0;
 c.x[30]++;os_GetSystemTick(&c);assert(g_rgs_clock_count==2);c.x[30]--;
 g_rgs_next=120;os_GetSystemTick(&c);assert(g_rgs_clock_count==2);g_rgs_next=119;
 tid=77;os_GetSystemTick(&c);assert(g_rgs_clock_foreign==1&&g_rgs_clock_count==2&&GetLastError()==444);tid=42;
 for(int i=0;i<40;i++)os_GetSystemTick(&c);
 assert(g_rgs_clock_count==32&&g_rgs_clock_dropped==10&&!logs);
 rgs_clock_capture(119,0);assert(!g_rgs_clock_replay&&g_rgs_clock_done);
 fixed=1;os_GetSystemTick(&c);assert(c.x[0]==0x123456789ULL&&g_rgs_clock_count==32);
 puts("CLOCK_SOURCE_PASS");return 0;
}
'''.replace('/* OBSERVER */', block).replace('/* HANDLER */', handler).replace('/* WRAPPER */', wrapper)
        out = ROOT / 'artifacts/local/replay-clock-source'
        out.mkdir(exist_ok=True, parents=True)
        folder = Path(tempfile.mkdtemp(prefix='run-', dir=out))
        source = folder / 'clock.c'
        source.write_text(fixture)
        print('Evidence:', folder)
        for opt in ('-O1', '-O3'):
            exe = folder / (opt[1:] + '.exe')
            result = subprocess.run([resolve_clang(None), opt, str(source), '-o', str(exe)], capture_output=True, text=True, timeout=60)
            (folder / (opt[1:] + '-build.log')).write_text(result.stdout + result.stderr)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for mode, code in (('enabled', 0), ('disabled', 0), ('invalid', 74)):
                result = subprocess.run([str(exe), mode], capture_output=True, text=True, timeout=10)
                (folder / (opt[1:] + '-' + mode + '.log')).write_text(result.stdout + result.stderr)
                self.assertEqual(result.returncode, code, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
