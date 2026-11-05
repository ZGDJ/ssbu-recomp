"""Exact-source lifecycle composition; synthetic cadence/pages, real ExitProcess.

First run the frozen 214-check witness suite unchanged (receipt routing only).
Reuse its current-source translation and replace only the driver/CRT boundaries.
Compare full bytes against that immediate-cutoff baseline, not a second model.
No game, package build, capacity/admission query or gameplay qualification.
"""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from test_catch_source import function


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise AssertionError((old, source.count(old)))
    return source.replace(old, new)


@unittest.skipUnless(os.name == "nt", "Windows source/ExitProcess harness")
class LoopWitnessLifecycleTests(unittest.TestCase):
    def test_lifecycle(self):
        parent = ROOT / "artifacts/local/loop-witness-lifecycle-repair-20261105"
        parent.mkdir(parents=True, exist_ok=True)
        out = Path(tempfile.mkdtemp(prefix="lifecycle-", dir=parent))
        print("Lifecycle evidence:", out, flush=True)
        spec = importlib.util.spec_from_file_location("frozen_witness_suite", ROOT / "tests/test_loop_witness_source.py")
        suite = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(suite)
        mkdtemp = tempfile.mkdtemp
        receipts = []

        def route_receipt(*args, **kwargs):
            if kwargs.get("prefix") == "source-":
                kwargs["dir"] = out
                value = mkdtemp(*args, **kwargs)
                receipts.append(Path(value))
                return value
            return mkdtemp(*args, **kwargs)

        tempfile.mkdtemp = route_receipt
        try:
            suite.LoopWitnessSourceTests("test_producers").test_producers()
        finally:
            tempfile.mkdtemp = mkdtemp
        self.assertEqual(len(receipts), 1)
        baseline = receipts[0]
        original = (baseline / "production.c").read_text()
        manifest = json.loads((baseline / "manifest.json").read_text())
        raw = {p: (ROOT / p).read_bytes() for p in (
            "runtime/hostrt.c", "runtime/boot.c", "runtime/display.c", "runtime/nnhid.c",
            "tests/test_loop_witness_lifecycle.py", "tests/loop_witness_lifecycle_fixture.c")}
        for p, b in raw.items():
            q = out / "snapshot" / p
            q.parent.mkdir(parents=True, exist_ok=True)
            q.write_bytes(b)
        host = raw["runtime/hostrt.c"].decode().replace("\r\n", "\n")
        driver = raw["tests/loop_witness_lifecycle_fixture.c"].decode().replace("\r\n", "\n")
        driver = replace_once(driver, "/* HOST_EXIT_SOURCE */", function(host, "report_and_exit"))
        startup = function(host, "runtime_init")
        startup_call = "    rbn_witness_exit_init();"
        self.assertIn(startup_call, startup)
        self.assertLess(startup.index(startup_call), startup.index("g_handlers = calloc"))
        boot = raw["runtime/boot.c"].decode().replace("\r\n", "\n")
        self.assertLess(boot.index('runtime_init(g_elf,'), boot.index("    display_init();"))
        self.assertLess(boot.index('runtime_init(g_elf,'), boot.index("CreateThread(NULL, (SIZE_T)1 << 30, guest_main"))
        driver = replace_once(driver, "    /* STARTUP_EXIT_CALL */", startup_call)
        source = replace_once(original, function(original, "main"), driver)
        source = replace_once(source, "static int mode, late, disabled, repeated, write_fail, flush_fail, close_fail;",
            "static void lifecycle_io(const char *,FILE *);\nstatic int lifecycle_ferror(FILE *);\n"
            "static void lifecycle_reject(void);\nstatic int mode, late, disabled, repeated, write_fail, flush_fail, close_fail;")
        source = replace_once(source, 'fprintf(stderr,"WITNESS_REJECT mode=%d\\n",mode); _Exit(73);',
            'lifecycle_reject(); fprintf(stderr,"WITNESS_REJECT mode=%d\\n",mode); _Exit(73);')
        source = replace_once(source, 'if(write_fail==1 || (write_fail==2 && end)) return 0;',
            'lifecycle_io(end?"END-write":"data-write",f);\n    if(write_fail==1 || (write_fail==2 && end)) return 0;')
        source = replace_once(source, "static int flush_boundary(FILE *f) { return",
            'static int flush_boundary(FILE *f) { lifecycle_io(end_written?"END-flush":"data-flush",f); return')
        source = replace_once(source, "int r=fclose(f); return close_fail ? EOF : r;",
            'lifecycle_io("before-close",f); int r=fclose(f); lifecycle_io("after-close",f); return close_fail ? EOF : r;')
        source = replace_once(source, "#define fclose close_boundary", "#define fclose close_boundary\n#define ferror lifecycle_ferror")
        source = replace_once(source, "#undef fclose", "#undef fclose\n#undef ferror")
        (out / "production.c").write_text(source)
        # Source bodies remain exact; only synthetic driver/platform seams differ.
        bodies = {
            "runtime/rb_net.c": ("rbn_witness_shutdown", "rbw_shutdown", "rbn_witness_exit_init", "rbn_witness_init", "rbw_cutoff", "rbw_write",
                "rbn_witness_drain", "rbn_witness_trace", "rbn_witness_h2", "rbn_witness_pass", "rbn_witness_final",
                "rbn_witness_reserve", "rbn_witness_complete", "rbn_witness_idle", "rbn_finalize"),
            "runtime/r1_state.c": ("r1_frame_end", "r1_loop_witness_trace", "r1_loop_witness_drain", "r1_loop_witness_held"),
            "runtime/rb_rollback.c": ("rbg_rollback", "rbg_step_body"),
            "runtime/r1_ring.c": ("rgv_after", "rgv_loop_after_pass"),
            "runtime/hostrt.c": ("report_and_exit",),
        }
        for path, names in bodies.items():
            production = (ROOT / path).read_text()
            for name in names:
                self.assertEqual(function(source, name), function(production, name), name)
        shutdown = function(source, "rbn_witness_shutdown")
        self.assertEqual(set(re.findall(r"\bg_w\w+", shutdown)), {"g_wexit"})
        self.assertNotIn("rbn_witness_on", shutdown)
        self.assertNotIn("rbw_write", shutdown)
        self.assertLess(function(host, "report_and_exit").index("rbn_witness_shutdown();"),
                        function(host, "report_and_exit").index("g_exit_report_hook"))
        self.assertIn("ExitProcess((UINT)code);", function(host, "report_and_exit"))
        self.assertIn("report_and_exit(0);", raw["runtime/boot.c"].decode())
        self.assertIn("report_and_exit(0);", raw["runtime/display.c"].decode())

        env = {k: v for k, v in os.environ.items() if not k.upper().startswith(("SSBU_", "RECOMP_"))}
        env.update(TMP=str(out), TEMP=str(out), TMPDIR=str(out))
        compiler = manifest["compiler"]
        results = []
        captures = {}
        cases = [(m, late, 0, 0) for m in (0, 1, 2, 3, 4, 19, 20) for late in (0, 1)]
        cases += [(m, late, 0, 0) for m in range(10, 19) for late in (0, 1)]
        cases += [(m, late, 0, 0) for m in (21, 22, 24, 25, 26, 27, 28, 29, 30) for late in (0, 1)]
        cases += [(m, late, 0, 27) for m in (19, 20) for late in (0, 1)]
        cases += [(m, late, disabled, 27) for m in (10, 11, 19, 20) for late in (0, 1) for disabled in (1, 2)]
        cases += [(0, late, disabled, 0) for late in (0, 1) for disabled in (1, 2)]
        cases += [(m, late, 0, 0) for m in (31, 32, 33) for late in (0, 1)]
        cases += [(m, late, disabled, 27) for m in (31, 32) for late in (0, 1) for disabled in (1, 2)]

        def compile_variant(label, code, opt):
            cfile = out / f"{label}.c"
            cfile.write_text(code)
            exe = out / f"{label}{opt}.exe"
            command = [compiler, "-std=c11", "-Werror=implicit-function-declaration", opt,
                "-I", str(baseline / "snapshot/runtime"), str(cfile), "-o", str(exe)]
            build = subprocess.run(command, env=env, capture_output=True, text=True, timeout=60)
            (out / f"{label}{opt}-build.json").write_text(json.dumps(dict(command=command,
                exit=build.returncode, stdout=build.stdout, stderr=build.stderr), indent=2)+"\n")
            self.assertEqual(build.returncode, 0, build.stdout+build.stderr)
            return exe

        def run_case(exe, opt, case, label="current"):
            mode, late, disabled, requested = case
            work = out / f"{label}{opt}-m{mode}-l{late}-d{disabled}-e{requested}"
            work.mkdir()
            callenv = dict(env, SSBU_RB_NET=f"loop,{late}", SSBU_RB_NET_PLAYER="0", SSBU_RB_NET_DELAY="1",
                SSBU_RB_NET_BOT="7", SSBU_RB_NET_LOOP_BOT2="19", SSBU_RB_NET_LOOP_LAT2="11,0",
                SSBU_RB_NET_KEEP="1", SSBU_RB_NET_RECAP="1", SSBU_RB_NET_PACE="1", SSBU_RB_NET_LASTLITE="0",
                SSBU_RB_NET_DETAIL="1", SSBU_RB_NET_CKPADS="1", SSBU_RB_LOOP_VERIFY="1", SSBU_RB_SIM_VERIFY="1",
                SSBU_TRACE_FRAMES="500", SSBU_RB_NET_LOG="net.txt")
            if not disabled:
                callenv["SSBU_RB_LOOP_WITNESS"] = "1"
            elif disabled == 2:
                callenv["SSBU_RB_LOOP_WITNESS"] = "0"
            command = [str(exe), str(mode), str(late), str(disabled), str(requested)]
            p = subprocess.run(command, cwd=work, env=callenv, capture_output=True, text=True, timeout=20)
            net = (work / "net.txt").read_bytes() if (work / "net.txt").exists() else b""
            fight = (work / "fight.txt").read_bytes() if (work / "fight.txt").exists() else b""
            record = dict(label=work.name, command=command, exit=p.returncode, stdout=p.stdout, stderr=p.stderr,
                net_sha256=hashlib.sha256(net).hexdigest(), fight_sha256=hashlib.sha256(fight).hexdigest())
            (work / "run.json").write_text(json.dumps(record, indent=2)+"\n")
            results.append(record)
            (out / "results.json").write_text(json.dumps(results, indent=2)+"\n")
            return p, net, fight

        for opt in ("-O1", "-O3"):
            exe = compile_variant("lifecycle", source, opt)
            for case in cases:
                mode, late, disabled, requested = case
                p, net, fight = run_case(exe, opt, case)
                captures[opt, case] = (p.returncode, net, fight, p.stdout)
                events = [json.loads(line[2:]) for line in net.decode().splitlines() if line.startswith("o ")]
                closed = mode in (0, 1, 2, 3, 4, 19, 20)
                expected = requested if disabled or mode in (19, 20) else 0 if closed else 73
                self.assertEqual(p.returncode, expected, (case, p.stdout, p.stderr))
                if not disabled and closed:
                    reference = baseline / f"{opt}-m0-l{late}-d0-r0"
                    self.assertEqual(net, (reference / "net.txt").read_bytes(), (opt, case, "whole net bytes"))
                    self.assertEqual(fight, (reference / "fight.txt").read_bytes(), (opt, case, "whole fighter bytes"))
                    self.assertEqual([e["event"] for e in events], list(range(1, len(events)+1)))
                    self.assertEqual(events[-1]["kind"], "END")
                    self.assertEqual(events[-1]["pad_reads"], 2*(499+late))
                    self.assertEqual(events[-1]["final_last"], 499)
                    io = re.findall(r"LIFECYCLE_IO (\S+)", p.stderr)
                    self.assertEqual(io[-8:], ["data-write", "data-flush", "data-error-check", "END-write",
                        "END-flush", "END-error-check", "before-close", "after-close"])
                    if late:
                        self.assertEqual(next(e for e in events if e["kind"]=="COMPLETE")["diff"], [1,1,1])
                elif not disabled:
                    self.assertIn("WITNESS_REJECT", p.stderr)
                    if mode <= 22 or mode >= 31:
                        self.assertIn("shutdown before safe drained END", p.stderr)
                        self.assertIn("LIFECYCLE_EXIT_REJECT no_shutdown_io=1 reports=0", p.stderr)
                    else:
                        self.assertIn("net close" if mode==30 else "net write/flush", p.stderr)
                    # END may physically exist after flush/error/close; exit is mandatory.
                    if mode not in (17, 18, 28, 29, 30):
                        self.assertFalse(any(e["kind"]=="END" for e in events), case)
                else:
                    self.assertFalse(events)
                    self.assertNotIn("WITNESS_REJECT", p.stderr)
            # Disabled exits match the exact prior report body with the guard
            # removed. This mutation is a compatibility control, not production.
            control = replace_once(source, function(host, "report_and_exit"),
                replace_once(function(host, "report_and_exit"), "    rbn_witness_shutdown();\n", ""))
            old_exit = compile_variant("disabled-exit-control", control, opt)
            for case in cases:
                if case[2] and case[0] in (10, 11, 19, 20, 31, 32):
                    p, net, fight = run_case(old_exit, opt, case, "prior-exit")
                    self.assertEqual((p.returncode, net, fight, p.stdout), captures[opt, case])
                    self.assertNotIn("WITNESS_REJECT", p.stderr)
            for late in (0, 1):
                for mode in (0, 10, 11, 19, 20, 31, 32):
                    requested = 0 if mode==0 else 27
                    self.assertEqual(captures[opt, (mode,late,1,requested)], captures[opt, (mode,late,2,requested)])
            print(opt, "lifecycle and disabled exit controls passed", flush=True)
        self.assertEqual(manifest["sources"], {p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in manifest["sources"]})
        self.assertEqual({p: hashlib.sha256(b).hexdigest() for p,b in raw.items()},
                         {p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in raw})
        (out / "SUMMARY.json").write_text(json.dumps(dict(status="passed", executions=len(results),
            baseline_summary=json.loads((baseline/"SUMMARY.json").read_text()),
            production_bodies_exact=bodies, source_hashes={**manifest["sources"], **{p:hashlib.sha256(b).hexdigest() for p,b in raw.items()}},
            compiler=compiler, compiler_sha256=manifest["compiler_sha256"],
            translation_sha256=hashlib.sha256((out/"production.c").read_bytes()).hexdigest(),
            native_ready=False, resolved=False, authoritative=0, native_game_launched=False, host_build=False,
            limits="Synthetic cadence/fighter/ring/holds; exact producer/coordinator/raw bodies and real Win32 threads/ExitProcess. No native safety, mapping, battle/oracle or durability proof."), indent=2)+"\n")


if __name__ == "__main__":
    unittest.main()
