#!/usr/bin/env python3
"""Build real game-free rollback sources and preserve bounded run evidence.

Windows: deps/python/Scripts/python.exe tools/run_rollback_tests.py
Requires clang plus a working C runtime/linker (bundled LLVM or PATH clang).
--clang selects an explicit compiler; no downloads, game data or save access.
Known-defect reproduction is separate from a correctness pass.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def resolve_clang(explicit: str | None) -> str:
    candidates = [explicit] if explicit else [
        str(ROOT / "deps/llvm/bin/clang.exe"),
        shutil.which("clang"),
        str(Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "LLVM/bin/clang.exe"),
    ]
    for candidate in candidates:
        if candidate:
            resolved = shutil.which(candidate)
            if resolved:
                return str(Path(resolved).resolve())
    raise RuntimeError("clang unavailable: install LLVM and a compatible C runtime/linker, or pass --clang")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clang")
    parser.add_argument("--timeout", type=float, default=60, help="seconds per compile/run (default 60)")
    args = parser.parse_args()
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error("--timeout must be finite and positive")
    parent = ROOT / "artifacts/local/rollback-tests"
    parent.mkdir(parents=True, exist_ok=True)
    output = Path(tempfile.mkdtemp(prefix="run-", dir=parent))
    # Keep compiler intermediates in the same writable, isolated evidence folder.
    environment = os.environ.copy()
    environment.update(TMP=str(output), TEMP=str(output), TMPDIR=str(output))
    report = {"started_utc": datetime.now(timezone.utc).isoformat(),
              "scope": "source-only; no gameplay qualification; M7.4 remains unfixed",
              "status": "failed", "steps": []}

    def run(label: str, command: list[str]) -> str:
        step = {"name": label, "command": command}
        report["steps"].append(step)
        try:
            result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                                    errors="replace", timeout=args.timeout, check=False, env=environment)
            step.update(returncode=result.returncode, stdout=result.stdout, stderr=result.stderr)
        except (OSError, subprocess.TimeoutExpired) as exc:
            step["error"] = str(exc)
            raise RuntimeError(f"{label}: {exc}") from exc
        (output / f"{label}.log").write_text(result.stdout + result.stderr, encoding="utf-8")
        print(f"{label}: exit {result.returncode}", flush=True)
        if result.returncode:
            raise RuntimeError(f"{label} failed: see {output / (label + '.log')}")
        return result.stdout

    try:
        compiler = resolve_clang(args.clang)
        run("compiler", [compiler, "--version"])
        targets = {
            "cb_refusal_audit_test": ["tests/cb_refusal_audit_test.c"],
            "restore_refusal_audit_test": ["tests/restore_refusal_audit_test.c"],
            "restore_plan_test": ["tests/restore_plan_test.c"],
            "restore_resources_test": ["tests/restore_resources_test.c"],
            "cb_restore_test": ["tests/cb_restore_test.c"],
            "cb_capture_test": ["tests/cb_capture_test.c"],
            "slot_metadata_test": ["tests/slot_metadata_test.c"],
            "fiber_capture_test": ["tests/fiber_capture_test.c"],
            "rb_resource_policy_test": ["tests/rb_resource_policy_test.c"],
            "restore_probe_test": ["tests/restore_probe_test.c"],
            "bounded_trace_test": ["tests/bounded_trace_test.c"],
            "rb_test": ["tests/rb_test.c", "runtime/rb_input.c", "runtime/rb_wire.c", "runtime/rb_timesync.c"],
            "rb_failure_test": ["tests/rb_failure_test.c", "runtime/rb_input.c"],
        }
        if os.name == "nt":
            targets["restore_memory_win_test"] = ["tests/restore_memory_win_test.c"]
            targets["restore_probe_win_test"] = ["tests/restore_probe_win_test.c"]
        for name, sources in targets.items():
            executable = output / (name + (".exe" if os.name == "nt" else ""))
            run(name + "-build", [compiler, "-std=c11", "-O1", "-Iruntime", *sources, "-o", str(executable)])
            stdout = run(name + "-run", [str(executable)])
            if name == "rb_failure_test" and "KNOWN DEFECT REPRODUCED:" not in stdout:
                raise RuntimeError("Missing required known-defect reproduction result")
            print(stdout.strip(), flush=True)
        report["status"] = "passed_with_known_defect_reproduced"
        return 0
    except RuntimeError as exc:
        report["error"] = str(exc)
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    finally:
        (output / "results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"Evidence: {output / 'results.json'}", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
