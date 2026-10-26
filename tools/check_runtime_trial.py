"""Reject failed runtime trials even when shutdown races leave exit code zero.

This gate complements mandatory bounded-trace and refusal-observer comparisons.
It does not certify gameplay, trace coverage or absence of unlogged failures.
Explicit --forward-only checks disabled-capture evidence instead of requiring r1.log.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re


FAILURE = re.compile(r"\bfatal\b|HOLD RELEASE FAILED|\bunhandled exception\b", re.I)
FORWARD_DISABLED = ("SSBU_R1", "SSBU_RUNAHEAD", "SSBU_RB_SIM", "SSBU_RB_NET", "SSBU_LS")


def inspect_forward_config(path: Path) -> list:
    """Check the existing private launcher record against its prelaunch inventory.

    This is artifact consistency, not attestation of loaded code or match progress.
    Only the explicit bounded Windows launcher command form is accepted.
    """
    try:
        command = json.loads((path / "command.json").read_text(encoding="utf-8-sig"))
        identity = json.loads((path / "prelaunch-identity.json").read_text(encoding="utf-8-sig"))
        if not isinstance(command, list) or len(command) < 2 or not all(isinstance(v, str) and v for v in command):
            raise ValueError("invalid launcher command")
        if not isinstance(identity, dict):
            raise ValueError("invalid prelaunch inventory")
        # Accept the explicitly reviewed isolated interpreter form as well as
        # historical commands. Other interpreter flags remain unsupported.
        script_index = 2 if command[1] == "-I" else 1
        if len(command) <= script_index:
            raise ValueError("missing launcher script")
        arguments = command[script_index + 1:]
        recorded_hash = identity.pop("identity_sha256", None)
        # battle_identity.digest's existing canonical format, without importing setup.
        actual_hash = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        if recorded_hash != actual_hash or identity.get("format") != 1 or identity.get("game_version") != "13.0.5":
            raise ValueError("prelaunch inventory identity mismatch")
        options, environment = {}, {}
        allowed = {"--build", "--userdata", "--exe", "--seconds", "--seq", "--log",
                   "--identity-runtime", "--identity-output", "--seed", "--env"}
        if len(arguments) % 2:
            raise ValueError("invalid launcher argument pairs")
        for key, value in zip(arguments[::2], arguments[1::2]):
            if key not in allowed or value.startswith("--"):
                raise ValueError("unsupported launcher argument")
            if key == "--env":
                name, separator, setting = value.partition("=")
                if not separator or not name or name.upper() in environment or name != name.upper():
                    raise ValueError("invalid or ambiguous environment override")
                environment[name] = setting
            else:
                if key in options:
                    raise ValueError("duplicate launcher argument")
                options[key] = value
        if not (allowed - {"--seed", "--env"}).issubset(options):
            raise ValueError("incomplete identified launcher command")
        if (Path(options["--identity-output"]).resolve() != (path / "prelaunch-identity.json").resolve()
                or Path(options["--log"]).resolve() != (path / "game.log").resolve()):
            raise ValueError("command names another trial's evidence")
        seconds = int(options["--seconds"])
        if seconds <= 0 or type(identity.get("launcher_seconds")) is not int or identity["launcher_seconds"] != seconds:
            raise ValueError("bounded duration does not match identity")
        if options["--exe"] != identity.get("executable_name") or Path(command[script_index]).name != "run.py":
            raise ValueError("launcher or executable does not match identity")
        for filename, role in ((command[script_index], "launcher"), (options["--seq"], "sequence_file")):
            contents = Path(filename).read_bytes()
            if identity.get(role) != {"size": len(contents), "sha256": hashlib.sha256(contents).hexdigest()}:
                raise ValueError(role + " bytes do not match identity")
        effective = identity.get("effective_settings", {})
        zero = {"value_sha256": hashlib.sha256(b"0").hexdigest()}
        for name in FORWARD_DISABLED:
            if environment.get(name) != "0" or effective.get(name) != zero:
                raise ValueError(name + " is not explicitly disabled in command and identity")
        # Other scalar overrides must not contradict the captured effective values.
        path_roles = {"SSBU_ROMFS": "content", "SSBU_USERDATA": "initial_userdata",
                      "SSBU_FONTS": "fonts", "SSBU_TZDIR": "zoneinfo", "SSBU_NRO_BIN": "nro_override",
                      "SSBU_MODS": "mods", "SSBU_CHARACTERS": "characters", "SSBU_FIGHTER_BIN": "fighter_override"}
        file_settings = {"SSBU_OPUS_DLL", "SSBU_CONFIG", "SSBU_GRAPHICS_CONFIG", "SSBU_DLC_LIST", "SSBU_SDK_ELF"}
        if environment.get("SSBU_LS_ROUTE") not in (None, "", "0"):
            file_settings.add("SSBU_LS_ROUTE")
        for name, value in environment.items():
            if name.startswith(("SSBU_", "RECOMP_", "VK_")):
                if name in path_roles or name in file_settings:
                    role = path_roles.get(name, name)
                    expected = {"tree" if name in path_roles else "file": role}
                    recorded_input = identity.get("inputs", {}).get(role, {})
                    if not isinstance(recorded_input, dict) or not re.fullmatch(r"[0-9a-f]{64}", str(recorded_input.get("sha256", ""))):
                        raise ValueError("path environment override has no input identity")
                else:
                    expected = {"value_sha256": hashlib.sha256(value.encode()).hexdigest()}
                if effective.get(name) != expected:
                    raise ValueError("command environment contradicts prelaunch identity")
        launcher = (path / "launcher.log").read_text(encoding="utf-8-sig")
        markers = [line for line in launcher.splitlines() if line.startswith("prelaunch battle identity:")]
        if markers != ["prelaunch battle identity: " + recorded_hash]:
            raise ValueError("launcher did not record this prelaunch identity")
        exits = [line for line in launcher.splitlines() if line.startswith("game exited with code")]
        if len(exits) != 1 or not re.fullmatch(r"game exited with code 0 after [0-9]+ s", exits[0]):
            raise ValueError("launcher did not record one successful process exit")
    except (OSError, UnicodeError, ValueError, TypeError, AttributeError):
        return ["forward-only: missing, invalid or contradictory command/prelaunch evidence"]
    return []


def inspect_trial(path: Path, *, forward_only: bool = False) -> dict:
    path = Path(path)
    errors = []
    if forward_only:
        errors.extend(inspect_forward_config(path))
    try:
        result = json.loads((path / "result.json").read_text(encoding="utf-8-sig"))
        code = result.get("exit") if isinstance(result, dict) else None
        if type(code) is not int or code != 0:
            errors.append("result.json: missing/invalid/nonzero process exit")
    except (OSError, UnicodeError, ValueError):
        errors.append("result.json: missing or invalid result")
    for name in (("game.log", "r1.log", "launcher.log") if forward_only else ("game.log", "r1.log")):
        if forward_only and name == "r1.log" and not (path / name).exists() and not (path / name).is_symlink():
            continue
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
        "scope": ("forward-only process exit, fatal-log and disabled-capture configuration gate only; "
                  "not match completion, reference equivalence or rollback qualification" if forward_only else
                  "process exit and fatal-log gate only; require separate trace and observer comparisons"),
        "gameplay_certified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trial", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--forward-only", action="store_true",
                        help="require identified disabled-capture command evidence; allow absent r1.log")
    args = parser.parse_args()
    result = inspect_trial(args.trial, forward_only=args.forward_only)
    report = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(report, encoding="utf-8")
    print(report, end="")
    return int(result["status"] != "passed")


if __name__ == "__main__":
    raise SystemExit(main())
