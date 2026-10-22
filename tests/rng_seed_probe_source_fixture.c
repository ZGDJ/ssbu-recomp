#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <assert.h>
typedef struct {uint64_t x[32];uint8_t extra[32];} Ctx;
typedef void (*ImportFn)(Ctx *);
typedef struct {uint64_t addr;ImportFn fn;} Entry;
#define GAME_13_0_5 1305
static int g_game_build=GAME_13_0_5,g_fh_rng_probe=1,g_fh_trace_enabled=1;
static struct {long long frame;} g_fh_f[1];
static int g_fh_n=1,vector_kind;
#define GA(a) (a)
static ImportFn g_fh_seed_orig;
static volatile LONG g_fh_seed_calls;
static int g_fh_seed_id,checkpoint_reads;
static long long hook_calls(int id){assert(id==17);checkpoint_reads++;return 1234567890123LL;}
static Entry fn_table[4];static int fn_table_count;
static const uint64_t target=0x71015016e0ull,expected_hash=0x346dd402d6c23b0bull,random_base=0x12340000;
static const char *setting="1",*mode;
static int code_reads,word_reads,base_reads,hash_calls,install_calls,trace_failures,original_calls,hook_fail,hash_fail,original_finished,missing_base;
static Ctx expected_input,expected_output;
static char sink[32768];static size_t sink_used;
static void fh_seed_probe(Ctx *,void *);
static void original(Ctx *c){
    assert(!memcmp(c,&expected_input,sizeof *c));original_calls++;original_finished=1;
    c->x[0]=0x99999999;c->x[30]=0x88888888;c->x[25]=0x77777777;c->extra[0]^=0xff;
    expected_output=*c;
}
static char *fixture_getenv(const char *name){assert(!strcmp(name,"SSBU_RNG_SEED_PROBE"));return (char *)setting;}
static uint8_t rd8(uint64_t a){assert(a==target+(unsigned)code_reads&&code_reads<0x88);return (uint8_t)code_reads++;}
static uint32_t rd32(uint64_t a){assert(original_finished&&a==random_base+4ull*(word_reads%45));return 0xabc00000u+(unsigned)(word_reads++%45);}
static uint64_t rd64(uint64_t address){
    assert(original_finished);base_reads++;
    if(address==GA(0x71052c25b0ull))return vector_kind==1?0:0x10000;
    if(address==0x10000)return vector_kind==2?0:0x20000;
    if(address==0x20000)return vector_kind==3?0:random_base+(vector_kind==6?1:0);
    assert(address==0x20008);
    if(vector_kind==4)return random_base+176;
    if(vector_kind==5)return random_base-4;
    return random_base+180+(vector_kind==6?1:0);
}
static uint64_t fh_fnv(uint64_t h,const void *p,size_t n){
    assert(h==0xcbf29ce484222325ull);hash_calls++;
    if(n==0x88){assert(code_reads==0x88);for(size_t i=0;i<n;i++)assert(((const uint8_t *)p)[i]==(uint8_t)i);return hash_fail?0:expected_hash;}
    assert(n==45*sizeof(uint32_t));for(size_t i=0;i<45;i++)assert(((const uint32_t *)p)[i]==0xabc00000u+i);return 0x1122334455667788ull;
}
static int hook_install(uint64_t a,void (*fn)(Ctx *,void *),void *arg,ImportFn *out){
    assert(a==target&&fn==fh_seed_probe&&!arg&&out==&g_fh_seed_orig);assert(code_reads==0x88&&hash_calls==1);install_calls++;
    if(hook_fail)return 0;*out=original;return 17;
}
static void fight_trace_fail(const char *why){assert(!strcmp(why,"rng_seed_probe_identity"));trace_failures++;}
static int fixture_printf(const char *format,...){
    va_list args;va_start(args,format);int n=vsnprintf(sink+sink_used,sizeof sink-sink_used,format,args);va_end(args);
    assert(n>=0&&(size_t)n<sizeof sink-sink_used);sink_used+=(size_t)n;return n;
}
static void fixture_abort(void){
    assert(strcmp(mode,"success")&&trace_failures==1&&!g_fh_seed_orig&&!original_calls&&!word_reads&&!base_reads);
    assert(code_reads==(!strcmp(mode,"build")?0:0x88));assert(install_calls==(!strcmp(mode,"hook-failed")?1:0));
    puts("RNG_SEED_FATAL_ORACLE_PASS");fflush(stdout);abort();
}
#define getenv fixture_getenv
#define printf fixture_printf
#define abort fixture_abort
/* SOURCE */
#undef abort
#undef printf
static void reset(void){
    code_reads=word_reads=base_reads=hash_calls=install_calls=trace_failures=original_calls=hook_fail=hash_fail=original_finished=missing_base=0;
    sink_used=0;sink[0]=0;g_fh_seed_orig=NULL;g_fh_seed_calls=0;g_fh_seed_id=checkpoint_reads=0;g_game_build=GAME_13_0_5;g_fh_rng_probe=g_fh_trace_enabled=1;g_fh_f[0].frame=2;g_fh_n=1;vector_kind=0;
    setting="1";fn_table_count=3;fn_table[0]=(Entry){target,original};fn_table[1]=(Entry){target,NULL};fn_table[2]=(Entry){target+4,original};
}
static void call_observer(void){
    Ctx c;memset(&c,0x44,sizeof c);c.x[0]=0x12345678;c.x[30]=0xabcdef;c.x[25]=0xfeed1234;expected_input=c;original_finished=0;
    int before=original_calls;fh_seed_probe(&c,NULL);assert(original_calls==before+1&&!memcmp(&c,&expected_output,sizeof c));
}
static int occurrences(const char *text){int n=0;const char *p=sink;while((p=strstr(p,text))!=NULL){n++;p+=strlen(text);}return n;}
static void checkpoint_tests(void){
    reset();g_fh_seed_calls=23;fh_seed_checkpoint("before",2,3);
    assert(!checkpoint_reads&&!sink_used&&!code_reads&&!word_reads&&!base_reads&&g_fh_seed_calls==23);
    g_fh_seed_id=17;fh_seed_checkpoint("after",1,1234567890124LL);
    assert(checkpoint_reads==1&&!strcmp(sink,"[rng-seed] checkpoint phase=after slot=1 frame=1234567890124 entries=1234567890123 eligible=23\n"));
    assert(!code_reads&&!word_reads&&!base_reads&&!hash_calls&&!original_calls&&g_fh_seed_calls==23);
}
static void success(void){
    checkpoint_tests();
    const char *disabled[]={NULL,"0","","true","01"};
    for(size_t i=0;i<sizeof disabled/sizeof disabled[0];i++){reset();setting=disabled[i];fh_seed_probe_start();assert(!code_reads&&!word_reads&&!base_reads&&!hash_calls&&!install_calls&&!trace_failures&&!sink_used);}
    reset();fh_seed_probe_start();assert(code_reads==0x88&&hash_calls==1&&install_calls==1&&g_fh_seed_id==17&&g_fh_seed_orig==original&&!trace_failures);
    assert(strstr(sink,"installed=1")&&strstr(sink,"matches=1 observer=1"));
    sink_used=0;sink[0]=0;hash_calls=0;
    for(int i=0;i<33;i++)call_observer();
    assert(original_calls==33&&g_fh_seed_calls==33&&base_reads==32*4&&word_reads==32*45&&hash_calls==32);
    assert(occurrences("phase=before")==32&&occurrences("phase=after")==32&&occurrences("truncated=1 limit=32")==1);
    assert(occurrences("seed=12345678 lr=abcdef owner_reg=feed1234 frame0=2")==32);
    assert(!strstr(sink,"seed=99999999")&&!strstr(sink,"lr=88888888"));
    call_observer();assert(original_calls==34&&base_reads==32*4&&word_reads==32*45&&occurrences("truncated=1")==1);
    for(int kind=1;kind<=6;kind++){
        reset();g_fh_seed_orig=original;vector_kind=kind;call_observer();
        assert(original_calls==1&&base_reads==(kind==1?1:kind==2?2:4)&&!word_reads&&!hash_calls&&occurrences("available=0")==1);
    }
    for(int interval=0;interval<4;interval++){
        reset();g_fh_seed_orig=original;if(interval==0)g_fh_n=0;else g_fh_f[0].frame=interval==1?0:interval==2?4:-1;
        call_observer();assert(original_calls==1&&!g_fh_seed_calls&&!base_reads&&!word_reads&&!hash_calls&&!sink_used);
    }
    puts("RNG_SEED_PROBE_PASS");
}
int main(int argc,char **argv){
    SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);_set_abort_behavior(0,_WRITE_ABORT_MSG|_CALL_REPORTFAULT);assert(argc==2);mode=argv[1];reset();
    if(!strcmp(mode,"success")){success();return 0;}
    if(!strcmp(mode,"build"))g_game_build=1304;
    else if(!strcmp(mode,"fingerprint"))hash_fail=1;
    else if(!strcmp(mode,"missing"))fn_table[0].fn=NULL;
    else if(!strcmp(mode,"duplicate"))fn_table[1].fn=original;
    else if(!strcmp(mode,"early-off"))g_fh_rng_probe=0;
    else if(!strcmp(mode,"trace-off"))g_fh_trace_enabled=0;
    else {assert(!strcmp(mode,"hook-failed"));hook_fail=1;}
    fh_seed_probe_start();puts("UNEXPECTED_SUCCESS");return 0;
}
