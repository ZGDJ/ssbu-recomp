"""Reject failed runtime trials even when shutdown races leave exit code zero.

This gate complements mandatory bounded-trace and refusal-observer comparisons.
It does not certify gameplay, trace coverage or absence of unlogged failures.
"""
import argparse
import json
from pathlib import Path
import re


FAILURE = re.compile(r"\bfatal\b|HOLD RELEASE FAILED|\bunhandled exception\b", re.I)


def inspect_trial(path: Path) -> dict:
    path = Path(path)
    errors = []
    try:
        result = json.loads((path / "result.json").read_text(encoding="utf-8-sig"))
        code = result.get("exit") if isinstance(result, dict) else None
        if type(code) is not int or code != 0:
            errors.append("result.json: missing/invalid/nonzero process exit")
    except (OSError, UnicodeError, ValueError):
        errors.append("result.json: missing or invalid result")
    for name in ("game.log", "r1.log"):
        try:
            log = (path / name).read_text(encoding="utf-8", errors="strict")
        except (OSError, UnicodeError):
            errors.append(f"{name}: missing or unreadable log")
            continue
        if not log.strip():
            errors.append(f"{name}: empty log")
        for number, line in enumerate(log.splitlines(), 1):
            if FAILURE.search(line):
                errors.append(f"{name}:{number}: fatal or failed hold-release diagnostic")
    return {
        "status": "failed" if errors else "passed",
        "errors": errors,
        "scope": "process exit and fatal-log gate only; require separate trace and observer comparisons",
        "gameplay_certified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trial", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = inspect_trial(args.trial)
    report = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(report, encoding="utf-8")
    print(report, end="")
    return int(result["status"] != "passed")


if __name__ == "__main__":
    raise SystemExit(main())
