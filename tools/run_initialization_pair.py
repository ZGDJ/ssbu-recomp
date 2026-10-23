"""Prepare or explicitly launch a reviewed, freshly admitted NET_INIT_ONLY pair.

A plan supplies two existing, isolated builds (work/config/sysdata/binaries prepared
by root), an immutable userdata template and warm cache template. This tool never
builds. Default is preparation only. --launch requires the input plan's canonical
SHA256 as --reviewed-plan; root must independently review tooling and plan first.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid

from check_initialization_pair import (ROOT, REQUIRED, PROBES, digest, file_id,
    read_json, require, trace500, compare, inspect_pair, scalar, immutable_digest, expected_fields, admit, REQUIRED_OUTPUTS, attempt_record)
from check_runtime_trial import inspect_trial
from battle_identity import capture, tree_id, inventory


def write_new(path, value):
    with Path(path).open('x',encoding='utf-8') as f:
        json.dump(value,f,indent=2); f.write('\n')


def validate_plan(plan):
    expected_fields(plan)
    require(type(plan['seconds']) is int and 1 <= plan['seconds'] <= 900, 'duration must be 1..900 seconds')
    require(type(plan['seed']) is int and 0 < plan['seed'] < 2**64, 'explicit nonzero uint64 seed required')
    require(type(plan['port']) is int and 1024 <= plan['port'] <= 65535, 'invalid port')
    require(type(plan['instrumented']) is bool, 'instrumented must be boolean')
    require(Path(plan['exe']).name == plan['exe'] and plan['exe'].lower().endswith('.exe'), 'bare executable filename required')
    require(set(plan['peers']) == {'host','join'}, 'exactly host and join required')
    # Only reviewed scalar/path controls: prevent caller-supplied output collisions,
    # handshake bypass, seed overrides, extra captures and implicit runtime modes.
    allowed = {'SSBU_ROMFS','SSBU_NRO_BIN','SSBU_FONTS','SSBU_TZDIR','SSBU_OPUS_DLL',
               'SSBU_CONFIG','SSBU_GRAPHICS_CONFIG','SSBU_DEBUG_MATCH','SSBU_DEBUG_END',
               'SSBU_VK_PREP','SSBU_ONLINE_STUN','SSBU_ONLINE_UPNP','SSBU_ONLINE_LOOPBACK'}
    env = plan['environment']
    require(isinstance(env,dict) and set(env) <= allowed and 'SSBU_ROMFS' in env, 'unsupported/missing plan environment')
    require(all(isinstance(v,str) for v in env.values()), 'environment values must be strings')
    require(env.get('SSBU_ONLINE_LOOPBACK') == '1' and env.get('SSBU_ONLINE_STUN') == 'off' and env.get('SSBU_ONLINE_UPNP') == 'off', 'local direct pair transport required')
    for k in allowed - {'SSBU_DEBUG_MATCH','SSBU_DEBUG_END','SSBU_VK_PREP','SSBU_ONLINE_STUN','SSBU_ONLINE_UPNP','SSBU_ONLINE_LOOPBACK'}:
        if k in env: require(Path(env[k]).is_absolute(), 'absolute input paths required')
    paths=[Path(plan[k]).resolve() for k in ('output','runtime','save_source','cache_source','reference','disabled_control')]
    paths += [Path(plan['peers'][r]['build']).resolve() for r in ('host','join')]
    require(all(Path(plan[k]).is_absolute() for k in ('output','runtime','save_source','cache_source','reference','disabled_control')), 'absolute plan paths required')
    for i,a in enumerate(paths):
        for b in paths[i+1:]:
            require(not a.is_relative_to(b) and not b.is_relative_to(a), 'plan paths overlap')
    for peer in plan['peers'].values():
        require(Path(peer['build']).is_absolute() and Path(peer['sequence']).is_absolute(), 'absolute peer paths required')
        tape=Path(peer['sequence']).read_text()
        require('@fight' in tape and '@match1on' not in tape, 'local pad fight tape required')
    require(file_id(plan['reference']) == plan['reference_identity'], 'original reference identity mismatch')
    trace500(plan['reference'])
    require(tree_id(plan['save_source']) == plan['save_identity'], 'save source changed')
    require(tree_id(plan['cache_source']) == plan['cache_identity'], 'warm cache source changed')
    package=Path(plan['runtime']); manifest=read_json(package/'manifest.json')
    require(file_id(package/'ssbu_native.exe') == plan['package_executable'], 'package executable mismatch')
    require(manifest['tree_digest'] == plan['package_source'], 'package source mismatch')
    control=Path(plan['disabled_control'])
    require(inspect_trial(control,forward_only=True)['status'] == 'passed', 'disabled original-reference control failed')
    compare(trace500(control/'fight.txt'),trace500(plan['reference']))
    identity=read_json(control/'prelaunch-identity.json')
    require(identity['effective_settings'].get('SSBU_MEM_KEEP') == scalar('0') and identity['effective_settings'].get('SSBU_SKYLINE') == scalar('0'), 'disabled control requires MEM_KEEP/SKYLINE zero')
    require(identity['executable'] == plan['package_executable'] and identity['tree_digest'] == plan['package_source'], 'disabled control is another candidate')


def host_sample():
    script = r'''$ErrorActionPreference='Stop'
$m=Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory
$p=@(Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^(ssbu.*|clang.*|lld.*|ninja|cmake|msbuild)\.exe$' -or ($_.Name -match '^python.*\.exe$' -and $_.CommandLine -match '(build\.py|build_opt\.py|setup\.py|install\.py)') } | Select-Object Name,ProcessId)
@{time=[DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()/1000.0;available_commit=[double]$m.CommitLimit-[double]$m.CommittedBytes;committed=[double]$m.CommittedBytes;available_mib=[double]$m.AvailableMBytes;processes=$p} | ConvertTo-Json -Depth 4 -Compress'''
    r=subprocess.run(['powershell','-NoProfile','-Command',script],capture_output=True,text=True,timeout=30,check=True)
    return json.loads(r.stdout)


def prepare(plan):
    validate_plan(plan)
    out=Path(plan['output']); out.mkdir()  # Never overwrite a failed or prior packet.
    write_new(out/'plan.json',plan)
    attempt=dict(format=2,attempt_id=str(uuid.uuid4()),plan_sha256=digest(plan),created_at=time.time())
    write_new(out/'attempt.json',attempt)
    commands={}
    for role,peer in plan['peers'].items():
        trial=out/role; trial.mkdir()
        build=Path(peer['build']).resolve()
        require(not (build/'cache').exists(), 'peer cache must be absent before fresh template copy')
        # inventory rejects links before copy; templates are hash-pinned above.
        inventory(plan['save_source']); inventory(plan['cache_source'])
        shutil.copytree(plan['save_source'],trial/'userdata')
        shutil.copytree(plan['cache_source'],build/'cache')
        fresh=tree_id(trial/'userdata'); cache=tree_id(build/'cache')
        require(fresh==plan['save_identity'] and cache==plan['cache_identity'], 'fresh copy mismatch')
        env=dict(plan['environment'],**REQUIRED)
        env.update(SSBU_RB_NET_SEED=str(plan['seed']),SSBU_FIXED_SEED=str(plan['seed']),
                   SSBU_ONLINE=('host:' if role=='host' else 'join:127.0.0.1:')+str(plan['port']),
                   SSBU_USERDATA=str(trial/'userdata'),SSBU_R1_LOG=str(trial/'r1.log'),
                   SSBU_TRACE_FRAMES='500')
        for k in PROBES: env[k]='1' if plan['instrumented'] else '0'
        env['SSBU_FIGHT_HASH']=str(trial/'fight.txt')
        env['SSBU_SEQ']=' '.join(l.strip() for l in Path(peer['sequence']).read_text().splitlines() if l.strip() and not l.startswith('#'))
        exe=build/'work'/plan['exe']
        identity=capture(build=build,runtime=plan['runtime'],exe=exe,sequence=peer['sequence'],env=env,seconds=plan['seconds'],outputs=[trial/'game.log',trial/'prelaunch-identity.json',trial/'r1.log',trial/'fight.txt'])
        identity.pop('identity_sha256')
        identity['pair_launcher']=file_id(__file__)
        identity['identity_sha256']=digest(identity)
        command=dict(attempt_id=attempt['attempt_id'],argv=[str(exe),str(build/'binaries/13.0.5/main.elf'),str(plan['seconds'])],cwd=str(build/'work'),environment=env,
                     identity_sha256=identity['identity_sha256'],pair_launcher=identity['pair_launcher'],plan_sha256=digest(plan),fresh_userdata=fresh,initial_cache=cache)
        write_new(trial/'prelaunch-identity.json',identity)
        write_new(trial/'command.json',command)
        commands[role]=command
    # Validate both inventories and all peer invariants before either process exists.
    from check_initialization_pair import config
    ids={r:config(out/r,r,plan)[0] for r in commands}
    for key in ('runtime_manifest','executable','modules','game_inputs','binary_input_directory','tree_digest','inputs'):
        require(ids['host'][key]==ids['join'][key], 'prelaunch peer mismatch: '+key)
    return commands


def recheck(plan, commands, *, before_launch):
    """Rehash real inputs, never reuse an earlier boolean or cached inventory."""
    package=Path(plan['runtime'])
    manifest=read_json(package/'manifest.json')
    for name, expected in manifest['files'].items():
        path=(package/name).resolve()
        require(path.is_relative_to(package.resolve()), 'package manifest traversal')
        require(file_id(path)==expected, 'package file changed: '+name)
    hashes={}
    for role,c in commands.items():
        peer=plan['peers'][role]; trial=Path(plan['output'])/role
        current=capture(build=peer['build'],runtime=plan['runtime'],exe=c['argv'][0],
                        sequence=peer['sequence'],env=c['environment'],seconds=plan['seconds'])
        current['pair_launcher']=file_id(__file__)
        expected=read_json(trial/'prelaunch-identity.json')
        require(current['pair_launcher']==c['pair_launcher'], 'launcher changed')
        require(immutable_digest(current)==immutable_digest(expected), 'immutable peer inputs changed: '+role)
        if before_launch:
            require(current['inputs']['initial_userdata']==plan['save_identity'], 'fresh save changed: '+role)
            require(tree_id(Path(peer['build'])/'cache')==plan['cache_identity'], 'fresh cache changed: '+role)
        hashes[role]=immutable_digest(current)
    return hashes


def metadata_snapshot(plan, commands):
    """Cheap post-hash consistency screen, NOT recursive/concurrent-writer proof.

    Stat the frozen source/package/module/ELF/tool paths and declared input roots;
    hash small command/identity evidence. Content descendants were fully hashed
    before admission and will be fully hashed afterward, not during this screen.
    """
    out=Path(plan['output']); package=Path(plan['runtime'])
    manifest=read_json(package/'manifest.json')
    paths={package/'manifest.json', Path(__file__), ROOT/'scripts/battle_identity.py', ROOT/'scripts/run.py'}
    paths.update(package/n for n in manifest['files'])
    paths.update(ROOT/n for n in manifest['tree_files'])
    evidence={'plan':file_id(out/'plan.json'),'attempt':file_id(out/'attempt.json')}
    for role,c in commands.items():
        peer=plan['peers'][role]; build=Path(peer['build']); trial=out/role
        identity=read_json(trial/'prelaunch-identity.json')
        paths.update(build/'work'/n for n in identity['modules'])
        paths.update(build/'binaries/13.0.5'/n for n in identity['game_inputs'])
        paths.update((Path(c['argv'][0]),Path(peer['sequence']),build/'state.json',build/'config',build/'characters'))
        state=read_json(build/'state.json'); paths.add(Path(state['tools']['clang']))
        for key in ('SSBU_ROMFS','SSBU_NRO_BIN','SSBU_FONTS','SSBU_TZDIR','SSBU_OPUS_DLL','SSBU_CONFIG','SSBU_GRAPHICS_CONFIG'):
            if key in c['environment']: paths.add(Path(c['environment'][key]))
        for name in ('prelaunch-identity.json','command.json'):
            evidence[role+'/'+name]=file_id(trial/name)
    stats={}
    for path in sorted(paths,key=str):
        if not path.exists():
            stats[str(path)]={'absent':True}; continue
        require(not path.is_symlink(), 'metadata path became linked')
        st=path.stat()
        stats[str(path)]=[st.st_size,st.st_mtime_ns,st.st_dev,st.st_ino]
    return digest(dict(stats=stats,evidence=evidence))


def launch(plan,commands):
    out=Path(plan['output']); attempt=attempt_record(out,plan)
    checks=dict(plan_sha256=digest(plan), errors=[], verification_methods=dict(after_preparation='full',after_admission='metadata',post_run='full'))
    completed=dict(format=2,attempt_id=attempt['attempt_id'],plan_sha256=digest(plan),admission_sha256=None,peers={},outputs={},errors=[])
    processes=[]
    try:
        checks['after_preparation']=recheck(plan,commands,before_launch=True)
        metadata=metadata_snapshot(plan,commands)
        samples=[host_sample()]; time.sleep(15); samples.append(host_sample())
        write_new(out/'admission.json',samples)
        completed['admission_sha256']=digest(samples)
        admit(samples,time.time())
        require(metadata_snapshot(plan,commands)==metadata, 'post-admission metadata/evidence changed')
        checks['prelaunch_metadata_sha256']=metadata
        checks['after_admission']=checks['after_preparation']
        admit(samples,time.time())
        for role in ('host','join'):
            c=commands[role]; trial=out/role
            require(c['attempt_id']==attempt['attempt_id'], 'command attempt changed')
            env={k:v for k,v in os.environ.items() if not k.startswith(('SSBU_','RECOMP_','VK_'))}
            env.update(c['environment'])
            log=(trial/'game.log').open('xb')
            try:
                requested=time.time()
                admit(samples,requested)  # At EACH actual native process boundary.
                p=subprocess.Popen(c['argv'],cwd=c['cwd'],env=env,stdout=log,stderr=subprocess.STDOUT)
            except BaseException:
                log.close(); raise
            returned=time.time()
            row=dict(pid=p.pid,start_requested_at=requested,start_returned_at=returned,ended_at=None,exit=None,timed_out=False,closed=False,outputs={})
            completed['peers'][role]=row
            processes.append((role,p,log,time.monotonic()))
            admit(samples,returned)  # A delayed CreateProcess cannot pass stale admission.
            with (trial/'launcher.log').open('x',encoding='utf-8') as f:
                f.write('prelaunch battle identity: '+c['identity_sha256']+'\n')
        for role,p,log,start in processes:
            row=completed['peers'][role]
            try:
                row['exit']=p.wait(timeout=max(1,plan['seconds']+120-(time.monotonic()-start)))
            except subprocess.TimeoutExpired:
                row['timed_out']=True
                subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],capture_output=True,check=True,timeout=10)
                row['exit']=p.wait(timeout=30)
            row['ended_at']=time.time()
    except BaseException as exc:
        checks['errors'].append(type(exc).__name__+': '+str(exc))
        raise
    finally:
        for role,p,log,start in processes:
            row=completed['peers'][role]; trial=out/role
            if row['ended_at'] is None:
                try:
                    if p.poll() is None:
                        subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],capture_output=True,check=True,timeout=10)
                    row['exit']=p.wait(timeout=30)
                    row['ended_at']=time.time()
                except (OSError,subprocess.SubprocessError) as exc:
                    checks['errors'].append('owned-process cleanup failed: '+str(exc))
            log.close()
            row['closed']=row['ended_at'] is not None
            try:
                result={k:row[k] for k in ('pid','start_requested_at','start_returned_at','ended_at','exit','timed_out')}
                write_new(trial/'result.json',dict(result,attempt_id=attempt['attempt_id'],role=role))
                if (trial/'launcher.log').exists():
                    with (trial/'launcher.log').open('a',encoding='utf-8') as f: f.write('game exited with code '+str(row['exit'])+'\n')
            except (OSError,ValueError,TypeError) as exc:
                checks['errors'].append('result close failed: '+str(exc))
        if processes:
            try:
                checks['post_run']=recheck(plan,commands,before_launch=False)
            except (OSError, ValueError, KeyError, TypeError) as exc:
                checks['errors'].append('post-run: '+str(exc))
        write_new(out/'inventory-rechecks.json', checks)
        completed['errors']=list(checks['errors'])
        for name in ('plan.json','attempt.json','admission.json','inventory-rechecks.json'):
            try: completed['outputs'][name]=file_id(out/name)
            except (OSError,ValueError) as exc: completed['errors'].append(name+': '+str(exc))
        for role,row in completed['peers'].items():
            path=out/role
            for name in sorted(REQUIRED_OUTPUTS | ({'r1.log'} if (path/'r1.log').exists() else set())):
                try: row['outputs'][name]=file_id(path/name)
                except (OSError,ValueError) as exc: completed['errors'].append(role+'/'+name+': '+str(exc))
        write_new(out/'completion.json',completed)
        # Retain readable original-reference verdicts on partial/failed launches too.
        result=inspect_pair(out); write_new(out/'pair-gate.json',result)
    return result


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('plan',type=Path)
    ap.add_argument('--launch',action='store_true')
    ap.add_argument('--reviewed-plan',help='canonical SHA256 of independently reviewed input plan')
    a=ap.parse_args()
    try:
        require(not sys.flags.optimize,'unoptimized Python required')
        plan=read_json(a.plan)
        if a.launch:
            require(os.name=='nt','Windows only')
            require(a.reviewed_plan==digest(plan),'root review acknowledgement missing/mismatched')
        commands=prepare(plan)
        if not a.launch:
            print('Prepared only; no launch. Review plan SHA256: '+digest(plan))
            print('A launch requires a new output and fresh isolated builds/cache paths.'); return 0
        result=launch(plan,commands)
        print(json.dumps(result,indent=2)); return int(result['status']!='passed')
    except (OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError) as exc:
        print('REFUSED: '+str(exc),file=sys.stderr); return 1

if __name__=='__main__':
    raise SystemExit(main())
