"""Disposable trial artifact checks; telemetry comparison remains a separate gate."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from check_runtime_trial import FORWARD_DISABLED, inspect_trial


class RuntimeTrialTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.trial = Path(self.temporary.name) / "trial"
        self.trial.mkdir()
        self.result = self.trial / "result.json"
        self.result.write_text(json.dumps({"exit": 0}), encoding="utf-8")
        for name in ("game.log", "r1.log"):
            (self.trial / name).write_text("normal diagnostic output\n", encoding="utf-8")

    def verdict(self, expected):
        report = inspect_trial(self.trial)
        self.assertEqual(report["status"], expected, report)
        self.assertIsInstance(report["errors"], list)
        if expected == "failed":
            self.assertTrue(report["errors"], report)
        else:
            self.assertEqual(report["errors"], [])
        return report

    def test_clean_artifacts_without_trace_pass_this_gate(self):
        self.assertFalse((self.trial / "fight.txt").exists())
        self.verdict("passed")

    def test_zero_exit_fatal_in_either_log(self):
        diagnostics = (
            "r1: HOLD FATAL: resume ownership was lost",
            "r1: fatal: copy-worker completion wait failed",
            "r1: RING RESTORE FATAL: commit failed",
            "FATAL EXCEPTION: access violation",
            "r1: hold fatal: watchdog release",
            "HOLD RELEASE FAILED: resume thread failed",
            "Unhandled exception: access violation",
        )
        for name in ("game.log", "r1.log"):
            for diagnostic in diagnostics:
                with self.subTest(log=name, diagnostic=diagnostic):
                    path = self.trial / name
                    path.write_text("normal start\n" + diagnostic + "\n", encoding="utf-8")
                    self.verdict("failed")
                    path.write_text("normal diagnostic output\n", encoding="utf-8")

    def test_late_fatal_after_apparent_success_is_failure(self):
        (self.trial / "r1.log").write_text(
            "capture complete\nrestore observers PASS\n" + "progress\n" * 4096 +
            "r1: HOLD FATAL: failed to resume thread\n", encoding="utf-8")
        self.verdict("failed")

    def test_hold_refused_is_not_fatal(self):
        for name in ("game.log", "r1.log"):
            (self.trial / name).write_text(
                "r1: HOLD REFUSED: thread was busy\nr1: capture refused: resource unavailable\nnonfatal diagnostic\n",
                encoding="utf-8")
        self.verdict("passed")

    def test_nonzero_exit(self):
        for code in (1, -1, 3221225477):
            with self.subTest(exit=code):
                self.result.write_text(json.dumps({"exit": code}), encoding="utf-8")
                self.verdict("failed")

    def test_missing_artifacts(self):
        for name in ("result.json", "game.log", "r1.log"):
            with self.subTest(artifact=name):
                path = self.trial / name
                original = path.read_bytes()
                path.unlink()
                self.verdict("failed")
                path.write_bytes(original)

    def test_empty_artifacts(self):
        for name in ("result.json", "game.log", "r1.log"):
            with self.subTest(artifact=name):
                path = self.trial / name
                original = path.read_bytes()
                path.write_bytes(b"")
                self.verdict("failed")
                path.write_bytes(original)

    def test_whitespace_and_invalid_utf8_logs(self):
        for name in ("game.log", "r1.log"):
            for contents in (b" \r\n\t", b"normal\n\xff\xfe"):
                with self.subTest(artifact=name, contents=contents):
                    path = self.trial / name
                    original = path.read_bytes()
                    path.write_bytes(contents)
                    self.verdict("failed")
                    path.write_bytes(original)

    def test_result_utf8_bom(self):
        self.result.write_text(json.dumps({"exit": 0}), encoding="utf-8-sig")
        self.verdict("passed")

    def test_invalid_result(self):
        for contents in ("{bad json", "[]", "null", '"result"', "{}", '{"exit": null}',
                         '{"exit": "0"}', '{"exit": false}', '{"exit": 0.0}'):
            with self.subTest(contents=contents):
                self.result.write_text(contents, encoding="utf-8")
                self.verdict("failed")

    def test_missing_trial_directory(self):
        report = inspect_trial(self.trial / "missing")
        self.assertEqual(report["status"], "failed", report)
        self.assertTrue(report["errors"])

    def test_cli_exit_and_machine_readable_report(self):
        output = Path(self.temporary.name) / "report.json"
        for fatal in (False, True):
            with self.subTest(fatal=fatal):
                if fatal:
                    (self.trial / "r1.log").write_text("r1: HOLD FATAL: failure\n", encoding="utf-8")
                result = subprocess.run(
                    [sys.executable, str(ROOT / "tools/check_runtime_trial.py"),
                     str(self.trial), "--output", str(output)],
                    capture_output=True, text=True, timeout=15)
                self.assertEqual(result.returncode, 1 if fatal else 0, result.stdout + result.stderr)
                report = json.loads(output.read_text(encoding="utf-8"))
                self.assertEqual(report["status"], "failed" if fatal else "passed", report)
                self.assertEqual(bool(report["errors"]), fatal)

    def test_cli_without_output(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "tools/check_runtime_trial.py"), str(self.trial)],
            capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class ForwardRuntimeTrialTests(unittest.TestCase):
    def setUp(self):
        RuntimeTrialTests.setUp(self)
        (self.trial / "r1.log").unlink()
        self.sequence = self.trial / "sequence.txt"
        self.sequence.write_text("NONE:10\n", encoding="utf-8")
        launcher = ROOT / "scripts/run.py"
        self.command = [sys.executable, str(launcher)]
        for key, value in (("build", self.trial / "build"), ("userdata", self.trial / "userdata"),
                           ("exe", "probe.exe"), ("seconds", "10"), ("seq", self.sequence),
                           ("log", self.trial / "game.log"), ("identity-runtime", self.trial / "package"),
                           ("identity-output", self.trial / "prelaunch-identity.json")):
            self.command += ["--" + key, str(value)]
        for name in FORWARD_DISABLED:
            self.command += ["--env", name + "=0"]
        def file_id(path):
            contents = path.read_bytes()
            return {"sha256": hashlib.sha256(contents).hexdigest(), "size": len(contents)}
        self.identity = {"format": 1, "game_version": "13.0.5", "launcher_seconds": 10,
                         "executable_name": "probe.exe", "launcher": file_id(launcher),
                         "sequence_file": file_id(self.sequence),
                         "effective_settings": {name: {"value_sha256": hashlib.sha256(b"0").hexdigest()}
                                                for name in FORWARD_DISABLED}}
        self.save_evidence()

    def save_evidence(self):
        identity = dict(self.identity)
        fingerprint = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        identity["identity_sha256"] = fingerprint
        (self.trial / "prelaunch-identity.json").write_text(json.dumps(identity), encoding="utf-8")
        (self.trial / "command.json").write_text(json.dumps(self.command), encoding="utf-8")
        (self.trial / "launcher.log").write_text("prelaunch battle identity: " + fingerprint +
                                                "\ngame exited with code 0 after 10 s\n", encoding="utf-8")

    def forward_verdict(self, expected):
        report = inspect_trial(self.trial, forward_only=True)
        self.assertEqual(report["status"], expected, report)
        self.assertFalse(report["gameplay_certified"])
        return report

    def test_forward_missing_r1_requires_explicit_mode(self):
        self.assertEqual(inspect_trial(self.trial)["errors"], ["r1.log: missing or unreadable log"])
        report = self.forward_verdict("passed")
        self.assertIn("not match completion", report["scope"])

    def test_forward_requires_every_artifact(self):
        for name in ("command.json", "prelaunch-identity.json", "launcher.log", "game.log", "result.json"):
            with self.subTest(name=name):
                path = self.trial / name
                original = path.read_bytes()
                path.unlink()
                self.forward_verdict("failed")
                path.write_bytes(original)

    def test_forward_rejects_missing_enabled_and_contradictory_flags(self):
        for name in FORWARD_DISABLED:
            original = self.identity["effective_settings"][name]
            for value in (None, {}, {"value_sha256": hashlib.sha256(b"1").hexdigest()}):
                with self.subTest(name=name, value=value):
                    if value is None:
                        del self.identity["effective_settings"][name]
                    else:
                        self.identity["effective_settings"][name] = value
                    self.save_evidence()
                    self.forward_verdict("failed")
                    self.identity["effective_settings"][name] = original
            index = self.command.index(name + "=0")
            self.command[index] = name + "=1"
            self.save_evidence()
            self.forward_verdict("failed")
            self.command[index] = name + "=0"
            saved = self.command[:]
            del self.command[index - 1:index + 1]
            self.save_evidence()
            self.forward_verdict("failed")
            self.command = saved

    def test_forward_rejects_invalid_commands(self):
        original = self.command
        for command in ([], {}, "run.py", [None], original + ["--play"],
                        original + ["--seconds", "10"], original + ["--env", "SSBU_R1=0"],
                        original + ["--env", "ssbu_r1=1"], original + ["--env", "BROKEN"],
                        original + ["--env", "SSBU_UNKNOWN=1"]):
            with self.subTest(command=command):
                self.command = command
                self.save_evidence()
                self.forward_verdict("failed")
        self.command = original

    def test_forward_rejects_wrong_trial_duration_exe_and_launcher(self):
        for key, value in (("--log", str(self.trial / "other.log")),
                           ("--identity-output", str(self.trial / "other.json")),
                           ("--seconds", "0"), ("--seconds", "11"), ("--seconds", "bad"),
                           ("--exe", "other.exe")):
            with self.subTest(key=key, value=value):
                index = self.command.index(key) + 1
                saved = self.command[index]
                self.command[index] = value
                self.save_evidence()
                self.forward_verdict("failed")
                self.command[index] = saved
        self.command[1] = str(self.sequence)
        self.save_evidence()
        self.forward_verdict("failed")

    def test_forward_rejects_changed_tape_or_identity(self):
        self.sequence.write_text("changed", encoding="utf-8")
        self.forward_verdict("failed")
        self.sequence.write_text("NONE:10\n", encoding="utf-8")
        path = self.trial / "prelaunch-identity.json"
        identity = json.loads(path.read_text(encoding="utf-8"))
        identity["launcher_seconds"] = 99
        path.write_text(json.dumps(identity), encoding="utf-8")
        self.forward_verdict("failed")

    def test_forward_rejects_wrong_or_multiple_launch_markers(self):
        path = self.trial / "launcher.log"
        original = path.read_text(encoding="utf-8")
        for text in ("", "prelaunch battle identity: wrong\n", original * 2):
            path.write_text(text, encoding="utf-8")
            self.forward_verdict("failed")

    def test_forward_keeps_process_and_log_gates(self):
        for name in ("game.log", "r1.log"):
            for diagnostic in ("HOLD FATAL: fail", "HOLD RELEASE FAILED", "Unhandled exception", "", " \n"):
                with self.subTest(name=name, diagnostic=diagnostic):
                    (self.trial / name).write_text(diagnostic, encoding="utf-8")
                    self.forward_verdict("failed")
            (self.trial / name).write_text("normal output\n", encoding="utf-8")
        self.forward_verdict("passed")
        self.result.write_text('{"exit": 1}', encoding="utf-8")
        self.forward_verdict("failed")

    def test_forward_rejects_launcher_fatal_and_conflicting_exit(self):
        path = self.trial / "launcher.log"
        original = path.read_text(encoding="utf-8")
        for diagnostic in ("FATAL EXCEPTION: access violation", "HOLD RELEASE FAILED", "Unhandled exception"):
            path.write_text(original + diagnostic + "\n", encoding="utf-8")
            report = self.forward_verdict("failed")
            self.assertTrue(any("launcher.log:" in error for error in report["errors"]))
        for replacement in ("", "game exited with code 1 after 10 s", "game exited with code nope after 10 s",
                            "game exited with code 0 after 10 s\ngame exited with code 0 after 10 s"):
            path.write_text(original.replace("game exited with code 0 after 10 s", replacement), encoding="utf-8")
            self.forward_verdict("failed")

    def test_forward_rejects_malformed_scalar_identity(self):
        self.command += ["--env", "SSBU_TEST=actual"]
        for setting in ({}, {"tree": "content"}, {"file": "SSBU_TEST"},
                        {"value_sha256": hashlib.sha256(b"other").hexdigest()}, None, []):
            with self.subTest(setting=setting):
                self.identity["effective_settings"]["SSBU_TEST"] = setting
                self.save_evidence()
                self.forward_verdict("failed")
        self.identity["effective_settings"]["SSBU_TEST"] = {"value_sha256": hashlib.sha256(b"actual").hexdigest()}
        self.save_evidence()
        self.forward_verdict("passed")

    def test_forward_accepts_only_identified_supported_path_overrides(self):
        for name, kind, role in (("SSBU_ROMFS", "tree", "content"), ("SSBU_CONFIG", "file", "SSBU_CONFIG")):
            with self.subTest(name=name):
                self.command += ["--env", name + "=private-path"]
                self.identity["effective_settings"][name] = {kind: role}
                self.identity.setdefault("inputs", {})[role] = {"sha256": "a" * 64}
                self.save_evidence()
                self.forward_verdict("passed")
                self.identity["inputs"][role] = {}
                self.save_evidence()
                self.forward_verdict("failed")
                self.identity["inputs"][role] = {"sha256": "a" * 64}
                self.identity["effective_settings"][name] = {kind: "wrong-role"}
                self.save_evidence()
                self.forward_verdict("failed")
                self.command = self.command[:-2]

    def test_forward_cli(self):
        result = subprocess.run([sys.executable, str(ROOT / "tools/check_runtime_trial.py"),
                                 str(self.trial), "--forward-only"],
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(json.loads(result.stdout)["gameplay_certified"])


if __name__ == "__main__":
    unittest.main()
